"""D30 — Box 1 rubric scoring for tasks with no single right answer: deterministic, and never shown to Box 2 or 3."""
import json

import pytest

from amoeba.task.evaluate import number_found, rubric_score
from amoeba.task.models import Rubric, Task
from scripts.run_task import run_one
from tests.conftest import ROOT, fx, mock


# ---- the number matcher -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,value,unit", [
    ("one year is 21.9 TB of raw events", 21.9, "TB"),
    ("one year is 21,900 GB", 21.9, "TB"),
    ("one year is 19.92 TiB", 21.9, "TB"),          # the same bytes in binary units (the v1 false negative)
    ("about 20,885.3 GB per year", 21.9, "TB"),      # TB written, TiB-style arithmetic: within 5%
    ("60,000,000 KB per day", 60, "GB"),
    ("57.22 GiB per day", 60, "GB"),
    ("first-year revenue USD 10 million", 1e7, "USD"),
    ("first-year revenue $10M", 1e7, "USD"),
    ("first-year revenue: 10,000,000", 1e7, "USD"),
])
def test_number_found_accepts_equivalent_spellings(text, value, unit):
    assert number_found(text, value, unit) is not None


@pytest.mark.parametrize("text,value,unit", [
    ("storage: 15TB", 10, "TB"),
    ("a $10 add-on", 1e7, "USD"),
    ("10 million events", 10, "TB"),                 # right digits, wrong kind of quantity
    ("22.5 TB", 21.9, "TB"),                         # 2.7% off is fine, but not with tolerance 1%
])
def test_number_found_rejects_other_quantities(text, value, unit):
    assert number_found(text, value, unit, tolerance=0.01 if "22.5" in text else 0.05) is None


# ---- rubric_score -----------------------------------------------------------------------------------------------
RUBRIC = Rubric.model_validate({
    "required_deliverables": [{"name": "risk table", "any_of": [r"risk (table|register)"]}, {"name": "runbook"}],
    "expected_numbers": [{"name": "yearly storage", "value": 21.9, "unit": "TB"}],
    "constraints_to_respect": [{"name": "30 minutes late", "any_of": [r"30[- ]min"]}],
    "must_not": [{"name": "price without a source", "pattern": r"costs? \$\d+", "unless_nearby": r"source"}],
})


def test_rubric_score_items_and_fraction():
    answer = "Risk table below. Storage: 19.92 TiB/year. Page if 30-minute SLA missed. It costs $400 a month."
    r = rubric_score(answer, RUBRIC)
    got = {i["name"]: i["pass"] for i in r["items"]}
    assert got == {"risk table": True, "runbook": False, "yearly storage": True, "30 minutes late": True,
                   "price without a source": False}
    assert (r["passed"], r["total"], r["score"]) == (3, 5, 0.6) and r["judge"] is None
    assert next(i for i in r["items"] if i["name"] == "yearly storage")["evidence"] == "19.92 TiB"
    cited = answer.replace("a month.", "a month (source: AWS pricing page).")
    assert next(i for i in rubric_score(cited, RUBRIC)["items"] if i["kind"] == "must_not")["pass"] is True


def test_judge_hook_is_a_separate_signal():
    calls = []
    judge = lambda a, r: calls.append(a) or {"score": 0.0, "why": "LLM judge disagrees"}
    r = rubric_score("runbook", RUBRIC, judge=judge)
    assert calls == ["runbook"] and r["judge"]["why"] == "LLM judge disagrees"
    assert r["score"] == rubric_score("runbook", RUBRIC)["score"]     # the judge never moves the score


def test_complex_tasks_have_rubrics():
    tasks = [Task.model_validate(json.loads(l)) for l in (ROOT / "tasks/draft_eval_complex.jsonl").read_text().splitlines()
             if l.strip()]
    assert all(t.rubric and t.rubric.required_deliverables and t.rubric.expected_numbers and t.rubric.must_not
               for t in tasks)
    nums = {t.id: [(x.value, x.unit) for x in t.rubric.expected_numbers] for t in tasks}
    assert nums["clickstream-pipeline"] == [(60, "GB"), (21.9, "TB")] and nums["ebike-us-entry"] == [(1e7, "USD")]


def test_result_json_carries_the_rubric_score(tmp_path, envelope, tools):
    task = Task(prompt="Compute 17 * 23 + 5.", rubric={"required_deliverables": [{"name": "396"}, {"name": "memo"}]})
    r = run_one(task, "flat", mock(planner=[fx("draft_round_ok")], worker=[fx("worker_final_output")]),
                envelope, tools, tmp_path)
    saved = json.loads((tmp_path / r.run_id / "result.json").read_text())
    assert saved["score"] == 0.5 and [i["pass"] for i in saved["rubric"]["items"]] == [True, False]


# ---- guard: the rubric never reaches a Box 2 or Box 3 prompt -------------------------------------------------------
SENTINELS = ["ZQX-DELIVERABLE", "ZQX-ANYOF", "ZQX-NUMBER", "ZQX-UNIT", "ZQX-CONSTRAINT", "ZQX-MUSTNOT", "ZQX-PATTERN",
             "ZQX-NEARBY", "987654.321"]
SECRET = {"required_deliverables": [{"name": "ZQX-DELIVERABLE", "any_of": ["ZQX-ANYOF"]}],
          "expected_numbers": [{"name": "ZQX-NUMBER", "value": 987654.321, "unit": "ZQX-UNIT"}],
          "constraints_to_respect": [{"name": "ZQX-CONSTRAINT"}],
          "must_not": [{"name": "ZQX-MUSTNOT", "pattern": "ZQX-PATTERN", "unless_nearby": "ZQX-NEARBY"}]}
APPROVE = fx("observer_d24_approve")
SCRIPTS = {
    "d19": dict(planner=[fx("draft_round_ok")]),
    "d24": dict(planner=[fx("draft_d24_full")], agent_observer=[APPROVE], plan_observer=[APPROVE]),
}


@pytest.mark.parametrize("prompts", ["d19", "d24"])
@pytest.mark.parametrize("topology", ["flat", "boss_reviewers"])
def test_rubric_never_reaches_box2_or_box3_prompts(prompts, topology, tmp_path, envelope, tools):
    task = Task(prompt="Compute 17 * 23 + 5.", rubric=SECRET)
    llm = mock(worker=[fx("worker_final_output")], solver=["396"], critic=["Action: Agree\nAction Input: fine."],
               **SCRIPTS[prompts])
    r = run_one(task, topology, llm, envelope, tools, tmp_path, draft_prompts=prompts, quality_gate=True)
    kinds = {c["kind"] for c in llm.calls}
    assert {"planner", "agent_observer", "plan_observer"} <= kinds and r.error is None
    assert kinds & ({"worker"} if topology == "flat" else {"solver", "critic"})
    sent = json.dumps([c["messages"] for c in llm.calls])
    assert [s for s in SENTINELS if s in sent] == []
    assert r.rubric["total"] == 4                                   # Box 1 did score it, after the run
