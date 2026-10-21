"""D128 — Box 4 names the real cause: replies the provider blocked, a step that ran out of turns while it also lacked
something, and marks written in bold. Offline: stub clients that answer like a blocking provider."""
from amoeba.adapt.fixes import candidates
from amoeba.adapt.stuck import diagnose, out_of_turns_item, step_signals
from amoeba.interp.plan_runner import PROVIDER_BLOCKED, blocked_marks, missing_input_marks
from amoeba.interp.trace import TracedLLM, TraceWriter
from amoeba.llm.cache import CachedLLM, is_blocked
from amoeba.llm.client import ChatResponse, LLMClient
from amoeba.task.parsers import MissingSections
from tests.test_router_d97 import MSG, entry, router

READABLE = "## Thought\nok\n\n## CurrentStep\nx\n\n## Action\nFinal Output\n\n## ActionInput\n42\n"


class Blocking(LLMClient):
    """Blocks the first `n` calls (finish reason content_filter, nothing written), then answers."""
    model = "stub"

    def __init__(self, n: int, answer: str = READABLE):
        self.n, self.answer, self.calls = n, answer, 0

    def chat_messages(self, messages, seed=0, max_tokens=None, **kw):
        self.calls += 1
        if self.calls <= self.n:
            return ChatResponse("", 900, 0, finish_reason="content_filter")
        return ChatResponse(self.answer, 900, 30, finish_reason="stop")


def test_a_blocked_reply_is_counted_and_not_retried():
    """D134 replaces D128's one identical retry (it was blocked the same way every time): no retry."""
    tr = TraceWriter(None)
    stub = Blocking(1)
    assert TracedLLM(stub, tr).chat_messages(MSG).content == "" and stub.calls == 1
    assert tr.provider_blocked == 1 and [e["amoeba.retry"] for e in tr.events("provider_blocked")] == [False]


def test_a_blocked_reply_gets_no_repair_call_and_says_it_was_blocked():
    stub = Blocking(5)
    try:
        TracedLLM(stub, TraceWriter(None)).chat_sections("sys", "user", ["Action"])
    except MissingSections as e:
        assert getattr(e, "blocked", False) is True
    else:
        raise AssertionError("a blocked reply has no sections")
    assert stub.calls == 1                         # the call only: no retry (D134), no repair call


def test_the_cache_never_stores_a_blocked_reply(tmp_path):
    stub = Blocking(1)
    cached = CachedLLM(stub, tmp_path / "cache")
    assert is_blocked(cached.chat_messages(MSG))
    assert cached.chat_messages(MSG).content == READABLE and stub.calls == 2      # asked again, not replayed


def test_in_routed_mode_a_blocked_reply_goes_to_the_next_model(tmp_path):
    r = router([entry("a", price=(0.1, 0.1)), entry("b", price=(0.2, 0.2))], tmp_path,
               _client_for={"a": Blocking(9)})
    resp = r.chat_messages(MSG)
    assert resp.content == "from b"
    assert r.decisions[-1]["fallbacks"] == [{"from": "a", "to": "b", "reason": "provider_blocked"}]
    assert r.usage["a"]["calls"] == 1 and r.usage["b"]["calls"] == 1             # the blocked call is counted
    one = router([entry("a")], tmp_path, _client_for={"a": Blocking(9)})
    assert is_blocked(one.chat_messages(MSG))                                     # one model: nowhere to go


def test_blocked_turns_are_their_own_cause_and_get_more_turns_once():
    meta = {"step": 3, "status": "incomplete", "turns": 5, "finished": False, "roles": ["Analyst"],
            "unreadable_turns": [{"agent": "Analyst", "turn": t, "why": "x", "blocked": True} for t in (1, 2, 4)]
            + [{"agent": "Analyst", "turn": 5, "why": "missing sections ['Action']"}],
            "status_reason": "max_turns; unreadable replies: 4", "causes": ["max_turns"]}
    sig = step_signals(meta)
    assert [s["signal"] for s in sig][:2] == ["provider_blocked", "unreadable_reply"]
    d = diagnose(sig)
    assert d["cause"] == "provider_blocked" and d["allowed_edits"] == ["compact_prompt", "switch_model"]   # D145
    assert d["evidence"][0].startswith("3 of 5 turns: the model service blocked the reply")
    fixes, _ = candidates(d, 3, {"opts": {"max_turns": 5}})
    assert [f["kind"] for f in fixes] == ["compact_prompt"]                     # D145: no longer more turns
    fixes, _ = candidates(d, 3, {"opts": {"max_turns": 5, "compact": True}, "alt_models": ["gemma-api"]})
    assert [(f["kind"], f["params"]) for f in fixes] == [("switch_model", {"model": "gemma-api"})]
    assert candidates(d, 3, {"opts": {"compact": True}})[0] == []                # (c): nothing left, the task stops
    assert PROVIDER_BLOCKED == "provider_blocked"


def test_running_out_of_turns_is_seen_even_when_something_was_lacked():
    assert out_of_turns_item("turn budget — candidates not logged") and out_of_turns_item("Ran out of turns")
    assert not out_of_turns_item("github_api_fetch") and not out_of_turns_item("turnover data")
    meta = {"step": 1, "status": "partial", "roles": ["Researcher"], "finished": False, "turns": 5,
            "blocked": ["github_api_fetch", "turn budget"], "status_reason": "lacked: github_api_fetch, turn budget"}
    sig = {s["signal"]: s for s in step_signals(meta, plan={1: {"output": "repos", "roles": ["Researcher"]}})}
    assert "max_turns" in sig and sig["capability_unfilled"]["items"] == ["github_api_fetch"]
    meta = {**meta, "blocked": ["github_api_fetch"], "status_reason": "lacked: github_api_fetch; max_turns"}
    assert "max_turns" in {s["signal"] for s in step_signals(meta, plan={1: {"output": "x", "roles": []}})}


def test_bold_marks_are_read_like_plain_ones():
    text = "Done what I could.\n**BLOCKED:** Census API key — every call needs a key\n- **MISSING INPUT:** CPI series — step 2"
    assert blocked_marks(text) == ["Census API key"]
    assert missing_input_marks(text) == ["CPI series — step 2"]
