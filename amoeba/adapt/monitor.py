"""D85 — Box 4, the Monitor (Phase 2 spec §5). Plain code: it reads the practice stream's run records per family and
raises an alarm when the scores drop or a cause appears. Thresholds: amoeba/config/adapt.yaml monitor.

- Score alarm: the mean of the last W = 3 scores is below mu_ref − max(2·sigma_ref, 0.10); mu_ref and sigma_ref come
  from the family's practice runs since its last accepted change and before the window (at least 4; until then, no
  alarm).
- Cause alarm: a D61 cause (capability, checks, max_turns, unused_tool, claimed_file_missing) or a failed rubric item
  (the feedback channel, "feedback:<item>") is in ≥ 50% of the window after ≤ 20% of the reference runs.
- D93: only observed signals raise an alarm. A capability cause counts only when plain code found the gap
  (contract_missing); a step whose only capability evidence is the helper's own BLOCKED line is declared (kept in
  `declared`, never an alarm signal).
- No alarm while the family is in a dwell period after an accept or cooling down after a reject (LoopState.quiet_until).
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, stdev
from typing import Literal

from pydantic import BaseModel, Field

from amoeba.adapt.recipe import adapt_config
from amoeba.adapt.stream import StreamTask, feedback

D61_CAUSES = ("capability", "checks", "max_turns", "unused_tool", "claimed_file_missing")


# box: mon_records
class PracticeRecord(BaseModel):
    """What the loop keeps from one practice run (the only rubric information is the failed item names)."""

    order: int
    task_id: str
    family: str
    run_dir: str = ""
    score: float | None = None
    failed_items: list[str] = Field(default_factory=list)
    causes: list[str] = Field(default_factory=list)          # distinct observed D61 causes in any step (D93)
    declared: list[str] = Field(default_factory=list)        # D93: causes only the model's own words support
    recipe_version: int = 1
    error: str | None = None

    def signals(self) -> set[str]:
        return set(self.causes) | {f"feedback:{i}" for i in self.failed_items}


# box: mon_records
def practice_record(task: StreamTask, run_dir: str | Path, recipe_version: int = 1) -> PracticeRecord:
    """Read one practice run's folder: score, failed item names (feedback channel), D61 causes, error."""
    d = Path(run_dir)
    r = json.loads((d / "result.json").read_text(encoding="utf-8"))
    causes, declared = set(), set()
    for f in sorted((d / "artifacts").glob("step_*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for c in s.get("causes") or []:
            blocked_only = c == "capability" and not s.get("contract_missing") and "blocked_canonical" in s
            (declared if blocked_only else causes).add(c)
    return PracticeRecord(order=task.order, task_id=task.id, family=task.family, run_dir=str(d), score=r.get("score"),
                          failed_items=feedback(r.get("rubric")), causes=sorted(c for c in causes if c in D61_CAUSES),
                          declared=sorted(c for c in declared - causes if c in D61_CAUSES),
                          recipe_version=recipe_version, error=r.get("error"))


# box: mon_records
class LoopState(BaseModel):
    """Per family: where the reference starts (after the last accepted change) and the quiet period."""

    family: str
    reference_from: int = 0          # practice order from which runs count as reference (accept order + 1)
    quiet_until: int = 0             # no alarm at or before this order (dwell after accept, cool-down after reject)


# box: monitor
class Alarm(BaseModel):
    family: str
    kind: Literal["score", "cause", "retention"]     # D100: retention = the pre-shift replay fell
    window: list[str]                # run ids (folder names) of the window
    before: float                    # mean score (or rate) of the reference runs
    after: float                     # mean score (or rate) in the window
    at_order: int
    signals: list[str] = Field(default_factory=list)       # cause alarms: the cause(s) that rose
    window_orders: list[int] = Field(default_factory=list)
    reference_orders: list[int] = Field(default_factory=list)
    inputs: dict = Field(default_factory=dict)   # D95: window and reference scores, reference mean and spread, threshold


# box: monitor
def _rate(recs: list[PracticeRecord], sig: str) -> float:
    return sum(sig in r.signals() for r in recs) / len(recs)


# box: monitor, ov_m4
def monitor(records: list[PracticeRecord], state: LoopState) -> Alarm | None:
    """Box 4 after the family's latest practice run. A score alarm wins over a cause alarm (both are reported)."""
    c = adapt_config()["monitor"]
    recs = sorted((r for r in records if r.family == state.family), key=lambda r: r.order)
    W = int(c["window"])
    if len(recs) < W or recs[-1].order <= state.quiet_until:
        return None
    window = recs[-W:]
    ref = [r for r in recs[:-W] if r.order >= state.reference_from]
    if len(ref) < int(c["min_reference"]):
        return None
    common = dict(family=state.family, window=[Path(r.run_dir).name or r.task_id for r in window],
                  at_order=recs[-1].order, window_orders=[r.order for r in window],
                  reference_orders=[r.order for r in ref])
    rose = sorted(s for s in set().union(*(r.signals() for r in window))
                  if _rate(window, s) >= c["cause_high"] and _rate(ref, s) <= c["cause_low"])
    scores_ref = [r.score or 0.0 for r in ref]
    mu, sd = mean(scores_ref), (stdev(scores_ref) if len(scores_ref) > 1 else 0.0)
    after = mean(r.score or 0.0 for r in window)
    threshold = mu - max(c["score_sigma"] * sd, c["score_floor"])
    common["inputs"] = {"window_runs": common["window"], "window_scores": [r.score for r in window],
                        "reference_runs": [Path(r.run_dir).name or r.task_id for r in ref],
                        "reference_scores": [r.score for r in ref], "reference_mean": round(mu, 4),
                        "reference_sd": round(sd, 4), "score_threshold": round(threshold, 4),
                        "window_mean": round(after, 4), "cause_rates": {s: {"window": round(_rate(window, s), 3),
                                                                           "reference": round(_rate(ref, s), 3)}
                                                                       for s in rose},
                        "cause_high": c["cause_high"], "cause_low": c["cause_low"]}
    if after < threshold:
        return Alarm(kind="score", before=round(mu, 4), after=round(after, 4), signals=rose, **common)
    if rose:
        s = rose[0]
        return Alarm(kind="cause", before=round(_rate(ref, s), 4), after=round(_rate(window, s), 4), signals=rose,
                     **common)
    return None
