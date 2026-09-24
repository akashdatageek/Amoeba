"""D51 — collaborative refinement in multi-role steps: concat (earlier behaviour) or critique (draft → reviews →
revise, at most 2 rounds, ended by plain code)."""
import json

from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from amoeba.task.models import Task
from amoeba.tools.registry import default_registry
from scripts.run_task import parse_args, run_one
from tests.conftest import mock
from tests.test_plan_runner import APPROVE, DIAMOND, plan_team, scripted
from tests.test_refine import out

AGREE = "## Verdict\nAGREE\n\n## Issues\nnone\n"
REVISE = "## Verdict\nREVISE\n\n## Issues\n1. Add the p95 latency you measured.\n2. Name the source of the price.\n"


def worker(n, k, prompt):
    body = out(n) + ("\nVerdict: PASS\nIssues: none" if n == "3" else "")
    return body + (f"\nrevision {k}" if "Your teammates reviewed your draft" in prompt else "")


def run(task, envelope, trace, tools, critic, collab="critique"):
    w = scripted(worker)
    llm, cfg = plan_team(task, envelope, trace, plan_worker=w, plan_critic=critic)
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions(collab=collab)).run(cfg, task, seed=0)
    three = [s for s in ep.steps if s["step"] == 3][-1]
    return llm, w, ep, three


def test_reviewers_agree_on_the_first_draft(task, envelope, trace, tools):
    llm, w, ep, three = run(task, envelope, trace, tools, [AGREE])
    assert three["collab"] == {"mode": "critique", "drafter": "Cost Analyst", "reviewers": ["Schema Engineer"],
                               "rounds": 1, "revisions": 0, "objections": {"Schema Engineer": [0]}, "agreed": True}
    assert w.seen["3"] == 1 and three["roles"] == ["Cost Analyst", "Schema Engineer"]
    art = [c for c in llm.calls_of("plan_critic")][0]["messages"][-1]["content"]
    assert "The draft, written by Cost Analyst\nOUT-three" in art
    assert "done_when: both agree within 10%" in art and "p95 latency measured at 5,000 queries/min" in art
    # one merged output: the drafter's text, no per-role headings
    step4 = llm.calls_of("plan_summariser")[0]["messages"][-1]["content"]
    assert "### Schema Engineer" not in step4 and "OUT-three" in step4


def test_revise_then_agree(task, envelope, trace, tools):
    llm, w, ep, three = run(task, envelope, trace, tools, [REVISE, AGREE])
    c = three["collab"]
    assert (c["rounds"], c["revisions"], c["agreed"], c["objections"]) == (2, 1, True, {"Schema Engineer": [2, 0]})
    revise_prompt = [x for x in llm.calls_of("plan_worker") if "(step 3)" in x["messages"][-1]["content"]][-1]
    p = revise_prompt["messages"][-1]["content"]
    assert "- Schema Engineer: 1. Add the p95 latency you measured.\n- Schema Engineer: 2. Name the source" in p
    assert [e["amoeba.revise"] for e in trace.events("collab_round")] == [["Schema Engineer"], []]


def test_rounds_run_out_without_agreement(task, envelope, trace, tools):
    llm, w, ep, three = run(task, envelope, trace, tools, [REVISE])
    c = three["collab"]
    assert (c["rounds"], c["revisions"], c["agreed"]) == (2, 2, False) and len(llm.calls_of("plan_critic")) == 2
    assert three["status"] == "done"                     # disagreement is recorded, not a failed step


def test_concat_keeps_the_earlier_behaviour(task, envelope, trace, tools):
    llm, w, ep, three = run(task, envelope, trace, tools, [AGREE], collab="concat")
    assert three["collab"] is None and llm.calls_of("plan_critic") == [] and w.seen["3"] == 2


def test_an_unreadable_review_counts_as_agreement(task, envelope, trace, tools):
    llm, w, ep, three = run(task, envelope, trace, tools, ["looks fine to me"])
    assert three["collab"]["agreed"] is True and len(trace.events("review_unreadable")) == 1


def test_result_json_and_cli_default(tmp_path, envelope):
    w = scripted(worker)
    llm = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=w,
               plan_critic=[REVISE, AGREE])
    r = run_one(Task(prompt="Compute 17 * 23 + 5."), "plan", llm, envelope, default_registry(), tmp_path,
                draft_prompts="d24", plan_options=PlanOptions(collab="critique", self_refine="on-issues"))
    ref = json.loads((tmp_path / r.run_id / "result.json").read_text())["refinement"]
    assert (ref["collab"], ref["collab_steps"], ref["collab_agreed"], ref["collab_rounds"]) == ("critique", 1, 1, 2)
    assert parse_args(["--toy"]).collab == "critique"
