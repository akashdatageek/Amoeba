"""T8 — run_boss_reviewers."""
from amoeba.interp.runtime import Interpreter
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from tests.conftest import fx, mock


def run(task, envelope, trace, tools, **script):
    llm = mock(planner=[fx("draft_three_roles")], solver=["396"], **script)
    cfg = instantiate(draft_team(task, llm, envelope, trace), "boss_reviewers", task, envelope)
    ep = Interpreter(llm, tools, trace).run(cfg, task)
    return llm, cfg, ep


def critic_calls(llm, role_description):
    return [c for c in llm.calls_of("critic") if role_description in c["messages"][0]["content"]]


def test_one_disagreement_then_agree(task, envelope, trace, tools):
    llm, cfg, ep = run(task, envelope, trace, tools, critic=[fx("critic_disagree"), fx("critic_agree")])
    assert len(llm.calls_of("solver")) == 2
    assert ep.answer == "396" and ep.error is None
    # critics see the plan as an assistant history message "[<solver name>]: ..."
    first_critic_msgs = llm.calls_of("critic")[0]["messages"]
    assert first_critic_msgs[1] == {"role": "assistant", "content": "[Writer]: 396"}
    assert first_critic_msgs[0]["content"].startswith("Now you are a mathematician who checks arithmetic")
    assert first_critic_msgs[-1]["content"].startswith("Now the group is asking your opinion")
    # round 2: everyone saw the one disagreement, then the revised plan
    round2 = llm.calls_of("critic")[2]["messages"]
    assert [m["content"] for m in round2[1:-1]] == [
        "[Writer]: 396", "[Mathematician]: The answer should show the intermediate product 391 before adding 5.",
        "[Writer]: 396"]
    solver2 = llm.calls_of("solver")[1]["messages"]
    assert [m["role"] for m in solver2] == ["system", "assistant", "assistant", "user"]
    assert "Write the code step by step." not in solver2[-1]["content"]


def test_all_agree_from_the_start(task, envelope, trace, tools):
    llm, _, ep = run(task, envelope, trace, tools, critic=[fx("critic_agree")])
    assert len(llm.calls_of("solver")) == 1 and len(llm.calls_of("critic")) == 2
    assert ep.answer == "396"


def test_always_disagree_caps_at_four_solver_calls(task, envelope, trace, tools):
    llm, _, _ = run(task, envelope, trace, tools, critic=[fx("critic_disagree")])
    assert len(llm.calls_of("solver")) == 4
    assert len(critic_calls(llm, "a mathematician")) == 3 and len(critic_calls(llm, "an auditor")) == 3
    # critic max_history = 3: the last critic call carries only the 3 most recent memory items
    last = llm.calls_of("critic")[-1]["messages"]
    assert len(last) == 5 and all(m["role"] == "assistant" for m in last[1:-1])


def test_unparseable_critic_counts_as_agree(task, envelope, trace, tools):
    llm, _, ep = run(task, envelope, trace, tools, critic=[fx("critic_unparseable")])
    assert len(llm.calls_of("solver")) == 1
    assert len(llm.calls_of("critic")) == 4   # 2 critics × 2 attempts
    assert ep.answer == "396"
