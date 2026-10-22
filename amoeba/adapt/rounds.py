"""D162 — Box 4 saves every round. One row per round in <run>/rounds.jsonl and the same row as a `round` event in the
hash-chained events.jsonl (amoeba/adapt/evidence.py): the task, the niche (recorded, never used to split), the
cause, each edit with its scope and `because` quote, each probe's result (status, cleared / kept / new signals,
tokens, samples), the pick and its reason, and the step's status after the round. The single rung is recorded in the
same shape with one probe. A closing `run_end` row carries the run's sim_score (D161). No model call is made here
and nothing about the run changes; D163's verdicts and lessons are read from these rows."""
from __future__ import annotations

import json
from pathlib import Path

from amoeba.adapt.evidence import EvidenceLog

ROUNDS = "rounds.jsonl"
PROBE_KEYS = ("scope", "op", "params", "status", "limited", "cleared", "kept", "new", "tokens", "turns", "samples",
              "composed_of")


# box: rounds
def niche_of(r) -> str:
    """The run's niche profile name ("general" without one): recorded on every row, never used to split."""
    return getattr(getattr(r.i.tools, "niche", None), "name", None) or "general"


# box: rounds
def round_row(r, n: int, rnd: dict, mode: str, outcome: str) -> dict:
    """The row for one finished round of step n (rnd: the round record probe.py or the single rung built)."""
    art = r.artifacts.get(n)
    status = art["meta"]["status"] if art else ("replanned" if outcome == "replanned" else None)
    return {"kind": "round", "task_id": r.task.id, "niche": niche_of(r), "step": n, "cause": rnd.get("cause"),
            "mode": mode, "signals": list(rnd.get("signals") or []),
            "edits": [{"scope": c["scope"], "op": c["op"], "params": c.get("params") or {},
                       "because": c.get("because") or ""} for c in rnd.get("candidates") or [] if c.get("op")],
            "probes": [{k: p[k] for k in PROBE_KEYS if k in p} for p in rnd.get("probes") or []],
            "pick": rnd.get("pick"), "pick_reason": rnd.get("pick_reason") or "", "base": rnd.get("base"),
            "flags": {k: rnd[k] for k in ("complementary", "shared_failure") if k in rnd},
            "step_status": status, "outcome": outcome}


# box: rounds
def write_round(r, row: dict) -> dict:
    """Append the row to <run>/rounds.jsonl and to events.jsonl (event `round`); nothing without a run folder."""
    run_dir = getattr(r, "run_dir", None)
    if run_dir is not None:
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        with open(Path(run_dir) / ROUNDS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        r.log_event("round", row)
    r.rounds.append(row)
    return row


# box: rounds
def read_rounds(run_dir: str | Path) -> list[dict]:
    p = Path(run_dir) / ROUNDS
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


# box: rounds
def close_rounds(run_dir: str | Path, task_id: str, sim_score: dict | None, judge: str | None,
                 status: str | None) -> dict | None:
    """The closing run_end row (its sim_score, judge hash and status), only when the run had a round."""
    p = Path(run_dir) / ROUNDS
    if not p.exists():
        return None
    row = {"kind": "run_end", "task_id": task_id, "sim_score": sim_score, "judge_hash": judge, "status": status}
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    EvidenceLog(run_dir).append("run_end", row)
    return row
