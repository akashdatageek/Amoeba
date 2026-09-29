"""D77 — the user context file (--context user.yaml): who is asking, so the task can be read the way they mean it.

The first stub of the Memory box. It is read-only: loaded once per run, never written by a run. Keys kept:
location, organisation (or organization), role; anything else is ignored. The task interpretation step (Box 1 → 2)
reads it; nothing else does yet.
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
    return MappingProxyType(out)


# box: interpret
def context_text(ctx: Mapping[str, str]) -> str:
    return "\n".join(f"- {k}: {ctx[k]}" for k in KEYS if k in ctx) or "None given."
