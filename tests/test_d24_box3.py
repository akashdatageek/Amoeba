"""D24 step 5 — the role card and the step detail reach Box 3's prompts; d19 teams are unchanged."""
from amoeba.interp.runtime import Interpreter
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from tests.conftest import fx, mock

APPROVE = fx("observer_d24_approve")


def team(task, envelope, trace, topology, **script):
    llm = mock(planner=[fx("draft_d24_full")], agent_observer=[APPROVE], plan_observer=[APPROVE], **script)
    cfg = instantiate(draft_team(task, llm, envelope, trace, prompts="d24"), topology, task, envelope)
    return llm, cfg


def test_flat_worker_prompt_carries_role_card_and_step_detail(task, envelope, trace, tools):
    llm, cfg = team(task, envelope, trace, "flat", worker=[fx("worker_final_output")])
    cost = next(a for a in cfg.agents.values() if a.name == "Cost Analyst")
    assert cost.goal == "a defensible monthly cost" and cost.skills == ["TCO modelling", "managed-database pricing"]
    assert cfg.plan[2].depends_on == [1, 2] and cfg.plan[0].done_when == "every cell sourced"
    ep = Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    first = llm.calls_of("worker")[0]["messages"][1]["content"]
    assert "Goal: a defensible monthly cost" in first
    assert "Skills: TCO modelling; managed-database pricing" in first
    assert "Outputs: cost table (markdown table: provider x db x monthly USD)" in first
    assert "Success criteria: every number has a source" in first
    assert "do: 1) search current pricing\n2) compute 10 TB storage and peak compute" in first
    assert "output: cost table (markdown)" in first and "done_when: every cell sourced" in first
    assert ep.answer == "396"


def test_boss_reviewers_role_description_carries_the_card(task, envelope, trace, tools):
    llm, cfg = team(task, envelope, trace, "boss_reviewers", solver=["396"],
                    critic=["Action: Agree\nAction Input: fine."])
    Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    critic_system = llm.calls_of("critic")[0]["messages"][0]["content"]
    assert "Goal: a defensible monthly cost" in critic_system or "Goal: a tested schema" in critic_system
    # the AgentVerse solver prepend has no ${role_description} slot (config.yaml:28-32), so the solver sees no card
    assert "Goal:" not in llm.calls_of("solver")[0]["messages"][0]["content"]


def test_d19_worker_prompt_is_unchanged(task, envelope, trace, tools):
    llm = mock(planner=[fx("draft_round_ok")], worker=[fx("worker_final_output")])
    cfg = instantiate(draft_team(task, llm, envelope, trace), "flat", task, envelope)
    Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    first = llm.calls_of("worker")[0]["messages"][1]["content"]
    assert "Goal:" not in first and "done_when:" not in first
    assert "# Task [Calculator]: Evaluate 17 * 23 + 5 with the calc tool." in first
