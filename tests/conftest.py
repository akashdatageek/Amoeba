from __future__ import annotations

import os
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


# D154: AMOEBA_TEST_PROPOSER=scoped runs a test module with every PlanOptions under --proposer scoped unless the test
# sets it (tests/test_scoped_proposers_d154.py re-runs the Box 4 tests this way). A scripted single-proposer reply has
# no `because`; the shim adds the first evidence line the proposer was shown, so the scoped checks can pass.
if os.environ.get("AMOEBA_TEST_PROPOSER") == "scoped":
    import json as _json
    import re as _re

    from amoeba.interp.plan_runner import PlanOptions as _PO

    _po_init = _PO.__init__

    def _scoped_init(self, *a, **kw):
        _po_init(self, *a, **kw)
        if "proposer" not in kw:
            self.proposer = "scoped"

    _PO.__init__ = _scoped_init
    _mock_next = MockLLMClient._next

    def _scoped_next(self, kind, messages, seed):
        """A scoped call answers from the test's single fix_proposer script: the next scripted edit goes to the scope
        whose allowed list offers its op (with the first evidence line as its `because`); the other scope is told
        nothing fits and gives no candidate. A scope with its own script is answered from it."""
        if kind not in ("fix_proposer_inv", "fix_proposer_dom") or kind in self._script:
            return _mock_next(self, kind, messages, seed)
        user = messages[-1]["content"]
        src = self._script.get("fix_proposer")
        nxt = (src[0] if isinstance(src, list) and src else src(messages, seed) if callable(src) else None)
        try:
            obj = _json.loads(nxt[nxt.index("{"):nxt.rindex("}") + 1]) if isinstance(nxt, str) else None
        except ValueError:
            obj = None
        offered = _re.findall(r"^- (\w+): params", user.split("# Edits allowed for this cause", 1)[-1], _re.M)
        if not (isinstance(obj, dict) and "edit" in obj) or obj["edit"].get("op") not in offered:
            if isinstance(obj, dict) and "edit" in obj:
                return "No edit of my scope fits."
            return _mock_next(self, "fix_proposer", messages, seed)        # a scripted non-edit (no fix) is shared
        out = _mock_next(self, "fix_proposer", messages, seed)
        ev = _re.search(r"Cause: [^\n]*\n- ([^\n]+)", user)
        obj["because"] = (ev.group(1) if ev else "")[:60]
        return _json.dumps(obj)

    MockLLMClient._next = _scoped_next


# D136: AMOEBA_TEST_PROTOCOL=v2 runs a test module with every PlanOptions in native tool-calling mode and protocol v2
# unless the test sets those itself (tests/test_protocol_v2_d136.py runs the Box 4 tests this way).
if os.environ.get("AMOEBA_TEST_PROTOCOL") == "v2":
    from amoeba.interp.plan_runner import PlanOptions

    _plain_init = PlanOptions.__init__

    def _v2_init(self, *a, **kw):
        _plain_init(self, *a, **kw)
        if "native_tools" not in kw:
            self.native_tools = "on"
        if "protocol" not in kw:
            self.protocol = "v2"

    PlanOptions.__init__ = _v2_init

    # D141: these Box 4 tests script their drafts (Boxes 1 and 2) in the legacy text format; the v2 pass covers
    # Boxes 3 and 4, so drafting keeps the legacy readers here (tests/test_protocol_v2_all_d141.py covers v2 drafting)
    import amoeba.task.draft as _draft
    import amoeba.task.interpret as _interpret
    import amoeba.task.plan_search as _plan_search
    for _m in (_draft, _interpret, _plan_search):
        _m.protocol_of = lambda trace: "legacy"

    # a scripted tool-writer reply in the legacy format (JSON head + ```python block) answers a typed call too
    from amoeba.adapt.toolmaker import parse_tool
    from amoeba.task.schemas import ToolWriterOut

    _plain_chat = MockLLMClient.chat_messages

    def _typed_chat(self, messages, seed=0, max_tokens=None, tools=None, schema=None, **opts):
        resp = _plain_chat(self, messages, seed, max_tokens=max_tokens, tools=tools, schema=schema, **opts)
        if schema is ToolWriterOut and resp.parsed is None and resp.content:
            try:
                resp.parsed = ToolWriterOut(**parse_tool(resp.content)).model_dump(mode="json")
            except (ValueError, TypeError):
                pass
        return resp

    MockLLMClient.chat_messages = _typed_chat
