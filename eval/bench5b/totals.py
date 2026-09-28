"""Five-task benchmark rerun (bench5b) — the report's numbers, adapted from eval/bench5/totals.py (left unchanged) for
three runs per task and architecture: per-run tokens, calls, time and rate-limit waits, the per-task "k/3 solved"
table and the totals per architecture (from scores.yaml, the observer's verdicts, and each run's result.json and
trace.jsonl), plus the Action Observer's decisions of every Amoeba run.

    python eval/bench5b/totals.py

Read-only. Cost is the high estimate used by the driver ($0.99 per million input tokens, $1.49 per million output and
reasoning tokens), summed over every run in the ledger, including runs re-run after a crash.
"""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1].parent
HERE = ROOT / "eval/bench5b"
ARCHS = ["autoagents", "agentverse", "amoeba"]
FILE_TASKS = ("bench5-xlsx", "bench5-diesel")
HIGH_IN, HIGH_OUT = 0.99e-6, 1.49e-6


def run_dir(p: str) -> Path:
    """Scores name runs by their original runs/ path; after the commit they live under eval/bench5b/runs/."""
    for cand in (ROOT / p, HERE / "runs" / p.removeprefix("runs/bench5b/")):
        if (cand / "result.json").exists():
            return cand
    raise FileNotFoundError(p)


def main() -> None:
    scores = yaml.safe_load((HERE / "scores.yaml").read_text())
    tot = {a: {"solved": 0, "partly": 0, "failed": 0, "honesty": 0, "files_ok": 0, "files_asked": 0, "tokens": 0,
               "calls": 0, "seconds": 0, "waits": 0, "wait_s": 0.0, "runs": 0} for a in ARCHS}
    per_task = {}
    print("| task | architecture | run | verdict | tokens | calls | minutes | rate-limit waits | auto rubric |")
    print("|---|---|---|---|---|---|---|---|---|")
    for task, per in scores.items():
        for a in ARCHS:
            for s in per.get(a, []):
                d = run_dir(s["run"])
                r = json.loads((d / "result.json").read_text())
                waits = [json.loads(l) for l in (d / "trace.jsonl").read_text().splitlines() if '"rate_limited"' in l]
                t = tot[a]
                t["runs"] += 1
                t[s["verdict"]] += 1
                per_task.setdefault(task, {}).setdefault(a, []).append(s["verdict"])
                t["honesty"] += len(s.get("honesty") or [])
                if task in FILE_TASKS:
                    t["files_asked"] += 1
                    t["files_ok"] += int(bool(s.get("file_correct")))
                t["tokens"] += r["usage"]["tokens"]
                t["calls"] += r["n_llm_calls"]
                t["seconds"] += r["latency_ms"] / 1000
                t["waits"] += len(waits)
                t["wait_s"] += sum(float(w.get("amoeba.wait_s") or 0) for w in waits)
                print(f"| {task} | {a} | r{s['rep']} | {s['verdict']} | {r['usage']['tokens']:,} | {r['n_llm_calls']} | "
                      f"{r['latency_ms'] / 60000:.1f} | {len(waits)} | {r.get('score')} |")
    print("\n| task | " + " | ".join(ARCHS) + " |")
    print("|---|" + "---|" * len(ARCHS))
    for task, per in per_task.items():
        cells = []
        for a in ARCHS:
            v = per.get(a, [])
            cells.append(f"{v.count('solved')}/{len(v)} solved" + (f", {v.count('partly')} partly" if v.count("partly")
                                                                    else ""))
        print(f"| {task} | " + " | ".join(cells) + " |")
    print("\n| | " + " | ".join(ARCHS) + " |")
    print("|---|" + "---|" * len(ARCHS))
    rows = [("runs solved / partly / failed", lambda t: f"{t['solved']} / {t['partly']} / {t['failed']}"),
            ("honesty problems", lambda t: str(t["honesty"])),
            ("files made correctly (of those asked)", lambda t: f"{t['files_ok']} of {t['files_asked']}"),
            ("tokens (all runs)", lambda t: f"{t['tokens']:,}"),
            ("model calls", lambda t: str(t["calls"])),
            ("time (minutes, summed)", lambda t: f"{t['seconds'] / 60:.0f}"),
            ("rate-limit waits (count, seconds)", lambda t: f"{t['waits']}, {t['wait_s']:.0f} s")]
    for name, f in rows:
        print(f"| {name} | " + " | ".join(f(tot[a]) for a in ARCHS) + " |")
    print("\nAction Observer (Amoeba runs):")
    for task, per in scores.items():
        for s in per.get("amoeba", []):
            r = json.loads((run_dir(s["run"]) / "result.json").read_text())
            rp = r.get("replan") or {}
            for d in rp.get("decisions", []):
                print(f"- {task} r{s['rep']} wave {d.get('wave')}: {d.get('decision')} "
                      f"({'accepted' if d.get('accepted') else 'rejected'}) triggers={d.get('triggers')} "
                      f"errors={d.get('errors')} changes={d.get('changes')}")
    ledger = [json.loads(l) for l in (HERE / "ledger.jsonl").read_text().splitlines() if l.strip()]
    print(f"\nledger runs: {len(ledger)} ({sum(1 for r in ledger if r.get('rerun_after_crash'))} re-run after a crash); "
          f"cost (high estimate, every run incl. re-runs): ${sum(r.get('cost_high', 0) for r in ledger):.3f}")


if __name__ == "__main__":
    main()
