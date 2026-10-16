"""D146 — hand-grade Box 4's diagnoses: every stuck episode of a run, one at a time.

    python -m scripts.grade_episodes <run folder>

Reads <run>/events.jsonl (the hash-chained log; never changed) and asks, for each `stuck` row, whether the diagnosed
cause was right (r), partly right (p) or wrong (w), or to skip it (s), with an optional note. The grades go to
<run>/grades.json next to the run; a run graded before keeps its earlier grades unless they are graded again.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GRADES = {"r": "right", "p": "partly", "w": "wrong"}


# box: evidence
def episodes(run: Path) -> list[dict]:
    """The stuck rows of a run's events.jsonl, in order."""
    path = run / "events.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []
    return [{"seq": r["seq"], **r["data"]} for r in rows if r.get("event") == "stuck"]


# box: evidence
def grade(run: str | Path, ask=input, out=print) -> dict:
    """Ask for a grade per episode; returns and writes grades.json ({run, episodes: [{seq, step, attempt, cause,
    grade, note}]})."""
    run = Path(run)
    path = run / "grades.json"
    old = {g["seq"]: g for g in (json.loads(path.read_text(encoding="utf-8")).get("episodes", [])
                                 if path.exists() else [])}
    eps = episodes(run)
    if not eps:
        out(f"no stuck episodes in {run / 'events.jsonl'}")
    for e in eps:
        out(f"\n[{e['seq']}] step {e['step']}, attempt {e['attempt']}: cause {e['cause']} "
            f"(signals: {', '.join(e.get('signals') or [])})")
        for line in e.get("evidence") or []:
            out(f"    - {line}")
        while True:
            a = (ask("right / partly / wrong / skip [r/p/w/s]: ") or "").strip().lower()[:1]
            if a in GRADES or a == "s":
                break
        if a == "s":
            continue
        note = (ask("note (optional): ") or "").strip()
        old[e["seq"]] = {"seq": e["seq"], "step": e["step"], "attempt": e["attempt"], "cause": e["cause"],
                         "grade": GRADES[a], "note": note}
    result = {"run": str(run), "episodes": [old[k] for k in sorted(old)]}
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    counts = {g: sum(1 for x in result["episodes"] if x["grade"] == g) for g in GRADES.values()}
    out(f"\nwrote {path}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run")
    args = p.parse_args(argv)
    grade(args.run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
