"""D77 — the user context file (--context user.yaml): who is asking, so the task can be read the way they mean it.

The first stub of the Memory box. It is read-only: loaded once per run, never written by a run. Keys kept:
location, organisation (or organization), role, standards; anything else is ignored. The task interpretation step
(Box 1 → 2) reads it, and Box 2's Planner and Plan Observer read its standards.

`standards:` holds lasting preferences the user wrote ("answers end with an Assumptions section"); an older entry with
`approved:` (from D99's proposals, removed by D117) still counts. No run and no agent writes this file.
"""
from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

KEYS = ("location", "organisation", "role")
ALIASES = {"organization": "organisation", "org": "organisation", "city": "location"}


# box: interpret
def load_context(path: str | Path | None) -> Mapping[str, str]:
    """The user context as a read-only mapping (empty when no file is given)."""
    if not path:
        return MappingProxyType({})
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the context file must be a mapping such as 'organisation: ...'")
    out = {}
    for k, v in data.items():
        key = ALIASES.get(str(k).strip().lower(), str(k).strip().lower())
        if key in KEYS and isinstance(v, (str, int, float)) and str(v).strip():
            out[key] = str(v).strip()
    stds = approved_standards(data.get("standards"))
    if stds:
        out["standards"] = stds
    return MappingProxyType(out)


# box: interpret
def approved_standards(entries) -> tuple[str, ...]:
    """D99: the standards that count — the user's own plain lines and entries carrying `approved:`; a proposal
    copied in without approval is ignored."""
    out = []
    for e in entries or []:
        if isinstance(e, str) and e.strip():
            out.append(e.strip())
        elif isinstance(e, dict) and e.get("approved") and str(e.get("text") or "").strip():
            out.append(str(e["text"]).strip())
    return tuple(out)


# box: interpret
def context_text(ctx: Mapping) -> str:
    lines = [f"- {k}: {ctx[k]}" for k in KEYS if k in ctx]
    lines += [f"- standard: {s}" for s in ctx.get("standards", ())]
    return "\n".join(lines) or "None given."


STANDARDS_HEAD = "\n\n# The user's standards (lasting preferences they approved)\n"
STANDARDS_TAIL = {"planner": "Plan so the final answer meets each standard.",
                  "plan_observer": "Check item: the plan lets the final answer meet each standard; report each one it "
                                   "does not as a problem."}


# box: interpret
def standards_slots(ctx: Mapping | None) -> dict[str, str]:
    """D99: Box 2's text for the approved standards, per reader (appended to the {lessons} slot); {} without any,
    so the prompts stay byte-identical."""
    stds = (ctx or {}).get("standards") or ()
    if not stds:
        return {}
    body = "\n".join(f"- {s}" for s in stds)
    return {who: f"{STANDARDS_HEAD}{body}\n{tail}" for who, tail in STANDARDS_TAIL.items()}
