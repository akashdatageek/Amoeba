"""T4 — the drafting loop."""
import pytest

from amoeba.task.draft import DraftError, draft_team
from tests.conftest import fx, mock

OK, COMPLAINT = "observer_no_suggestions", "observer_complaint"


def test_consensus_round1(task, envelope, trace):
    llm = mock(planner=[fx("draft_round_ok")])
    d = draft_team(task, llm, envelope, trace)
    assert d.rounds_used == 1 and d.consensus
    assert [r.name for r in d.created_roles] == ["Calculator", "Writer"]
    assert d.created_roles[0].tools == ["calc"]                      # unknown 'web_search' stripped
    assert any(not r.tools for r in d.created_roles)                 # summariser present
    assert [s.agent_names for s in d.plan] == [["Calculator"], ["Writer"]]   # '[Editor]' step dropped
    assert len(trace.spans("chat")) == 3 and len(llm.calls_of("planner")) == 1


def test_consensus_round3_under_current_round_rule(task, envelope, trace):
    # cumulative rule (AutoAgents) would stop after round 2; the current-round rule needs round 3
    llm = mock(planner=[fx("draft_round_ok")],
               agent_observer=[fx(OK), fx(COMPLAINT), fx(OK)],
               plan_observer=[fx(COMPLAINT), fx(OK), fx(OK)])
    d = draft_team(task, llm, envelope, trace)
    assert d.rounds_used == 3 and d.consensus
    assert len(llm.calls_of("agent_observer")) == 3 and len(llm.calls_of("plan_observer")) == 3   # observers every round
    assert len(trace.spans("chat")) == 9
    # the planner sees only the latest round's suggestions (manager.py:45)
    third_planner_prompt = llm.calls_of("planner")[2]["messages"][1]["content"]
    assert "## Role Suggestions\n1. The Calculator role" in third_planner_prompt
    assert "## Plan Suggestions\nNo Suggestions" in third_planner_prompt
    # the plan observer receives the cumulative PLAN suggestions (bug D3 fixed)
    third_plan_obs_prompt = llm.calls_of("plan_observer")[2]["messages"][1]["content"]
    assert "## Plan Suggestions\n1. The Calculator role" in third_plan_obs_prompt


def test_never_consensus_uses_last_draft(task, envelope, trace):
    llm = mock(planner=[fx("draft_round_ok")], agent_observer=[fx(COMPLAINT)], plan_observer=[fx(COMPLAINT)])
    d = draft_team(task, llm, envelope, trace)
    assert d.rounds_used == 3 and not d.consensus
    assert len(trace.spans("chat")) == 9
    assert d.raw_draft == fx("draft_round_ok")


def test_bad_json_blob_skipped(task, envelope, trace):
    d = draft_team(task, mock(planner=[fx("draft_bad_json_blob")]), envelope, trace)
    assert [r.name for r in d.created_roles] == ["Calculator", "Writer"]


def test_summariser_appended_when_missing(task, envelope, trace):
    d = draft_team(task, mock(planner=[fx("draft_no_summariser")]), envelope, trace)
    assert d.created_roles[-1].name == "Language Expert" and d.created_roles[-1].tools == []
    assert len(d.created_roles) == 3


def test_missing_section_gets_one_repair_call_then_drafterror(task, envelope, trace):
    llm = mock(planner=["## Thought\nno sections here\n"])
    with pytest.raises(DraftError):
        draft_team(task, llm, envelope, trace)
    assert len(llm.calls_of("planner")) == 2   # original + one repair
    assert "# Error" in llm.calls_of("planner")[1]["messages"][1]["content"]


ONE_ROLE = '''## Selected Roles List:
```
```

## Created Roles List:
```
{"name": "Writer", "description": "states the answer", "tools": [], "suggestions": "", "prompt": "You are a Writer."}
```

## Execution Plan:
1. [Writer]: State the answer.

## RoleFeedback
x

## PlanFeedback
y
'''


def test_roster_too_small_is_drafterror(task, envelope, trace):
    # a single no-tool role: no summariser is appended, so the roster stays at 1
    with pytest.raises(DraftError, match="roster size"):
        draft_team(task, mock(planner=[ONE_ROLE]), envelope, trace)


def test_no_step_names_a_role_is_drafterror(task, envelope, trace):
    empty_plan = fx("draft_round_ok").replace("[Calculator]", "[Nobody]").replace("[Writer]", "[Nobody]")
    with pytest.raises(DraftError, match="empty plan"):
        draft_team(task, mock(planner=[empty_plan]), envelope, trace)


def test_substring_fallback_matches_like_autoagents(task, envelope, trace):
    # "[Senior Calculator]: ..." names no roster entry exactly; group.py:61-64 matches "Calculator" by substring
    text = fx("draft_round_ok").replace("1. [Calculator]:", "1. [Senior Calculator]:")
    d = draft_team(task, mock(planner=[text]), envelope, trace)
    assert d.plan[0].agent_names == ["Calculator"]
