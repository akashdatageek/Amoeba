"""Professor benchmark — the report's numbers: per-run tokens, calls, time and rate-limit waits, and the totals per
architecture (from scores.yaml, the observer's verdicts, and each scored run's result.json and trace.jsonl).

    python eval/professor/totals.py

Read-only. Cost is the high estimate used by the driver ($0.99 per million input tokens, $1.49 per million output and
reasoning tokens), summed over every run in the ledger, including the one invalid run that was re-run.
"""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1].parent
ARCHS = ["autoagents", "agentverse", "amoeba"]
HIGH_IN, HIGH_OUT = 0.99e-6, 1.49e-6


def run_dir(p: str) -> Path:
    """Scores name runs by their original runs/ path; after the commit they live under eval/professor/runs/."""
    for cand in (ROOT / p, ROOT / "eval/professor/runs" / p.removeprefix("runs/professor/")):
        if (cand / "result.json").exists():
            return cand
    raise FileNotFoundError(p)


def main() -> None:
    scores = yaml.safe_load((ROOT / "eval/professor/scores.yaml").read_text())
    tot = {a: {"solved": 0, "partly": 0, "failed": 0, "honesty": 0, "files_ok": 0, "files_asked": 0, "tokens": 0,
               "calls": 0, "seconds": 0, "waits": 0, "wait_s": 0.0} for a in ARCHS}
    print("| task | architecture | verdict | tokens | calls | minutes | rate-limit waits | auto rubric |")
    print("|---|---|---|---|---|---|---|---|")
    for task, per in scores.items():
        for a in ARCHS:
            s = per[a]
            d = run_dir(s["run"])
            r = json.loads((d / "result.json").read_text())
            waits = [json.loads(l) for l in (d / "trace.jsonl").read_text().splitlines() if '"rate_limited"' in l]
            t = tot[a]
            t[s["verdict"]] += 1
            t["honesty"] += len(s.get("honesty") or [])
            if task in ("prof-xlsx", "prof-diesel"):
                t["files_asked"] += 1
                t["files_ok"] += int(bool(s.get("file_correct")))
            t["tokens"] += r["usage"]["tokens"]
            t["calls"] += r["n_llm_calls"]
            t["seconds"] += r["latency_ms"] / 1000
            t["waits"] += len(waits)
            t["wait_s"] += sum(float(w.get("amoeba.wait_s") or 0) for w in waits)
            print(f"| {task} | {a} | {s['verdict']} | {r['usage']['tokens']:,} | {r['n_llm_calls']} | "
                  f"{r['latency_ms'] / 60000:.1f} | {len(waits)} | {r.get('score')} |")
    print()
    print("| | " + " | ".join(ARCHS) + " |")
    print("|---|" + "---|" * len(ARCHS))
    rows = [("tasks solved / partly / failed", lambda t: f"{t['solved']} / {t['partly']} / {t['failed']}"),
            ("honesty problems", lambda t: str(t["honesty"])),
            ("files made correctly (of those asked)", lambda t: f"{t['files_ok']} of {t['files_asked']}"),
            ("tokens (all five tasks)", lambda t: f"{t['tokens']:,}"),
            ("model calls", lambda t: str(t["calls"])),
            ("time (minutes, summed)", lambda t: f"{t['seconds'] / 60:.0f}"),
            ("rate-limit waits (count, seconds)", lambda t: f"{t['waits']}, {t['wait_s']:.0f} s")]
    for name, f in rows:
        print(f"| {name} | " + " | ".join(f(tot[a]) for a in ARCHS) + " |")
    ledger = [json.loads(l) for l in (ROOT / "eval/professor/ledger.jsonl").read_text().splitlines() if l.strip()]
    print(f"\nledger runs: {len(ledger)}; cost (high estimate, every run incl. re-runs): "
          f"${sum(r.get('cost_high', 0) for r in ledger):.3f}")


if __name__ == "__main__":
    main()
