"""Rounds 3b and 4 — the report's numbers from eval/round4/scores.yaml (observer scores) and facts.json (digest.py).

    python eval/round4/aggregate.py        # prints markdown tables; writes eval/round4/aggregate.json
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
TASKS = ["r1-code-run", "r1-weather", "r1-pdf-read", "r1-xlsx", "r1-chart", "r1-fx-email", "r1-route", "r1-repo",
         "r1-deck", "r1-full-chain"]
CHECKS = ["C1", "C2", "C3", "C4", "C5", "C6"]
# round 3 (docs/eval/round3/report.md), round 2b and 1 C1–C5 totals, one run per task
R3 = {"r1-code-run": [1, 1, 0, 1, 1, 1], "r1-weather": [1, 1, 1, 0, 1, 0], "r1-pdf-read": [1, 1, 1, 0, 1, 1],
      "r1-xlsx": [0, 1, 1, 1, 1, 1], "r1-chart": [1, 1, 1, 1, 1, 1], "r1-fx-email": [1, 1, 1, 0, 0, 0],
      "r1-route": [1, 1, 0, 1, 0, 0], "r1-repo": [1, 1, 1, 0, 1, 1], "r1-deck": [0, 1, 0, 1, 0, 0],
      "r1-full-chain": [0, 1, 1, 0, 1, 1]}
TOTALS = {"R1": 34, "R2": 36, "R2b": 35, "R3": 36}


def fmt(xs: list[float]) -> str:
    m = st.mean(xs)
    return f"{m:.2f} ({min(xs):g}–{max(xs):g})" if min(xs) != max(xs) else f"{m:.2f}"


def main() -> None:
    S = yaml.safe_load((HERE / "scores.yaml").read_text())
    F = json.loads((HERE / "facts.json").read_text())
    out: dict = {"per_task": {}, "per_check": {}, "cost": {}, "contract": {}}
    lines = ["| Task | R3 (1 run) | 3b C1–C5 mean (range) | R4 C1–C5 mean (range) | 3b C6 | R4 C6 |", "|---|---|---|---|---|---|"]
    per_round = {"r3b": {c: [] for c in CHECKS}, "r4": {c: [] for c in CHECKS}}
    for t in TASKS:
        row = {}
        for rnd in ("r3b", "r4"):
            reps = S[t].get(rnd, {})
            c15 = [sum(v[:5]) for v in reps.values()]
            row[rnd] = {"c1_5": c15, "c6": [v[5] for v in reps.values()],
                        "checks": {c: st.mean(v[i] for v in reps.values()) for i, c in enumerate(CHECKS)} if reps else {}}
            for i, c in enumerate(CHECKS):
                per_round[rnd][c].append(st.mean(v[i] for v in reps.values()) if reps else float("nan"))
        out["per_task"][t] = row
        lines.append(f"| {t} | {sum(R3[t][:5])}/5 | {fmt(row['r3b']['c1_5'])} | {fmt(row['r4']['c1_5'])} | "
                     f"{fmt(row['r3b']['c6'])} | {fmt(row['r4']['c6'])} |")
    print("\n".join(lines))
    print("\n| Check | R3 | 3b (sum of task means) | R4 (sum of task means) | change |\n|---|---|---|---|---|")
    for i, c in enumerate(CHECKS):
        a, b = sum(per_round["r3b"][c]), sum(per_round["r4"][c])
        out["per_check"][c] = {"R3": sum(R3[t][i] for t in TASKS), "r3b": a, "r4": b}
        print(f"| {c} | {sum(R3[t][i] for t in TASKS)} | {a:.2f} | {b:.2f} | {b - a:+.2f} |")
    t3b = sum(sum(per_round['r3b'][c]) for c in CHECKS[:5]); t4 = sum(sum(per_round['r4'][c]) for c in CHECKS[:5])
    print(f"| C1–C5 | 36 | {t3b:.2f} | {t4:.2f} | {t4 - t3b:+.2f} |")
    out["totals"] = {"r3b": t3b, "r4": t4}
    # cost: every ok run, per round
    for rnd in ("r3b", "r4"):
        runs = [f for f in F if f["round"] == rnd]
        calls = [f["calls"] for f in runs]
        billed = [f["usage"]["tokens"] for f in runs]
        cc = [f["contract_refine_cost"] for f in runs]
        out["cost"][rnd] = {"runs": len(runs), "calls": sum(calls), "calls_mean": st.mean(calls),
                            "billed": sum(billed), "billed_mean": st.mean(billed),
                            "input": sum(f["usage"]["input"] for f in runs),
                            "output": sum(f["usage"]["output"] for f in runs),
                            "reasoning": sum(f["usage"]["reasoning"] for f in runs),
                            "contract_calls": sum(c["calls"] for c in cc), "contract_pure_calls": sum(c["pure_calls"] for c in cc),
                            "contract_tokens": sum(c["input"] + c["output"] + c["reasoning"] for c in cc)}
        hi = out["cost"][rnd]["input"] * 0.99e-6 + (out["cost"][rnd]["output"] + out["cost"][rnd]["reasoning"]) * 1.49e-6
        lo = out["cost"][rnd]["input"] * 0.09e-6 + (out["cost"][rnd]["output"] + out["cost"][rnd]["reasoning"]) * 0.34e-6
        out["cost"][rnd]["usd"] = [round(lo, 3), round(hi, 3)]
    print("\n| Round | Runs | Calls (mean) | Billed tokens (mean) | Est. cost | Contract refine calls (pure) | Their tokens |\n|---|---|---|---|---|---|---|")
    for rnd, c in out["cost"].items():
        print(f"| {rnd} | {c['runs']} | {c['calls']} ({c['calls_mean']:.1f}) | {c['billed']:,} ({c['billed_mean']:,.0f}) | "
              f"${c['usd'][0]:.2f}–${c['usd'][1]:.2f} | {c['contract_calls']} ({c['contract_pure_calls']}) | {c['contract_tokens']:,} |")
    # contract facts (round 4)
    r4 = [f for f in F if f["round"] == "r4"]
    steps = [(f["task"], f["repeat"], s) for f in r4 for s in f["steps"]]
    latest = {}
    for t, r, s in steps:
        latest[(t, r, s["step"])] = s
    ch = [(k, s) for k, s in latest.items() if s["changed_by_contract"]]
    nn = [x for f in r4 for x in f["not_needed_lines"]]
    out["contract"] = {"steps_latest": len(latest), "changed_by_contract": [(k[0], k[1], k[2], s["status_reason"]) for k, s in ch],
                       "not_needed_lines": len(nn), "not_needed_print": sum("Print" in x["line"][:25] for x in nn),
                       "refines_with_contract": sum(1 for s in latest.values() if "contract" in (s["refine_reason"] or "")),
                       "rework_skipped": [(f["task"], f["repeat"], r.get("amoeba.step")) for f in r4 for r in f["rework_skipped"]]}
    print("\ncontract:", json.dumps(out["contract"], indent=1))
    (HERE / "aggregate.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
