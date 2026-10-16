"""D141 — protocol v2 for every call: typed reply models (no thought field), `ask()` in the three output modes with
one repair call, clean v2 prompts, and each call site rendering its typed reply into the text its legacy reader
parses. Offline (MockLLMClient)."""
import json
import re
from pathlib import Path

import pytest

from amoeba.config.prompts import PROMPT
from amoeba.interp.step_protocol import banned_words, compact_step_prompt
from amoeba.interp.trace import TracedLLM, TraceWriter
from amoeba.llm.ask import Unreadable, ask, output_mode_of, protocol_of
from amoeba.llm.client import ChatResponse, MockLLMClient
from amoeba.task import schemas as S
from amoeba.task.models import Task

PROMPTS = Path("amoeba/config/prompts")
V2_FILES = sorted(PROMPTS.glob("*_v2.txt"))
REASONING_ASKS = [r"(?i)show your reasoning", r"(?i)think step by step", r"(?i)explain your reasoning",
                  r"(?i)chain[- ]of[- ]thought"]


def v2_trace() -> TraceWriter:
    t = TraceWriter(None, episode_id="ep-v2")
    t.protocol = "v2"
    return t


def traced(script: dict, mode: str = "schema") -> TracedLLM:
    m = MockLLMClient(script=script)
    m.output_mode = mode
    return TracedLLM(m, v2_trace())


# ---- prompts and schemas ---------------------------------------------------------------------------------------
def test_every_v2_prompt_is_ours_and_free_of_the_text_protocol():
    assert len(V2_FILES) >= 12
    for f in V2_FILES:
        text = f.read_text(encoding="utf-8")
        head = text.split("\n", 1)[0]
        assert head.startswith("# source: ours — DEVIATION D1"), f.name
        body = text.split("\n", 1)[1]
        assert banned_words(body) == [], (f.name, banned_words(body))
        for pat in REASONING_ASKS:
            assert not re.search(pat, body), (f.name, pat)


def test_legacy_prompts_are_untouched():
    for stem in ("interpret", "plan_replan", "plan_critique", "pool_pick", "tool_writer"):
        first = (PROMPTS / f"{stem}.txt").read_text(encoding="utf-8").split("\n", 1)[0]
        assert "ours — DEVIATION D141" not in first, stem


def _fields(model, seen=None) -> set[str]:
    seen = seen or set()
    out = set()
    for name, f in model.model_fields.items():
        out.add(name)
        ann = f.annotation
        for sub in getattr(ann, "__args__", ()) + (ann,):
            if isinstance(sub, type) and hasattr(sub, "model_fields") and sub not in seen:
                seen.add(sub)
                out |= _fields(sub, seen)
    return out


def test_no_reply_model_has_a_thought_or_reasoning_field():
    for kind, model in S.SCHEMAS.items():
        names = _fields(model)
        assert not names & {"thought", "thoughts", "reasoning", "chain_of_thought", "thinking"}, kind


def test_rationale_is_at_most_two_sentences():
    out = S.FamilyOut(family="x", why="y", rationale="One. Two. Three. Four.")
    assert out.rationale == "One. Two."


# ---- ask() --------------------------------------------------------------------------------------------------------
FAM = {"family": "calc", "why": "numbers"}


def test_ask_schema_mode_returns_the_typed_reply_and_logs_the_rationale():
    llm = traced({"family_classifier": [dict(FAM, rationale="Has numbers.")]})
    out = ask(llm, "family", [{"role": "user", "content": "You sort a task into one of a fixed list of task families"}],
              S.FamilyOut)
    assert out.family == "calc"
    assert llm.llm.calls[0]["schema"] is S.FamilyOut
    ev = [r for r in llm.trace.records if r.get("name") in ("ask", "ask_rationale")]
    assert [r["name"] for r in ev] == ["ask", "ask_rationale"]


def test_ask_submit_tool_mode_reads_the_tool_call():
    resp = ChatResponse(content="", tool_calls=[{"name": "submit_family", "input": json.dumps(FAM)}])
    llm = traced({"family_classifier": [resp]}, mode="submit_tool")
    out = ask(llm, "family", [{"role": "user", "content": "You sort a task into one of a fixed list of task families"}],
              S.FamilyOut)
    call = llm.llm.calls[0]
    assert out.family == "calc" and call["tools"][0]["function"]["name"] == "submit_family"
    assert "call the tool submit_family" in call["messages"][-1]["content"]


def test_ask_json_prompt_mode_shows_the_schema_and_validates():
    llm = traced({"family_classifier": ["```json\n" + json.dumps(FAM) + "\n```"]}, mode="json_prompt")
    out = ask(llm, "family", [{"role": "user", "content": "You sort a task into one of a fixed list of task families"}],
              S.FamilyOut)
    assert out.family == "calc"
    assert '"family"' in llm.llm.calls[0]["messages"][-1]["content"] and llm.llm.calls[0]["schema"] is None


def test_ask_makes_one_repair_call_quoting_the_error_then_raises():
    llm = traced({"family_classifier": [{"family": "calc"}, {"nope": 1}]}, mode="json_prompt")
    with pytest.raises(Unreadable) as e:
        ask(llm, "family", [{"role": "user", "content": "You sort a task into one of a fixed list of task families"}],
            S.FamilyOut)
    calls = llm.llm.calls
    assert len(calls) == 2 and "did not validate" in calls[1]["messages"][-1]["content"]
    assert "why" in calls[1]["messages"][-1]["content"]                 # the exact field pydantic named
    assert "after one repair call" in e.value.why
    assert any(r.get("name") == "ask_unreadable" for r in llm.trace.records)


def test_ask_repair_succeeds_on_the_second_reply():
    llm = traced({"family_classifier": ["not json", FAM]}, mode="json_prompt")
    assert ask(llm, "family", [{"role": "user", "content": "You sort a task into one of a fixed list of task "
                                                           "families"}], S.FamilyOut).family == "calc"


def test_ask_raises_at_once_on_a_blocked_reply():
    blocked = ChatResponse(content="", finish_reason="refusal", refusal_category="cyber")
    llm = traced({"family_classifier": [blocked]})
    with pytest.raises(Unreadable) as e:
        ask(llm, "family", [{"role": "user", "content": "You sort a task into one of a fixed list of task families"}],
            S.FamilyOut)
    assert e.value.blocked and len(llm.llm.calls) == 1


def test_a_free_form_schema_falls_back_to_json_prompt():
    llm = traced({"fix_proposer": [json.dumps({"edit": {"op": "replan_remaining", "params": {"plan": "p"}}, "reason": "x"})]})
    ask(llm, "fix", [{"role": "user", "content": "You propose one fix for a stuck step of a team plan"}], S.FixOut)
    ev = next(r for r in llm.trace.records if r.get("name") == "ask")
    assert ev["amoeba.mode"] == "json_prompt"


def test_output_mode_and_protocol_defaults():
    assert output_mode_of(TracedLLM(MockLLMClient(), TraceWriter(None))) == "schema"
    assert protocol_of(TraceWriter(None)) == "legacy" and protocol_of(v2_trace()) == "v2"


# ---- to_legacy feeds the same readers ------------------------------------------------------------------------------
def test_read_task_v2_renders_entities_for_the_same_decider():
    from amoeba.task.interpret import read_task
    reply = {"entities": [{"entity": "Paris", "readings": [
        {"reading": "Paris, France", "why": "most common", "confidence": 0.9},
        {"reading": "Paris, Texas", "why": "a US town", "confidence": 0.1}]}]}
    llm = traced({"interpreter": [reply]})
    out = read_task("Weather in Paris tomorrow", llm)
    assert out["entities"][0]["entity"] == "Paris" and out["working"]
    assert "You read a task before any planning" in llm.llm.calls[0]["messages"][0]["content"]
    assert llm.llm.calls[0]["schema"] is S.ReadingOut


def test_read_task_v2_unreadable_settles_nothing():
    from amoeba.task.interpret import read_task
    llm = traced({"interpreter": ["x", "y"]}, mode="json_prompt")
    assert read_task("Weather in Paris", llm)["entities"] == []


def test_family_v2(monkeypatch):
    from amoeba.task.interpret import classify_family
    llm = traced({"family_classifier": [{"family": "research", "why": "sources"}]})
    fams = {"research": {"description": "find facts", "keywords": ["zzzz-never"]}}
    out = classify_family("Tell me something", llm, families=fams)
    assert out["family"] == "research" and llm.llm.calls[0]["schema"] is S.FamilyOut


def test_pool_pick_v2():
    from amoeba.pool.stock import pick

    class Q:
        kind, canonical, name, what_it_does, input, output = "tool", "geo", "geo", "geocode", "a place", "lat/lon"
    llm = traced({"pool_picker": [{"choice": "mcp:geo"}]})
    cands = [{"id": "mcp:geo", "name": "geo", "kind": "tool", "description": "geocoder"}]
    assert pick(llm, Q, "Analyst", "", cands) == "mcp:geo"
    assert llm.llm.calls[0]["schema"] is S.PoolPickOut
    llm = traced({"pool_picker": [{"choice": "made-up"}]})
    assert pick(llm, Q, "Analyst", "", cands) is None                  # still checked against the list by code


def test_critique_and_replan_render_the_legacy_sections():
    from amoeba.interp.plan_runner import parse_verdict_block
    c = S.to_legacy("critique", S.CritiqueOut(verdict="REVISE", issues=["the total is wrong"]))
    assert "## Verdict\nREVISE" in c and "1. the total is wrong" in c
    r = S.to_legacy("replan", S.ReplanOut(decision="DROP_STEP", reason="moot", steps="step: 3", unmet="R2: gone",
                                         capability_requests=[]))
    assert "## Decision\nDROP_STEP" in r and "## Steps\nstep: 3" in r and "## Unmet\nR2: gone" in r
    assert parse_verdict_block is not None


def test_tool_writer_renders_head_and_code():
    t = S.to_legacy("tool_writer", S.ToolWriterOut(name="add", description="adds", input="a, b",
                                                   code="def run(args):\n    return 1\n"))
    head, code = t.split("\n```python\n")
    assert json.loads(head)["name"] == "add" and code.startswith("def run(args)")


def test_review_text_can_keep_only_blocking_issues():
    out = S.ReviewOut(verdict="REVISE", issues=[
        S.IssueOut(severity="blocking", step=2, problem="no source", fix="add one"),
        S.IssueOut(severity="minor", problem="wording", fix="shorter")])
    assert "wording" in S.review_text(out) and "wording" not in S.review_text(out, only_blocking=True)
    assert S.review_text(out).endswith("## Verdict\nREVISE")


def _plan() -> dict:
    role = {"name": "Analyst", "seniority": "senior", "description": "does math", "goal": "answer", "responsibilities":
            ["compute"], "skills": ["math"], "tools": ["calc"], "inputs": ["task"], "outputs":
            [{"artifact": "number", "format": "text"}], "success_criteria": ["correct"], "constraints": [],
            "covers": ["R1"], "is_summariser": False, "prompt": "You are an analyst."}
    writer = dict(role, name="Writer", is_summariser=True, prompt="You write the answer.")
    return {"requirements": [{"id": "R1", "text": "the number"}], "givens": ["17, 23, 5"], "open_questions": [],
            "roles": [role, writer], "capability_requests": [], "risks": ["none"],
            "plan": [{"number": 1, "roles": ["Analyst"], "title": "Compute", "kind": "work", "covers": ["R1"],
                      "depends_on": [], "do": "use calc", "output": "memo: the number", "done_when": "R1 answered"},
                     {"number": 2, "roles": ["Writer"], "title": "Write", "kind": "work", "covers": ["R1"],
                      "depends_on": [1], "do": "write it", "output": "memo: answer", "done_when": "R1 stated"}]}


def test_draft_team_v2_runs_on_typed_replies(envelope):
    from amoeba.task.draft import draft_team
    trace = v2_trace()
    approve = {"verdict": "APPROVE", "issues": []}
    llm = MockLLMClient(script={"planner": [_plan()], "agent_observer": [approve], "plan_observer": [approve]})
    task = Task(id="t", prompt="Compute 17 * 23 + 5.", family="arith")
    d = draft_team(task, llm, envelope, trace, planning_tier="full")
    assert [r.name for r in d.created_roles] == ["Analyst", "Writer"] and len(d.plan) == 2
    assert d.plan[0].covers == ["R1"]
    assert {c["schema"] for c in llm.calls} == {None, S.ReviewOut}       # PlanOut goes as json_prompt (D142 params)
    assert '"plan"' in llm.calls_of("planner")[0]["messages"][-1]["content"]
    for c in llm.calls:
        assert banned_words(c["messages"][-1]["content"]) == []


def test_draft_team_v2_unreadable_review_is_revise(envelope):
    from amoeba.task.draft import draft_team
    llm = MockLLMClient(script={"planner": [_plan()], "agent_observer": ["?"],
                                "plan_observer": [{"verdict": "APPROVE", "issues": []}]})
    d = draft_team(Task(id="t", prompt="Compute 17 * 23 + 5.", family="arith"), llm, envelope, v2_trace(),
                   max_rounds=1, planning_tier="full")
    assert d.rounds[0].agent_verdict == "REVISE"


def test_legacy_draft_is_unchanged(envelope):
    from amoeba.task.draft import draft_team
    llm = MockLLMClient(script={"planner": [_plan()]})
    with pytest.raises(Exception):                        # a JSON reply is no d19 section text
        draft_team(Task(id="t", prompt="x", family="arith"), llm, envelope, TraceWriter(None))
    assert llm.calls[0]["schema"] is None


# ---- compact variant -----------------------------------------------------------------------------------------------
def test_compact_step_prompt_keeps_the_work_and_trims_the_card():
    user = ("# Your role card\nName: A\nGoal: g\nBackground: long story\nOutputs: o\n\n# Task\nT\n\n"
            "# Step\ndo it\n")
    c = compact_step_prompt(user)
    assert "Background" not in c and "Name: A" in c and "Goal: g" in c and "# Task\nT" in c and "do it" in c
    assert len(c) < len(user)


def test_a_blocked_step_turn_is_retried_once_as_the_compact_variant():
    blocked = ChatResponse(content="", finish_reason="refusal", refusal_category="cyber")
    ok = ChatResponse(content="fine")
    m = MockLLMClient(responses=[blocked, ok])
    tl = TracedLLM(m, v2_trace())
    full = [{"role": "user", "content": "# Your role card\nName: A\nBackground: x\n\n# Task\nT"}]
    r = tl.chat_messages(full, compact=[{"role": "user", "content": compact_step_prompt(full[0]["content"])}])
    assert r.content == "fine" and len(m.calls) == 2
    assert "Background" not in m.calls[1]["messages"][0]["content"]
    assert any(x.get("name") == "compact_retry" for x in tl.trace.records)


def test_a_schema_the_provider_will_not_compile_goes_as_json_prompt(monkeypatch):
    import amoeba.llm.ask as A
    monkeypatch.setattr(A, "REJECTED", set())

    class Strict(MockLLMClient):
        def chat_messages(self, messages, seed=0, max_tokens=None, tools=None, schema=None, **kw):
            if schema is not None:
                raise RuntimeError("Error code: 400 - The compiled grammar is too large, which would cause "
                                   "performance issues.")
            return super().chat_messages(messages, seed, max_tokens=max_tokens, tools=tools, **kw)
    m = Strict(script={"family_classifier": [json.dumps(FAM)]})
    llm = TracedLLM(m, v2_trace())
    msgs = [{"role": "user", "content": "You sort a task into one of a fixed list of task families"}]
    assert ask(llm, "family", msgs, S.FamilyOut).family == "calc"
    assert any(r.get("name") == "ask_schema_rejected" for r in llm.trace.records)
    assert ask(llm, "family", msgs, S.FamilyOut).family == "calc"          # remembered: no second rejected call
    assert sum(r.get("name") == "ask_schema_rejected" for r in llm.trace.records) == 1


def test_other_provider_errors_are_not_swallowed(monkeypatch):
    class Down(MockLLMClient):
        def chat_messages(self, *a, **k):
            raise RuntimeError("503 overloaded")
    with pytest.raises(RuntimeError):
        ask(TracedLLM(Down(), v2_trace()), "family", [{"role": "user", "content": "x"}], S.FamilyOut)
