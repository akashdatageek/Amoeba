"""D62 — equal tool access for the baselines (--equal-tools on): the D32 web grant for flat and boss_reviewers, and
tool calls for boss_reviewers' solver and critics. Offline, with the mock LLM."""
from amoeba.interp.runtime import Interpreter, grant_web
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from amoeba.tools.web import WEB_TOOLS
from tests.conftest import fx, mock


def boss(task, envelope, trace, tools, equal, **script):
    llm = mock(planner=[fx("draft_three_roles")], **script)
    cfg = instantiate(draft_team(task, llm, envelope, trace), "boss_reviewers", task, envelope)
    critic = next(a for a in cfg.agents.values() if a.role == "critic")
    critic.tools = ["calc"]                                   # a tool the team was given, held by a critic
    ep = Interpreter(llm, tools, trace, equal_tools=equal).run(cfg, task)
    return llm, cfg, ep


def test_the_solver_can_call_a_team_tool_and_then_answers(task, envelope, trace, tools):
    llm, cfg, ep = boss(task, envelope, trace, tools, True,
                        solver=["Action: calc\nActionInput: 17 * 23 + 5", "The answer is 396."],
                        critic=[fx("critic_agree")])
    solver = next(a for a in cfg.agents.values() if a.role == "solver")
    assert "calc" in solver.tools                            # the solver holds every tool the team was given
    calls = llm.calls_of("solver")
    tools_line = next(l for l in calls[0]["messages"][0]["content"].splitlines() if l.startswith("Tools you may use"))
    assert "calc" in tools_line
    assert calls[1]["messages"][-1] == {"role": "user", "content": "Result of calc:\n396"}
    assert ep.answer == "The answer is 396."
    assert [s["gen_ai.tool.name"] for s in trace.spans("execute_tool")] == ["calc"]


def test_without_the_flag_nothing_changes(task, envelope, trace, tools):
    llm, cfg, ep = boss(task, envelope, trace, tools, False, solver=["Action: calc\nActionInput: 1+1"],
                        critic=[fx("critic_agree")])
    assert ep.answer == "Action: calc\nActionInput: 1+1"      # plain text, as AgentVerse would pass it on
    assert trace.spans("execute_tool") == [] and "Tools you may use" not in \
        llm.calls_of("solver")[0]["messages"][0]["content"]
    assert "calc" not in next(a for a in cfg.agents.values() if a.role == "solver").tools


def test_an_unknown_tool_name_is_just_the_answer(task, envelope, trace, tools):
    _, _, ep = boss(task, envelope, trace, tools, True, solver=["Action: route_engine\nActionInput: Chicago"],
                    critic=[fx("critic_agree")])
    assert ep.answer.startswith("Action: route_engine") and trace.spans("execute_tool") == []


def test_tool_calls_are_capped_then_the_answer_is_asked_for(task, envelope, trace, tools):
    llm, _, ep = boss(task, envelope, trace, tools, True, solver=["Action: calc\nActionInput: 1+1"],
                      critic=[fx("critic_agree")])
    assert len(trace.spans("execute_tool")) == 5              # limits.max_turns
    assert llm.calls_of("solver")[-1]["messages"][-1]["content"].startswith("No more tool calls are allowed")


def test_the_web_grant_follows_the_d32_rule(task, envelope, trace):
    llm = mock(planner=[fx("draft_three_roles")])
    cfg = instantiate(draft_team(task, llm, envelope, trace), "flat", task, envelope)
    a, b = list(cfg.agents.values())[:2]
    cfg.meta["capability_requests"] = [{"name": "web search", "for_role": a.name}]
    grant_web(cfg, trace)
    assert set(WEB_TOOLS) <= set(a.tools) and not set(WEB_TOOLS) & set(b.tools)
    [ev] = trace.events("capability_mapped")
    assert ev["amoeba.equal_tools"] is True and ev["gen_ai.agent.name"] == a.name


def test_baseline_replies_get_the_plan_runners_room(task, envelope, trace, tools):
    llm, _, _ = boss(task, envelope, trace, tools, True, solver=["396"], critic=[fx("critic_agree")])
    assert {c["max_tokens"] for c in llm.calls if c["kind"] in ("solver", "critic")} == {8192}
    llm, _, _ = boss(task, envelope, trace, tools, False, solver=["396"], critic=[fx("critic_agree")])
    assert {c["max_tokens"] for c in llm.calls if c["kind"] in ("solver", "critic")} != {8192}
