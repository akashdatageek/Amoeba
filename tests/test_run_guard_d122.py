"""D122 — limits that do not throw away nearly finished work: the runaway guard (model calls with no progress, armed
only once the plan runner started), finish mode near a hard cap (no fixes, rework, dispute resolution or re-planning),
the answer assembled from the finished steps when a run is stopped, and dispute pairing that needs the same scale and
unit. Offline, with the mock LLM."""
from amoeba.interp.disputes import disputed_figures
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from amoeba.llm.limits import RunLimitReached, RunLimits
from amoeba.llm.toy_mock import toy_mock_client
from amoeba.task.source import ToyTaskSource
from scripts.run_task import run_one
from tests.test_fixes_d117 import BODY, good, reply
from tests.test_plan_runner import plan_team, step_no


class FakeTrace:
    def __init__(self):
        self.ev, self.sp = [], []

    def events(self, name=None):
        return [e for e in self.ev if name is None or e["name"] == name]

    def spans(self, name=None):
        return [s for s in self.sp if name is None or s["name"] == name]

    def event(self, name, attrs):
        self.ev.append({"name": name, **attrs})

    def call(self):
        self.sp.append({"name": "chat", "gen_ai.usage.input_tokens": 100, "gen_ai.usage.output_tokens": 10})


def test_the_runaway_guard_counts_calls_without_progress_once_the_plan_runner_started():
    t, lim = FakeTrace(), RunLimits(stall_calls=3)
    for _ in range(5):                       # drafting: not counted (no plan_graph yet)
        t.call()
        lim.check(t)
    t.event("plan_graph", {})
    lim.check(t)                             # the check runs before each call: armed here
    t.call()
    t.event("step_done", {"amoeba.step": 1, "amoeba.status": "partial"})    # progress: a new step
    lim.check(t)
    t.call()
    t.event("step_done", {"amoeba.step": 1, "amoeba.status": "partial"})    # the same step again: no progress
    lim.check(t)
    t.call()
    lim.check(t)
    t.call()
    try:                                     # 3 calls since the last progress mark
        lim.check(t)
        raise AssertionError("expected a stall stop")
    except RunLimitReached as e:
        assert e.code == "stalled" and "no progress in the last 3 model calls" in str(e)
    assert t.events("stall_stop")[0]["amoeba.calls_without_progress"] == 3


def test_the_guard_never_stops_a_baseline_and_no_limits_stop_nothing(tmp_path, envelope, tools):
    task = ToyTaskSource(0, 1).tasks()[0]
    r = run_one(task, "flat", toy_mock_client(), envelope, tools, tmp_path, limits=RunLimits(stall_calls=1))
    assert r.error is None                   # no plan_graph in a flat run: the guard never arms
    assert RunLimits(stall_calls=None).active() is False and RunLimits().finishing(FakeTrace()) is False


def stuck_then_fine(messages, seed):
    n = step_no(messages)
    return reply("calc", "1 + 1") if n == "1" else good(n)         # step 1 never finishes: max_turns, stuck


def test_finish_mode_skips_the_optional_fixes_and_records_it(task, envelope, trace, tools):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=stuck_then_fine, fix_proposer=["no fix"] * 4)
    trace.limits = RunLimits(max_tokens=10**9, finish_share=0.0)   # finish mode from the start
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions(adapt="on", failed_step="run")).run(cfg, task, seed=0)
    assert ep.stuck and not trace.events("fix_try")               # stuck, but no fix in finish mode
    assert ep.run_guard["finish_mode"] is True and ep.run_guard["skipped"]["fixes"] >= 1
    assert trace.events("finish_mode") and len(trace.events("finish_mode")) == 1
    assert ep.answer                                              # the run still reached the answer step


def test_a_stall_stop_assembles_the_answer_from_the_finished_steps(task, envelope, trace, tools):
    def script(messages, seed):
        n = step_no(messages)
        return reply("calc", "1 + 1") if n == "3" else good(n)      # step 3 loops on calc
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script, fix_proposer=["no fix"] * 6)
    trace.limits = RunLimits(stall_calls=4)
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions(adapt="on", failed_step="run")).run(cfg, task, seed=0)
    assert ep.error.startswith("stalled: stopped with step(s)") and "4" in ep.error.split("not run")[0]
    assert ep.answer.startswith("# Partial answer") and "## Step 1:" in ep.answer and "## Step 2:" in ep.answer
    assert ep.run_guard["stopped"]["code"] == "stalled" and 4 in ep.run_guard["stopped"]["steps_not_run"]


def test_disputes_need_the_same_scale_and_unit():
    """H3 re-run 3fcf80bb: 16 resolver calls on figures that only shared a label word."""
    own = ("Purchase Price (BEV): Range of $325,000 [S21] to $420,000.\nDiesel: 6.5 MPG\n"
           "Diesel truck price $180,000")
    outs = {2: "| Charger | $70,000 | price range $35 per kW |",
            3: "Diesel: 420,000 mi over 7 years\nDiesel truck price $150,000"}
    assert [(d["verifier"], d["worker"]) for d in disputed_figures(own, outs)] == [("$180,000", "$150,000")]
