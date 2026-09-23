"""D24 step 4 — deterministic draft_quality checks: recorded in Draft/result.json/trace, never used to reject."""
import json

from amoeba.task.draft import draft_team
from amoeba.task.models import Task
from scripts.eval_draft import derived_correct
from scripts.run_task import run_one
from tests.conftest import fx, mock

FULL = fx("draft_d24_full")
APPROVE = fx("observer_d24_approve")


def d24(task, envelope, trace, text):
    return draft_team(task, mock(planner=[text], agent_observer=[APPROVE], plan_observer=[APPROVE]),
                      envelope, trace, prompts="d24")


def test_full_d24_draft(task, envelope, trace):
    q = d24(task, envelope, trace, FULL).quality
    c = q["checks"]
    assert c["requirements_covered"]["ok"] and c["requirements_covered"]["requirements"] == 4
    assert c["dependencies_valid"]["ok"] and c["roles_fully_defined"]["ok"] and c["tools_accounted"]["ok"]
    assert c["summariser"] == {"ok": True, "declared_by_planner": 1, "name": "Memo Writer", "tools": [], "owns_steps": [4]}
    # step 3 cross-checks R2/R3, but the same two roles did steps 1-2: not an independent verification
    assert c["verification_step"] == {"ok": False, "steps": []}
    assert q["failed_checks"] == ["verification_step"] and (q["passed"], q["failed"], q["na"]) == (5, 1, 0)
    [ev] = trace.events("draft_quality")
    assert ev["amoeba.quality.failed_checks"] == "verification_step"


def test_verification_by_another_role(task, envelope, trace):
    text = FULL.replace("3. [Schema Engineer, Cost Analyst]: Cross-check numbers", "3. [Schema Engineer]: Cross-check numbers")
    assert d24(task, envelope, trace, text).quality["checks"]["verification_step"] == {"ok": True, "steps": [3]}


def test_problems_are_recorded_not_rejected(task, envelope, trace):
    text = (FULL.replace("   depends_on: 3\n", "   depends_on: 5\n")                           # points forward
                .replace('"goal": "a tested schema in both databases", ', "")                  # thin role
                .replace('"tools": [], "inputs": ["steps 1-3"]', '"tools": ["echo"], "inputs": ["steps 1-3"]')
                .replace("R4: deliver a recommendation memo with a risk table", "R4: deliver a memo\nR5: a slide deck"))
    d = d24(task, envelope, trace, text)                                                       # still accepted
    c = d.quality["checks"]
    assert c["dependencies_valid"] == {"ok": False, "bad": [{"step": 4, "depends_on": 5}]}
    assert c["roles_fully_defined"]["thin"] == {"Schema Engineer": ["goal"]}
    assert c["summariser"]["ok"] is False and c["summariser"]["tools"] == ["echo"]
    assert c["requirements_covered"]["uncovered_by_steps"] == ["R5"]
    assert set(d.quality["failed_checks"]) >= {"dependencies_valid", "roles_fully_defined", "summariser",
                                               "requirements_covered"}


def test_d19_draft_reports_na_where_it_has_no_fields(task, envelope, trace):
    q = draft_team(task, mock(planner=[fx("draft_round_ok")]), envelope, trace).quality
    c = q["checks"]
    assert c["requirements_covered"]["ok"] is None and c["verification_step"]["ok"] is None
    assert c["dependencies_valid"]["ok"] is None and q["na"] == 3
    assert c["tools_accounted"] == {"ok": False, "missing_not_requested_by_planner": ["web_search"]}
    assert c["roles_fully_defined"]["defined"] == 0


def test_result_json_carries_it(tmp_path, envelope, tools):
    r = run_one(Task(prompt="Compute 17 * 23 + 5.", ground_truth="396"), "flat",
                mock(planner=[FULL], agent_observer=[APPROVE], plan_observer=[APPROVE],
                     worker=[fx("worker_final_output")]),
                envelope, tools, tmp_path, draft_prompts="d24")
    saved = json.loads((tmp_path / r.run_id / "result.json").read_text())
    assert saved["draft_quality"]["failed_checks"] == ["verification_step"]
    assert json.loads((tmp_path / r.run_id / "plan.json").read_text())["quality"]["passed"] == 5


def test_derived_correct():
    t = Task(prompt="p", expected={"derived": [["10 TB", "10,000 GB"], ["83 queries per second", "83 qps"]]})
    assert derived_correct(t, "storage: 10,000 GB total; about 83 QPS at peak") is True
    assert derived_correct(t, "storage: 15TB; 83 qps") is False
    assert derived_correct(Task(prompt="p"), "anything") is None
