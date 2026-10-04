"""D77 — the user context file (--context user.yaml): who is asking, so the task can be read the way they mean it.

The first stub of the Memory box. It is read-only: loaded once per run, never written by a run. Keys kept:
location, organisation (or organization), role, standards; anything else is ignored. The task interpretation step
(Box 1 → 2) reads it, and Box 2's Planner and Plan Observer read its standards.

D99 — user memory: `standards:` holds lasting user preferences ("answers end with an Assumptions section"). A line
counts only when the user wrote it (a plain string) or approved it (an entry with `approved:`). The loop may only
PROPOSE a line (`propose_standards`: the same feedback item failed in ≥3 practice runs across ≥2 task families →
eval/loop/<stream>/memory_proposals.jsonl); `scripts/approve_memory.py` is the only writer of an approved line and logs
the approval in events.jsonl. No run and no agent writes this file.
"""
from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import json
from datetime import datetime, timezone

import yaml

KEYS = ("location", "organisation", "role")
PROPOSE_RUNS, PROPOSE_FAMILIES = 3, 2           # D99: a proposal needs the same item failing this widely
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# box: memory
def read_proposals(root: str | Path) -> list[dict]:
    f = Path(root) / "memory_proposals.jsonl"
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()] if f.exists() else []


# box: memory
def propose_standards(records, root: str | Path, ev=None, runs: int = PROPOSE_RUNS,
                      families: int = PROPOSE_FAMILIES) -> list[dict]:
    """D99: the loop's only way toward user memory. A feedback item failed in ≥`runs` practice runs across
    ≥`families` task families becomes one proposal row (once per item) in memory_proposals.jsonl and an event; it
    enters user memory only through scripts/approve_memory.py."""
    seen: dict[str, dict] = {}
    for r in records:
        for item in r.failed_items:
            s = seen.setdefault(item, {"runs": [], "families": set()})
            s["runs"].append(r.order)
            s["families"].add(r.family)
    have = {p["item"] for p in read_proposals(root)}
    new = []
    for item, s in sorted(seen.items()):
        if item in have or len(s["runs"]) < runs or len(s["families"]) < families:
            continue
        row = {"id": f"P{len(have) + len(new) + 1}", "ts": _now(), "item": item,
               "text": f"Answers satisfy the requirement '{item}'.", "runs": sorted(s["runs"]),
               "families": sorted(s["families"]), "status": "proposed"}
        new.append(row)
    if new:
        Path(root).mkdir(parents=True, exist_ok=True)
        with open(Path(root) / "memory_proposals.jsonl", "a", encoding="utf-8") as fh:
            for row in new:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                if ev is not None:
                    ev.append("memory_proposal", row, key=f"memory_proposal:{row['id']}")
    return new


# box: memory
def approve_standard(context_file: str | Path, proposal: dict, text: str | None = None, ev=None) -> dict:
    """D99: the user's approval (scripts/approve_memory.py): the proposal's line (or the user's rewording) is added
    to `standards:` with `approved:` and the proposal id, and the approval is an events.jsonl row. A proposal is
    approved once."""
    path = Path(context_file)
    data = (yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the context file must be a mapping")
    stds = list(data.get("standards") or [])
    if any(isinstance(e, dict) and e.get("proposal") == proposal["id"] for e in stds):
        raise ValueError(f"proposal {proposal['id']} is already approved")
    entry = {"text": (text or proposal["text"]).strip(), "approved": _now(), "proposal": proposal["id"],
             "item": proposal["item"]}
    data["standards"] = stds + [entry]
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    if ev is not None:
        ev.append("memory_approval", {**entry, "context_file": path.name}, key=f"memory_approval:{proposal['id']}")
    return entry
