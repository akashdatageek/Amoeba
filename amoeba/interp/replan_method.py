"""D108 — a re-plan must change the method that failed.

In the hard probe both of H2's re-plans added steps with the same role, tools and query style as the failed step, and
they failed the same way. Here plain code checks every step a re-plan adds or rewrites: if it replaces a failed step
(it covers the same requirements, or it is the same role doing nearly the same thing), it must change the method in
at least one way its text states — a different tool (one the failed step never used, named in the step), a different
source type (data files or tables, official/government sources, an API, or a named site the failed step never read),
or a decomposed query (one search per entity, year or series). A step that repeats the failed method makes the whole
decision rejected, and the rejection is logged with what was repeated.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

TOOL_WORDS = {"web_search": r"\b(?:web[_ ]search|search)\b", "fetch_url": r"\b(?:fetch(?:_url)?|read the (?:page|source)|"
              r"download|open the (?:page|link))\b",
              "local:Bash": r"\b(?:bash|python|script|code|run|compute in the sandbox)\b",
              "local:Read": r"\b(?:read the file|local:read|open the file)\b", "calc": r"\b(?:calc|calculate|compute)\b",
              "local:Write": r"\b(?:write (?:a|the) file|save)\b"}
SOURCE_TYPES = {"data": r"\b(?:csv|xlsx|excel|spreadsheet|data ?file|dataset|data table|table [a-z]?-?\d+|download)\b",
                "official": r"\b(?:official|government|\.gov\b|agency|bureau|statistics office|census|bls|fred|eurostat)\b",
                "api": r"\bapi\b"}
SPLIT = re.compile(r"\b(?:one (?:search|query|lookup) (?:per|for each|at a time)|per (?:year|state|entity|series|country|"
                   r"region|item)|for each (?:year|state|entity|series|country|region|item)|separately|split (?:the|into))\b",
                   re.I)
DOMAIN = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:gov|org|com|edu|int|net|io)(?:\.[a-z]{2})?)\b", re.I)
STOP = {"the", "a", "an", "and", "of", "for", "to", "in", "on", "with", "from", "step", "data", "all", "each", "by"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9-]{2,}", (text or "").lower()) if w not in STOP}


# box: action_obs
def failed_method(meta: dict, role_tools: set[str], queries: list[str]) -> dict:
    """How a failed step worked: tools it used (or its roles held), source types and sites it read, its queries."""
    used = {c.get("tool") for c in meta.get("tool_calls") or [] if c.get("tool")} or set(role_tools)
    urls = [s.get("url", "") for s in meta.get("sources") or []]
    hosts = {(urlparse(u).hostname or "").lower().removeprefix("www.") for u in urls} - {""}
    from amoeba.tools.research import official
    kinds = ({"official"} if any(official(u) for u in urls) else set()) | \
        ({"data"} if any(s.get("data") for s in meta.get("sources") or []) else set())
    return {"step": meta.get("step"), "roles": list(meta.get("roles") or []), "tools": sorted(used),
            "source_types": sorted(kinds), "sites": sorted(hosts), "queries": queries[:6],
            "covers": list(meta.get("covers") or []), "text": meta.get("output_spec") or ""}


# box: action_obs
def replaces(step: dict, failed: dict[int, dict]) -> int | None:
    """The failed step a new or rewritten step replaces: same requirements covered, else same role with a near text."""
    covers = set(step["fields"].get("covers") or [])
    best = [(len(covers & set(f["covers"])), n) for n, f in failed.items() if covers & set(f["covers"])]
    if best:
        return max(best)[1]
    words = _words(step["text"] + " " + step["fields"].get("do", ""))
    for n, f in failed.items():
        fw = _words(f["text"] + " " + " ".join(f["queries"]))
        if set(step["roles"]) & set(f["roles"]) and words and len(words & fw) / max(1, len(words | fw)) >= 0.4:
            return n
    return None


# box: action_obs
def method_change(step: dict, f: dict, step_tools: set[str]) -> list[str]:
    """The ways the step's text changes the failed method (empty = it repeats it)."""
    text = " ".join([step["text"], *(str(v) for v in step["fields"].values() if isinstance(v, str))]).lower()
    out = []
    for t in sorted(step_tools - set(f["tools"])):
        if re.search(TOOL_WORDS.get(t, re.escape(t.lower())), text, re.I) or t.lower() in text:
            out.append(f"tool {t}")
    for kind, pat in SOURCE_TYPES.items():
        if kind not in f["source_types"] and re.search(pat, text, re.I):
            out.append(f"source type {kind}")
    sites = {d.lower().removeprefix("www.") for d in DOMAIN.findall(text)} - set(f["sites"])
    out += [f"site {d}" for d in sorted(sites)]
    if SPLIT.search(text):
        out.append("decomposed query")
    return out


# box: action_obs
def failed_methods_text(failed: dict[int, dict]) -> str:
    """What the observer is shown about each failed step's method (D108)."""
    lines = []
    for n, f in sorted(failed.items()):
        lines.append(f"- step {n} ({', '.join(f['roles'])}): tools {', '.join(f['tools']) or 'none'}; sources "
                     f"{', '.join(f['sites'][:6]) or 'none'} ({', '.join(f['source_types']) or 'no official or data source'});"
                     f" queries: {'; '.join(q[:100] for q in f['queries']) or 'none'}")
    return "\n".join(lines)
