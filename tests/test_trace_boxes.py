"""D55 — every trace line names the as-built page box whose code wrote it (amoeba.box), for flat, boss_reviewers and
plan runs, and the ids are the page's own."""
import json
import sys
from pathlib import Path

import pytest

from amoeba.interp.trace import BOX2_BOX, EVENT_BOX, SPAN_BOX, TraceWriter
from amoeba.llm.toy_mock import toy_mock_client
from amoeba.safety.envelope import Envelope
from amoeba.task.source import ToyTaskSource
from amoeba.tools.registry import default_registry
from scripts.run_task import run_one

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import arch_extract as X  # noqa: E402

IDS = {b["id"] for b in X.BOXES}


def test_the_tables_name_real_boxes():
    assert set(EVENT_BOX.values()) | set(SPAN_BOX.values()) | set(BOX2_BOX.values()) <= IDS


@pytest.mark.parametrize("topology", ["flat", "boss_reviewers", "plan"])
def test_every_line_has_a_box(tmp_path, topology):
    tools = default_registry()
    llm = toy_mock_client()
    r = run_one(ToyTaskSource(0, 1).tasks()[0], topology, llm, Envelope.from_registry(tools, model=llm.model), tools,
                tmp_path)
    lines = [json.loads(l) for l in (tmp_path / r.run_id / "trace.jsonl").read_text().splitlines()]
    assert lines and all(l.get("amoeba.box") in IDS for l in lines), [l["name"] for l in lines if l.get("amoeba.box") not in IDS]
    boxes = {l["amoeba.box"] for l in lines}
    assert {"planner", "agent_obs", "plan_obs", "interpreter"} <= boxes
    assert {"flat": {"helper"}, "boss_reviewers": {"solver", "critics"}, "plan": {"plan_step", "plan_summary"}}[topology] <= boxes
    chats = [l for l in lines if l["name"] == "chat"]
    assert {c["amoeba.box"] for c in chats if c.get("gen_ai.agent.name") == "agent_observer"} == {"agent_obs"}


def test_events_inherit_the_open_span_and_can_name_their_own():
    t = TraceWriter()
    with t.span("invoke_agent", {"amoeba.box": "helper"}):
        t.event("something_new")
        t.event("blocked")
        with t.span("chat"):
            pass
    t.event("orphan")
    assert [r.get("amoeba.box") for r in t.records] == ["helper", "read_action", "helper", "helper", None]
