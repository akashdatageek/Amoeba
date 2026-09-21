"""T7 — run_flat."""
from amoeba.interp.runtime import SYNTHESIZE_HINT, Interpreter
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from tests.conftest import fx, mock


def run(task, envelope, trace, tools, llm):
    cfg = instantiate(draft_team(task, llm, envelope, trace), "flat", task, envelope)
    return cfg, Interpreter(llm, tools, trace).run(cfg, task, seed=0)


def test_answer_is_last_steps_final_output(task, envelope, trace, tools):
    llm = mock(planner=[fx("draft_round_ok")], worker=[fx("worker_calc"), fx("worker_final_output")])
    cfg, ep = run(task, envelope, trace, tools, llm)
    assert ep.answer == "396" and ep.error is None
    calls = [c["messages"][1]["content"] for c in llm.calls_of("worker")]
    assert len(calls) == 3   # step 1: calc turn + final turn; step 2: final
    # {context} is the STEP text and {previous} holds the task
    assert "# Task [Calculator]: Evaluate 17 * 23 + 5 with the calc tool." in calls[0]
    assert "# Execution Result of Previous Agents [Question/Task: Compute 17 * 23 + 5. Reply with just the number.]" in calls[0]
    # the tool ran and its result landed in the shared scratchpad for turn 2
    assert [s["gen_ai.tool.name"] for s in trace.spans("execute_tool")] == ["calc"]
    assert ">Calculator Substep:\nEvaluate 17 * 23 + 5.\n>Subresponse:\n396\n" in calls[1]
    # step 2 sees the task AND step 1's published message
    assert "Question/Task: Compute 17 * 23 + 5" in calls[2]
    assert "user: \n## Step\n[Calculator]: Evaluate" in calls[2] and ">>>> Final Output" in calls[2]
    assert "# Task [Writer]: State the final number" in calls[2]
    assert "# Tools ['Print', 'Final Output']" in calls[2] and "# Tools ['calc', 'Print', 'Final Output']" in calls[0]
    # trace + episode bookkeeping
    assert len(trace.spans("invoke_workflow")) == 1
    assert ep.n_llm_calls == 3 and ep.total_tokens == sum(
        s["gen_ai.usage.input_tokens"] + s["gen_ai.usage.output_tokens"] for s in trace.spans("chat")[3:])
    assert [m.name for m in ep.history] == ["Calculator", "Calculator", "Writer"]


def test_never_final_hits_max_turns(task, envelope, trace, tools):
    llm = mock(planner=[fx("draft_round_ok")], worker=[fx("worker_never_final")])
    cfg, ep = run(task, envelope, trace, tools, llm)
    assert ep.error == "max_turns"
    assert ep.answer.startswith("\n## Step\n[Writer]") and "## Action\nNote an intermediate observation." in ep.answer
    calls = [c["messages"][1]["content"] for c in llm.calls_of("worker")]
    assert len(calls) == 10   # 2 steps × 5 turns
    step1 = calls[:5]
    assert [SYNTHESIZE_HINT in c for c in step1] == [False, False, False, False, True]   # 5th iteration only
    assert step1[4].count(SYNTHESIZE_HINT) == 1
