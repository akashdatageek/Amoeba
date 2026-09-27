"""Rounds 3b and 4 driver: one (round, repeat) per process, the ten tasks one at a time, with the $5 guard per round.

    python eval/round4/run_rounds.py --round r3b --repeat 1 --contract off
    python eval/round4/run_rounds.py --round r4  --repeat 1 --contract on

Settings are round 3's (round 2b + --local-tools on, round 1's drafts) plus --step-contract. Each repeat has its own
cache namespace (observer-<round>-rep<k>) and runs folder (runs/<round>/rep<k>/), so repeats are independent samples.
Guard: before each run, the round's cost so far (every repeat, high price estimate: $0.99 per 1M input, $1.49 per 1M
output + reasoning) plus the most expensive run seen so far must stay under $5; otherwise the repeat stops.
Keys come from private env files and are never printed.
"""
import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SP = Path(os.environ.get("AMOEBA_SCRATCH", "/tmp/claude-0/-home-user-Amoeba/6ad97438-2398-5c56-be15-1b8885aa050c/scratchpad"))
TASKS = ROOT / "tasks" / "observer_round1.jsonl"
GUARD_USD = 5.0
HIGH_IN, HIGH_OUT = 0.99e-6, 1.49e-6


def env_from(files):
    env = {k: v for k, v in os.environ.items() if k not in ("AMOEBA_BASE_URL", "AMOEBA_MODEL", "AMOEBA_API_KEY")}
    for f in files:
        for line in Path(f).read_text().splitlines():
            line = line.strip().removeprefix("export ").strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env["AMOEBA_SANDBOX"] = "1"
    return env


def cost_high(usage: dict) -> float:
    return usage.get("input", 0) * HIGH_IN + (usage.get("output", 0) + usage.get("reasoning", 0)) * HIGH_OUT


def ledger(rnd: str) -> list[dict]:
    p = ROOT / "eval" / "round4" / f"ledger_{rnd}.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def append(rnd: str, rec: dict) -> None:
    p = ROOT / "eval" / "round4" / f"ledger_{rnd}.jsonl"
    with open(p, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(rec) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", required=True)
    ap.add_argument("--repeat", type=int, required=True)
    ap.add_argument("--contract", choices=["on", "off"], required=True)
    ap.add_argument("--only", default="", help="comma-separated task ids (default: all ten)")
    a = ap.parse_args()
    env = env_from([SP / "gemma.env", SP / "tavily.env"])
    runs_dir = ROOT / "runs" / a.round / f"rep{a.repeat}"
    runs_dir.mkdir(parents=True, exist_ok=True)
    tasks = [l for l in TASKS.read_text().splitlines() if l.strip()]
    only = {x for x in a.only.split(",") if x}
    for line in tasks:
        tid = json.loads(line)["id"]
        if only and tid not in only:
            continue
        done = [r for r in ledger(a.round) if r["repeat"] == a.repeat and r["task"] == tid and r.get("ok")]
        if done:
            continue
        spent = [r["cost_high"] for r in ledger(a.round)]
        if sum(spent) + max(spent or [0.5]) >= GUARD_USD:
            print(f"[guard] {a.round}: ${sum(spent):.2f} spent (high estimate); stopping before {tid}", flush=True)
            return 2
        one = SP / f"{a.round}_rep{a.repeat}_{tid}.jsonl"
        one.write_text(line + "\n")
        before = set(runs_dir.iterdir())
        cmd = [str(ROOT / ".venv/bin/python"), "-m", "scripts.run_task", "--tasks", str(one),
               "--llm", "openai", "--profile", "gemma-api", "--draft-prompts", "d24", "--topology", "plan",
               "--web-tools", "--self-refine", "on-issues", "--collab", "critique",
               "--llm-cache", "runs/cache", "--llm-cache-mode", "record",
               "--llm-cache-namespace", f"observer-{a.round}-rep{a.repeat}",
               "--max-tokens-per-run", "400000", "--max-calls-per-run", "150", "--min-seconds-between-calls", "1",
               "--pool", "--drafts-from", "eval/round1/runs", "--draft-pick", "0",
               "--local-tools", "on", "--step-contract", a.contract, "--runs-dir", str(runs_dir)]
        t0 = time.time()
        log = SP / f"{a.round}_rep{a.repeat}.log"
        with open(log, "a") as lf:
            lf.write(f"\n=== {tid} {time.strftime('%H:%M:%S')}\n")
            lf.flush()
            rc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=lf, stderr=subprocess.STDOUT).returncode
        new = sorted(set(runs_dir.iterdir()) - before)
        rec = {"round": a.round, "repeat": a.repeat, "task": tid, "rc": rc, "wall_s": int(time.time() - t0),
               "run": str(new[-1].relative_to(ROOT)) if new else None, "ok": False, "cost_high": 0.0}
        if new and (new[-1] / "result.json").exists():
            r = json.loads((new[-1] / "result.json").read_text())
            rec.update(ok=rc == 0 and not str(r.get("error") or "").startswith(("api:", "draft:")),
                       error=r.get("error"), usage=r["usage"], cost_high=round(cost_high(r["usage"]), 4))
        append(a.round, rec)
        print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
