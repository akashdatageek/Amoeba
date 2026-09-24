from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.interp.trace import TraceWriter
from amoeba.llm.client import MockLLMClient
from amoeba.safety.envelope import Envelope
from amoeba.task.models import Task
from amoeba.tools.registry import default_registry

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parent.parent


def fx(name: str) -> str:
    return (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")


@pytest.fixture
def tools():
    return default_registry()


@pytest.fixture
def envelope(tools):
    return Envelope.from_registry(tools, model="mock")


@pytest.fixture
def task():
    return Task(id="task-0001", prompt="Compute 17 * 23 + 5. Reply with just the number.", family="arith",
                ground_truth="396")


@pytest.fixture
def trace():
    return TraceWriter(None, episode_id="ep-test")


def mock(**script) -> MockLLMClient:
    """MockLLMClient with per-kind scripts; observers default to 'No Suggestions'."""
    script.setdefault("agent_observer", [fx("observer_no_suggestions")])
    script.setdefault("plan_observer", [fx("observer_no_suggestions")])
    if "plan_worker" in script:                     # the plan summariser's step (D35) answers like any plan step
        script.setdefault("plan_summariser", script["plan_worker"])
        script.setdefault("plan_critic", ["## Verdict\nAGREE\n\n## Issues\nnone\n"])   # D51 reviewers agree
    return MockLLMClient(script=script)
