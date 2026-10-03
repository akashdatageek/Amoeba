"""D84 — the ledger (Phase 2 spec §9.4): eval/loop/<stream>/ledger.jsonl, one row per event (calibration,
hypothesis, decision, reverted, unresolved). The source of the papers' adaptation tables; plain code reads it to
count hypotheses since the family's last accept (Bonferroni N) and the failed hypotheses (no repeats)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


# box: gate
class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def rows(self, family: str | None = None, event: str | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        out = [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]
        for r in out:                    # D84b: rows written before gate versions existed were decided under v1
            if r.get("event") == "decision":
                r.setdefault("gate_version", "v1")
        return [r for r in out if family in (None, r.get("family")) and event in (None, r.get("event"))]

    def append(self, row: dict) -> dict:
        row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **row}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def tried_since_accept(self, family: str) -> int:
        """Decided hypotheses of the family since its last accept (the next one makes N = this + 1)."""
        n = 0
        for r in self.rows(family, "decision"):
            n = 0 if r.get("decision") == "accept" else n + 1
        return n

    def failed(self, family: str) -> list[dict]:
        """The family's rejected hypotheses (edit and observed result), for the Architect and the repeat check."""
        return [r for r in self.rows(family, "decision") if r.get("decision") == "reject"]

    def calibration(self, family: str, recipe_hash: str, slice_key: str | None = None) -> dict | None:
        """The calibration of a recipe version on a held-out post slice (D84b: kept per slice; Stage A rows carry no
        slice and match slice_key None)."""
        rows = [r for r in self.rows(family, "calibration") if r.get("recipe_hash") == recipe_hash
                and r.get("slice") == slice_key]
        return rows[-1] if rows else None
