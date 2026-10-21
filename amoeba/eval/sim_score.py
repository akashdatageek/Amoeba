"""D161 — the task score slot. A task may name a scorer in its `sim` field ({"scorer": <name>, ...}); after the run,
plain code asks that scorer for the run's score on a seed and writes <run>/sim_score.json: score, the baseline score
on the same seed, delta, seed, scorer and the judge hash (judge.py). Box 4 never reads it; only the outer loop (D166)
compares it. Only a deterministic stand-in exists: a real simulator becomes one more entry in SCORERS."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol

NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


# box: frozen_judge
class SimScorer(Protocol):
    name: str

    def score(self, run_dir: Path, sim, seed: int) -> dict:
        """{"score": float, "baseline": float, "delta": float, "seed": int} for the run in run_dir (sim: SimSpec)."""


# box: frozen_judge
class StandInScorer:
    """The stand-in until a simulator is chosen: the answer's first number against `sim.expected`
    (1.0 when equal, falling linearly to 0 at 100% relative error; 0 with no number). `sim.baseline` (default 0) is the
    baseline score; the seed is recorded and, being deterministic, changes nothing."""

    name = "standin"

    def score(self, run_dir: Path, sim, seed: int) -> dict:
        sim = spec(sim)
        res = json.loads((Path(run_dir) / "result.json").read_text(encoding="utf-8"))
        m = NUMBER.search(str(res.get("answer") or ""))
        if sim.expected is None:
            raise ValueError("the stand-in scorer needs sim.expected")
        expected = float(sim.expected)
        if m is None:
            s = 0.0
        else:
            got = float(m.group(0).replace(",", ""))
            s = max(0.0, 1.0 - abs(got - expected) / max(abs(expected), 1e-9))
        base = float(sim.baseline)
        return {"score": round(s, 6), "baseline": base, "delta": round(s - base, 6), "seed": int(seed)}


SCORERS: dict[str, type] = {"standin": StandInScorer}


# box: frozen_judge
def spec(sim):
    """A SimSpec from a SimSpec or a plain dict."""
    from amoeba.task.models import SimSpec
    return sim if isinstance(sim, SimSpec) else SimSpec.model_validate(sim)


# box: frozen_judge
def score_run(run_dir: str | Path, task, seed: int, judge: str) -> dict | None:
    """Score one finished run with its task's scorer and write sim_score.json; None when the task names none."""
    sim = getattr(task, "sim", None)
    if not sim:
        return None
    sim = spec(sim)
    cls = SCORERS.get(sim.scorer)
    if cls is None:
        raise ValueError(f"unknown scorer {sim.scorer!r}; known: {sorted(SCORERS)}")
    out = {**cls().score(Path(run_dir), sim, seed), "scorer": cls.name, "judge_hash": judge}
    (Path(run_dir) / "sim_score.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out
