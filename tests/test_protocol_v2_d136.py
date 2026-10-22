"""D136 — the step protocol v2: no text sections in native mode, typed tool arguments checked by plain code, a typed
Final_Output that feeds the same readers as the text markers, the resolver's typed figures, and the fallback to legacy
without native tool calling. Offline (MockLLMClient answers a native call with its scripted action)."""
import json
import os
import subprocess
import sys

import pytest

import amoeba.interp.plan_runner as pr
from amoeba.config.prompts import PROMPT, render
from amoeba.interp.disputes import parse_resolution, settle
from amoeba.interp.plan_runner import (FINAL_OUTPUT, PlanOptions, blocked_marks, missing_data_marks,
                                       missing_input_marks, not_needed_marks, parse_verdict_block)
from amoeba.interp.runtime import UNAVAILABLE, Interpreter
from amoeba.interp.step_protocol import (HOW_TO_ACT_TEXT, PROVIDER_BLOCKED_NOTE_V2, TYPED, UNREADABLE_NOTE_V2,
                                         banned_words, bad_call_text, check_args, final_text, resolver_text,
                                         tool_schema, typed_input, typed_verdict, v2_text)
from amoeba.llm.client import ChatResponse
from amoeba.localtools.toolbox import TOOL_TEXT
from tests.test_fixes_d117 import BODY, good, reply
from tests.test_plan_runner import plan_team, step_no
from scripts.run_task import protocol_used

V2 = PlanOptions(native_tools="on", protocol="v2")
FILL = dict(task="T", today="Today is X.", card="Name: A", number=1, step="do it", inputs="(inputs)",
            completed="Nothing yet.", tools=str(["web_search", "calc", "Print", "Final Output"]), turns_left=3,
            unavailable=UNAVAILABLE.format(name="Bash"), name="A", deliverables="")
NOTES = [pr.VERIFY_NOTE, pr.VERIFY_TOOLS_NOTE, pr.VERIFY_COMPARE_NOTE, pr.LAST_TURN_NOTE, pr.MISSING_INPUT_NOTE,
         pr.CONTRACT_LINE.format(items="local:Bash (given to you)"), pr.REWORK_NOTE, pr.REVERIFY_NOTE, pr.RETRY_NOTE,
         pr.REVISION_NOTE, pr.REFINE_NOTE, pr.SELF_REVIEW_NOTE, pr.MADE_TOOL_NOTE, pr.WORKAROUND_NOTE,
         pr.FIX_INPUT_NOTE, pr.FIX_UPSTREAM_NOTE, pr.FRESH_NOTE, pr.RESEARCH_NOTE, pr.SOURCES_NOTE,
         pr.REASONING_REFUSED_NOTE, UNREADABLE_NOTE_V2, PROVIDER_BLOCKED_NOTE_V2, HOW_TO_ACT_TEXT,
         *(f"You may use local:{k} (local, sandboxed):\n{v[1]}" for k, v in TOOL_TEXT.items())]


def test_no_native_mode_prompt_mentions_the_text_protocol():
    for stem in ("plan_step_v2", "plan_resolve_v2", "plan_verify_own_v2"):
        text = render(getattr(PROMPT, stem), **FILL)
        assert banned_words(v2_text(text)) == [], stem             # the runner words the tool list for v2 too
        assert "# source: ours — DEVIATION D136" in open(f"amoeba/config/prompts/{stem}.txt").readline()
        assert banned_words(v2_text(text + "\n" + "\n".join(NOTES))) == [], stem
    summary = render(PROMPT.plan_summarise, **FILL).split("\n# Format\n")[0] + "\n\n" + HOW_TO_ACT_TEXT
    assert banned_words(v2_text(summary)) == []
    assert banned_words(render(PROMPT.plan_step, **FILL))                  # the legacy prompt is untouched
    assert banned_words(PROMPT.plan_step_system) == []


def test_a_v2_run_sends_clean_prompts_and_typed_tools(task, envelope, trace, tools):
    seen = []

    def script(messages, seed):
        seen.append(messages)
        return good(step_no(messages))
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script)
    ep = Interpreter(llm, tools, trace, plan_options=V2).run(cfg, task, seed=0)
    assert ep.error is None and seen
    for m in seen:
        assert banned_words(m[0]["content"] + "\n" + m[-1]["content"]) == []
    calls = [c for c in llm.calls if c.get("tools")]
    final = next(t["function"] for t in calls[0]["tools"] if t["function"]["name"] == "Final_Output")
    assert set(final["parameters"]["properties"]) >= {"status", "output", "blocked", "missing_data", "verdict"}
    assert not trace.events("protocol_fallback")


def test_typed_arguments_good_and_bad():
    s = tool_schema("web_search")
    assert s["required"] == ["query"] and check_args("web_search", {"query": "diesel"}, s) is None
    assert typed_input("web_search", {"query": "diesel"}, s) == "diesel"
    w = tool_schema("local:Write")
    assert json.loads(typed_input("local:Write", {"path": "a.md", "content": "x"}, w)) == {"file_path": "a.md",
                                                                                         "content": "x"}
    assert check_args("local:Write", {"path": "a.md", "content": ""}, w) is None      # an empty file is allowed
    assert check_args("web_search", {}, s) == "no query"
    assert check_args("web_search", {"query": "x", "q": "y"}, s).startswith("unknown argument")
    assert check_args("calc", {"expr": 5}, tool_schema("calc")).startswith("the wrong type")
    assert check_args("calc", "2+2", tool_schema("calc")).startswith("arguments that are not")
    text = bad_call_text("web_search", "no query", s)
    assert "it was not run" in text and "query (string, required)" in text and json.dumps(TYPED["web_search"][1]) in text
    assert set(TYPED) >= {"web_search", "fetch_url", "calc", "local:Bash", "local:Read", "local:Write", "find_tool"}
    mcp = {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}
    assert tool_schema("pool:weather", mcp) is mcp and tool_schema("pool:other")["required"] == ["input"]


def test_a_bad_call_is_not_run_and_the_helper_sees_the_schema(task, envelope, trace, tools):
    turns = {}

    def script(messages, seed):
        n = step_no(messages)
        turns[n] = turns.get(n, 0) + 1
        if n == "1" and turns[n] == 1:
            return ChatResponse("", tool_calls=[{"name": "calc", "input": json.dumps({"expression": "17*23+5"})}],
                                finish_reason="tool_calls")                   # wrong argument name
        if n == "1" and turns[n] == 2:
            assert "error: calc was called with no expr; it was not run" in messages[-1]["content"]
            return reply("calc", '{"expr": "17*23+5"}')                       # the corrected call runs
        return good(n)

    def give_calc(cfg):
        for a in cfg.agents.values():
            a.tools = list(dict.fromkeys([*a.tools, "calc"]))
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script)
    give_calc(cfg)
    Interpreter(llm, tools, trace, plan_options=V2).run(cfg, task, seed=0)
    rejected = trace.events("tool_args_rejected")
    assert rejected and rejected[0]["gen_ai.tool.name"] == "calc"
    ran = [s for s in trace.spans("execute_tool") if s.get("gen_ai.tool.name") == "calc"]
    assert len(ran) == 1                                                      # only the good call ran


TYPED_FINAL = {"status": "partial", "output": "Built the table [S1].",
               "blocked": ["chart tool — no chart made"], "missing_data": ["Indiana series — EIA area list"],
               "missing_input": ["the ATRI figure — step 4"], "not_needed": ["calc — no arithmetic"],
               "verdict": "FAIL", "issues": ["step 2: the sum is wrong, recompute it"]}
MARKERS = ("Verdict: FAIL\nBuilt the table [S1].\nBLOCKED: chart tool — no chart made\nNOT NEEDED: calc — no "
           "arithmetic\nMISSING DATA: Indiana series — EIA area list\nMISSING INPUT: the ATRI figure — step 4\n"
           "Issues:\n1. step 2: the sum is wrong, recompute it")


def test_typed_final_output_feeds_the_same_readers_as_the_markers():
    text = final_text(TYPED_FINAL)
    for read in (blocked_marks, missing_data_marks, missing_input_marks, not_needed_marks, parse_verdict_block):
        assert read(text) == read(MARKERS), read.__name__
    assert blocked_marks(text) == ["chart tool"] and missing_data_marks(text) == ["Indiana series — EIA area list"]
    assert typed_verdict(TYPED_FINAL) == parse_verdict_block(MARKERS)
    assert check_args(FINAL_OUTPUT, {"status": "maybe", "output": "x"}, {}).startswith("fields that do not fit")
    assert final_text({"status": "done", "output": "OUT"}) == "OUT"


def test_a_typed_final_output_reaches_the_step_meta_as_markers_do(task, envelope, trace, tools):
    def run(opts, out):
        def script(messages, seed):
            n = step_no(messages)
            return reply("Final Output", out) if n == "2" else good(n)
        llm, cfg = plan_team(task, envelope, trace, plan_worker=script)
        ep = Interpreter(llm, tools, trace, plan_options=opts).run(cfg, task, seed=0)
        return next(m for m in ep.steps if m["step"] == 2)
    typed = {**TYPED_FINAL, "output": f"OUT-2\n{BODY}", "verdict": None, "issues": []}
    legacy = run(PlanOptions(), final_text(typed))
    v2 = run(V2, json.dumps(typed))
    for k in ("missing_inputs", "missing_data", "status", "blocked"):
        assert v2.get(k) == legacy.get(k), k
    assert v2["missing_data"] == ["Indiana series — EIA area list"] and trace.events("final_output_typed")


def test_the_resolver_typed_output_settles_like_its_text():
    figures = {"figures": [{"n": 1, "value": "3.85 USD/gal", "evidence": '"price 3.85" [S1]', "verdict": "CHECK"},
                           {"n": 2, "value": "?", "evidence": "none", "verdict": "UNRESOLVED"}]}
    text = resolver_text(figures)
    legacy = ("## Figure 1\nValue: 3.85 USD/gal\nEvidence: \"price 3.85\" [S1]\nVerdict: CHECK\n\n"
              "## Figure 2\nValue: ?\nEvidence: none\nVerdict: UNRESOLVED")
    assert parse_resolution(text) == parse_resolution(legacy)
    disputes = [{"label": "price", "worker": "3.95", "verifier": "3.85", "step": 1, "worker_line": "x",
                 "verifier_line": "y"}, {"label": "b", "worker": "1", "verifier": "2", "step": 1,
                                         "worker_line": "", "verifier_line": ""}]
    assert settle(text, disputes, {"S1": "the price 3.85 a gallon"}, []) == \
        settle(legacy, disputes, {"S1": "the price 3.85 a gallon"}, [])
    schema = tool_schema(FINAL_OUTPUT, final_kind="resolve")
    assert schema["properties"]["figures"]["items"]["required"] == ["n", "value", "evidence", "verdict"]
    assert check_args(FINAL_OUTPUT, figures, schema, "resolve") is None


def test_v2_without_native_tools_falls_back_to_legacy(task, envelope, trace, tools):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=lambda m, s: good(step_no(m)))
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions(protocol="v2")).run(cfg, task, seed=0)
    assert ep.error is None
    ev = trace.events("protocol_fallback")
    assert ev and ev[0]["amoeba.used"] == "legacy"
    assert any("## ActionInput" in c["messages"][-1]["content"] for c in llm.calls_of("plan_worker"))
    assert protocol_used(PlanOptions(protocol="v2")) == {"asked": "v2", "used": "legacy",
                                                         "why": "no native tool calling on this run's models"}
    assert protocol_used(V2)["used"] == "v2" and protocol_used(PlanOptions()) is None


BOX4 = ["tests/test_diagnosis_d128.py", "tests/test_failed_step_d133.py", "tests/test_fixes_d117.py",
        "tests/test_ladder_d129.py", "tests/test_proposer_d117.py", "tests/test_stage_e_d117.py",
        "tests/test_stuck_d117.py", "tests/test_toolmaker_d125.py", "tests/test_workaround_d124.py"]


@pytest.mark.skipif(os.environ.get("AMOEBA_TEST_PROTOCOL") == "v2", reason="already the v2 pass")
def test_the_box4_tests_pass_in_v2_mode_too():
    """Box 4 needs no change: its tests run again with every PlanOptions in native mode and protocol v2."""
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *BOX4],
                         env={**os.environ, "AMOEBA_TEST_PROTOCOL": "v2"}, capture_output=True, text=True,
                         timeout=600)
    assert out.returncode == 0, out.stdout[-3000:]
