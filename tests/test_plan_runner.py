"""D31 — the plan topology: steps run over the depends_on graph and see only the artifacts they depend on."""
import json
import re

import pytest

from amoeba.config.schema import PlanStep
from amoeba.interp.plan_runner import PLAN_MAX_TOKENS, PlanGraphError, relink, waves
from amoeba.interp.runtime import Interpreter
from amoeba.llm.toy_mock import toy_mock_client
from amoeba.task.draft import DraftError, draft_team
from amoeba.task.instantiate import instantiate
from amoeba.task.models import Task
from amoeba.task.source import ToyTaskSource
from scripts.run_task import run_one
from tests.conftest import fx, mock

APPROVE = fx("observer_d24_approve")
FULL = fx("draft_d24_full")
# 1 -> 2, 1 -> 3, 2 -> 4, 3 -> 4
DIAMOND = (FULL.replace("   covers: R3\n   depends_on: none", "   covers: R3\n   depends_on: 1")
           .replace("   depends_on: 1, 2\n", "   depends_on: 1\n")
           .replace("   covers: R4\n   depends_on: 3", "   covers: R4\n   depends_on: 2, 3"))


def step_no(messages) -> str:
    return re.search(r"# Your step \(step (\d+)\)", messages[-1]["content"]).group(1)


def finish(messages, seed):
    n = step_no(messages)
    return f"## Thought\nDone.\n\n## CurrentStep\nstep {n}\n\n## Action\nFinal Output\n\n## ActionInput\nOUT-{n}\n"


def plan_team(task, envelope, trace, text=DIAMOND, **script):
    llm = mock(planner=[text], agent_observer=[APPROVE], plan_observer=[APPROVE], **script)
    return llm, instantiate(draft_team(task, llm, envelope, trace, prompts="d24"), "plan", task, envelope)


def steps(deps: dict[int, list[int]]) -> list[PlanStep]:
    return [PlanStep(index=n - 1, agent_ids=["a"], text=f"step {n}", depends_on=d) for n, d in deps.items()]


# ---- the graph ----------------------------------------------------------------------------------------------------
def test_waves_of_a_diamond():
    assert waves(steps({1: [], 2: [1], 3: [1], 4: [2, 3]})) == [[1], [2, 3], [4]]


def test_a_plan_without_depends_on_is_a_chain():
    assert waves(steps({1: [], 2: [], 3: []})) == [[1], [2], [3]]


@pytest.mark.parametrize("deps,msg", [({1: [2], 2: [1]}, "cycle"), ({1: [], 2: [7]}, "unknown step")])
def test_bad_graphs_are_rejected(deps, msg):
    with pytest.raises(PlanGraphError, match=msg):
        waves(steps(deps))


def test_dependency_on_a_dropped_step_is_relinked():
    kept = steps({1: [], 2: [1], 4: [1, 3]})
    written = {1: [], 2: [1], 3: [2], 4: [1, 3]}          # step 3 was dropped by Box 2 (it named no known role)
    out, events = relink(kept, written)
    assert [s.depends_on for s in out] == [[], [1], [1, 2]]
    assert events == [{"amoeba.step": 4, "amoeba.missing_step": 3, "amoeba.replaced_by": [2]}]


# ---- running it ---------------------------------------------------------------------------------------------------
def test_diamond_runs_in_order_and_steps_see_only_their_inputs(task, envelope, trace, tools, tmp_path):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=finish)
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path).run(cfg, task, seed=0)
    assert [(s["step"], s["wave"], s["received"], s["status"]) for s in ep.steps] == [
        (1, 1, [], "done"), (2, 2, [1], "done"), (3, 2, [1], "done"), (4, 3, [2, 3], "done")]
    assert ep.answer == "OUT-4" and ep.error is None
    seen = {}
    for c in llm.calls_of("plan_worker"):
        seen.setdefault(step_no(c["messages"]), []).append(c["messages"][-1]["content"])
    inputs = {n: re.search(r"# Inputs: .*?\n(.*?)\n\n# Work done", ps[0], re.S).group(1) for n, ps in seen.items()}
    assert "None: this step starts from the task alone." in inputs["1"]
    assert "OUT-1" in inputs["3"] and "OUT-2" not in inputs["3"]          # 3 depends on 1 only
    assert "OUT-2" in inputs["4"] and "OUT-3" in inputs["4"] and "OUT-1" not in inputs["4"]
    assert "Compute 17 * 23 + 5" in seen["4"][0] and "Constraints: 12-person team" in seen["1"][0]
    assert all(c["max_tokens"] == PLAN_MAX_TOKENS for c in llm.calls_of("plan_worker"))
    # the multi-role step records both helpers, in turn order
    three = ep.steps[2]
    assert [c["agent"] for c in three["contributions"]] == ["Cost Analyst", "Schema Engineer"]   # roster order
    # artifacts on disk: the text and its metadata
    meta = json.loads((tmp_path / "artifacts" / "step_3.json").read_text())
    assert meta["roles"] == ["Cost Analyst", "Schema Engineer"] and meta["covers"] == ["R2", "R3"]
    assert meta["output_spec"] == "reconciled figures" and meta["sources"] == []
    assert (tmp_path / "artifacts" / "step_4.md").read_text() == "OUT-4\n"
    ev = trace.events("plan_graph")[0]
    assert ev["amoeba.waves"] == [[1], [2, 3], [4]] and ev["amoeba.max_turns"] == 5


def test_a_cycle_is_rejected_before_any_box3_call(task, envelope, trace):
    cyc = DIAMOND.replace("   covers: R1, R2\n   depends_on: none", "   covers: R1, R2\n   depends_on: 4")
    llm = mock(planner=[cyc], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=finish)
    with pytest.raises(DraftError, match="V8 plan: cycle"):
        instantiate(draft_team(task, llm, envelope, trace, prompts="d24"), "plan", task, envelope)
    assert llm.calls_of("plan_worker") == []


def test_step_that_never_finishes_is_max_turns(task, envelope, trace, tools):
    stall = lambda m, s: "## Thought\nhm\n\n## CurrentStep\nthink\n\n## Action\nPrint\n\n## ActionInput\nthinking\n"
    llm, cfg = plan_team(task, envelope, trace, plan_worker=stall)
    ep = Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    assert ep.steps[0]["status"] == "max_turns" and ep.steps[0]["turns"] == 5
    assert ep.error == "max_turns"


def test_toy_tasks_with_a_d19_draft_run_as_a_chain(tmp_path, envelope, tools):
    for t in ToyTaskSource(0, 5).tasks():
        r = run_one(t, "plan", toy_mock_client(), envelope, tools, tmp_path)
        assert r.score == 1.0 and r.error is None
        saved = json.loads((tmp_path / r.run_id / "artifacts" / "step_2.json").read_text())
        assert saved["received"] == [1] and saved["status"] == "done"
