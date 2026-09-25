"""LLM clients — pattern from jiuwen_atm/llm_client.py (MIT): one OpenAI-compatible client, one mock.

Both expose ``chat(system, user, seed)`` and ``chat_messages(messages, seed)`` (the second carries
AgentVerse-style chat history) and return a ``ChatResponse`` with the token counts the API reported.
Phase 1 only records those counts in the trace; nothing enforces them.
"""
from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

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


# box: client
class LLMClient(ABC):
    model: str = ""

    def chat(self, system: str, user: str, seed: int = 0, max_tokens: int | None = None) -> ChatResponse:
        return self.chat_messages(
            [{"role": "system", "content": system}, {"role": "user", "content": user}], seed, max_tokens=max_tokens
        )

    @abstractmethod
    def chat_messages(self, messages: Messages, seed: int = 0, max_tokens: int | None = None) -> ChatResponse:
        """max_tokens: this call's reply limit; None = the client's default (D24: the Planner asks for more)."""


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
                 temperature: float = 0.2, max_tokens: int = 2048, max_rate_retries: int = 5,
                 min_seconds_between_calls: float = 0.0, sleep: Callable[[float], None] = time.sleep,
                 merge_system: bool = False, reasoning_effort: str | None = None):
        from openai import OpenAI  # imported lazily so tests never need it

        # D48: the SDK's own retries are off; rate limits are retried below, where each wait is recorded
        self._client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0)
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

    def chat_messages(self, messages: Messages, seed: int = 0, max_tokens: int | None = None) -> ChatResponse:
        t0 = time.perf_counter()
        kw = dict(model=self.model, messages=merge_system(messages) if self.merge_system else messages,
                  temperature=self.temperature, max_tokens=max_tokens or self.max_tokens)
        if self.reasoning_effort is not None:          # sent only when set (D49)
            kw["reasoning_effort"] = REASONING_EFFORTS[self.reasoning_effort]
        throttled, retries = self._throttle(), []
        while True:
            try:
                resp = self._create(kw, seed)
                break
            except Exception as e:
                status = getattr(e, "status_code", None)
                if status not in RATE_STATUS or len(retries) >= self.max_rate_retries or spend_cap(e):
                    e.amoeba_retries = retries   # the trace records the waits even when the call finally fails
                    raise
                after = retry_after(e)
                wait = after if after is not None else min(60.0, 2.0 * 2 ** len(retries))
                retries.append({"status": status, "wait_s": wait, "attempt": len(retries) + 1,
                                "retry_after": after})
                self._sleep(wait)
                self._last_call = time.monotonic()
        usage = getattr(resp, "usage", None)
        reasoning, source = _reasoning_tokens(usage)
        return ChatResponse(
            content=resp.choices[0].message.content or "",
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


RATE_STATUS = (429, 503)   # D48: too many requests / service unavailable — worth waiting for


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
        "planner": ("You are a manager and expert prompt engineer",
                    "delivery lead with 15+ years of experience running cross-functional projects"),        # D24
        "agent_observer": ("identifying issues in role design",
                           "You are a staffing reviewer who has built and run many expert teams"),         # D24
        "plan_observer": ("Review the Execution Plan for clarity",
                          "You are a senior delivery reviewer. You judge whether this plan"),              # D24
        "plan_summariser": "You are assembling the team's final answer",                                   # D35
        "plan_critic": "You are reviewing a teammate's draft for one step of a team plan",                 # D51
        "plan_worker": "You are carrying out one step of a team plan",                                     # D31
        "worker": "Based on prior agents' results and completed steps",
        "solver": "You are faced with the task",
        "critic": "Now the group is asking your opinion",
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
        if callable(src):
            return src(messages, seed)
        if isinstance(src, list) and src:
            return src.pop(0) if len(src) > 1 else src[0]
        if self._responses:
            return self._responses.pop(0)
        if self._responder is not None:
            return self._responder(messages, seed)
        raise RuntimeError(f"MockLLMClient: no scripted response for kind={kind!r}")

    def chat_messages(self, messages: Messages, seed: int = 0, max_tokens: int | None = None) -> ChatResponse:
        kind = self.classify(messages)
        content = self._next(kind, messages, seed)
        self.calls.append({"kind": kind, "messages": messages, "seed": seed, "response": content,
                           "max_tokens": max_tokens})
        n_in = sum(len(m.get("content", "")) for m in messages) // 4
        return ChatResponse(content=content, input_tokens=n_in, output_tokens=len(content) // 4,
                            model=self.model, finish_reason="stop")

    def calls_of(self, kind: str) -> list[dict]:
        return [c for c in self.calls if c["kind"] == kind]

    @property
    def n_calls(self) -> int:
        return len(self.calls)
