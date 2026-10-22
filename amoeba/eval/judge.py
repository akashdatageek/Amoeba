"""D161 — the frozen judge's hash. `amoeba/config/frozen.yaml` lists the judge files (D171: a path may hold `*`, and
every match is hashed with its own path); `judge_hash()` hashes them the
way the evidence log hashes a folder (amoeba/adapt/evidence.py: manifest_entries, sha256_text), so one digest names
exactly the judge a run was scored by. `same_judge()` refuses to compare runs whose hashes differ or are unknown."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from amoeba.adapt.evidence import manifest_entries, sha256_text

ROOT = Path(__file__).resolve().parents[2]
FROZEN = Path("amoeba") / "config" / "frozen.yaml"


# box: frozen_judge
class JudgeMismatch(ValueError):
    """Runs scored by different judges (or by an unknown one) are never compared."""


# box: frozen_judge
def frozen_paths(root: Path | None = None) -> list[str]:
    root = Path(root) if root is not None else ROOT
    return list((yaml.safe_load((root / FROZEN).read_text(encoding="utf-8")) or {}).get("paths") or [])


# box: frozen_judge
def judge_hash(root: Path | str | None = None) -> dict:
    """{"sha256": one digest, "paths": [{path, sha256 | "missing", files}]} for the judge files under root."""
    root = Path(root) if root is not None else ROOT
    parts = []
    for rel in frozen_paths(root):
        found = sorted(root.glob(rel)) if "*" in rel else ([root / rel] if (root / rel).exists() else [])   # D171
        entries = [([p.relative_to(root).as_posix()] if "*" in rel else []) + e for p in found
                   for e in manifest_entries(p) if "__pycache__" not in e[0]]
        parts.append({"path": rel, "sha256": sha256_text(json.dumps(entries, separators=(",", ":")))
                      if found else "missing", "files": len(entries)})
    return {"sha256": sha256_text(json.dumps(parts, separators=(",", ":"), sort_keys=True)), "paths": parts}


# box: frozen_judge
def same_judge(results: list[dict]) -> str:
    """The one judge hash all these results (result.json or sim_score.json dicts) share; JudgeMismatch otherwise."""
    hashes = [r.get("judge_hash") for r in results]
    if not hashes or any(not h for h in hashes):
        raise JudgeMismatch("a run has no judge hash: it cannot be compared")
    if len(set(hashes)) > 1:
        raise JudgeMismatch(f"the runs were scored by different judges: {sorted(set(h[:12] for h in hashes))}")
    return hashes[0]
