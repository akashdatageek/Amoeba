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
from amoeba.llm.profiles import BOX2_GROUPS
from amoeba.task.parsers import MissingSections, parse_sections, repair_prompt, require


# D55: every trace line names the as-built page box (tools/arch_extract.py BOXES id) whose code wrote it, so the page
# can replay any run. Spans and events not listed here take the box of the span they happen inside.
SPAN_BOX = {"invoke_workflow": "interpreter", "execute_tool": "tools", "stock_toolbox": "toolbox"}
EVENT_BOX = {
    "capability_request": "capreq", "unknown_tool": "resolver", "blocked": "read_action",
    "draft_quality": "checks", "quality_gate": "checks", "draft_reused": "handoff", "intake_review": "planner",
    "truncated": "client", "rate_limited": "client", "cache_miss": "client", "api_error": "client",
    "plan_graph": "plan_graph", "dependency_relinked": "plan_graph", "step_input": "plan_step",
    "input_truncated": "plan_step", "collab_round": "plan_step", "review_unreadable": "plan_step",
    "step_done": "step_check", "check_retry": "step_check", "rework": "step_check", "reverify": "step_check",
    "stale": "step_check", "refine": "step_check", "verification_inferred": "step_check",
    "step_contract": "step_check", "contract_check": "step_check", "rework_skipped": "step_check",   # D61
    "provenance": "provenance", "figure_ledger": "provenance",
    "summary_check": "plan_summary", "limitations_added": "plan_summary", "answer_assembled_by_code": "plan_summary",
    "capability_mapped": "tools", "web_tools": "tools", "web_search": "tools", "fetch_url": "tools",
    "tool_error": "tools", "tool_limit": "tools", "pool_call": "tools",
    "pool_unavailable": "toolbox", "pool_match": "toolbox", "pool_vet": "toolbox", "pool_pinned": "toolbox",
    "pool_connect_failed": "toolbox", "pool_summary": "toolbox",
}
BOX2_BOX = {"planner": "planner", "agent_observer": "agent_obs", "plan_observer": "plan_obs"}


# box: trace
class TraceWriter:
    """Spans: invoke_workflow | invoke_agent | chat | execute_tool. Kept in memory and, if a path is given, appended
    to a JSONL file as they close."""

    def __init__(self, path: str | Path | None = None, episode_id: str | None = None, log_content: bool = False,
                 stamp: dict | None = None):
        self.path = Path(path) if path else None
        self.stamp = {k: v for k, v in (stamp or {}).items() if v is not None}   # D54: on every line (amoeba.profile)
        self.log_content = log_content   # also write each call's messages and reply (gen_ai.input/output.messages)
        self.episode_id = episode_id or str(uuid4())
        self.records: list[dict] = []
        self._boxes: list[str | None] = []     # the box of each open span, innermost last (D55)
        self._fh = None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self.path, "a", encoding="utf-8")

    @contextmanager
    def span(self, name: str, attrs: dict | None = None) -> Iterator[dict]:
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "episode_id": self.episode_id, "kind": "span",
               "name": name, **self.stamp}
        rec.update({k: v for k, v in (attrs or {}).items() if v is not None})
        rec["amoeba.box"] = rec.get("amoeba.box") or SPAN_BOX.get(name) or self.box
        self._boxes.append(rec["amoeba.box"])
        t0 = time.perf_counter()
        try:
            yield rec
        except BaseException as e:
            rec["error.type"] = type(e).__name__
            raise
        finally:
            self._boxes.pop()
            rec["latency_ms"] = int((time.perf_counter() - t0) * 1000)
            self._write(rec)

    @property
    def box(self) -> str | None:
        """The box of the innermost open span (None outside every span)."""
        return self._boxes[-1] if self._boxes else None

    # box: trace
    def event(self, name: str, attrs: dict | None = None) -> dict:
        """A point-in-time record (kind "event"), e.g. capability_request, unknown_tool, blocked."""
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "episode_id": self.episode_id, "kind": "event",
               "name": name, **self.stamp}
        rec.update({k: v for k, v in (attrs or {}).items() if v is not None})
        rec["amoeba.box"] = rec.get("amoeba.box") or EVENT_BOX.get(name) or self.box
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
    def total_reasoning_tokens(self) -> int:
        """Hidden reasoning tokens (D27), kept apart from total_tokens (visible input + output)."""
        return sum(r.get("amoeba.usage.reasoning_tokens", 0) for r in self.spans("chat"))

    @property
    def n_llm_calls(self) -> int:
        return len(self.spans("chat"))

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None


# box: trace
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

    # box: trace
    def chat_messages(self, messages: Messages, seed: int = 0, *, agent_id: str | None = None,
                      agent_name: str | None = None, max_tokens: int | None = None, role: str | None = None,
                      _retry: bool = False) -> ChatResponse:
        """role: the call's role group (D54; Box 2 callers are known by name). A profile's RoleRouter picks the
        group's model and, when the profile sets one, its reply limit."""
        group = role or BOX2_GROUPS.get(agent_name or "")
        llm, cap = self.llm.route(group) if hasattr(self.llm, "route") else (self.llm, None)
        if cap and not _retry:
            max_tokens = cap
        attrs = {"gen_ai.agent.id": agent_id, "gen_ai.agent.name": agent_name, "amoeba.role_group": group,
                 "amoeba.box": BOX2_BOX.get(agent_name or ""),
                 "gen_ai.request.model": llm.model, "gen_ai.request.max_tokens": max_tokens,
                 "amoeba.retry_of_truncated": True if _retry else None}
        limits = getattr(self.trace, "limits", None)   # D47: opt-in per-run limits, checked before the call
        if limits is not None and limits.active():
            limits.check(self.trace)
        with self.trace.span("chat", attrs) as rec:
            if self.trace.log_content:   # OTel GenAI opt-in content capture: the exact prompt, even if the call fails
                rec["gen_ai.input.messages"] = [dict(m) for m in messages]
            try:
                resp = llm.chat_messages(messages, seed, max_tokens=max_tokens)
            except Exception as e:     # D48: the rate-limit waits before a call that still failed are logged too
                self._log_retries(getattr(e, "amoeba_retries", []), agent_name, failed=True)
                raise
            self._log_retries(resp.retries, agent_name)
            if resp.retries:
                rec["amoeba.rate_limit_retries"] = len(resp.retries)
            if resp.throttle_wait_s:
                rec["amoeba.throttle_wait_s"] = resp.throttle_wait_s
            if self.trace.log_content:
                rec["gen_ai.output.messages"] = [{"role": "assistant", "content": resp.content}]
            rec["gen_ai.response.model"] = resp.model or llm.model   # D54: the exact name the API returned
            rec["gen_ai.usage.input_tokens"] = resp.input_tokens
            rec["gen_ai.usage.output_tokens"] = resp.output_tokens
            if resp.finish_reason:
                rec["gen_ai.response.finish_reasons"] = [resp.finish_reason]
            if resp.cached:
                rec["amoeba.cache_hit"] = True   # D46: replayed from the response cache; no call was made
            if resp.reasoning_tokens:
                rec["amoeba.usage.reasoning_tokens"] = resp.reasoning_tokens
                rec["amoeba.usage.reasoning_source"] = resp.reasoning_source
            if resp.finish_reason == "length":   # D24: the reply was cut off at max_tokens — flag it
                rec["amoeba.truncated"] = True
                self.trace.event("truncated", {"gen_ai.agent.name": agent_name, "gen_ai.agent.id": agent_id,
                                               "gen_ai.request.max_tokens": max_tokens,
                                               "gen_ai.usage.output_tokens": resp.output_tokens,
                                               "amoeba.usage.reasoning_tokens": resp.reasoning_tokens or None,
                                               "amoeba.retry": bool(max_tokens) and not _retry})
        self.listener.on_llm_call(agent_id, resp)
        if resp.finish_reason == "length" and max_tokens and not _retry:
            # D27: hidden reasoning can use up the limit; ask once more with double room, then accept whatever comes
            return self.chat_messages(messages, seed, agent_id=agent_id, agent_name=agent_name,
                                      max_tokens=2 * max_tokens, role=role, _retry=True)
        return resp

    def _log_retries(self, retries: list, agent_name: str | None, failed: bool = False) -> None:
        for r in retries:
            self.trace.event("rate_limited", {"gen_ai.agent.name": agent_name, "http.status_code": r["status"],
                                              "amoeba.wait_s": r["wait_s"], "amoeba.attempt": r["attempt"],
                                              "amoeba.retry_after": r["retry_after"], "amoeba.gave_up": failed,
                                              "amoeba.dropped": r.get("error")})   # D57: connection | timeout

    def chat(self, system: str, user: str, seed: int = 0, **ids) -> ChatResponse:
        return self.chat_messages([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                  seed, **ids)

    # box: split
    def chat_sections(self, system: str, user: str, keys: list[str], seed: int = 0, **ids
                      ) -> tuple[str, dict[str, str]]:
        """AutoAgents _aask_v1: parse '## Section' blocks; a missing one gets one LLM repair call, then raises."""
        raw = self.chat(system, user, seed, **ids).content
        try:
            return raw, require(parse_sections(raw), keys)
        except MissingSections as e:
            raw2 = self.chat(system, repair_prompt(user, raw, keys, str(e)), seed, **ids).content
            try:
                return raw2, require(parse_sections(raw2), keys)
            except MissingSections as e2:
                e2.raw = raw2   # the repaired reply, so a caller can still use the sections it did write
                raise
