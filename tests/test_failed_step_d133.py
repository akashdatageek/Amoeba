"""D133 — a step that ends with no output blocks only the steps that need it. The diamond plan: 1 → 2, 3 → 4
(the summariser's step 4 needs 2 and 3). Offline."""
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from tests.test_fixes_d117 import NO_EDIT, ON, good
from tests.test_plan_runner import plan_team, step_no


def silent_two(messages, seed):
    """Step 2's helper never writes a readable reply, as when the service blocks every turn: no output."""
    n = step_no(messages)
    return "" if n == "2" else good(n)          # empty: unreadable in the text and the native protocol (D136)


def run(task, envelope, trace, tools, opts):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=silent_two, fix_proposer=[NO_EDIT])
    return Interpreter(llm, tools, trace, plan_options=opts).run(cfg, task, seed=0)


def test_dependents_mode_skips_only_what_needs_the_failed_step(task, envelope, trace, tools):
    ep = run(task, envelope, trace, tools, PlanOptions(failed_step="dependents"))
    by = {m["step"]: m for m in ep.steps}
    assert by[2]["status"] == "incomplete" and by[3]["status"] == "done"          # 3 does not need 2: it ran
    assert by[4]["blocked_upstream"] == [2] and by[4]["turns"] == 0               # 4 needs 2: skipped, no call
    assert trace.events("step_skipped") == [{**trace.events("step_skipped")[0], "amoeba.step": 4,
                                             "amoeba.blocked_by": [2]}]
    assert ep.error.startswith("blocked_upstream: step(s) 2 ended with no output; skipped 4")
    assert "OUT-1" in ep.answer and "OUT-3" in ep.answer                           # assembled from what exists


def test_run_mode_keeps_the_earlier_behaviour(task, envelope, trace, tools):
    ep = run(task, envelope, trace, tools, PlanOptions(failed_step="run"))
    by = {m["step"]: m for m in ep.steps}
    assert "blocked_upstream" not in by[4] and by[4]["turns"] >= 1                 # 4 ran on step 2's empty output
    assert not trace.events("step_skipped")


def test_with_adapt_on_a_stuck_step_no_longer_stops_the_task(task, envelope, trace, tools, monkeypatch):
    import amoeba.interp.plan_runner as pr
    from amoeba.adapt.fixes import limits
    monkeypatch.setattr(pr, "fix_limits", lambda: {**limits(), "stop_when_exhausted": True})
    from dataclasses import replace
    ep = run(task, envelope, trace, tools, replace(ON, failed_step="dependents"))
    by = {m["step"]: m for m in ep.steps}
    assert by[3]["status"] == "done" and by[4].get("blocked_upstream") == [2]
    assert trace.events("stuck_step_kept_going") and not trace.events("adapt_stop")
