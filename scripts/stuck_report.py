"""D117 Stage B: the stuck watch run over stored run folders, offline (no model call).

For every run folder below the given roots (a folder with result.json and artifacts/step_*.json), each step attempt
is read the way the live watch reads it (amoeba/adapt/stuck.py): the attempt before is step_N.first.json when the step
was redone; the unfilled requests come from capability_requests.json (or result.json). It prints, per run set (the
root's name and the first folder below it, e.g. eval/probe_hard), the steps, the stuck steps, the counts per cause and per signal,
and the coverage (step records without tool calls cannot show a repeated error).

    python -m scripts.stuck_report eval [more roots] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from amoeba.adapt.stuck import diagnose, is_stuck, step_signals


# box: stuck
def run_folders(roots: list[str]) -> list[tuple[str, Path]]:
    """(run set, run folder) for every run folder under the roots once: a symlinked copy, or the same run path in a
    second checkout, counts once. The run set is the root's name and the run's first folder below it (eval/round4)."""
    seen, out = set(), []
    for root in roots:
        for res in sorted(Path(root).rglob("result.json")):
            run = res.parent
            rel = run.relative_to(root)
            if os.path.realpath(run) in seen or str(rel) in seen or not (run / "artifacts").is_dir():
                continue
            seen |= {os.path.realpath(run), str(rel)}
            out.append((str(Path(Path(root).name) / rel.parts[0]) if len(rel.parts) > 1 else Path(root).name, run))
    return out


def _load(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# box: stuck
def run_stuck(run: Path) -> list[dict]:
    """One record per step attempt of a stored run: {step, attempt, status, stuck, cause, signals, evidence,
    has_tool_calls}."""
    requests = _load(run / "capability_requests.json")
    if requests is None:
        requests = (_load(run / "result.json") or {}).get("requested_capabilities") or []
    unfilled = [q for q in requests if isinstance(q, dict) and q.get("status") == "unfilled"]
    out = []
    for p in sorted((run / "artifacts").glob("step_*.json"), key=lambda x: x.name):
        stem = p.name[:-len(".json")]
        if stem.endswith(".first") or not stem[len("step_"):].isdigit():
            continue
        first = _load(p.with_name(f"{stem}.first.json"))
        attempts = ([(first, None)] if first else []) + [(_load(p), first)]
        for i, (meta, previous) in enumerate(attempts, 1):
            if not isinstance(meta, dict):
                continue
            sig = step_signals(meta, previous=previous, unfilled=unfilled)
            stuck = is_stuck(meta, sig)
            d = diagnose(sig) if stuck else {"cause": None, "signals": [], "evidence": []}
            out.append({"step": meta.get("step"), "attempt": i, "status": meta.get("status"), "stuck": stuck,
                        "reason": meta.get("status_reason") or "",
                        "cause": d["cause"], "signals": d["signals"], "evidence": d["evidence"],
                        "has_tool_calls": "tool_calls" in meta})
    return out


# box: stuck
def report(roots: list[str]) -> dict:
    """Counts per run set and in total."""
    sets: dict[str, dict] = {}
    for key, run in run_folders(roots):
        s = sets.setdefault(key, {"runs": 0, "runs_with_stuck": 0, "attempts": 0, "stuck": 0, "not_done": 0,
                                  "no_tool_calls": 0, "causes": Counter(), "signals": Counter(), "examples": [],
                                  "not_done_no_signal": Counter()})
        recs = run_stuck(run)
        s["runs"] += 1
        s["runs_with_stuck"] += any(r["stuck"] for r in recs)
        for r in recs:
            s["attempts"] += 1
            s["not_done"] += r["status"] != "done"
            s["no_tool_calls"] += not r["has_tool_calls"]
            if r["status"] != "done" and not r["stuck"]:
                s["not_done_no_signal"][r["reason"].split(":")[0].split(";")[0].strip() or "(no reason)"] += 1
            if r["stuck"]:
                s["stuck"] += 1
                s["causes"][r["cause"]] += 1
                s["signals"].update(r["signals"])
                if len(s["examples"]) < 3:
                    s["examples"].append({"run": run.name, **{k: r[k] for k in ("step", "cause", "evidence")}})
    total = {"runs": 0, "runs_with_stuck": 0, "attempts": 0, "stuck": 0, "not_done": 0, "no_tool_calls": 0,
             "causes": Counter(), "signals": Counter(), "not_done_no_signal": Counter()}
    for s in sets.values():
        for k in total:
            total[k] += s[k]
    return {"sets": sets, "total": total}


def _row(name: str, s: dict) -> str:
    causes = ", ".join(f"{c} {n}" for c, n in s["causes"].most_common()) or "-"
    signals = ", ".join(f"{c} {n}" for c, n in s["signals"].most_common()) or "-"
    return (f"{name}\n  runs {s['runs']} (with a stuck step {s['runs_with_stuck']}); step attempts {s['attempts']}, "
            f"not done {s['not_done']}, stuck {s['stuck']}; without tool calls {s['no_tool_calls']}\n"
            f"  causes: {causes}\n  signals: {signals}"
            + (f"\n  not done, no signal: {', '.join(f'{c} {n}' for c, n in s['not_done_no_signal'].most_common())}"
               if s["not_done_no_signal"] else ""))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("roots", nargs="+")
    p.add_argument("--json", help="also write the counts here")
    a = p.parse_args(argv)
    r = report(a.roots)
    for name, s in sorted(r["sets"].items()):
        print(_row(name, s))
    print(_row("TOTAL", r["total"]))
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=2, default=dict), encoding="utf-8")


if __name__ == "__main__":
    main()
