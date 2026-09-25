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


# D52: a task whose numbers and deliverables the draft_d24_full fixture carries into its Requirements and Givens
DB_PROMPT = ("For 50 tenants at 200 GB each, gather current benchmark results for PostgreSQL and MongoDB, estimate "
             "the monthly cost, prototype and test the event schema in both databases, and deliver a recommendation "
             "memo with a risk table.")


@pytest.fixture
def db_task():
    return Task(id="db-choice", prompt=DB_PROMPT, family="design")


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
