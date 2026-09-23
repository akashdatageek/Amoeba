"""Everything drafting did is kept: every round (Draft.rounds), failed drafts, and prompts/replies in the trace."""
import json

import pytest

from amoeba.interp.trace import TraceWriter
from amoeba.task.draft import DraftError, draft_team
from amoeba.task.models import Task
from scripts.run_task import main, run_one
from tests.conftest import fx, mock

OK, COMPLAINT = "observer_no_suggestions", "observer_complaint"
BRACES = fx("draft_round_ok").replace('"You are a Calculator.', '"You are a Calculator. Evaluate {expression}.')


def test_every_round_is_recorded(task, envelope, trace):
    llm = mock(planner=[fx("draft_round_ok")], agent_observer=[fx(OK), fx(COMPLAINT), fx(OK)],
               plan_observer=[fx(COMPLAINT), fx(OK), fx(OK)])
    d = draft_team(task, llm, envelope, trace)
    assert [r.index for r in d.rounds] == [1, 2, 3] and [r.consensus for r in d.rounds] == [False, False, True]
    first = d.rounds[0]
    assert first.planner_raw == fx("draft_round_ok") and [x["name"] for x in first.roles] == ["Calculator", "Writer"]
    assert first.plan[0] == {"agents": ["Calculator"], "text": first.plan[0]["text"]} and len(first.plan) == 3
    assert first.agent_observer.startswith("No Suggestions") and first.plan_observer.startswith("1. The Calculator")
    assert first.plan_observer_raw == fx(COMPLAINT) and d.rounds[1].agent_observer_raw == fx(COMPLAINT)
    assert d.rounds[-1].planner_raw == d.raw_draft


def test_failed_draft_keeps_its_rounds(task, envelope, trace):
    with pytest.raises(DraftError) as ei:
        draft_team(task, mock(planner=[BRACES]), envelope, trace)
    [r] = ei.value.rounds
    assert r.planner_raw == BRACES and [x["name"] for x in r.roles] == ["Writer"] and r.consensus


def test_missing_section_failure_keeps_the_open_round(task, envelope, trace):
    with pytest.raises(DraftError) as ei:
        draft_team(task, mock(planner=["## Thought\nno sections here\n"]), envelope, trace)
    assert [r.index for r in ei.value.rounds] == [1] and ei.value.rounds[0].planner_raw == ""


def test_run_one_writes_plan_json_for_a_failed_draft(tmp_path, envelope, tools):
    r = run_one(Task(prompt="Compute 17 * 23 + 5.", ground_truth="396"), "flat", mock(planner=[BRACES]),
                envelope, tools, tmp_path)
    saved = json.loads((tmp_path / r.run_id / "plan.json").read_text())
    assert saved["error"] == r.error == "draft: roster size 1 outside 2..5"
    assert saved["rounds"][0]["planner_raw"] == BRACES and r.draft_rounds == 1   # the round that ran is counted


def test_trace_content_is_opt_in_on_the_writer(task, envelope):
    off, on = TraceWriter(None), TraceWriter(None, log_content=True)
    draft_team(task, mock(planner=[fx("draft_round_ok")]), envelope, off)
    draft_team(task, mock(planner=[fx("draft_round_ok")]), envelope, on)
    assert not any("gen_ai.input.messages" in s for s in off.spans("chat"))
    planner = on.spans("chat")[0]
    assert [m["role"] for m in planner["gen_ai.input.messages"]] == ["system", "user"]
    assert "You are a manager and expert prompt engineer" in planner["gen_ai.input.messages"][1]["content"]
    assert planner["gen_ai.output.messages"] == [{"role": "assistant", "content": fx("draft_round_ok")}]


def test_cli_logs_content_by_default(tmp_path):
    assert main(["--toy", "--n", "1", "--runs-dir", str(tmp_path / "a")]) == 0
    assert main(["--toy", "--n", "1", "--runs-dir", str(tmp_path / "b"), "--no-log-content"]) == 0
    lines = lambda d: [json.loads(l) for p in d.glob("*/trace.jsonl") for l in p.read_text().splitlines()]
    chats_a = [s for s in lines(tmp_path / "a") if s["name"] == "chat"]
    assert chats_a and all("gen_ai.input.messages" in s and "gen_ai.output.messages" in s for s in chats_a)
    assert not any("gen_ai.input.messages" in s for s in lines(tmp_path / "b"))
    plan = json.loads(next((tmp_path / "a").glob("*/plan.json")).read_text())
    assert len(plan["rounds"]) == plan["rounds_used"] and plan["rounds"][0]["planner_raw"]
