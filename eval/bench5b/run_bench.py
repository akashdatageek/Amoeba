"""Five-task benchmark, rerun after the fixes D63–D71: 5 tasks × 3 architectures × 3 runs (45 runs).
Adapted from eval/bench5/run_bench.py (left unchanged).

    python eval/bench5b/run_bench.py draft          # Box 2 redrafts each task once (fixed prompts), into drafts/
    python eval/bench5b/run_bench.py picks          # one pool / local pick per task and request (D70), picks.json
    python eval/bench5b/run_bench.py run [--only bench5-loan] [--reps 1,2,3]

Every architecture gets the same flags: model and profile, toolbox (calc, web_search / fetch_url, the pool and the
local tools with AMOEBA_SANDBOX=1), limits, the saved Box 2 draft and the shared picks, D62 equal tool access. Only
--topology differs, plus --step-contract on --replan on for Amoeba. For each task and run k the three architectures
run at the same time; cache namespaces bench5b-<arch>-r<k>; runs folder runs/bench5b/<arch>/. After the first batch
the driver projects cost (high price estimate) and time and stops if the projection passes $10. A run is re-run only
after a crash that is not the architecture's doing (an API or quota error), and the ledger says so. Keys come from
private env files and are never printed.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "eval" / "bench5b"
SP = Path(os.environ.get("AMOEBA_SCRATCH", "/tmp/claude-0/-home-user-Amoeba/6ad97438-2398-5c56-be15-1b8885aa050c/scratchpad"))
TASKS = ROOT / "tasks" / "bench5.jsonl"
LEDGER = HERE / "ledger.jsonl"
DRAFTS = HERE / "drafts"
PICKS = HERE / "picks.json"
ARCHS = {"autoagents": ["--topology", "flat", "--step-contract", "off"],
         "agentverse": ["--topology", "boss_reviewers", "--step-contract", "off"],
         "amoeba": ["--topology", "plan", "--step-contract", "on", "--replan", "on"]}
CLIENT = ["--llm", "openai", "--profile", "gemma-api", "--llm-cache", "runs/cache", "--llm-cache-mode", "record",
          "--min-seconds-between-calls", "1", "--max-rate-retries", "8"]
COMMON = [*CLIENT, "--draft-prompts", "d24", "--web-tools", "--self-refine", "on-issues", "--collab", "critique",
          "--max-tokens-per-run", "400000", "--max-calls-per-run", "150",
          "--pool", "--local-tools", "on", "--equal-tools", "on",
          "--drafts-from", str(DRAFTS.relative_to(ROOT)), "--draft-pick", "0",
          "--picks-file", str(PICKS.relative_to(ROOT))]
GUARD_USD = 10.0
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


def task_lines(only: str = "") -> list[str]:
    lines = [l for l in TASKS.read_text().splitlines() if l.strip()]
    return [l for l in lines if not only or json.loads(l)["id"] in only.split(",")]


def one_task_file(line: str) -> Path:
    tid = json.loads(line)["id"]
    f = SP / f"bench5b_{tid}.jsonl"
    f.write_text(line + "\n")
    return f


def draft(e: dict) -> int:
    """Box 2 once per task with the fixed prompts; it is shown the toolbox Box 3 will have (D68)."""
    cmd = [str(ROOT / ".venv/bin/python"), "-m", "scripts.eval_draft", "--tasks", str(TASKS), "--repeats", "1",
           *CLIENT, "--llm-cache-namespace", "bench5b-draft", "--draft-prompts", "d24",
           "--web-tools", "--local-tools", "on", "--pool", "--out", str(DRAFTS)]
    return subprocess.run(cmd, cwd=ROOT, env=e).returncode


def picks(e: dict, only: str = "") -> int:
    """D70: the toolbox step alone, once per task, so the three architectures share one pick per request."""
    rc = 0
    for line in task_lines(only):
        cmd = [str(ROOT / ".venv/bin/python"), "-m", "scripts.run_task", "--tasks", str(one_task_file(line)),
               *COMMON, "--topology", "plan", "--picks-only", "--llm-cache-namespace", "bench5b-picks",
               "--runs-dir", str(SP / "bench5b_picks_runs")]
        rc |= subprocess.run(cmd, cwd=ROOT, env=e).returncode
    return rc


def crashed(rec: dict) -> bool:
    return not rec["ok"] and str(rec.get("error") or "").startswith(("api:", "cache_miss"))


def run_batch(line: str, rep: int, e: dict) -> list[dict]:
    tid = json.loads(line)["id"]
    f = one_task_file(line)
    procs = {}
    t0 = time.time()
    for arch, flags in ARCHS.items():
        done = [r for r in ledger() if r["task"] == tid and r["arch"] == arch and r["rep"] == rep]
        if done and not crashed(done[-1]):
            continue
        d = ROOT / "runs" / "bench5b" / arch
        d.mkdir(parents=True, exist_ok=True)
        before = set(d.iterdir())
        log = open(SP / f"bench5b_{arch}.log", "a")
        log.write(f"\n=== {tid} r{rep} {datetime.now(timezone.utc):%H:%M:%S}\n")
        log.flush()
        cmd = [str(ROOT / ".venv/bin/python"), "-m", "scripts.run_task", "--tasks", str(f), *COMMON, *flags,
               "--llm-cache-namespace", f"bench5b-{arch}-r{rep}", "--runs-dir", str(d)]
        procs[arch] = (subprocess.Popen(cmd, cwd=ROOT, env=e, stdout=log, stderr=subprocess.STDOUT), before, d,
                       time.time(), bool(done))
    out = []
    for arch, (p, before, d, ts, rerun) in procs.items():
        rc = p.wait()
        new = sorted(set(d.iterdir()) - before, key=lambda x: x.stat().st_mtime)
        rec = {"task": tid, "arch": arch, "rep": rep, "rc": rc, "run": str(new[-1].relative_to(ROOT)) if new else None,
               "ok": False, "cost_high": 0.0, "rerun_after_crash": rerun}
        if new and (new[-1] / "result.json").exists():
            r = json.loads((new[-1] / "result.json").read_text())
            rec.update(ok=rc == 0 and not str(r.get("error") or "").startswith(("api:", "draft:", "cache_miss")),
                       error=r.get("error"), usage=r["usage"], calls=r.get("n_llm_calls"),
                       wall_s=round(r.get("latency_ms", 0) / 1000), cost_high=round(cost_high(r["usage"]), 4))
        with open(LEDGER, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
        out.append(rec)
        print(json.dumps(rec), flush=True)
    print(f"[batch] {tid} r{rep}: {int(time.time() - t0)} s", flush=True)
    return out


def run(e: dict, only: str, reps: list[int]) -> int:
    lines = task_lines(only)
    t_start, first = time.time(), True
    for line in lines:
        for rep in reps:
            run_batch(line, rep, e)
            for _ in range(2):                         # a crash that is not the architecture's doing: re-run (logged)
                last = [r for r in ledger() if r["task"] == json.loads(line)["id"] and r["rep"] == rep]
                latest = {r["arch"]: r for r in last}
                if not any(crashed(r) for r in latest.values()):
                    break
                print(f"[rerun] crash in {[a for a, r in latest.items() if crashed(r)]}: re-running", flush=True)
                run_batch(line, rep, e)
            if first:
                first = False
                spent = sum(r["cost_high"] for r in ledger())
                batches = len(lines) * len(reps)
                per = time.time() - t_start
                proj = spent * batches
                print(f"[projection] batch 1: ${spent:.3f} (high), {per / 60:.1f} min; projected ${proj:.2f} and "
                      f"{per * batches / 3600:.1f} h for {batches} batches", flush=True)
                if proj > GUARD_USD:
                    print("[guard] projection over $10 — stopping", flush=True)
                    return 2
            spent = sum(r["cost_high"] for r in ledger())
            if spent > GUARD_USD:
                print(f"[guard] spent ${spent:.2f} > $10 — stopping", flush=True)
                return 2
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["draft", "picks", "run"])
    ap.add_argument("--only", default="")
    ap.add_argument("--reps", default="1,2,3")
    a = ap.parse_args()
    e = env()
    if a.what == "draft":
        return draft(e)
    if a.what == "picks":
        return picks(e, a.only)
    return run(e, a.only, [int(x) for x in a.reps.split(",")])


if __name__ == "__main__":
    sys.exit(main())
