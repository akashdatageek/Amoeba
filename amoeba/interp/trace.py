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

from amoeba.llm.client import ChatResponse, LLMClient, Messages, opts_kw, tools_kw
from amoeba.llm.cache import is_blocked
from amoeba.llm.profiles import BOX2_GROUPS
from amoeba.task.parsers import MissingSections, parse_sections, repair_prompt, require, unglue


# D55: every trace line names the as-built page box (tools/arch_extract.py BOXES id) whose code wrote it, so the page
# can replay any run. Spans and events not listed here take the box of the span they happen inside.
SPAN_BOX = {"invoke_workflow": "interpreter", "execute_tool": "tools", "stock_toolbox": "toolbox"}
EVENT_BOX = {
    "capability_request": "capreq", "unknown_tool": "resolver", "blocked": "read_action",
    "draft_quality": "checks", "quality_gate": "checks", "draft_reused": "handoff", "intake_review": "planner",
    "task_interpretation": "interpret", "interpretation_question": "interpret",                            # D77
    "subject_questions_routed": "interpret", "assumption_stated": "interpret",
    "truncated": "client", "provider_blocked": "client", "rate_limited": "client", "cache_miss": "client", "api_error": "client",
    "prompt_asks_for_reasoning": "client", "compact_retry": "client",                                 # D134, D139
    "plan_graph": "plan_graph", "dependency_relinked": "plan_graph", "step_input": "plan_step",
    "input_truncated": "plan_step", "collab_round": "plan_step", "review_unreadable": "plan_step",
    "step_done": "step_check", "check_retry": "step_check", "rework": "step_check", "reverify": "step_check",
    "stale": "step_check", "refine": "step_check", "verification_inferred": "step_check",
    "step_contract": "step_check", "contract_check": "step_check", "rework_skipped": "step_check",   # D61
    "contract_checks": "step_check", "ask_schema_rejected": "client",                                # D142, D141
    "tool_result_spilled": "plan_step",                                                               # D144
    "verifier_tools": "step_check",                                                                   # D65
    "freshness": "plan_summary",                                                                      # D67
    "file_block_adapted": "read_action", "not_an_answer": "solver",                                   # D70
    "office_check": "localtools",                                                                     # D71
    "provenance": "provenance", "figure_ledger": "provenance",
    "summary_check": "plan_summary", "limitations_added": "plan_summary", "answer_assembled_by_code": "plan_summary",
    "capability_mapped": "tools", "web_tools": "tools", "web_search": "tools", "fetch_url": "tools",
    "tool_error": "tools", "tool_limit": "tools", "pool_call": "tools",
    "pool_unavailable": "toolbox", "pool_match": "toolbox", "pool_vet": "toolbox", "pool_pinned": "toolbox",
    "pool_connect_failed": "toolbox", "pool_summary": "toolbox", "pool_pick_reused": "toolbox",   # D70
    "pool_fallthrough": "toolbox", "citation_relabelled": "provenance", "repeated_tool_error": "plan_step",   # D131                                                                    # D127
    "replan_trigger": "action_obs", "replan_decision": "action_obs", "replan_validated": "action_obs",   # D63
    "plan_version": "action_obs", "requirement_status": "action_obs",
}
BOX2_BOX = {"planner": "planner", "agent_observer": "agent_obs", "plan_observer": "plan_obs",
            "interpreter": "interpret", "fix_proposer": "proposer",
            "plan_searcher": "interpret"}   # D77, D87 (D117: the in-task fix proposer), D120


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
        self.provider_blocked = 0              # D128: calls the provider blocked (content_filter), retries included
        self.reasoning_refusals: list[dict] = []   # D134: refusals because a prompt asks for the model's reasoning
        self.protocol = "legacy"               # D141: the run's protocol (legacy | v2); run_one and the plan runner set it
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


# box: router
def _route_attrs(dec: dict) -> dict:
    """D97: a routing decision as trace attributes."""
    return {f"amoeba.route.{k}": v for k, v in dec.items()}


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "config" / "prompts"


# box: trace
def _signatures() -> dict[str, str]:
    """D134: each prompt file's first long literal line (no {placeholder}), which a rendered prompt contains."""
    if not hasattr(_signatures, "cache"):
        sig = {}
        for f in sorted(PROMPTS_DIR.glob("*.txt")):
            for line in f.read_text(encoding="utf-8").splitlines()[1:]:
                if len(line.strip()) >= 30 and "{" not in line:
                    sig[f.name] = line.strip()
                    break
        _signatures.cache = sig
    return _signatures.cache


# box: trace
def prompt_sources(messages: Messages) -> list[str]:
    """D134: the prompt files (amoeba/config/prompts) a call's messages were rendered from, found by each file's
    first literal line; the files that ask for a '## Thought' section come first."""
    text = "\n".join(str(m.get("content") or "") for m in messages)
    found = [f for f, line in _signatures().items() if line in text]
    thought = [f for f in found if "## Thought" in (PROMPTS_DIR / f).read_text(encoding="utf-8")]
    return thought + [f for f in found if f not in thought]


class TracedLLM:
    """Wraps an LLMClient so every call emits one ``chat`` span carrying the token counts the API returned."""

    def __init__(self, llm: LLMClient, trace: TraceWriter, listener: NoopListener | None = None,
                 data_class: str = "normal"):
        self.llm, self.trace, self.listener = llm, trace, listener or NoopListener()
        self.data_class = data_class                  # D97: "sensitive" keeps the router to local models

    # box: trace
    def chat_messages(self, messages: Messages, seed: int = 0, *, agent_id: str | None = None,
                      agent_name: str | None = None, max_tokens: int | None = None, role: str | None = None,
                      step: int | None = None, checks=None, needs=(), _retry: bool = False,
                      _blocked_retry: bool = False, tools: list | None = None, compact: Messages | None = None,
                      **opts) -> ChatResponse:
        """role: the call's role group (D54; Box 2 callers are known by name). A profile's RoleRouter picks the
        group's model and, when the profile sets one, its reply limit. D97: with a ModelRouter every call states a
        CallSpec (role, step, size, needs, data class, the steps it checks) and the router picks the model.
        D134: opts (schema, effort, thinking_display, cache_prefix) go to the client as they are."""
        opts = opts_kw(opts)
        group = role or BOX2_GROUPS.get(agent_name or "")
        routed = hasattr(self.llm, "call") and hasattr(self.llm, "route") and hasattr(self.llm, "registry")
        if routed:
            llm, cap = self.llm, None
        else:
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
                if routed:                                 # D97: the router decides, and the decision is logged
                    from amoeba.llm.router import NoModelAvailable, spec_for
                    spec = spec_for(agent_name, group, messages, max_tokens, step, checks or (),
                                    (*needs, "tools") if tools else needs,      # D132: only models that call tools
                                    getattr(llm, "data_class", self.data_class))
                    try:
                        resp, dec = llm.call(spec, messages, seed, max_tokens, **tools_kw(tools), **opts)
                    except NoModelAvailable:
                        self.trace.event("route", {"amoeba.box": "router", **_route_attrs(llm.decisions[-1])})
                        self.trace.event("no_model", {"amoeba.box": "router", "amoeba.role": spec.role,
                                                      "amoeba.step": step})
                        raise
                    rec["gen_ai.request.model"] = llm.registry[dec["chosen"]].model
                    self.trace.event("route", {"amoeba.box": "router", **_route_attrs(dec)})
                else:
                    resp = llm.chat_messages(messages, seed, max_tokens=max_tokens, **tools_kw(tools), **opts)
            except Exception as e:     # D48: the rate-limit waits before a call that still failed are logged too
                self._log_retries(getattr(e, "amoeba_retries", []), agent_name, failed=True)
                raise
            self._log_retries(resp.retries, agent_name)
            if resp.retries:
                rec["amoeba.rate_limit_retries"] = len(resp.retries)
            if resp.throttle_wait_s:
                rec["amoeba.throttle_wait_s"] = resp.throttle_wait_s
            if tools:
                rec["amoeba.native_tools"] = len(tools)           # D132: the call offered tools natively
            if self.trace.log_content:
                rec["gen_ai.output.messages"] = [{"role": "assistant", "content": resp.content,
                                                  **({"tool_calls": resp.tool_calls} if resp.tool_calls else {})}]
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
            if resp.cache_read_tokens:                     # D134: the provider's prompt cache (Messages API)
                rec["amoeba.usage.cache_read_tokens"] = resp.cache_read_tokens
            if resp.cache_write_tokens:
                rec["amoeba.usage.cache_write_tokens"] = resp.cache_write_tokens
            if resp.refusal_category:
                rec["amoeba.refusal_category"] = resp.refusal_category
            if opts.get("schema") is not None:
                rec["amoeba.schema"] = getattr(opts["schema"], "__name__", str(opts["schema"]))
                rec["amoeba.schema_parsed"] = resp.parsed is not None
            if opts.get("effort"):
                rec["amoeba.effort"] = opts["effort"]
            if resp.thinking_summary and self.trace.log_content:
                rec["amoeba.thinking_summary"] = resp.thinking_summary
            if resp.finish_reason == "length":   # D24: the reply was cut off at max_tokens — flag it
                rec["amoeba.truncated"] = True
                self.trace.event("truncated", {"gen_ai.agent.name": agent_name, "gen_ai.agent.id": agent_id,
                                               "gen_ai.request.max_tokens": max_tokens,
                                               "gen_ai.usage.output_tokens": resp.output_tokens,
                                               "amoeba.usage.reasoning_tokens": resp.reasoning_tokens or None,
                                               "amoeba.retry": bool(max_tokens) and not _retry})
        self.listener.on_llm_call(agent_id, resp)
        if is_blocked(resp):
            # D134 (replaces D128's one identical retry, which was blocked the same way every time): no retry here.
            # A refusal because the prompt asks for the model's reasoning is the prompt's fault and is named loudly;
            # any other block (a category, or none) is the caller's turn to handle (routed mode already asked the next
            # candidate model, router.py)
            self.trace.provider_blocked += 1
            category = resp.refusal_category
            self.trace.event("provider_blocked", {"gen_ai.agent.name": agent_name, "gen_ai.agent.id": agent_id,
                                                  "gen_ai.response.finish_reasons": [resp.finish_reason],
                                                  "amoeba.refusal_category": category,
                                                  "amoeba.step": step, "amoeba.retry": False})
            if category == "reasoning_extraction":
                files = prompt_sources(messages)
                rec = {"agent": agent_name, "step": step, "prompt_files": files}
                self.trace.reasoning_refusals.append(rec)
                self.trace.event("prompt_asks_for_reasoning", {
                    "gen_ai.agent.name": agent_name, "amoeba.step": step, "amoeba.prompt_files": files,
                    "amoeba.note": "the model refused because this prompt asks it to write out its reasoning "
                                   "(a '## Thought' section); the turn is unreadable — fix the prompt (--protocol v2)"})
            elif compact and not _blocked_retry:
                # D139: any other block is sent once more, as the compact variant of the same prompt (D141)
                self.trace.event("compact_retry", {"gen_ai.agent.name": agent_name, "amoeba.step": step,
                                                   "amoeba.refusal_category": category})
                return self.chat_messages(compact, seed, agent_id=agent_id, agent_name=agent_name,
                                          max_tokens=max_tokens, role=role, step=step, checks=checks, needs=needs,
                                          _retry=_retry, _blocked_retry=True, tools=tools, **opts)
        if resp.finish_reason == "length" and max_tokens and not _retry:
            # D27: hidden reasoning can use up the limit; ask once more with double room, then accept whatever comes
            return self.chat_messages(messages, seed, agent_id=agent_id, agent_name=agent_name,
                                      max_tokens=2 * max_tokens, role=role, step=step, checks=checks, needs=needs,
                                      _retry=True, tools=tools, **opts)
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
        """AutoAgents _aask_v1: parse '## Section' blocks; a missing one gets one LLM repair call, then raises.
        D128: a reply the provider blocked gets no repair call (it would be blocked too); MissingSections carries
        blocked=True so the caller counts the turn as blocked, not as a format slip."""
        resp = self.chat(system, user, seed, **ids)
        raw = resp.content
        try:
            return raw, self._sections(raw, keys, ids)
        except MissingSections as e:
            if is_blocked(resp):
                e.raw, e.blocked, e.category = raw, True, resp.refusal_category    # D134: the refusal category
                raise
            raw2 = self.chat(system, repair_prompt(user, raw, keys, str(e)), seed, **ids).content
            try:
                return raw2, self._sections(raw2, keys, ids)
            except MissingSections as e2:
                e2.raw = raw2   # the repaired reply, so a caller can still use the sections it did write
                raise

    # box: split
    def _sections(self, raw: str, keys: list[str], ids: dict) -> dict[str, str]:
        """D123: a reply missing a required heading is read once more with the heading unglued (plain code, no call)
        before the repair call is made; a reply read that way is a `sections_unglued` event."""
        try:
            return require(parse_sections(raw), keys)
        except MissingSections as e:
            fixed = unglue(raw, e.missing)
            if fixed == raw:
                raise
            sec = require(parse_sections(fixed), keys)
            self.trace.event("sections_unglued", {"amoeba.box": "split", "amoeba.sections": e.missing,
                                                  "gen_ai.agent.name": ids.get("agent_name")})
            return sec
