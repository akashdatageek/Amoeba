"""TraceWriter — one JSONL line per span, OpenTelemetry GenAI attribute names — and the traced LLM wrapper.

Token counts are recorded from the API response and summed; nothing in Phase 1 enforces them.
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from amoeba.llm.client import ChatResponse, LLMClient, Messages
from amoeba.task.parsers import MissingSections, parse_sections, repair_prompt, require


class TraceWriter:
    """Spans: invoke_workflow | invoke_agent | chat | execute_tool. Kept in memory and, if a path is given, appended
    to a JSONL file as they close."""

    def __init__(self, path: str | Path | None = None, episode_id: str | None = None, log_content: bool = False):
        self.path = Path(path) if path else None
        self.log_content = log_content   # also write each call's messages and reply (gen_ai.input/output.messages)
        self.episode_id = episode_id or str(uuid4())
        self.records: list[dict] = []
        self._fh = None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self.path, "a", encoding="utf-8")

    @contextmanager
    def span(self, name: str, attrs: dict | None = None) -> Iterator[dict]:
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "episode_id": self.episode_id, "kind": "span",
               "name": name}
        rec.update({k: v for k, v in (attrs or {}).items() if v is not None})
        t0 = time.perf_counter()
        try:
            yield rec
        except BaseException as e:
            rec["error.type"] = type(e).__name__
            raise
        finally:
            rec["latency_ms"] = int((time.perf_counter() - t0) * 1000)
            self._write(rec)

    def event(self, name: str, attrs: dict | None = None) -> dict:
        """A point-in-time record (kind "event"), e.g. capability_request, unknown_tool, blocked."""
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "episode_id": self.episode_id, "kind": "event",
               "name": name}
        rec.update({k: v for k, v in (attrs or {}).items() if v is not None})
        self._write(rec)
        return rec

    def events(self, name: str | None = None) -> list[dict]:
        return [r for r in self.records if r.get("kind") == "event" and (name is None or r["name"] == name)]

    def _write(self, rec: dict) -> None:
        self.records.append(rec)
        if self._fh:
            self._fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            self._fh.flush()

    def spans(self, name: str | None = None) -> list[dict]:
        return [r for r in self.records if r.get("kind") == "span" and (name is None or r["name"] == name)]

    @property
    def total_tokens(self) -> int:
        return sum(r.get("gen_ai.usage.input_tokens", 0) + r.get("gen_ai.usage.output_tokens", 0)
                   for r in self.spans("chat"))

    @property
    def n_llm_calls(self) -> int:
        return len(self.spans("chat"))

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None


class NoopListener:
    """Phase 3's monitor implements these; Phase 1 passes a no-op so Interpreter's signature never changes."""

    def on_llm_call(self, agent_id: str | None, resp: ChatResponse) -> None:
        pass

    def on_tool_call(self, agent_id: str | None, result: str) -> None:
        pass


class TracedLLM:
    """Wraps an LLMClient so every call emits one ``chat`` span carrying the token counts the API returned."""

    def __init__(self, llm: LLMClient, trace: TraceWriter, listener: NoopListener | None = None):
        self.llm, self.trace, self.listener = llm, trace, listener or NoopListener()

    def chat_messages(self, messages: Messages, seed: int = 0, *, agent_id: str | None = None,
                      agent_name: str | None = None) -> ChatResponse:
        attrs = {"gen_ai.agent.id": agent_id, "gen_ai.agent.name": agent_name,
                 "gen_ai.request.model": self.llm.model}
        with self.trace.span("chat", attrs) as rec:
            if self.trace.log_content:   # OTel GenAI opt-in content capture: the exact prompt, even if the call fails
                rec["gen_ai.input.messages"] = [dict(m) for m in messages]
            resp = self.llm.chat_messages(messages, seed)
            if self.trace.log_content:
                rec["gen_ai.output.messages"] = [{"role": "assistant", "content": resp.content}]
            rec["gen_ai.request.model"] = resp.model or self.llm.model
            rec["gen_ai.usage.input_tokens"] = resp.input_tokens
            rec["gen_ai.usage.output_tokens"] = resp.output_tokens
        self.listener.on_llm_call(agent_id, resp)
        return resp

    def chat(self, system: str, user: str, seed: int = 0, **ids) -> ChatResponse:
        return self.chat_messages([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                  seed, **ids)

    def chat_sections(self, system: str, user: str, keys: list[str], seed: int = 0, **ids
                      ) -> tuple[str, dict[str, str]]:
        """AutoAgents _aask_v1: parse '## Section' blocks; a missing one gets one LLM repair call, then raises."""
        raw = self.chat(system, user, seed, **ids).content
        try:
            return raw, require(parse_sections(raw), keys)
        except MissingSections as e:
            raw2 = self.chat(system, repair_prompt(user, raw, keys, str(e)), seed, **ids).content
            return raw2, require(parse_sections(raw2), keys)
