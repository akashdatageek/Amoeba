"""D70 — baseline harness fixes (our port, not their design): AutoAgents' Write File blocks reach our Write tool;
reply readers never cut an answer at a sub-heading, drop thinking tags wherever they stand (malformed ones too), and
a reply that is only a tool request is not a final answer; equal tool access and reply room hold for all three."""
import json

from amoeba.interp.runtime import EQUAL_MAX_TOKENS, Interpreter, file_block_write, strip_thought
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from tests.conftest import fx, mock

CODE = "import openpyxl\nwb = openpyxl.Workbook()\nwb.save('fuel.xlsx')\n"


def test_a_write_file_block_becomes_a_write_call():
    act, inp = file_block_write("local:Write", f">>>generate_excel.py\n{CODE}>>>END", ["local:Write"])
    assert act == "local:Write" and json.loads(inp) == {"file_path": "generate_excel.py", "content": CODE}
    _, fenced = file_block_write("local:Write", f"```python\n>>>generate_excel.py\n{CODE}```", ["local:Write"])
    assert json.loads(fenced)["content"] == CODE                              # no END, in a fence
    assert file_block_write("Write File", ">>>a.txt\nhi\n>>>END", ["local:Write"])[0] == "local:Write"
    assert file_block_write("local:Write", '{"file_path": "a.txt", "content": "hi"}', ["local:Write"]) is None
    assert file_block_write("local:Write", ">>>a.txt\nhi", []) is None       # only for a helper that holds Write


def test_thinking_is_dropped_wherever_it_stands():
    assert strip_thought("<thought>plan</thought>Action: calc\nActionInput: 1+1") == "Action: calc\nActionInput: 1+1"
    assert strip_thought("<thought\nthe plan\n</thought>Action: calc\nActionInput: 1") == "Action: calc\nActionInput: 1"
    assert strip_thought("I will think.</thought>\nThe answer is 4.") == "The answer is 4."
    assert strip_thought("Intro <think>hm</think> then the answer.") == "Intro then the answer."
    assert strip_thought("No tags here.") == "No tags here."


def flat_team(task, envelope, trace, worker):
    llm = mock(planner=[fx("draft_three_roles")], worker=worker)
    cfg = instantiate(draft_team(task, llm, envelope, trace), "flat", task, envelope)
    return llm, cfg


def test_the_flat_answer_is_not_cut_at_its_first_sub_heading(task, envelope, trace, tools):
    memo = ("**MEMORANDUM**\nFollowing the analysis, please find the data below.\n\n### 1. Cited Source\n"
            "Price: $6.529 per gallon [EIA, 09/21/26]\n\n### 2. Summary Table\n| Leg | Gallons |\n|---|---|\n| A | 28.46 |")
    reply = f"## Thought\n<thought>ok</thought>\n\n## CurrentStep\nfinal\n\n## Action\nFinal Output\n\n## ActionInput\n{memo}\n---"
    llm, cfg = flat_team(task, envelope, trace, [reply])
    ep = Interpreter(llm, tools, trace).run(cfg, task)
    assert ep.answer == memo                                  # before D70: "**MEMORANDUM** ... please find the data below."


def test_a_flat_write_file_block_saves_the_file(task, envelope, trace, tools):
    got = []
    tools.register("local:Write", "local tool Write", lambda text: got.append(json.loads(text)) or "[local:Write] ok")
    block = f"## Thought\nt\n\n## CurrentStep\nsave\n\n## Action\nlocal:Write\n\n## ActionInput\n>>>generate_excel.py\n{CODE}>>>END"
    done = "## Thought\nt\n\n## CurrentStep\ndone\n\n## Action\nFinal Output\n\n## ActionInput\nsaved generate_excel.py"
    llm, cfg = flat_team(task, envelope, trace, [block, done])
    first = cfg.agents[cfg.plan[0].agent_ids[0]]
    first.tools.append("local:Write")
    Interpreter(llm, tools, trace).run(cfg, task)
    assert got[0] == {"file_path": "generate_excel.py", "content": CODE}
    [ev] = trace.events("file_block_adapted")
    assert ev["amoeba.file"] == "generate_excel.py"


def test_a_solver_that_ends_on_a_tool_request_has_no_answer(task, envelope, trace, tools):
    llm = mock(planner=[fx("draft_three_roles")], solver=["<thought\nlet me write\n</thought>Action: route_engine\nActionInput: x"],
               critic=[fx("critic_agree")])
    cfg = instantiate(draft_team(task, llm, envelope, trace), "boss_reviewers", task, envelope)
    next(a for a in cfg.agents.values() if a.role == "critic").tools = ["calc"]
    ep = Interpreter(llm, tools, trace, equal_tools=True).run(cfg, task)
    assert ep.error == "no_answer" and ep.answer.startswith("Action: route_engine")     # the thought is gone
    assert trace.events("not_an_answer")
    assert llm.calls_of("solver")[-1]["messages"][-1]["content"].startswith("No more tool calls are allowed")


def test_equal_reply_room_for_all_three_runners(task, envelope, trace, tools):
    reply = "## Thought\nt\n\n## CurrentStep\nc\n\n## Action\nFinal Output\n\n## ActionInput\n396"
    for topology in ("flat", "boss_reviewers"):
        llm = mock(planner=[fx("draft_three_roles")], worker=[reply], solver=["396"], critic=[fx("critic_agree")])
        cfg = instantiate(draft_team(task, llm, envelope, trace), topology, task, envelope)
        Interpreter(llm, tools, trace, equal_tools=True).run(cfg, task)
        helpers = [c for c in llm.calls if c["kind"] in ("worker", "solver", "critic")]
        assert helpers and all(c["max_tokens"] == EQUAL_MAX_TOKENS for c in helpers), topology
