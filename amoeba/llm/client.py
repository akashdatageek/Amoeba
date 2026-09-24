"""LLM clients — pattern from jiuwen_atm/llm_client.py (MIT): one OpenAI-compatible client, one mock.

Both expose ``chat(system, user, seed)`` and ``chat_messages(messages, seed)`` (the second carries
AgentVerse-style chat history) and return a ``ChatResponse`` with the token counts the API reported.
Phase 1 only records those counts in the trace; nothing enforces them.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

Messages = list[dict[str, str]]


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


class OpenAICompatibleClient(LLMClient):
    """Any OpenAI-compatible endpoint (vLLM, Ollama, OpenAI, DeepSeek ...)."""

    def __init__(self, base_url: str | None, api_key: str, model: str,
                 temperature: float = 0.2, max_tokens: int = 2048):
        from openai import OpenAI  # imported lazily so tests never need it

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.sends_seed = True   # False once the endpoint has rejected the field (Gemini's OpenAI layer does)

    def chat_messages(self, messages: Messages, seed: int = 0, max_tokens: int | None = None) -> ChatResponse:
        t0 = time.perf_counter()
        kw = dict(model=self.model, messages=messages, temperature=self.temperature,
                  max_tokens=max_tokens or self.max_tokens)
        try:
            resp = self._client.chat.completions.create(**kw, **({"seed": seed} if self.sends_seed else {}))
        except Exception as e:   # openai.BadRequestError; matched by status so the SDK's error classes don't matter
            if not (self.sends_seed and getattr(e, "status_code", None) == 400 and "seed" in str(e)):
                raise
            self.sends_seed = False   # the run is then not seed-reproducible on this endpoint
            resp = self._client.chat.completions.create(**kw)
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
        )


Responder = Callable[[Messages, int], str]


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
