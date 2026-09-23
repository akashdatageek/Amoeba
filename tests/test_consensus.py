"""Consensus — D24: both verdicts exactly APPROVE; D25 (d19): a reply with a numbered suggestion is no approval."""
from amoeba.task.draft import approves, draft_team, n_suggestions
from tests.conftest import fx, mock

REAL = fx("observer_numbered_then_no_suggestions")   # db-choice, attempt 1 round 2: four fixes, then "No Suggestions."
OK = fx("observer_no_suggestions")
D24_APPROVE, D24_REVISE = fx("observer_d24_approve"), fx("observer_d24_revise")
NO_VERDICT = "## Thought\nfine\n\n## Suggestions\nNone\n"


def suggestions(text):
    return text.split("## Suggestions", 1)[1]


def test_real_reply_with_four_fixes_is_not_an_approval():
    s = suggestions(REAL)
    assert "No Suggestions" in s                       # the original substring test would call this approval
    assert n_suggestions(s) == 4 and not approves(s)
    assert approves("No Suggestions") and approves("1. No Suggestions.")   # a numbered 'No Suggestions' is still one


def test_d19_round_with_that_reply_is_not_consensus(task, envelope, trace):
    d = draft_team(task, mock(planner=[fx("draft_round_ok")], agent_observer=[REAL, OK], plan_observer=[OK]),
                   envelope, trace)
    assert [r.consensus for r in d.rounds] == [False, True] and d.rounds_used == 2
    assert d.rounds[0].agent_suggestions_n == 4 and d.rounds[0].agent_verdict is None


def d24(task, envelope, trace, agent, plan):
    return draft_team(task, mock(planner=[fx("draft_d24_full")], agent_observer=agent, plan_observer=plan),
                      envelope, trace, prompts="d24")


def test_d24_both_approve_is_consensus(task, envelope, trace):
    d = d24(task, envelope, trace, [D24_APPROVE], [D24_APPROVE])
    assert d.consensus and d.rounds_used == 1
    assert (d.rounds[0].agent_verdict, d.rounds[0].plan_verdict) == ("APPROVE", "APPROVE")


def test_d24_one_revise_is_not(task, envelope, trace):
    d = d24(task, envelope, trace, [D24_REVISE, D24_APPROVE], [D24_APPROVE])
    assert [r.consensus for r in d.rounds] == [False, True]
    assert d.rounds[0].agent_verdict == "REVISE" and d.rounds[0].agent_suggestions_n == 1


def test_d24_approve_with_conditions_is_not_approve(task, envelope, trace):
    other = D24_APPROVE.replace("## Verdict\nAPPROVE", "## Verdict\nAPPROVE once step 3 is fixed")
    d = d24(task, envelope, trace, [other], [D24_APPROVE])
    assert not d.consensus and d.rounds[0].agent_verdict == "OTHER"


def test_d24_missing_verdict_gets_one_repair_then_counts_as_revise(task, envelope, trace):
    llm = mock(planner=[fx("draft_d24_full")], agent_observer=[NO_VERDICT], plan_observer=[D24_APPROVE])
    d = draft_team(task, llm, envelope, trace, prompts="d24")
    assert d.rounds_used == 3 and not d.consensus                       # never approved, draft still used
    assert [r.agent_verdict for r in d.rounds] == ["REVISE"] * 3
    assert len(llm.calls_of("agent_observer")) == 6                     # each round: the reply + one repair call
    assert "## Verdict" in llm.calls_of("agent_observer")[1]["messages"][1]["content"]
