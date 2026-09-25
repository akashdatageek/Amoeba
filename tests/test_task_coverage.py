"""D52 — task intake check: every number and deliverable-like phrase of the task reaches the Planner's Requirements
and Givens (recorded in draft_quality; a hard check under --quality-gate)."""
from amoeba.task.draft import draft_team
from amoeba.task.models import Task
from amoeba.task.quality import deliverable_phrases, task_coverage
from tests.conftest import DB_PROMPT, fx, mock

FULL = fx("draft_d24_full")
APPROVE = fx("observer_d24_approve")
REQ = {"R1": "gather current benchmark results for PostgreSQL and MongoDB",
       "R2": "estimate the monthly cost for 50 tenants at 200 GB each",
       "R3": "prototype and test the event schema in both databases",
       "R4": "deliver a recommendation memo with a risk table"}


def draft(prompt, planner, gate=False, trace=None, envelope=None):
    llm = mock(planner=planner, agent_observer=[APPROVE], plan_observer=[APPROVE])
    return llm, draft_team(Task(id="t", prompt=prompt), llm, envelope, trace, prompts="d24", quality_gate=gate)


def test_phrases_are_cut_at_joining_words():
    assert [(k, p) for k, p, _ in deliverable_phrases("Prototype and test the schema; then build a demo.")] == [
        ("prototype", "Prototype"), ("test", "test the schema"), ("build", "build a demo")]
    assert [k for k, _, _ in deliverable_phrases("We tested, estimated, assessed, gathered, built and planned it")] == [
        "test", "estimate", "assess", "gather", "build", "plan"]
    assert deliverable_phrases("a testimony and a planet") == []            # other words are not the verbs


def test_everything_carried():
    c = task_coverage(DB_PROMPT, REQ, [])
    assert c["ok"] and c["numbers"] == ["50", "200"] and c["missing_numbers"] == [] and c["missing_phrases"] == []
    assert "test the event schema in both databases" in c["phrases"]


def test_numbers_may_sit_in_givens():
    req = {**REQ, "R2": "estimate the monthly cost"}
    assert task_coverage(DB_PROMPT, req, [])["missing_numbers"] == ["50", "200"]
    assert task_coverage(DB_PROMPT, req, ["given: 50 tenants x 200 GB"])["ok"]


def test_a_weakened_verb_is_missing():
    req = {**REQ, "R3": "prototype and estimate the event schema load"}              # "test" became "estimate"
    c = task_coverage(DB_PROMPT, req, [])
    assert not c["ok"] and c["missing_phrases"] == ["test the event schema in both databases"]


def test_same_verb_other_object_is_missing():
    c = task_coverage("Assess the migration risk and deliver a memo.", {"R1": "assess the cost", "R2": "deliver a memo"}, [])
    assert c["missing_phrases"] == ["Assess the migration risk"]


def test_recorded_in_the_draft_and_the_trace(envelope, trace):
    _, d = draft(DB_PROMPT + " Finish within 3 weeks and assess the migration risk.", [FULL], trace=trace,
                 envelope=envelope)
    c = d.quality["checks"]["task_coverage"]
    assert c["missing_numbers"] == ["3"] and c["missing_phrases"] == ["assess the migration risk"]
    assert d.consensus and "task_coverage" in d.quality["failed_checks"]           # recorded only: still accepted
    [ev] = trace.events("draft_quality")
    assert "task_coverage" in ev["amoeba.quality.failed_checks"]


def test_fed_to_the_quality_gate(envelope, trace):
    fixed = FULL.replace("- assumption: 30% yearly data growth",
                         "- assumption: 30% yearly data growth\n- given: finish within 3 weeks")
    fixed = fixed.replace("R4: deliver a recommendation memo with a risk table",
                          "R4: deliver a recommendation memo with a risk table\nR5: assess the migration risk")
    fixed = fixed.replace('"covers": ["R4"], "is_summariser": true', '"covers": ["R4", "R5"], "is_summariser": true')
    fixed = fixed.replace("   covers: R4\n", "   covers: R4, R5\n")
    indep = lambda t: t.replace("3. [Schema Engineer, Cost Analyst]: Cross-check numbers",
                                "3. [Schema Engineer]: Cross-check numbers").replace("   depends_on: 1, 2\n", "   depends_on: 1\n")
    llm, d = draft(DB_PROMPT + " Finish within 3 weeks and assess the migration risk.", [indep(FULL), indep(fixed)],
                   gate=True, trace=trace, envelope=envelope)
    assert d.rounds[0].gate_failed == ["task_coverage"] and d.rounds[1].gate_failed == [] and d.consensus
    second = llm.calls_of("planner")[1]["messages"][1]["content"]
    assert "Numbers in the task that no requirement or given carries: 3." in second
    assert 'Task phrases no requirement keeps (same verb, same object): "assess the migration risk".' in second
