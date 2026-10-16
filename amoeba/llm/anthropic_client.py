"""D134 — Claude through its own Messages API (the `anthropic` SDK), next to the OpenAI-compatible client.

Why a second client: Claude's OpenAI-compatible endpoint ignores response_format, strict, reasoning_effort and seed and
answers a blocked call with an empty `content_filter` reply that names no reason. The Messages API gives structured
outputs (`output_config.format`), effort, a thinking summary, prompt caching and, on a refusal, `stop_details.category`
(cyber, bio, frontier_llm, reasoning_extraction, general_harms) — the category is what tells a prompt that asks for the
model's reasoning ("## Thought") apart from a real safety refusal.

`provider: anthropic` in models.yaml (a profile or a registry entry) selects this client (`make_client`). It speaks
the same `chat_messages` as every other client: OpenAI-style messages and tool specs go in, a ChatResponse comes out
(tool calls in `tool_calls`, input as a JSON string as the OpenAI client returns it). What it never sends: a
temperature (the model takes only the default), a seed (there is none), a forced tool_choice (400 on Sonnet 5.5), a
fixed thinking size. Adaptive thinking stays on; effort is set per call.
"""
from __future__ import annotations

import json
import time
from typing import Callable

from amoeba.llm.client import (ChatResponse, LLMClient, Messages, RATE_STATUS, dropped, retry_after, spend_cap)

EFFORTS = ("low", "medium", "high", "xhigh", "max")
THINKING_DISPLAYS = ("summarized", "omitted")
# the Messages API's stop reasons → the finish reasons the rest of Amoeba reads (OpenAI's words)
FINISH = {"end_turn": "stop", "stop_sequence": "stop", "max_tokens": "length", "tool_use": "tool_calls",
          "refusal": "refusal", "pause_turn": "pause_turn", "model_context_window_exceeded": "length"}
OVERLOADED = 529                       # Claude's "overloaded" status: retried like a 503
SCHEMA_LIMITS = {"optional": 24, "unions": 16}   # structured outputs: at most this many optional fields / unions


# box: client
class SchemaTooComplex(ValueError):
    """A pydantic schema that Claude's structured outputs cannot take (recursion, too many optional fields or
    unions). Raised before any call is made."""


# box: client
def claude_schema(model_or_schema) -> dict:
    """D134: a pydantic model's JSON schema (or a JSON schema dict) in the subset Claude's structured outputs take:
    every object closed (additionalProperties false), no numeric or length bounds, no minItems above 1, no
    recursion, and at most SCHEMA_LIMITS optional fields and unions in all. Raises SchemaTooComplex otherwise."""
    schema = model_or_schema.model_json_schema() if hasattr(model_or_schema, "model_json_schema") else \
        json.loads(json.dumps(model_or_schema))
    defs = schema.get("$defs") or {}
    count = {"optional": 0, "unions": 0}

    def walk(node, stack: tuple[str, ...]):
        if isinstance(node, list):
            return [walk(x, stack) for x in node]
        if not isinstance(node, dict):
            return node
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.split("/")[-1]
            if name in stack:
                raise SchemaTooComplex(f"recursive schema: {' -> '.join((*stack, name))}")
            return walk(defs[name], (*stack, name))
        out = {}
        for k, v in node.items():
            if k in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "minLength",
                     "maxLength", "maxItems", "pattern", "title", "default", "$defs"):
                continue
            if k == "minItems" and isinstance(v, int) and v > 1:
                continue
            if k == "properties" and isinstance(v, dict):        # field names are kept whatever they are called
                out[k] = {name: walk(sub, stack) for name, sub in v.items()}
            else:
                out[k] = walk(v, stack) if k != "required" else v
        if "anyOf" in out or "oneOf" in out:
            count["unions"] += 1
            if "oneOf" in out:
                out["anyOf"] = out.pop("oneOf")
        if out.get("type") == "object" or "properties" in out:
            extra = node.get("additionalProperties")
            if extra not in (None, False) and not out.get("properties"):
                raise SchemaTooComplex(f"a free-form object (dict) at {' -> '.join(stack) or 'the top'}: Claude's "
                                       f"structured outputs need named fields")
            out["additionalProperties"] = False
            props = out.get("properties") or {}
            count["optional"] += len([p for p in props if p not in (out.get("required") or [])])
        return out

    result = walk(schema, ())
    for k, cap in SCHEMA_LIMITS.items():
        if count[k] > cap:
            raise SchemaTooComplex(f"{count[k]} {'optional fields' if k == 'optional' else 'unions'} "
                                   f"(Claude's structured outputs take at most {cap})")
    return result


# box: client
def claude_messages(messages: Messages) -> tuple[str, list[dict]]:
    """D134: OpenAI-style messages → (system text, Messages-API messages). System messages are joined into the
    top-level system; an assistant message's tool_calls become tool_use blocks; a `tool` message becomes a
    tool_result block in a user turn; consecutive turns of one role are merged into one."""
    system = "\n\n".join(m.get("content") or "" for m in messages if m.get("role") == "system" and m.get("content"))
    out: list[dict] = []
    for i, m in enumerate(messages):
        role = m.get("role")
        if role == "system":
            continue
        blocks: list[dict] = []
        if role == "tool":
            role = "user"
            blocks.append({"type": "tool_result", "tool_use_id": m.get("tool_call_id") or f"toolu_{i}",
                           "content": m.get("content") or ""})
        else:
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for j, c in enumerate(m.get("tool_calls") or [] if role == "assistant" else []):
                fn = c.get("function") or c
                raw = fn.get("arguments", fn.get("input", "{}"))
                try:
                    args = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
                except ValueError:
                    args = {"input": raw}
                blocks.append({"type": "tool_use", "id": c.get("id") or f"toolu_{i}_{j}", "name": fn.get("name"),
                               "input": args if isinstance(args, dict) else {"input": args}})
        if not blocks:
            continue
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": blocks})
    return system, out


# box: client
def claude_tools(tools: list | None) -> list[dict]:
    """D134: OpenAI function specs → Messages-API tools (name, description, input_schema)."""
    out = []
    for t in tools or []:
        fn = t.get("function") or t
        out.append({"name": fn["name"], "description": fn.get("description") or "",
                    "input_schema": fn.get("parameters") or fn.get("input_schema")
                    or {"type": "object", "properties": {}}})
    return out


# box: client
class AnthropicClient(LLMClient):
    """D134: Claude's Messages API. `client` is for tests (a stand-in object with `messages.create`); a real run builds
    the SDK client from the key. Per call: `tools` (OpenAI specs), `schema` (a pydantic model → structured output,
    validated into ChatResponse.parsed), `effort`, `thinking_display`, `cache_prefix` (cache the system text and the
    tool list)."""

    cache_tag = "anthropic-messages"     # CachedLLM keys this client's replies apart from the OpenAI-compatible route

    def __init__(self, api_key: str, model: str, max_tokens: int = 2048, max_rate_retries: int = 5,
                 sleep: Callable[[float], None] = time.sleep, request_timeout_s: float | None = None,
                 effort: str | None = None, thinking_display: str = "omitted", cache_prefix: bool = False,
                 base_url: str | None = None, client=None):
        if effort is not None and effort not in EFFORTS:
            raise ValueError(f"effort must be one of {EFFORTS}, not {effort!r}")
        if thinking_display not in THINKING_DISPLAYS:
            raise ValueError(f"thinking_display must be one of {THINKING_DISPLAYS}, not {thinking_display!r}")
        if client is None:
            import anthropic   # imported lazily so tests never need the network or a key

            # the SDK's own retries are off: rate limits are retried below, where each wait is recorded (D48)
            extra = {"timeout": float(request_timeout_s)} if request_timeout_s else {}
            root = base_url.rstrip("/").removesuffix("/v1") if base_url else None   # the SDK adds /v1 itself
            client = anthropic.Anthropic(api_key=api_key, max_retries=0, **({"base_url": root} if root else {}),
                                         **extra)
        self._client, self.model, self.max_tokens = client, model, max_tokens
        self.temperature = None              # never sent; CachedLLM reads it for the key
        self.max_rate_retries, self._sleep = max_rate_retries, sleep
        self.effort, self.thinking_display, self.cache_prefix = effort, thinking_display, cache_prefix

    def request(self, messages: Messages, max_tokens: int | None = None, tools: list | None = None,
                schema=None, effort: str | None = None, thinking_display: str | None = None,
                cache_prefix: bool | None = None) -> dict:
        """The keyword arguments of messages.create for one call (kept apart so tests check the mapping)."""
        system, msgs = claude_messages(messages)
        kw: dict = {"model": self.model, "max_tokens": max_tokens or self.max_tokens, "messages": msgs}
        cache = self.cache_prefix if cache_prefix is None else cache_prefix
        if system:
            kw["system"] = [{"type": "text", "text": system, **({"cache_control": {"type": "ephemeral"}}
                                                                if cache else {})}]
        if tools:
            kw["tools"] = claude_tools(tools)
            if cache:
                kw["tools"][-1]["cache_control"] = {"type": "ephemeral"}
        config: dict = {}
        effort = effort or self.effort
        if effort:
            if effort not in EFFORTS:
                raise ValueError(f"effort must be one of {EFFORTS}, not {effort!r}")
            config["effort"] = effort
        if schema is not None:
            config["format"] = {"type": "json_schema", "schema": claude_schema(schema)}
        if config:
            kw["output_config"] = config
        if (thinking_display or self.thinking_display) == "summarized":
            kw["thinking"] = {"type": "adaptive", "display": "summarized"}
        return kw

    def chat_messages(self, messages: Messages, seed: int = 0, max_tokens: int | None = None,
                      tools: list | None = None, schema=None, effort: str | None = None,
                      thinking_display: str | None = None, cache_prefix: bool | None = None) -> ChatResponse:
        t0 = time.perf_counter()
        kw = self.request(messages, max_tokens, tools, schema, effort, thinking_display, cache_prefix)
        retries: list[dict] = []
        while True:
            try:
                resp = self._client.messages.create(**kw)
                break
            except Exception as e:
                status, lost = getattr(e, "status_code", None), dropped(e)
                if (status not in (*RATE_STATUS, OVERLOADED) and lost is None) or \
                        len(retries) >= self.max_rate_retries or spend_cap(e):
                    e.amoeba_retries = retries
                    raise
                after = retry_after(e)
                wait = after if after is not None else min(60.0, 2.0 * 2 ** len(retries))
                retries.append({"status": status, "wait_s": wait, "attempt": len(retries) + 1,
                                "retry_after": after, "error": lost})
                if lost == "timeout" and kw.get("max_tokens"):          # D131: less room after a call that hung
                    kw["max_tokens"] = max(1024, int(kw["max_tokens"]) // 2)
                    retries[-1]["max_tokens_after"] = kw["max_tokens"]
                self._sleep(wait)
        return self.response(resp, schema, retries, int((time.perf_counter() - t0) * 1000))

    def response(self, resp, schema=None, retries: list | None = None, latency_ms: int = 0) -> ChatResponse:
        """A Messages-API reply as a ChatResponse."""
        text, calls, thoughts = [], [], []
        for b in getattr(resp, "content", None) or []:
            kind = getattr(b, "type", None)
            if kind == "text":
                text.append(b.text or "")
            elif kind == "tool_use":
                calls.append({"id": getattr(b, "id", None), "name": b.name,
                              "input": json.dumps(getattr(b, "input", None) or {}, ensure_ascii=False)})
            elif kind == "thinking" and getattr(b, "thinking", None):
                thoughts.append(b.thinking)
        stop = getattr(resp, "stop_reason", None)
        details = getattr(resp, "stop_details", None)
        usage = getattr(resp, "usage", None)
        g = lambda k: int(getattr(usage, k, 0) or 0) if usage is not None else 0   # noqa: E731
        fresh, read, write = g("input_tokens"), g("cache_read_input_tokens"), g("cache_creation_input_tokens")
        out = g("output_tokens")
        od = getattr(usage, "output_tokens_details", None) if usage is not None else None
        thinking = int(getattr(od, "thinking_tokens", 0) or 0) if od is not None else 0
        content = "".join(text)
        parsed = None
        if schema is not None and stop != "refusal" and content.strip():
            try:
                parsed = schema.model_validate_json(content).model_dump(mode="json") if hasattr(
                    schema, "model_validate_json") else json.loads(content)
            except ValueError:
                parsed = None          # the caller sees parsed=None and the raw text (json_prompt repairs it)
        return ChatResponse(
            content=content, tool_calls=calls, finish_reason=FINISH.get(stop, stop),
            input_tokens=fresh + read + write,            # the whole prompt; cache_* say how much of it was cached
            output_tokens=max(0, out - thinking),         # visible output; thinking is reported apart (D27)
            reasoning_tokens=thinking, reasoning_source="reported" if thinking else None,
            model=getattr(resp, "model", None) or self.model, latency_ms=latency_ms, retries=list(retries or []),
            parsed=parsed, thinking_summary="\n\n".join(thoughts) or None,
            refusal_category=getattr(details, "category", None) if stop == "refusal" else None,
            cache_read_tokens=read, cache_write_tokens=write)


# box: client
def make_client(provider: str | None, *, base_url: str | None, api_key: str, model: str, max_tokens: int = 2048,
                max_rate_retries: int = 5, min_seconds_between_calls: float = 0.0, merge_system: bool = False,
                reasoning_effort: str | None = None, temperature: float | None = 0.2,
                request_timeout_s: float | None = None) -> LLMClient:
    """D134: `provider: anthropic` → AnthropicClient (the Messages API); anything else → the OpenAI-compatible client
    as before. merge_system, temperature and reasoning_effort do not apply to the Messages API."""
    if is_anthropic(provider):
        return AnthropicClient(api_key=api_key, model=model, max_tokens=max_tokens, max_rate_retries=max_rate_retries,
                               request_timeout_s=request_timeout_s, base_url=base_url)
    from amoeba.llm.client import OpenAICompatibleClient
    return OpenAICompatibleClient(base_url=base_url, api_key=api_key, model=model, max_tokens=max_tokens,
                                  max_rate_retries=max_rate_retries,
                                  min_seconds_between_calls=min_seconds_between_calls, merge_system=merge_system,
                                  reasoning_effort=reasoning_effort, temperature=temperature,
                                  request_timeout_s=request_timeout_s)


# box: client
def is_anthropic(provider: str | None) -> bool:
    return (provider or "").strip().lower() == "anthropic"
