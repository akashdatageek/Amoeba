"""D151 — budgets scale with the model and are shared fairly: the fixes' token allowance is a multiple of the run's
average step-attempt cost so far (not a fixed number), and with a run token cap each step gets a share of what is
left, so a step that keeps failing stops retrying at its share (kept_going, with the reason) and the later steps still
run. Offline (MockLLMClient)."""
import amoeba.interp.plan_runner as pr
from amoeba.adapt.fixes import limits
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from amoeba.llm.client import MockLLMClient
from amoeba.llm.limits import RunLimits
from tests.test_fixes_d117 import NO_EDIT, good, reply, step_no
from tests.test_plan_runner import plan_team


def stall(messages, seed):
    n = step_no(messages)
    return reply("calc", "1 + 1") if n == "1" else good(n)


class Heavy(MockLLMClient):
    """The same replies, each call billed `factor` times the tokens (a model that thinks or reads more)."""
    factor = 3

    def chat_messages(self, *a, **kw):
        r = super().chat_messages(*a, **kw)
        r.input_tokens, r.output_tokens = r.input_tokens * self.factor, r.output_tokens * self.factor
        return r


def go(task, envelope, trace, tools, tmp_path, heavy=False, opts=None):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=stall, fix_proposer=[NO_EDIT])
    if heavy:
        llm.__class__ = Heavy                     # only the plan run is billed heavier (drafting is done)
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path,
                     plan_options=opts or PlanOptions(adapt="on", failed_step="run")).run(cfg, task, seed=0)
    return ep


def test_a_model_using_three_times_the_tokens_gets_three_times_the_fix_allowance(task, envelope, tools, tmp_path,
                                                                                    monkeypatch):
    from amoeba.interp.trace import TraceWriter
    monkeypatch.setattr(pr, "fix_limits", lambda: {**limits(), "stop_when_exhausted": False})
    light = go(task, envelope, TraceWriter(None, episode_id="l"), tools, tmp_path / "l")
    heavy = go(task, envelope, TraceWriter(None, episode_id="h"), tools, tmp_path / "h", heavy=True)
    a, b = light.adaptation["token_allowance"], heavy.adaptation["token_allowance"]
    assert a > 0 and 2.9 <= b / a <= 3.1, (a, b)


def test_a_step_that_keeps_failing_stops_at_its_share_and_later_steps_still_run(task, envelope, trace, tools,
                                                                                  tmp_path, monkeypatch):
    monkeypatch.setattr(pr, "fix_limits", lambda: {**limits(), "stop_when_exhausted": False})
    trace.limits = RunLimits(max_tokens=22_000)
    ep = go(task, envelope, trace, tools, tmp_path)
    assert not trace.events("budget_stop"), "the run cap stopped the run"
    ran = {e["amoeba.step"] for e in trace.events("step_done")}
    assert ran == {1, 2, 3, 4}
    kept = [k for k in ep.adaptation["kept_going"] if k["step"] == 1]
    assert kept and "share" in kept[0]["why"], ep.adaptation["kept_going"]
