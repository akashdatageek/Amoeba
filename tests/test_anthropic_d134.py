"""D134 — Claude's own Messages API (AnthropicClient), refusal categories and the retry policy that replaces D128's
identical retry. Offline: a stand-in object plays the SDK client; nothing reaches the network."""
import json
from types import SimpleNamespace as NS

import pytest
from pydantic import BaseModel

from amoeba.adapt.stuck import step_signals
from amoeba.config.schema import AgentSpec
from amoeba.interp.trace import TracedLLM, TraceWriter, prompt_sources
from amoeba.llm.anthropic_client import (AnthropicClient, SchemaTooComplex, claude_messages, claude_schema,
                                         claude_tools, make_client)
from amoeba.llm.cache import CachedLLM, cache_key, is_blocked
from amoeba.llm.client import ChatResponse, LLMClient, MockLLMClient, OpenAICompatibleClient
from amoeba.task.models import Rubric, Task
from scripts.run_task import reasoning_refusal_lines
from tests.test_router_d97 import MSG, entry, router


class FakeMessages:
    def __init__(self, replies):
        self.replies, self.sent = list(replies), []

    def create(self, **kw):
        self.sent.append(kw)
        r = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(r, Exception):
            raise r
        return r


def fake(*replies, **kw):
    msgs = FakeMessages(replies)
    return AnthropicClient(api_key="unused", model="claude-sonnet-5-5", client=NS(messages=msgs), sleep=lambda s: None,
                           **kw), msgs


def reply(*blocks, stop="end_turn", category=None, read=0, write=0, fresh=100, out=40, thinking=0):
    usage = NS(input_tokens=fresh, output_tokens=out, cache_read_input_tokens=read, cache_creation_input_tokens=write,
               output_tokens_details=NS(thinking_tokens=thinking))
    return NS(content=list(blocks), stop_reason=stop, usage=usage, model="claude-sonnet-5-5",
              stop_details=NS(type="refusal", category=category, explanation="x") if stop == "refusal" else None)


def text(t):
    return NS(type="text", text=t)


SPEC = {"type": "function", "function": {"name": "web_search", "description": "search the web",
                                         "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                                                        "required": ["query"]}}}


def test_messages_and_tools_map_to_the_messages_api():
    msgs = [{"role": "system", "content": "You are X."}, {"role": "user", "content": "Find Y."},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "t1", "name": "web_search",
                                                                  "input": json.dumps({"query": "y"})}]},
            {"role": "tool", "tool_call_id": "t1", "content": "result"}, {"role": "user", "content": "go on"}]
    system, out = claude_messages(msgs)
    assert system == "You are X."
    assert [m["role"] for m in out] == ["user", "assistant", "user"]           # tool result + user text merged
    assert out[1]["content"] == [{"type": "tool_use", "id": "t1", "name": "web_search", "input": {"query": "y"}}]
    assert out[2]["content"][0] == {"type": "tool_result", "tool_use_id": "t1", "content": "result"}
    assert out[2]["content"][1] == {"type": "text", "text": "go on"}
    assert claude_tools([SPEC]) == [{"name": "web_search", "description": "search the web",
                                     "input_schema": SPEC["function"]["parameters"]}]


def test_the_request_never_carries_temperature_seed_or_a_forced_tool():
    c, sent = fake(reply(text("ok")))
    r = c.chat_messages(MSG, seed=7, max_tokens=300, tools=[SPEC])
    kw = sent.sent[0]
    assert r.content == "ok" and kw["max_tokens"] == 300 and kw["model"] == "claude-sonnet-5-5"
    assert not {"temperature", "seed", "tool_choice", "thinking", "output_config"} & set(kw)
    assert "cache_control" not in json.dumps(kw)


def test_effort_schema_thinking_and_cache_go_where_the_api_wants_them():
    class Answer(BaseModel):
        figure: float
        source: str

    c, sent = fake(reply(text('{"figure": 3.5, "source": "EIA"}')), effort="low")
    r = c.chat_messages([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}], tools=[SPEC],
                        schema=Answer, thinking_display="summarized", cache_prefix=True)
    kw = sent.sent[0]
    assert kw["output_config"]["effort"] == "low"
    fmt = kw["output_config"]["format"]
    assert fmt["type"] == "json_schema" and fmt["schema"]["additionalProperties"] is False
    assert kw["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"} and kw["tools"][-1]["cache_control"]
    assert r.parsed == {"figure": 3.5, "source": "EIA"}
    with pytest.raises(ValueError, match="effort"):
        c.chat_messages(MSG, effort="huge")


def test_the_reply_maps_back_tool_calls_thinking_cache_and_usage():
    blocks = [NS(type="thinking", thinking="I should search."), text("Searching."),
              NS(type="tool_use", id="toolu_1", name="web_search", input={"query": "diesel"})]
    c, _ = fake(reply(*blocks, stop="tool_use", read=800, write=200, fresh=50, out=90, thinking=30))
    r = c.chat_messages(MSG, tools=[SPEC])
    assert r.finish_reason == "tool_calls" and r.content == "Searching."
    assert r.tool_calls == [{"id": "toolu_1", "name": "web_search", "input": json.dumps({"query": "diesel"})}]
    assert r.thinking_summary == "I should search."
    assert (r.input_tokens, r.cache_read_tokens, r.cache_write_tokens) == (1050, 800, 200)
    assert (r.output_tokens, r.reasoning_tokens) == (60, 30)                   # visible + thinking = billed 90


def test_a_refusal_keeps_its_category_and_counts_as_blocked():
    c, _ = fake(reply(stop="refusal", category="reasoning_extraction", out=0))
    r = c.chat_messages(MSG)
    assert r.finish_reason == "refusal" and r.refusal_category == "reasoning_extraction" and is_blocked(r)
    assert c.chat_messages(MSG).parsed is None


def test_overloaded_and_rate_limits_are_retried_and_recorded():
    class Err(Exception):
        def __init__(self, status):
            super().__init__(f"status {status}")
            self.status_code = status
    c, sent = fake(Err(529), Err(429), reply(text("ok")))
    r = c.chat_messages(MSG)
    assert r.content == "ok" and [x["status"] for x in r.retries] == [529, 429] and len(sent.sent) == 3
    c2, _ = fake(Err(400))
    with pytest.raises(Err):
        c2.chat_messages(MSG)


def test_provider_anthropic_selects_the_messages_api_client():
    assert isinstance(make_client("anthropic", base_url=None, api_key="k", model="m"), AnthropicClient)
    assert isinstance(make_client("google-ai-studio", base_url="http://x/v1", api_key="k", model="m"),
                      OpenAICompatibleClient)


def test_the_schema_converter_on_our_models():
    for model in (Rubric, Task):
        s = claude_schema(model)

        def objects(node):
            if isinstance(node, dict):
                if node.get("type") == "object" or "properties" in node:
                    yield node
                for v in node.values():
                    yield from objects(v)
            elif isinstance(node, list):
                for v in node:
                    yield from objects(v)
        assert all(o["additionalProperties"] is False for o in objects(s))
        flat = json.dumps(s)
        assert "$ref" not in flat and "$defs" not in flat and '"minimum"' not in flat and '"default"' not in flat
    with pytest.raises(SchemaTooComplex, match="free-form object"):
        claude_schema(AgentSpec)                    # pool: list[dict] has no named fields

    class Node(BaseModel):
        name: str
        children: list["Node"] = []
    with pytest.raises(SchemaTooComplex, match="recursive"):
        claude_schema(Node)
    many = {"type": "object", "properties": {f"f{i}": {"type": "string"} for i in range(25)}, "required": []}
    with pytest.raises(SchemaTooComplex, match="25 optional fields"):
        claude_schema(many)
    bounded = {"type": "object", "properties": {"n": {"type": "integer", "minimum": 1, "maximum": 5},
                                                "xs": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                                                "title": {"type": "string", "maxLength": 9}},
               "required": ["n", "xs", "title"]}
    out = claude_schema(bounded)
    assert out["properties"] == {"n": {"type": "integer"}, "xs": {"type": "array", "items": {"type": "string"}},
                                 "title": {"type": "string"}}


def test_the_mock_returns_a_scripted_dict_validated_into_parsed():
    class Pick(BaseModel):
        choice: int
    mock = MockLLMClient(responses=[{"choice": 2}, {"choice": "two"}])
    assert mock.chat_messages(MSG, schema=Pick).parsed == {"choice": 2}
    assert mock.chat_messages(MSG, schema=Pick).parsed is None                 # invalid → None, as a real endpoint
    assert mock.calls[0]["schema"] is Pick
    with pytest.raises(TypeError, match="unknown chat_messages option"):
        mock.chat_messages(MSG, colour="red")


class Refusing(LLMClient):
    model = "stub"

    def __init__(self, category=None, n=9):
        self.category, self.n, self.calls = category, n, 0

    def chat_messages(self, messages, seed=0, max_tokens=None, **kw):
        self.calls += 1
        if self.calls <= self.n:
            return ChatResponse("", 900, 0, finish_reason="refusal" if self.category else "content_filter",
                                refusal_category=self.category)
        return ChatResponse("from stub", 900, 30, finish_reason="stop")


def test_a_reasoning_refusal_is_not_retried_and_names_the_prompt_file():
    interp = (open("amoeba/config/prompts/interpret.txt", encoding="utf-8").read().split("\n", 1)[1]
              .replace("{task}", "T").replace("{context}", "None"))
    msgs = [{"role": "user", "content": interp}]
    assert prompt_sources(msgs)[0] == "interpret.txt"
    tr, stub = TraceWriter(None), Refusing("reasoning_extraction")
    r = TracedLLM(stub, tr).chat_messages(msgs, agent_name="interpreter")
    assert is_blocked(r) and stub.calls == 1
    ev = tr.events("prompt_asks_for_reasoning")
    assert ev and ev[0]["amoeba.prompt_files"][0] == "interpret.txt" and ev[0]["gen_ai.agent.name"] == "interpreter"
    assert tr.reasoning_refusals == [{"agent": "interpreter", "step": None, "prompt_files": ev[0]["amoeba.prompt_files"]}]
    lines = reasoning_refusal_lines(tr.reasoning_refusals)
    assert "REFUSED" in lines[0] and "interpret.txt" in lines[1]
    assert reasoning_refusal_lines(None) == []


def test_other_categories_and_uncategorised_blocks_are_not_retried_either():
    for cat in ("cyber", None):
        tr, stub = TraceWriter(None), Refusing(cat)
        TracedLLM(stub, tr).chat_messages(MSG)
        assert stub.calls == 1 and tr.events("provider_blocked")[0].get("amoeba.refusal_category") == cat
        assert not tr.events("prompt_asks_for_reasoning")


def test_routed_mode_moves_other_blocks_to_the_next_model_but_not_a_reasoning_refusal(tmp_path):
    r = router([entry("a", price=(0.1, 0.1)), entry("b", price=(0.2, 0.2))], tmp_path,
               _client_for={"a": Refusing("general_harms")})
    assert r.chat_messages(MSG).content == "from b"
    r2 = router([entry("a", price=(0.1, 0.1)), entry("b", price=(0.2, 0.2))], tmp_path,
                _client_for={"a": Refusing("reasoning_extraction")})
    assert is_blocked(r2.chat_messages(MSG)) and r2.decisions[-1]["fallbacks"] == []


def test_box4_names_the_categories_when_every_blocked_turn_has_one():
    base = {"step": 2, "turns": 3, "finished": False, "status": "incomplete", "roles": ["A"]}
    named = [{"agent": "A", "turn": t, "why": "x", "blocked": True, "category": "cyber"} for t in (1, 2)]
    sig = next(s for s in step_signals({**base, "unreadable_turns": named}) if s["signal"] == "provider_blocked")
    assert "refusal categories: cyber" in sig["evidence"][0] and sig["categories"] == ["cyber"]
    mixed = named + [{"agent": "A", "turn": 3, "why": "x", "blocked": True}]
    sig = next(s for s in step_signals({**base, "unreadable_turns": mixed}) if s["signal"] == "provider_blocked")
    assert "no category given" in sig["evidence"][0]


def old_key(model, messages, max_tokens, temperature, namespace, tools=None, options=None):
    """The response-cache key exactly as it was built before D134 (cache.py at a9022801)."""
    parts = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
             "namespace": namespace}
    if tools:
        parts["tools"] = tools
    if options and any(options.values()):
        parts["options"] = options
    return cache_key(parts)


def test_old_cache_keys_still_hit_and_new_options_join_only_when_set(tmp_path):
    gemma = OpenAICompatibleClient(base_url="http://x/v1", api_key="k", model="gemma-4-31b-it", merge_system=True)
    cached = CachedLLM(gemma, tmp_path, "replay", "r1")
    assert cached.key(MSG, 500) == old_key("gemma-4-31b-it", MSG, 500, 0.2, "r1",
                                           options={"merge_system": True, "reasoning_effort": None})
    assert cached.key(MSG, 500, [SPEC]) == old_key("gemma-4-31b-it", MSG, 500, 0.2, "r1", tools=[SPEC],
                                                   options={"merge_system": True, "reasoning_effort": None})
    compat = OpenAICompatibleClient(base_url="http://x/v1", api_key="k", model="claude-sonnet-5-5", temperature=None)
    assert CachedLLM(compat, tmp_path).key(MSG, 9) == old_key("claude-sonnet-5-5", MSG, 9, None, "")

    class S(BaseModel):
        a: int
    base = cached.key(MSG, 500)
    assert len({base, cached.key(MSG, 500, schema=S), cached.key(MSG, 500, effort="low")}) == 3
    assert cached.key(MSG, 500, thinking_display="summarized", cache_prefix=True) == base
    native, _ = fake(reply(text("ok")))
    assert CachedLLM(native, tmp_path).key(MSG, 9) != CachedLLM(compat, tmp_path).key(MSG, 9)   # its own route


def test_thinking_summary_and_cache_tokens_reach_the_trace():
    c, _ = fake(reply(NS(type="thinking", thinking="plan it"), text("done"), read=500, write=100, fresh=10))
    tr = TraceWriter(None, log_content=True)
    TracedLLM(c, tr).chat_messages(MSG, effort="medium")
    span = tr.spans("chat")[0]
    assert span["amoeba.usage.cache_read_tokens"] == 500 and span["amoeba.usage.cache_write_tokens"] == 100
    assert span["amoeba.thinking_summary"] == "plan it" and span["amoeba.effort"] == "medium"
    from amoeba.llm.limits import estimate
    u = estimate(tr.spans("chat"), "claude-sonnet-5-5")
    assert u["cost_usd"] == round((10 * 2.0 + 500 * 0.2 + 100 * 2.5 + 40 * 10.0) / 1e6, 6)
