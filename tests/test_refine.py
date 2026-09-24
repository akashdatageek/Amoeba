"""D50 — self-refinement from evidence: off | on-issues | always, with its own turns and before/after counts."""
import json

from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from amoeba.task.models import Task
from amoeba.tools.registry import default_registry
from scripts.run_task import parse_args, run_one
from tests.conftest import mock
from tests.test_plan_runner import APPROVE, BODY, DIAMOND, plan_team, scripted

CLEAN = BODY.replace("| storage | 10 TB |", "| storage | 10 TB [unverified] |")   # every figure tagged
WORD = {"1": "one", "2": "two", "3": "three", "4": "four"}                         # "OUT-1" would be a figure


def out(n):
    return f"OUT-{WORD[n]}\n{CLEAN}"


def untagged_first(n, k, prompt):
    """Step 1 first writes an untagged figure; told so, it tags it."""
    if n == "1" and "carry no [S#] or [unverified] tag" not in prompt:
        return f"{out(n)}\nStorage costs 4,200 USD per month."
    if n == "1":
        return f"{out(n)}\nStorage costs 4,200 USD per month [unverified]."
    return out(n) + ("\nVerdict: PASS\nIssues: none" if n == "3" else "")


def run(task, envelope, trace, tools, worker, mode):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=worker)
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions(self_refine=mode)).run(cfg, task, seed=0)
    return llm, ep


def test_on_issues_refines_an_untagged_figure_with_exactly_that_finding(task, envelope, trace, tools):
    w = scripted(untagged_first)
    llm, ep = run(task, envelope, trace, tools, w, "on-issues")
    one = ep.steps[0]
    assert one["refine_reason"] == "provenance" and w.seen["1"] == 2
    assert one["refine"]["before"] == {"failed_checks": 0, "untagged": 1, "hallucinated": 0}
    assert one["refine"]["after"] == {"failed_checks": 0, "untagged": 0, "hallucinated": 0}
    second = [c for c in llm.calls_of("plan_worker") if "(step 1)" in c["messages"][-1]["content"]][1]
    p = second["messages"][-1]["content"]
    assert "Plain code checked this step's output and found:\n1. 1 figure(s) carry no [S#] or [unverified] tag: 4,200." in p
    assert all(s["refine"] is None for s in ep.steps[1:])                     # nothing found elsewhere
    [ev] = trace.events("refine")
    assert (ev["amoeba.reason"], ev["amoeba.before.untagged"], ev["amoeba.after.untagged"]) == ("provenance", 1, 0)


def test_a_citation_of_an_unseen_source_is_named(task, envelope, trace, tools):
    w = scripted(lambda n, k, p: out(n) + ("\nPrice 3 USD [S9]." if (n, k) == ("2", 1) else "")
                 + ("\nVerdict: PASS\nIssues: none" if n == "3" else ""))
    llm, ep = run(task, envelope, trace, tools, w, "on-issues")
    two = ep.steps[1]
    assert two["refine_reason"] == "provenance" and two["refine"]["before"]["hallucinated"] == 1
    assert "these citations name sources you never saw: S9" in two["refine"]["findings"][0]


def test_off_refines_on_failed_checks_only(task, envelope, trace, tools):
    w = scripted(untagged_first)
    _, ep = run(task, envelope, trace, tools, w, "off")
    assert ep.steps[0]["refine"] is None and w.seen["1"] == 1


def test_always_adds_a_self_review_against_done_when_and_success_criteria(task, envelope, trace, tools):
    w = scripted(lambda n, k, p: out(n) + ("\nVerdict: PASS\nIssues: none" if n == "3" else ""))
    llm, ep = run(task, envelope, trace, tools, w, "always")
    one = ep.steps[0]
    assert one["refine_reason"] == "self_review" and w.seen["1"] == 2
    p = [c for c in llm.calls_of("plan_worker") if "(step 1)" in c["messages"][-1]["content"]][1]["messages"][-1]["content"]
    assert "done_when (every cell sourced)" in p and "success criteria (every number has a source)" in p
    assert one["turns"] == 2                                                   # 1 + 1 of the refine's own 2


def test_result_json_summarises_refinement_and_the_cli_default(tmp_path, envelope):
    w = scripted(untagged_first)
    llm = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=w)
    r = run_one(Task(prompt="Compute 17 * 23 + 5."), "plan", llm, envelope, default_registry(), tmp_path,
                draft_prompts="d24", plan_options=PlanOptions(self_refine="on-issues"))
    saved = json.loads((tmp_path / r.run_id / "result.json").read_text())["refinement"]
    assert saved["self_refine"] == "on-issues" and saved["steps_refined"] == 1
    assert saved["by_reason"] == {"provenance": 1} and (saved["before"]["untagged"], saved["after"]["untagged"]) == (1, 0)
    assert parse_args(["--toy"]).self_refine == "on-issues"
