"""D28 — independent verification (not self-reported) and the optional --quality-gate."""
from amoeba.config.prompts import PROMPT
from amoeba.task.draft import draft_team
from amoeba.task.models import Task
from tests.conftest import DB_PROMPT, fx, mock

FULL = fx("draft_d24_full")          # step 3 'Cross-check numbers' is done by the producers of steps 1-2
INDEPENDENT = FULL.replace("3. [Schema Engineer, Cost Analyst]: Cross-check numbers",
                           "3. [Schema Engineer]: Cross-check numbers").replace("   depends_on: 1, 2\n",
                                                                                "   depends_on: 1\n")
APPROVE = fx("observer_d24_approve")


def run(task, envelope, trace, planner, gate):
    llm = mock(planner=planner, agent_observer=[APPROVE], plan_observer=[APPROVE])
    task = Task(id="db-choice", prompt=DB_PROMPT)   # D52: a task the fixture's requirements carry (task_coverage)
    return llm, draft_team(task, llm, envelope, trace, prompts="d24", quality_gate=gate)


def test_independent_verification_by_a_non_producer(task, envelope, trace):
    _, d = run(task, envelope, trace, [INDEPENDENT], False)
    c = d.quality["checks"]["independent_verification"]
    assert c["ok"] and c["candidates"] == [{"step": 3, "verifiers": ["Schema Engineer"], "producers": ["Cost Analyst"],
                                            "independent": True}]


def test_plan_observer_prompt_requires_it():
    assert ("at least one step verifies numbers, sources or test results and is done by a role that did not\n"
            "   produce them; if missing, Verdict must be REVISE.") in PROMPT.d24_review_plan


def test_gate_off_by_default_approval_ends_drafting(task, envelope, trace):
    _, d = run(task, envelope, trace, [FULL], False)
    assert d.consensus and d.rounds_used == 1 and d.gate_hits == 0 and d.rounds[0].gate_failed == []


def test_gate_sends_the_draft_back_with_the_failed_checks(task, envelope, trace):
    llm, d = run(task, envelope, trace, [FULL, INDEPENDENT], True)
    assert d.rounds[0].gate_failed == ["independent_verification"] and not d.rounds[0].consensus
    assert d.rounds[1].gate_failed == [] and d.rounds[1].consensus and d.rounds_used == 2 and d.gate_hits == 1
    second = llm.calls_of("planner")[1]["messages"][1]["content"]
    assert "## Quality Gate (plain-code checks, must be fixed)" in second
    assert "done by a different role" in second
    [ev] = trace.events("quality_gate")
    assert ev["amoeba.gate.round"] == 1 and ev["amoeba.gate.failed"] == "independent_verification"


def test_gate_stays_within_the_round_cap(task, envelope, trace):
    _, d = run(task, envelope, trace, [FULL], True)
    assert d.rounds_used == 3 and not d.consensus and d.gate_hits == 3     # last draft still published
    assert d.quality["hard_failed"] == ["independent_verification"]


def test_gate_never_fires_on_checks_a_d19_draft_cannot_have(task, envelope, trace):
    d = draft_team(task, mock(planner=[fx("draft_round_ok")]), envelope, trace, quality_gate=True)
    assert d.consensus and d.gate_hits == 0 and d.quality["hard_failed"] == []
