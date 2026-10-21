"""D144 — context handling in steps: long tool results go to a file, local:Write inputs are summarised, turns older
than the last two are one line each, Print is not added twice, and the characters sent and saved are counted.
Offline."""
import json
import re
from pathlib import Path

from amoeba.interp.plan_runner import KEEP_TURNS, PlanOptions, _Work, one_line, write_summary
from amoeba.interp.runtime import Interpreter
from tests.test_fixes_d117 import good, reply
from tests.test_plan_runner import plan_team, step_no

LONG = "x" * 1000 + "MIDDLE" + "y" * 2000 + "END"


def test_one_line_and_write_summary():
    line = one_line("Analyst", "web_search", "diesel price " * 30, "result " * 50, True)
    assert line.startswith(">Analyst (web_search): diesel price") and "-> ok: result" in line and "\n" == line[-1]
    assert len(line) < 360
    s = write_summary(json.dumps({"file_path": "memo.md", "content": "A" * 1000}))
    assert s.startswith("write memo.md (1000 characters): " + "A" * 300) and "700 more characters" in s
    assert write_summary("not json") == "not json"


def test_compaction_keeps_the_last_two_turns_in_full():
    w = _Work(8)
    for t in range(5):
        w.turn = t
        w.add(f"FULL-{t} " + "z" * 200 + "\n", f"LINE-{t}\n")
    w.turn = 5
    view = w.view()
    assert "LINE-0" in view and "LINE-2" in view and "FULL-2" not in view
    assert "FULL-3" in view and "FULL-4" in view and KEEP_TURNS == 2
    assert w.chars_saved == len(w.completed) - len(view) > 0 and w.chars_sent == len(view)
    w.add("NOTE\n")                                   # a note plain code adds is never shortened
    w.turn = 9
    assert "NOTE" in w.view()


def run(task, envelope, trace, tools, tmp_path, script):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script)
    for a in cfg.agents.values():
        a.tools = list(a.tools) + ["echo"]
        a.limits.max_turns = 8
    ep = Interpreter(llm, tools, trace, run_dir=str(tmp_path)).run(cfg, task, seed=0)
    return llm, {m["step"]: m for m in ep.steps}


def test_a_long_result_goes_to_a_file_and_old_turns_shrink(task, envelope, trace, tools, tmp_path):
    seen = {}

    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        k = user.count(">") if n == "1" else 99
        calls = user.count("(echo)")
        seen.setdefault(n, []).append(user)
        if n == "1" and calls < 4:
            return reply("echo", LONG if calls == 0 else f"call {calls}")
        if n == "1" and "PRINTED-ONCE" not in user:
            return reply("Print", "PRINTED-ONCE")
        return good(n)
    llm, metas = run(task, envelope, trace, tools, tmp_path, script)
    second = seen["1"][1]
    result = second.split("(echo):", 1)[1].split(">Result:\n", 1)[1]                # echo's input is the long text itself; its result is cut
    assert "MIDDLE" not in result and "characters cut" in result and "tool_results/step1_1.txt" in result
    assert result.count("x" * 800) == 1 and LONG[-400:] in result
    saved = Path(tmp_path, "tool_results", "step1_1.txt")
    assert saved.read_text() == LONG
    fifth = seen["1"][4]                                  # turns 1-2 are one line each by now
    assert re.search(r">\w[^\n]* \(echo\): x{50,120} -> ok", fifth) and "characters cut" not in fifth
    last = seen["1"][-1]
    assert last.count("PRINTED-ONCE") == 1                # Print's echo is not added a second time
    ctx = metas[1]["context"]
    assert ctx["chars_saved"] > 0 and ctx["chars_sent"] > 0
    assert trace.events("tool_result_spilled")[0]["amoeba.chars"] == len(LONG)
