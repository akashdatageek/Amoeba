"""D24 — our Box 2 prompts, selected with --draft-prompts d24 (spec/BOX2_PROMPT_UPGRADE_D24.md)."""
import pytest

from amoeba.config.prompts import MANAGER_PREFIX, PROMPT, prompt_source, render
from amoeba.task.draft import draft_team
from scripts.extract_prompts import SOURCES
from tests.conftest import fx, mock

D24_FILES = ["d24_planner_system", "d24_create_team", "d24_create_team_format", "d24_agent_observer_system",
             "d24_review_team", "d24_plan_observer_system", "d24_review_plan"]


@pytest.mark.parametrize("stem", D24_FILES)
def test_d24_files_are_ours_and_not_checked_as_verbatim(stem):
    assert prompt_source(stem).startswith("# source: ours — DEVIATION D24")
    assert stem not in SOURCES
    assert getattr(PROMPT, stem).strip()


def d24_mock(**script):
    script.setdefault("planner", [fx("draft_d24_minimal")])
    script.setdefault("agent_observer", [fx("observer_d24_approve")])
    script.setdefault("plan_observer", [fx("observer_d24_approve")])
    return mock(**script)


def test_d24_sends_its_own_prompts_and_system_messages(task, envelope, trace):
    llm = d24_mock()
    d = draft_team(task, llm, envelope, trace, prompts="d24")
    assert d.prompts == "d24" and [r.name for r in d.created_roles] == ["Calculator", "Writer"]
    planner, agent_obs, plan_obs = (llm.calls_of(k)[0]["messages"] for k in ("planner", "agent_observer", "plan_observer"))
    assert planner[0]["content"] == PROMPT.d24_planner_system.strip() != MANAGER_PREFIX
    assert agent_obs[0]["content"] == PROMPT.d24_agent_observer_system.strip()
    assert plan_obs[0]["content"] == PROMPT.d24_plan_observer_system.strip()
    user = planner[1]["content"]
    assert "${" not in user and "at most 5 including the" in user and task.prompt in user
    assert '"outputs": [{"artifact": "cost table"' in user          # Template syntax: JSON braces stay single
    assert "## Risks and Decisions:" in user and "Prefer existing tools" not in user
    assert "R1: compute 17 * 23 + 5 exactly" in agent_obs[1]["content"] and "${" not in agent_obs[1]["content"]
    assert "- none material" in plan_obs[1]["content"] and "${" not in plan_obs[1]["content"]


def test_default_stays_d19(task, envelope, trace):
    llm = mock(planner=[fx("draft_round_ok")])
    d = draft_team(task, llm, envelope, trace)
    assert d.prompts == "d19"
    assert llm.calls_of("planner")[0]["messages"][0]["content"] == MANAGER_PREFIX
    assert "You are a manager and expert prompt engineer" in llm.calls_of("planner")[0]["messages"][1]["content"]


def test_unknown_prompt_set_is_refused(task, envelope, trace):
    with pytest.raises(ValueError, match="unknown draft prompts"):
        draft_team(task, mock(planner=[fx("draft_round_ok")]), envelope, trace, prompts="d99")


def test_d24_template_leaves_no_placeholder_unfilled():
    body = render(PROMPT.d24_create_team, context="c", existing_roles="[]", tools="t", history="h", suggestions="s",
                  max_agents="5", format_example="f")
    assert "${" not in body
