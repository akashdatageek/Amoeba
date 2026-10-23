"""LLM clients — pattern from jiuwen_atm/llm_client.py (MIT): one OpenAI-compatible client, one mock.

Both expose ``chat(system, user, seed)`` and ``chat_messages(messages, seed)`` (the second carries
AgentVerse-style chat history) and return a ``ChatResponse`` with the token counts the API reported.
Phase 1 only records those counts in the trace; nothing enforces them.
"""
from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

from amoeba.config.proxy import refresh_proxy
from amoeba.llm.quota import parse_quota

Messages = list[dict[str, str]]


# box: client
@dataclass
class ChatResponse:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    latency_ms: int = 0
    finish_reason: str | None = None   # "stop", "length" (hit max_tokens) ... as the API reported it
    reasoning_tokens: int = 0          # hidden reasoning ("thinking") tokens; they count against max_tokens (D27)
    reasoning_source: str | None = None   # "reported" (completion_tokens_details) | "total_minus_visible" | None
    cached: bool = False               # D46: served from the response cache, not the model
    retries: list = field(default_factory=list)   # D48: [{status, wait_s, attempt, retry_after}] before this reply
    throttle_wait_s: float = 0.0       # D48: time waited for --min-seconds-between-calls
    tool_calls: list = field(default_factory=list)   # D132: native tool calls, [{"name", "input"}] in reply order
    parsed: dict | None = None             # D134: a structured (schema) reply, validated by its pydantic model
    thinking_summary: str | None = None    # D134: Claude's summarized thinking (thinking_display="summarized")
    refusal_category: str | None = None    # D134: stop_details.category of a refusal (reasoning_extraction, cyber ...)
    cache_read_tokens: int = 0             # D134: prompt tokens read from the provider's prompt cache
    cache_write_tokens: int = 0            # D134: prompt tokens written to it


# box: client
class LLMClient(ABC):
    model: str = ""

    def chat(self, system: str, user: str, seed: int = 0, max_tokens: int | None = None) -> ChatResponse:
        return self.chat_messages(
            [{"role": "system", "content": system}, {"role": "user", "content": user}], seed, max_tokens=max_tokens
        )

    @abstractmethod
    def chat_messages(self, messages: Messages, seed: int = 0, max_tokens: int | None = None) -> ChatResponse:
        """max_tokens: this call's reply limit; None = the client's default (D24: the Planner asks for more).
        D132: a client that can call tools natively also takes `tools=` (OpenAI function specs) and returns the
        calls in ChatResponse.tool_calls; callers pass it only when they want native tool calling."""


# box: client
def tools_kw(tools: list | None) -> dict:
    """D132: `tools=` only when there are tools, so a client without native tool calling is called as before."""
    return {"tools": tools} if tools else {}


CALL_OPTIONS = ("schema", "effort", "thinking_display", "cache_prefix")   # D134: per-call options of chat_messages


# box: client
def opts_kw(opts: dict) -> dict:
    """D134: the per-call options that are set (schema, effort, thinking_display, cache_prefix), so a wrapper passes
    them on and a call without any is made exactly as before. An unknown option is an error, not ignored."""
    bad = set(opts) - set(CALL_OPTIONS)
    if bad:
        raise TypeError(f"unknown chat_messages option(s) {sorted(bad)}; allowed: {list(CALL_OPTIONS)}")
    return {k: v for k, v in opts.items() if v is not None}


# box: client
def parse_schema_reply(schema, content: str) -> dict | None:
    """D134: a reply's JSON validated by the call's pydantic model (a dict), or None when it is not valid JSON for
    that model. D139: through validate_reply (enum case, nulls for optional fields)."""
    text = (content or "").strip()
    m = re.search(r"(?s)```(?:json)?\s*(.*?)```", text)
    text = m.group(1).strip() if m else text
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return validate_reply(schema, data)


# box: client
def validate_reply(schema, data) -> dict | None:
    """D139: a structured reply validated by its pydantic model in code (a bound the provider's schema dropped is
    still enforced here). Enum values are matched case-insensitively (a model may change their case), and a null
    the provider required for an optional field (to_claude_schema) falls back to the field's default. Returns the
    validated dict, or None."""
    if not hasattr(schema, "model_validate"):
        return data if isinstance(data, dict) else None
    from pydantic import ValidationError
    js = schema.model_json_schema()
    fixed = _enum_case(data, js, js.get("$defs") or {})
    for attempt in (fixed, _drop_nulls(fixed)):
        try:
            return schema.model_validate(attempt).model_dump(mode="json")
        except (ValidationError, ValueError, TypeError):
            continue
    return None


def _enum_case(data, node: dict, defs: dict):
    """Enum strings matched case-insensitively against the JSON schema's enums."""
    if isinstance(node, dict) and "$ref" in node:
        node = defs.get(node["$ref"].split("/")[-1], {})
    if not isinstance(node, dict):
        return data
    if isinstance(data, str):
        enums = [e for e in node.get("enum") or [] if isinstance(e, str)]
        for b in node.get("anyOf") or []:
            b = defs.get(b["$ref"].split("/")[-1], {}) if isinstance(b, dict) and "$ref" in b else b
            enums += [e for e in (b.get("enum") or []) if isinstance(e, str)] if isinstance(b, dict) else []
        return next((e for e in enums if e.lower() == data.lower()), data)
    if isinstance(data, list):
        items = node.get("items") or next((b.get("items") for b in node.get("anyOf") or []
                                           if isinstance(b, dict) and b.get("items")), {})
        return [_enum_case(x, items, defs) for x in data]
    if isinstance(data, dict):
        props = node.get("properties") or next((
            (defs.get(b["$ref"].split("/")[-1], {}) if "$ref" in b else b).get("properties") for b in
            node.get("anyOf") or [] if isinstance(b, dict)
            and (defs.get(b.get("$ref", "#/x/").split("/")[-1], {}) if "$ref" in b else b).get("properties")), {})
        return {k: _enum_case(v, props.get(k, {}), defs) for k, v in data.items()}
    return data


def _drop_nulls(data):
    if isinstance(data, dict):
        return {k: _drop_nulls(v) for k, v in data.items() if v is not None}
    if isinstance(data, list):
        return [_drop_nulls(x) for x in data]
    return data


def _reasoning_tokens(usage) -> tuple[int, str | None]:
    """D27: hidden reasoning tokens. OpenAI reports completion_tokens_details.reasoning_tokens; Gemini's
    OpenAI-compatible endpoint leaves that null but its total_tokens exceeds prompt + completion by the reasoning
    (checked 2026-09-24: 11 + 15 visible, 407 total at max_tokens=400)."""
    if usage is None:
        return 0, None
    details = getattr(usage, "completion_tokens_details", None)
    reported = getattr(details, "reasoning_tokens", None) if details is not None else None
    if reported is not None:
        return int(reported), "reported"
    total, p, c = (getattr(usage, k, None) for k in ("total_tokens", "prompt_tokens", "completion_tokens"))
    if isinstance(total, int) and isinstance(p, int) and isinstance(c, int) and total > p + c:
        return total - p - c, "total_minus_visible"
    return 0, None


# box: client
class OpenAICompatibleClient(LLMClient):
    """Any OpenAI-compatible endpoint (vLLM, Ollama, OpenAI, DeepSeek ...)."""

    def __init__(self, base_url: str | None, api_key: str, model: str,
                 temperature: float | None = 0.2, max_tokens: int = 2048, max_rate_retries: int = 5,
                 min_seconds_between_calls: float = 0.0, sleep: Callable[[float], None] = time.sleep,
                 merge_system: bool = False, reasoning_effort: str | None = None,
                 request_timeout_s: float | None = None):
        from openai import OpenAI  # imported lazily so tests never need it

        # D48: the SDK's own retries are off; rate limits are retried below, where each wait is recorded
        # D131: request_timeout_s ends a call that hangs (a 26-minute planner call on Gemma); the retry below then asks
        # again with half the reply room, so a model that thinks at length has less to think through
        extra = {"timeout": float(request_timeout_s)} if request_timeout_s else {}
        self._client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0, **extra)
        self._connect = lambda: OpenAI(api_key=api_key, base_url=base_url, max_retries=0, **extra)   # D111: new proxy
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.sends_seed = True   # False once the endpoint has rejected the field (Gemini's OpenAI layer does)
        self.max_rate_retries, self.min_interval, self._sleep = max_rate_retries, min_seconds_between_calls, sleep
        self._last_call = 0.0
        # D49: for models without a system role (Gemma) and for models whose thinking can be set
        if reasoning_effort is not None and reasoning_effort not in REASONING_EFFORTS:
            raise ValueError(f"reasoning_effort must be one of {sorted(REASONING_EFFORTS)}, not {reasoning_effort!r}")
        self.merge_system, self.reasoning_effort = merge_system, reasoning_effort

    @property
    def request_options(self) -> dict:
        """What changes the request besides the messages (part of the response-cache key, D46)."""
        return {"merge_system": self.merge_system, "reasoning_effort": self.reasoning_effort}

    def _create(self, kw: dict, seed: int):
        try:
            return self._client.chat.completions.create(**kw, **({"seed": seed} if self.sends_seed else {}))
        except Exception as e:   # openai.BadRequestError; matched by status so the SDK's error classes don't matter
            if not (self.sends_seed and getattr(e, "status_code", None) == 400 and "seed" in str(e)):
                raise
            self.sends_seed = False   # the run is then not seed-reproducible on this endpoint
            return self._client.chat.completions.create(**kw)

    def _throttle(self) -> float:
        """D48: --min-seconds-between-calls (for free tiers): wait until that long after the previous call."""
        wait = self.min_interval - (time.monotonic() - self._last_call) if self._last_call else 0.0
        if wait > 0:
            self._sleep(wait)
        self._last_call = time.monotonic()
        return max(0.0, wait)

    def chat_messages(self, messages: Messages, seed: int = 0, max_tokens: int | None = None,
                      tools: list | None = None, schema=None, **opts) -> ChatResponse:
        """D134: `schema` is sent as OpenAI's response_format json_schema and the reply validated into `parsed` (an
        endpoint that ignores it leaves parsed None); effort, thinking_display and cache_prefix do not apply here."""
        opts_kw(opts)
        t0 = time.perf_counter()
        kw = dict(model=self.model, messages=merge_system(messages) if self.merge_system else messages,
                  max_tokens=max_tokens or self.max_tokens)
        if tools:                                      # D132: native tool calling
            kw["tools"] = tools
        if schema is not None:                         # D134
            from amoeba.llm.anthropic_client import claude_schema
            kw["response_format"] = {"type": "json_schema", "json_schema": {
                "name": getattr(schema, "__name__", "reply"), "schema": claude_schema(schema), "strict": True}}
        if self.temperature is not None:               # None: not sent (Claude's endpoint rejects values below 1)
            kw["temperature"] = self.temperature
        if self.reasoning_effort is not None:          # sent only when set (D49)
            kw["reasoning_effort"] = REASONING_EFFORTS[self.reasoning_effort]
        throttled, retries = self._throttle(), []
        while True:
            try:
                resp = self._create(kw, seed)
                break
            except Exception as e:
                status, lost = getattr(e, "status_code", None), dropped(e)   # D57: dropped connections too
                quota = parse_quota(str(e)) if status == 429 else None         # D160
                if quota and quota["kind"] == "daily":    # it will not clear today: retrying only wastes the waits
                    e.amoeba_quota, e.amoeba_retries = quota, retries
                    raise
                if (status not in RATE_STATUS and lost is None) or len(retries) >= self.max_rate_retries \
                        or spend_cap(e):
                    e.amoeba_retries = retries   # the trace records the waits even when the call finally fails
                    raise
                after = retry_after(e)
                if after is None and quota and quota["retry_s"] is not None:   # D160: the wait the reply asks for
                    after = min(60.0, quota["retry_s"])
                wait = after if after is not None else min(60.0, 2.0 * 2 ** len(retries))
                retries.append({"status": status, "wait_s": wait, "attempt": len(retries) + 1,
                                "retry_after": after, "error": lost})
                if lost == "timeout" and kw.get("max_tokens"):          # D131: less room after a call that hung
                    kw["max_tokens"] = max(1024, int(kw["max_tokens"]) // 2)
                    retries[-1]["max_tokens_after"] = kw["max_tokens"]
                if lost == "connection" and refresh_proxy() is not None:   # D111: the proxy moved; reconnect
                    self._client = self._connect()
                    retries[-1]["proxy_refreshed"] = True
                self._sleep(wait)
                self._last_call = time.monotonic()
        usage = getattr(resp, "usage", None)
        reasoning, source = _reasoning_tokens(usage)
        calls = [{"name": t.function.name, "input": t.function.arguments or ""}
                 for t in (getattr(resp.choices[0].message, "tool_calls", None) or []) if getattr(t, "function", None)]
        content = resp.choices[0].message.content or ""
        return ChatResponse(
            content=content, tool_calls=calls,
            parsed=parse_schema_reply(schema, content) if schema is not None else None,
            finish_reason=getattr(resp.choices[0], "finish_reason", None),
            reasoning_tokens=reasoning, reasoning_source=source,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            model=getattr(resp, "model", None) or self.model,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            retries=retries, throttle_wait_s=round(throttled, 3),
        )


# D49: --reasoning-effort values → what the OpenAI-compatible API takes ("none" turns thinking off on Gemini's layer)
REASONING_EFFORTS = {"off": "none", "low": "low", "medium": "medium", "high": "high"}


# box: client
def merge_system(messages: Messages) -> Messages:
    """D49: for models without a system role — the system text goes at the top of the first user message
    (or becomes a user message when there is none), and no system message is sent."""
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system" and m.get("content"))
    rest = [dict(m) for m in messages if m.get("role") != "system"]
    if not system:
        return rest
    for m in rest:
        if m.get("role") == "user":
            m["content"] = f"{system}\n\n{m['content']}"
            return rest
    return [{"role": "user", "content": system}, *rest]


RATE_STATUS = (429, 500, 502, 503, 504)   # D48: too many requests / service unavailable; D73: a server error
# (500 internal, 502 bad gateway, 504 gateway timeout) is usually gone a moment later — same waits, same cap


def dropped(e: BaseException) -> str | None:
    """D57: a dropped connection or a timeout (the SDK's APIConnectionError / APITimeoutError, or the plain Python
    ones) — worth another try like a 429. Its kind, or None for any other error."""
    names = {c.__name__ for c in type(e).__mro__}
    if "APITimeoutError" in names or isinstance(e, TimeoutError):
        return "timeout"
    if "APIConnectionError" in names or isinstance(e, ConnectionError):
        return "connection"
    return None


def api_error(e: BaseException) -> bool:
    """D57: an error from the model service itself (an HTTP status, a dropped connection, a timeout) that is still
    there after the retries; a run ends on it with error='api: ...' and keeps its records."""
    return getattr(e, "status_code", None) is not None or dropped(e) is not None


def describe_api_error(e: BaseException) -> str:
    status = getattr(e, "status_code", None)
    return f"{type(e).__name__}{f' {status}' if status else ''}: {' '.join(str(e).split())[:200]}"


# box: client
def quota_exhausted(e: BaseException) -> bool:
    """D160: the model service's daily quota is spent (a 429 whose quota is per day); the run stops and resumes later."""
    q = getattr(e, "amoeba_quota", None)
    if q is None and getattr(e, "status_code", None) == 429:
        q = parse_quota(str(e))
    return bool(q and q.get("kind") == "daily")


def spend_cap(e: Exception) -> bool:
    """A 429 that says a spending cap was reached will not clear in seconds: it is not retried."""
    return bool(re.search(r"spend(ing)? cap", str(e), re.I))


def retry_after(e: Exception) -> float | None:
    """The Retry-After header (seconds) of an API error, when the service sent one."""
    headers = getattr(getattr(e, "response", None), "headers", None) or {}
    value = headers.get("retry-after") or headers.get("Retry-After") if hasattr(headers, "get") else None
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None   # an HTTP date: fall back to the exponential wait


Responder = Callable[[Messages, int], str]


# box: toymock
class MockLLMClient(LLMClient):
    """Offline, deterministic stand-in used by every test.

    A call is first classified by the prompt text into a *kind* (see ``SIGNATURES``), then answered
    from, in order of precedence:

    1. ``script[kind]`` — a list (popped from the front; the last item repeats once exhausted) or a
       callable ``(messages, seed) -> str``;
    2. ``responses`` — one FIFO list shared by every kind;
    3. ``responder(messages, seed)`` — a callable fallback.

    Token counts are ``len(text) // 4`` so tests can check that the trace sums them.
    Every call is kept in ``calls`` as ``{kind, messages, seed, response}``.
    """

    SIGNATURES: dict[str, str | tuple[str, ...]] = {   # a kind may have several phrases (d19 and D24 prompts)
        "interpreter": "You read a task before any planning",                                            # D77
        "family_classifier": "You sort a task into one of a fixed list of task families",                  # D101
        "replanner": "You are the Action Observer of a team",                                            # D63
        "fix_proposer_inv": "SCOPE: HOW THE TEAM WORKS",                                              # D154
        "fix_proposer_dom": "SCOPE: WHAT AN EXPERT WOULD KNOW",                                       # D154
        "fix_picker": "You compare two attempts at one step of a team plan",                          # D154
        "reflector": "You write one lesson from a Box 4 round of a team plan",                        # D163
        "promoter": "You turn one proven lesson into one general setting",                            # D166
        "rubric_grader": "You grade one answer against a fixed rubric",                               # D171
        "fix_proposer": "You propose one fix for a stuck step of a team plan",                         # D117 D
        "tool_writer": "You write one small Python tool. A team is carrying out the task",               # D125
        "plan_searcher": "You decide, before a team is planned for a task, whether the planner needs",  # D120
        "planner": ("You are a manager and expert prompt engineer",
                    "delivery lead with 15+ years of experience running cross-functional projects"),        # D24
        "agent_observer": ("identifying issues in role design",
                           "You are a staffing reviewer who has built and run many expert teams"),         # D24
        "plan_observer": ("Review the Execution Plan for clarity",
                          "You are a senior delivery reviewer. You judge whether this plan"),              # D24
        "plan_summariser": "You are assembling the team's final answer",                                   # D35
        "plan_critic": "You are reviewing a teammate's draft for one step of a team plan",                 # D51
        "plan_worker": "You are carrying out one step of a team plan",                                     # D31
        "plan_verify_own": "You are checking steps of a team plan, and you first work out your own result",  # D90
        "plan_resolve": "You settle disagreements between a team member and an independent check",           # D109
        "worker": "Based on prior agents' results and completed steps",
        "solver": "You are faced with the task",
        "critic": "Now the group is asking your opinion",
        "pool_picker": "Choose the one candidate below that can do this job",                           # D56
    }

    def __init__(self, script: dict[str, list[str] | Responder] | None = None,
                 responses: list[str] | None = None, responder: Responder | None = None,
                 model: str = "mock"):
        self.model = model
        self._script = {k: (list(v) if isinstance(v, list) else v) for k, v in (script or {}).items()}
        self._responses = list(responses or [])
        self._responder = responder
        self.calls: list[dict] = []

    @classmethod
    def classify(cls, messages: Messages) -> str:
        text = "\n".join(m.get("content", "") for m in messages)
        for kind, signature in cls.SIGNATURES.items():
            if any(s in text for s in ((signature,) if isinstance(signature, str) else signature)):
                return kind
        return "other"

    def _next(self, kind: str, messages: Messages, seed: int) -> str:
        src = self._script.get(kind)
        if src is None and kind in ("fix_proposer_inv", "fix_proposer_dom"):   # D154: a test scripting one proposer
            src = self._script.get("fix_proposer")                               # answers both scoped calls
        if callable(src):
            return src(messages, seed)
        if isinstance(src, list) and src:
            return src.pop(0) if len(src) > 1 else src[0]
        if self._responses:
            return self._responses.pop(0)
        if self._responder is not None:
            return self._responder(messages, seed)
        raise RuntimeError(f"MockLLMClient: no scripted response for kind={kind!r}")

    def chat_messages(self, messages: Messages, seed: int = 0, max_tokens: int | None = None,
                      tools: list | None = None, schema=None, **opts) -> ChatResponse:
        """D134: with `schema`, a scripted dict (or JSON text) is the reply, validated by the model into `parsed`
        (an invalid one leaves parsed None, as a real endpoint's would). A scripted ChatResponse is returned as it
        is (refusals and tool calls in tests)."""
        opts = opts_kw(opts)
        kind = self.classify(messages)
        content = self._next(kind, messages, seed)
        self.calls.append({"kind": kind, "messages": messages, "seed": seed, "response": content,
                           "max_tokens": max_tokens, "tools": tools, "schema": schema, **opts})
        if isinstance(content, ChatResponse):
            return content
        if isinstance(content, dict):
            content = json.dumps(content)
        n_in = sum(len(m.get("content", "")) for m in messages) // 4
        calls = mock_tool_calls(content, tools) if tools else []
        return ChatResponse(content="" if calls else content, input_tokens=n_in, output_tokens=len(content) // 4,
                            model=self.model, finish_reason="tool_calls" if calls else "stop", tool_calls=calls,
                            parsed=parse_schema_reply(schema, content) if schema is not None and not calls else None)

    def calls_of(self, kind: str) -> list[dict]:
        return [c for c in self.calls if c["kind"] == kind]

    @property
    def n_calls(self) -> int:
        return len(self.calls)


# box: toymock
def mock_tool_calls(content: str, tools: list) -> list[dict]:
    """D132: the mock answers a native-tools call by turning a scripted text action (## Action / ## ActionInput)
    into one tool call, so every scripted test can run with native tool calling too. A reply without those
    sections stays text."""
    act = re.search(r"(?ms)^##\s*Action\s*\n(.*?)(?=^##\s|\Z)", content)
    inp = re.search(r"(?ms)^##\s*ActionInput\s*\n(.*)\Z", content)      # the input may hold ## headings
    if not act:
        return []
    fn, text = tool_fn_name(act.group(1).strip()), (inp.group(1).strip() if inp else "")
    return [{"name": fn, "input": json.dumps(mock_args(fn, text, tools))}]


# box: toymock
def mock_args(fn: str, text: str, tools: list) -> dict:
    """D136: a scripted ActionInput as the arguments the offered tool takes: `input` for a one-string tool (D132); for
    a typed tool (v2) a JSON object whose keys it takes (file_path read as path), else the text as its one required
    argument; Final_Output with plain text keeps `input` (the plan runner's text fallback)."""
    spec = next(((t.get("function") or t) for t in tools or [] if isinstance(t, dict)
                 and (t.get("function") or t).get("name") == fn), None)
    props = ((spec or {}).get("parameters") or {}).get("properties") or {} if spec else {}
    if not props or "input" in props:
        return {"input": text}
    try:
        obj = json.loads(text)
    except ValueError:
        obj = None
    if isinstance(obj, dict):
        obj = {("path" if k == "file_path" and "path" in props else k): v for k, v in obj.items()}
        if set(obj) <= set(props):
            return obj
    required = ((spec or {}).get("parameters") or {}).get("required") or list(props)
    if fn == "Final_Output" and "output" in props:        # D141: a scripted step end as a typed StepFinal
        return {"status": "done", "output": text}
    if fn != "Final_Output" and len(required) == 1:
        return {required[0]: text}
    return {"input": text}


# box: client
def tool_fn_name(name: str) -> str:
    """D132: a tool name as a function name the APIs accept (letters, digits, _ and -, at most 64): 'local:Bash' →
    'local_Bash', 'Final Output' → 'Final_Output'. The plan runner keeps the map back to the real name."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", name or "")[:64] or "tool"
