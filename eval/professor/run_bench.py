"""Professor benchmark driver: 5 tasks × 3 architectures, one task at a time, the three architectures in parallel.

    python eval/professor/run_bench.py [--only prof-loan] [--batch-1-only]

Every architecture gets the same flags (same model and profile, same toolbox — calc, web_search / fetch_url, the pool
and the local tools with AMOEBA_SANDBOX=1 — same limits, same saved Box 2 draft, D62 equal tool access); only
--topology differs, plus --step-contract on for Amoeba. Cache namespace professor-<arch>; runs folder
runs/professor/<arch>/. After batch 1 the driver projects cost (high price estimate) and time and stops if the
projection passes $5 or 7:00 am Central. Keys come from private env files and are never printed.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SP = Path(os.environ.get("AMOEBA_SCRATCH", "/tmp/claude-0/-home-user-Amoeba/6ad97438-2398-5c56-be15-1b8885aa050c/scratchpad"))
TASKS = ROOT / "tasks" / "professor.jsonl"
LEDGER = ROOT / "eval" / "professor" / "ledger.jsonl"
ARCHS = {"autoagents": ["--topology", "flat", "--step-contract", "off"],
         "agentverse": ["--topology", "boss_reviewers", "--step-contract", "off"],
         "amoeba": ["--topology", "plan", "--step-contract", "on"]}
COMMON = ["--llm", "openai", "--profile", "gemma-api", "--draft-prompts", "d24", "--web-tools",
          "--self-refine", "on-issues", "--collab", "critique", "--llm-cache", "runs/cache", "--llm-cache-mode", "record",
          "--max-tokens-per-run", "400000", "--max-calls-per-run", "150", "--min-seconds-between-calls", "1",
          "--pool", "--local-tools", "on", "--equal-tools", "on",
          "--drafts-from", "eval/professor/drafts", "--draft-pick", "0"]
GUARD_USD = 5.0
DEADLINE_UTC = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)      # 7:00 am Central (CDT)
HIGH_IN, HIGH_OUT = 0.99e-6, 1.49e-6


def env():
    e = {k: v for k, v in os.environ.items() if k not in ("AMOEBA_BASE_URL", "AMOEBA_MODEL", "AMOEBA_API_KEY")}
    for f in (SP / "gemma.env", SP / "tavily.env"):
        for line in f.read_text().splitlines():
            line = line.strip().removeprefix("export ").strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                e[k.strip()] = v.strip().strip('"').strip("'")
    e["AMOEBA_SANDBOX"] = "1"
    return e


def ledger() -> list[dict]:
    return [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()] if LEDGER.exists() else []


def cost_high(u: dict) -> float:
    return u.get("input", 0) * HIGH_IN + (u.get("output", 0) + u.get("reasoning", 0)) * HIGH_OUT


def run_batch(line: str, e: dict) -> list[dict]:
    tid = json.loads(line)["id"]
    one = SP / f"professor_{tid}.jsonl"
    one.write_text(line + "\n")
    procs = {}
    t0 = time.time()
    for arch, flags in ARCHS.items():
        if any(r["task"] == tid and r["arch"] == arch and r["ok"] for r in ledger()):
            continue
        d = ROOT / "runs" / "professor" / arch
        d.mkdir(parents=True, exist_ok=True)
        before = set(d.iterdir())
        log = open(SP / f"professor_{arch}.log", "a")
        log.write(f"\n=== {tid} {datetime.now(timezone.utc):%H:%M:%S}\n")
        log.flush()
        cmd = [str(ROOT / ".venv/bin/python"), "-m", "scripts.run_task", "--tasks", str(one), *COMMON, *flags,
               "--llm-cache-namespace", f"professor-{arch}", "--runs-dir", str(d)]
        procs[arch] = (subprocess.Popen(cmd, cwd=ROOT, env=e, stdout=log, stderr=subprocess.STDOUT), before, d, time.time())
    out = []
    for arch, (p, before, d, ts) in procs.items():
        rc = p.wait()
        new = sorted(set(d.iterdir()) - before)
        rec = {"task": tid, "arch": arch, "rc": rc, "wall_s": int(time.time() - ts),
               "run": str(new[-1].relative_to(ROOT)) if new else None, "ok": False, "cost_high": 0.0}
        if new and (new[-1] / "result.json").exists():
            r = json.loads((new[-1] / "result.json").read_text())
            rec.update(ok=rc == 0 and not str(r.get("error") or "").startswith(("api:", "draft:")), error=r.get("error"),
                       usage=r["usage"], calls=r.get("n_llm_calls"), cost_high=round(cost_high(r["usage"]), 4))
        with open(LEDGER, "a") as f:
            f.write(json.dumps(rec) + "\n")
        out.append(rec)
        print(json.dumps(rec), flush=True)
    print(f"[batch] {tid}: {int(time.time() - t0)} s", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--batch-1-only", action="store_true")
    a = ap.parse_args()
    e = env()
    lines = [l for l in TASKS.read_text().splitlines() if l.strip()]
    if a.only:
        lines = [l for l in lines if json.loads(l)["id"] in a.only.split(",")]
    t_start = time.time()
    for i, line in enumerate(lines):
        run_batch(line, e)
        if i == 0 and not a.only:
            L = ledger()
            spent = sum(r["cost_high"] for r in L)
            per_batch_s = time.time() - t_start
            proj_usd = spent * len(lines)
            proj_end = datetime.now(timezone.utc) + timedelta(seconds=per_batch_s * (len(lines) - 1))
            waits = []
            for r in L:
                if r.get("run"):
                    tr = ROOT / r["run"] / "trace.jsonl"
                    if tr.exists():
                        waits += [json.loads(x) for x in tr.read_text().splitlines() if '"rate_limited"' in x]
            print(f"[projection] batch 1: ${spent:.3f} (high), {per_batch_s/60:.1f} min; projected ${proj_usd:.2f}, "
                  f"finish ~{proj_end:%H:%M} UTC; rate-limit waits in batch 1: {len(waits)} "
                  f"({sum(w.get('amoeba.wait_s', 0) or 0 for w in waits):.0f} s)", flush=True)
            if proj_usd > GUARD_USD or proj_end > DEADLINE_UTC:
                print("[guard] projection over $5 or past 7:00 am Central — stopping", flush=True)
                return 2
            if a.batch_1_only:
                return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
