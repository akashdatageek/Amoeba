"""D56 — Box 3 starts by stocking the toolbox: each capability request Box 2 recorded may be filled from the pool.

LLM proposes, plain code disposes. For every request (deduplicated by kind, standard name and helper):
  1. match  (code)  keyword overlap with the cached pool index; the best `max_candidates`, tools and skills alike
                    (D58: the request's kind is only the planner's guess; the kind asked and picked are logged).
                    None above zero → unfilled, "no_candidates", and no AI call.
  2. pick   (AI)    one call in the "pool" role group: exactly one listed id, or NONE. Anything else is NONE.
  3. vet    (code)  tools: an HTTPS remote, a source repository, a pinned version, no key needed or the key in the
                    environment, the description unchanged since the index was built; after connecting, the
                    server's tools/list must match its pins. Skills: instruction-only (no scripts) and a short
                    body. Caps per helper and per run. The first failing rule is recorded as the reason.
  4. attach (code)  a tool becomes `pool:<name>` in this run's ToolRegistry, for the requesting helper(s) only; a
                    skill's SKILL.md body goes on that helper's role card. Both only inside POOL DATA blocks.
The step runs before the runner is chosen, so flat, boss_reviewers and plan runs all see what was attached.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from amoeba.config.prompts import PROMPT, render
from amoeba.config.schema import AgentSpec, TeamConfig
from amoeba.interp.trace import NoopListener, TracedLLM, TraceWriter
from amoeba.pool.index import load_index, load_pool_config, skill_body, text_sha256
from amoeba.pool.match import rank
from amoeba.pool.mcp import PoolLimits, PoolTools, SdkConnector, SourceBook, data_block, listing_digest
from amoeba.tools.registry import ToolRegistry

PICKER = "pool_picker"
THINKING = re.compile(r"<(thought|think|thinking)>.*?</\1>", re.S | re.I)
NONE = "NONE"
VERSION = re.compile(r"^v?\d+(\.\d+)*([-+][0-9A-Za-z.-]+)?$")
# D58: read-only tools only for now — a tool that says it acts outside (sends, posts, pays, deletes …) is refused.
# D60: also a tool that creates or changes anything in an outside service or account (a deck, doc or sheet is made
# locally with local tools instead)
SIDE_EFFECT = re.compile(r"\b(send|sends|sending|sent|e-?mails?|e-?mailing|mails?|mailing|mailer|post|posts|posting|"
                         r"publish\w*|pay|pays|paying|payments?|purchas\w*|delet\w*|write to|"
                         r"create|creates|creating|update|updating|upload|uploads|uploading|modify|modifies|"
                         r"modifying|edit|edits|editing|insert|inserts|inserting|remove|removes|removing|rename|"
                         r"renames|renaming|submit|submits|submitting|write|writes|writing|overwrite\w*|"
                         r"append|appends|appending)\b", re.I)


# box: toolbox
def side_effect(*texts: str) -> str | None:
    """The first outside-action word in a tool's name or description (names are split at - _ . /), or None."""
    for t in texts:
        m = SIDE_EFFECT.search(re.sub(r"[-_./]", " ", t or ""))
        if m:
            return m.group(0)
    return None


# box: toolbox
def paid_host(url: str, setup: "PoolSetup") -> bool:
    """D58: a host under a domain pool.yaml lists as pay-per-call (e.g. *.klymax402.com, x402 endpoints)."""
    host = (urlparse(url).hostname or "").lower()
    domains = [d.lower().lstrip("*.") for d in setup.config.get("paid_hosts") or []]
    return any(host == d or host.endswith("." + d) for d in domains)


# box: toolbox
@dataclass
class PoolSetup:
    """What a run needs to stock its toolbox: pool.yaml, where the cache is, how to reach a server, the env."""

    config: dict = field(default_factory=load_pool_config)
    cache_dir: str | Path | None = None               # default: pool.yaml's cache_dir
    connector: Any = None                             # default: SdkConnector (the MCP Python SDK over HTTPS)
    env: Mapping[str, str] = field(default_factory=lambda: os.environ)

    @property
    def dir(self) -> Path:
        return Path(self.cache_dir or self.config["cache_dir"])

    @property
    def limits(self) -> dict:
        return self.config["limits"]


# box: toolbox
def pick(llm: TracedLLM, q, helper: str, steps: str, candidates: list[dict], seed: int = 0,
         max_tokens: int | None = None) -> str | None:
    """The one AI call: the request and its candidates in, one listed id (or None) out. Parsed strictly.
    D60: max_tokens gives the reply room (pool.yaml pick_max_tokens); a reply cut off at it is asked once more with
    twice the room (TracedLLM, D27)."""
    lines = "\n".join(f"- id: {e['id']} | name: {e.get('title') or e['name']} | kind: {e['kind']} | description: "
                      f"{' '.join((e.get('description') or '').split())[:240]}" for e in candidates)
    user = render(PROMPT.pool_pick, kind=q.kind, name=q.canonical or q.name, what=q.what_it_does or "(not given)",
                  input=q.input or "(not given)", output=q.output or "(not given)", helper=helper,
                  steps=steps or "(not given)", candidates=data_block("pool candidates", lines))
    reply = llm.chat_messages([{"role": "user", "content": user}], seed, agent_name=PICKER, role="pool",
                              max_tokens=max_tokens).content
    # D58: Gemma writes its reasoning into the reply as <thought>…</thought> before the answer; the answer is what
    # follows a closed thinking block (an unclosed block leaves nothing that can match an id)
    answer = THINKING.sub("", reply or "").strip().strip("`'\"").strip()
    ids = {e["id"] for e in candidates}
    return answer if answer in ids else None


# box: toolbox
def vet(e: dict, setup: PoolSetup) -> tuple[str | None, dict, str | None]:
    """(reason it is refused or None, auth headers for a tool, skill body). The first failing rule wins."""
    lim = setup.limits
    if e["kind"] == "skill":
        if e.get("has_scripts"):
            return "has_scripts", {}, None
        body = skill_body(setup.dir, e)
        if body is None:
            return "body_missing", {}, None
        if len(body) > int(lim["max_skill_chars"]) or int(e.get("body_length", 0)) > int(lim["max_skill_chars"]):
            return "too_long", {}, None
        return None, {}, body
    if not e.get("remote_url", "").startswith("https://") or e.get("transport") not in ("streamable-http", "sse"):
        return "not_remote", {}, None
    if paid_host(e["remote_url"], setup):
        return "paid_endpoint", {}, None
    if side_effect(e.get("name", ""), e.get("title", ""), e.get("description", "")):
        return "side_effect", {}, None
    if not e.get("source_repo"):
        return "no_source", {}, None
    if not VERSION.match(e.get("version") or ""):
        return "no_version", {}, None
    headers: dict[str, str] = {}
    if e.get("auth_required"):
        a = (setup.config.get("auth_env") or {}).get(e["name"]) or {}
        key = setup.env.get(a.get("env", "")) if a.get("env") else None
        if not key or not a.get("header") or re.search(r"\{\w+\}", e["remote_url"]):
            return "auth_missing", {}, None
        headers[a["header"]] = str(a.get("format", "{key}")).replace("{key}", key)
    if text_sha256(e.get("description", "")) != e.get("description_sha256"):
        return "description_changed", {}, None
    return None, headers, None


# box: toolbox
def helpers_for(q, cfg: TeamConfig) -> list[AgentSpec]:
    """The helper(s) a request is for: its for_role, else every helper whose missing tools name it."""
    named = [a for a in cfg.agents.values() if q.for_role and a.name == q.for_role]
    return named or [a for a in cfg.agents.values() if q.name in a.missing_tools]


# box: toolbox
def steps_of(cfg: TeamConfig, agents: list[AgentSpec]) -> str:
    ids = {a.agent_id for a in agents}
    return " | ".join(f"{s.index + 1}. {s.text[:160]}" for s in cfg.plan if ids & set(s.agent_ids))[:500]


# box: toolbox
def _pins(setup: PoolSetup) -> dict:
    try:
        return json.loads((setup.dir / "pins.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# box: toolbox
def stock_toolbox(requests: list, cfg: TeamConfig, tools: ToolRegistry, llm, trace: TraceWriter,
                  setup: PoolSetup | None, seed: int = 0, local=None) -> tuple[ToolRegistry, dict]:
    """Fill what it can of `requests` (Box 2's capability requests) from the cached pool. Changes cfg's helpers
    (tools, missing tools, pool items) and each request's status / pool_id / candidates / reason. Returns the run's
    registry (a copy holding the pool tools when any were attached) and a summary for result.json.
    local: D59 — a LocalToolbox (--local-tools on): its items are candidates too, ranked first; setup may then be
    None (--no-pool: local items only)."""
    summary = {"status": "ran", "filled": 0, "unfilled": 0, "llm_calls": 0, "reasons": {}, "attached": []}
    index = load_index(setup.dir) if setup is not None else None
    if index is None and local is None:
        trace.event("pool_unavailable", {"amoeba.box": "toolbox", "amoeba.pool.cache_dir": str(setup.dir)})
        for q in requests:
            q.status, q.reason = "unfilled", "pool_unavailable"
        return tools, {**summary, "status": "unavailable", "unfilled": len(requests),
                       "reasons": {"pool_unavailable": len(requests)} if requests else {}}
    if index is None and setup is not None:   # D59: no pool cache, but local items can still fill requests
        trace.event("pool_unavailable", {"amoeba.box": "toolbox", "amoeba.pool.cache_dir": str(setup.dir)})
    pool_on = setup is not None
    setup = setup or PoolSetup()
    lim = setup.limits
    entries = (index or {}).get("entries") or []
    traced = TracedLLM(llm, trace, NoopListener())
    reg, pool = tools, None
    if local is not None:                     # D59: start claude mcp serve; skills come from the local listing
        local.start()
        entries = [e for e in entries if e["kind"] != "skill"]
        reg = tools.copy()
        reg.local = local
        local.book = getattr(tools, "web", None) or SourceBook()   # D61 (G7): one [S#] list with web and pool
    per_helper: dict[str, set[str]] = {}
    attached: set[str] = set()
    pins, pins_changed = _pins(setup), False
    groups: dict[tuple, list] = {}
    for q in requests:
        groups.setdefault((q.kind, (q.canonical or q.name).lower(), q.for_role), []).append(q)
    with trace.span("stock_toolbox", {"amoeba.box": "toolbox", "amoeba.pool.requests": len(requests),
                                      "amoeba.pool.entries": len(entries),
                                      "amoeba.pool.refreshed_at": (index or {}).get("refreshed_at")}):
        for group in groups.values():
            q = group[0]
            out = {"status": "unfilled", "pool_id": "", "candidates": [], "reason": ""}
            helpers = helpers_for(q, cfg)
            if q.kind == "tool" and (q.canonical in tools or q.name in tools):
                out["reason"] = "registered_tool"      # an existing tool covers it (e.g. web_search, D32)
            elif not helpers:
                out["reason"] = "no_helper"
            else:
                top = int(lim["max_candidates"])
                ranked = rank(q, entries, int(lim.get("vet_depth", 10 * top)))
                if local is not None:         # D59: local candidates join the internet ones
                    near = local.candidates(q, top)
                    ids = {e["id"] for _, e in near}
                    ranked = [x for x in ranked if x[1]["id"] not in ids]
                    # D61 (P14): a local item goes first only when an alias names it or it matches at least as
                    # well as the best internet candidate; the rest take their place by score (internet first on a tie)
                    best = ranked[0][0] if ranked else 0
                    first = [x for x in near if x[0] >= 100 or x[0] >= best]
                    ranked = first + sorted(ranked + [x for x in near if x not in first], key=lambda x: -x[0])
                # D60: vet before the pick — the picker is shown only candidates that pass, the best `top` of them
                shown, refused, verdicts = [], [], {}
                for s, e in ranked:
                    v = (local.vet(e), {}, None) if e.get("source") == "local" else vet(e, setup)
                    if v[0] is None:
                        shown.append((s, e))
                        verdicts[e["id"]] = v
                        if len(shown) == top:
                            break
                    else:
                        refused.append({"id": e["id"], "reason": v[0]})
                out["candidates"] = [e["id"] for _, e in shown]
                trace.event("pool_match", {"amoeba.capability": q.canonical or q.name, "amoeba.kind": q.kind,
                                           "gen_ai.agent.name": q.for_role or None,
                                           "amoeba.pool.candidates": [{"id": e["id"], "kind": e["kind"], "score": s}
                                                                      | ({"source": "local"} if e.get("source") == "local"
                                                                         else {}) for s, e in shown],
                                           "amoeba.pool.refused": refused})
                if not shown:
                    out["reason"] = "all_refused" if ranked else "no_candidates"   # no AI call either way
                else:
                    before = trace.n_llm_calls
                    chosen = pick(traced, q, ", ".join(a.name for a in helpers), steps_of(cfg, helpers),
                                  [e for _, e in shown], seed, max_tokens=int(lim.get("pick_max_tokens", 0)) or None)
                    summary["llm_calls"] += trace.n_llm_calls - before
                    entry = next((e for _, e in shown if e["id"] == chosen), None)
                    out["pool_id"] = chosen or ""
                    near = entry is not None and entry.get("source") == "local"            # D59
                    reason, headers, body = verdicts[chosen] if entry else ("pick_none", {}, None)
                    takers = [a for a in helpers if len(per_helper.get(a.agent_id, set()) - {chosen})
                              < int(lim["max_per_helper"])]
                    if reason is None and (not takers or (chosen not in attached
                                                          and len(attached) >= int(lim["max_per_run"]))):
                        reason = "cap_reached"
                    name = (entry["name"] if near else f"pool:{entry['name']}") if entry else ""
                    if reason is None and entry["kind"] == "tool" and not near and (pool is None or name not in pool.items):
                        if pool is None:
                            reg = tools.copy() if reg is tools else reg
                            pool = PoolTools(setup.connector or SdkConnector(float(lim["timeout_s"])),
                                             PoolLimits(int(lim["max_calls_per_step"]), float(lim["timeout_s"]),
                                                        int(lim["max_result_chars"])),
                                             book=getattr(local, "book", None) or getattr(tools, "web", None)
                                             or SourceBook(), trace=trace)
                            reg.pool = pool
                        try:
                            listing = pool.connector.tools(entry, headers)
                        except Exception as e:           # unreachable server: not attached, the run goes on
                            reason = "connect_failed"
                            trace.event("pool_connect_failed", {"amoeba.pool.id": entry["id"],
                                                                "error.type": f"{type(e).__name__}: {e}"[:300]})
                        else:
                            digest = listing_digest(listing)
                            if entry["id"] in pins and pins[entry["id"]].get("tools") != digest:
                                reason = "description_changed"
                            elif not listing:
                                reason = "no_tools"
                            elif any(side_effect(t["name"], t.get("description", "")) for t in listing):
                                reason = "side_effect"      # D58: a server that also offers an acting tool
                            else:
                                if entry["id"] not in pins:  # first use: pin what the server says now
                                    pins[entry["id"]] = {"version": entry.get("version"), "tools": digest}
                                    pins_changed = True
                                    trace.event("pool_pinned", {"amoeba.pool.id": entry["id"],
                                                                "amoeba.pool.tools": sorted(digest)})
                                pool.add_server(name, entry, headers, listing)
                                reg.register(name, f"pool tool {entry['name']} (MCP, D56)",
                                             lambda text, _n=name: pool.call(_n, text))
                    if reason is None:
                        for a in takers:
                            if near:                  # D59: a local tool, or a local skill (folder copied)
                                if entry["kind"] == "tool":
                                    local.attach_tool(a, name, reg, request=q.name)
                                else:
                                    local.attach_skill(a, entry, reg, request=q.name)
                                a.missing_tools = [t for t in a.missing_tools if t not in (q.name, q.canonical)]
                            else:
                                attach(a, entry, name, body, pool, q)
                            per_helper.setdefault(a.agent_id, set()).add(chosen)
                        attached.add(chosen)
                        out["status"] = "filled"
                        summary["attached"].append({"id": chosen, "kind": entry["kind"], "kind_requested": q.kind,
                                                    "as": name if entry["kind"] == "tool" else entry["name"],
                                                    "helpers": [a.name for a in takers]}
                                                   | ({"source": "local"} if near else {}))
                    out["reason"] = reason or ""
                    trace.event("pool_vet", {"amoeba.pool.id": chosen, "amoeba.capability": q.canonical or q.name,
                                             "amoeba.kind_requested": q.kind,                       # D58: the guess
                                             "amoeba.kind_picked": entry["kind"] if entry else None,  # what was chosen
                                             "amoeba.accepted": reason is None, "amoeba.reason": reason})
            for r in group:
                r.status, r.pool_id, r.candidates, r.reason = out["status"], out["pool_id"], out["candidates"], out["reason"]
            summary["filled" if out["status"] == "filled" else "unfilled"] += len(group)
            if out["reason"]:
                summary["reasons"][out["reason"]] = summary["reasons"].get(out["reason"], 0) + len(group)
        if local is not None:                 # D59: what the local server offered
            summary["local"] = {"server": getattr(local.server, "info", None), "error": local.error,
                                "exposed": [f"local:{n}" for n in local.exposed], "skills_listed": len(local.skills)}
            summary["pool"] = "ran" if index is not None else "unavailable" if pool_on else "off"
        trace.event("pool_summary", {f"amoeba.pool.{k}": v for k, v in summary.items() if k not in ("attached", "local")}
                    | {"amoeba.pool.attached": [a["as"] for a in summary["attached"]]})
    if pins_changed:
        try:
            (setup.dir / "pins.json").write_text(json.dumps(pins, indent=1, sort_keys=True), encoding="utf-8")
        except OSError as e:                  # a read-only cache: the pins hold for this run only
            trace.event("pool_pinned", {"amoeba.box": "toolbox", "error.type": f"pins.json not written: {e}"[:300]})
    return reg, summary


# box: toolbox
def attach(a: AgentSpec, entry: dict, name: str, body: str | None, pool: PoolTools | None, q) -> None:
    """Give one helper the item: a tool joins its tools (and is described on its prompt), a skill joins its card.
    The request's 'Tool X is unavailable this run' line goes away."""
    if entry["kind"] == "tool":
        if name not in a.tools:
            a.tools.append(name)
        a.pool.append({"kind": "tool", "id": entry["id"], "name": name, "request": q.name,
                       "text": data_block(f"tool {name}", pool.description(name))})
    else:
        label = f"Skill: {entry['name']} (from {entry.get('repo') or entry.get('source_repo')}@{entry.get('commit', '')[:12]})"
        a.pool.append({"kind": "skill", "id": entry["id"], "name": entry["name"],
                       "text": f"{label}\n{data_block('skill ' + entry['name'], body or '')}"})
    a.missing_tools = [t for t in a.missing_tools if t not in (q.name, q.canonical)]


# box: toolbox
def pool_tool_notes(agent: AgentSpec) -> list[str]:
    """Lines for a helper's prompt: how to use each pool tool it was given (as data)."""
    return [f"You may use {p['name']} (" + ("local, sandboxed" if p.get("source") == "local" else "from the pool")
            + f"):\n{p['text']}" for p in agent.pool if p["kind"] == "tool"]


# box: toolbox
def pool_skill_notes(agent: AgentSpec) -> list[str]:
    return [p["text"] for p in agent.pool if p["kind"] == "skill"]
