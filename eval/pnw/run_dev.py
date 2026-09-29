"""Development task (parking citation, after D77): "How to pay the P and W universities parking citation?" on the
three architectures, under two conditions — non-interactive with no user context, and with --context
eval/pnw/user.yaml (organisation: Purdue University Northwest, location: Hammond, Indiana). The task was looked at
while designing D77, so it is a development task, not a held-out test.

    python eval/pnw/run_dev.py            # both conditions: draft (interpretation on), picks, 3 runs in parallel

Per condition: Box 2 drafts once with the interpretation step (eval_draft --interpret on [--context]); the three
architectures reuse that draft and one shared tool pick, with the bench5b flags (--equal-tools on, web, pool, local
tools with AMOEBA_SANDBOX=1; Amoeba: --step-contract on --replan on). Cache namespaces pnw-<condition>-<arch>; runs
under runs/pnw/<condition>/<arch>/; ledger eval/pnw/ledger.jsonl. A run is re-run once only after a crash that is not
the architecture's doing. Keys come from private env files and are never printed.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench5b"))
from run_bench import CLIENT, HIGH_IN, HIGH_OUT, SP, env  # noqa: E402  (the bench5b driver's client flags and env)

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "eval" / "pnw"
TASKS = HERE / "task.jsonl"
LEDGER = HERE / "ledger.jsonl"
PY = str(ROOT / ".venv/bin/python")
ARCHS = {"autoagents": ["--topology", "flat", "--step-contract", "off"],
         "agentverse": ["--topology", "boss_reviewers", "--step-contract", "off"],
         "amoeba": ["--topology", "plan", "--step-contract", "on", "--replan", "on"]}
CONDITIONS = {"nocontext": [], "context": ["--context", str((HERE / "user.yaml").relative_to(ROOT))]}


def common(cond: str) -> list[str]:
    d = HERE / cond
    return [*CLIENT, "--draft-prompts", "d24", "--web-tools", "--self-refine", "on-issues", "--collab", "critique",
            "--max-tokens-per-run", "400000", "--max-calls-per-run", "150", "--pool", "--local-tools", "on",
            "--equal-tools", "on", "--drafts-from", str((d / "drafts").relative_to(ROOT)), "--draft-pick", "0",
            "--picks-file", str((d / "picks.json").relative_to(ROOT))]


def cost(u: dict) -> float:
    return u.get("input", 0) * HIGH_IN + (u.get("output", 0) + u.get("reasoning", 0)) * HIGH_OUT


def run_cond(cond: str, e: dict) -> None:
    d = HERE / cond
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run([PY, "-m", "scripts.eval_draft", "--tasks", str(TASKS), "--repeats", "1", *CLIENT,
                    "--llm-cache-namespace", f"pnw-{cond}-draft", "--draft-prompts", "d24", "--web-tools",
                    "--local-tools", "on", "--pool", "--interpret", "on", *CONDITIONS[cond], "--out", str(d / "drafts")],
                   cwd=ROOT, env=e, check=True)
    subprocess.run([PY, "-m", "scripts.run_task", "--tasks", str(TASKS), *common(cond), "--topology", "plan",
                    "--picks-only", "--llm-cache-namespace", f"pnw-{cond}-picks", "--runs-dir",
                    str(SP / f"pnw_{cond}_picks_runs")], cwd=ROOT, env=e)
    for attempt in (1, 2):
        procs = {}
        for arch, flags in ARCHS.items():
            done = [json.loads(l) for l in LEDGER.read_text().splitlines()] if LEDGER.exists() else []
            if any(r["cond"] == cond and r["arch"] == arch and r["ok"] for r in done):
                continue
            rd = ROOT / "runs" / "pnw" / cond / arch
            rd.mkdir(parents=True, exist_ok=True)
            before = set(rd.iterdir())
            log = open(SP / f"pnw_{cond}_{arch}.log", "a")
            cmd = [PY, "-m", "scripts.run_task", "--tasks", str(TASKS), *common(cond), *flags,
                   "--llm-cache-namespace", f"pnw-{cond}-{arch}", "--runs-dir", str(rd)]
            procs[arch] = (subprocess.Popen(cmd, cwd=ROOT, env=e, stdout=log, stderr=subprocess.STDOUT), rd, before)
        if not procs:
            return
        for arch, (p, rd, before) in procs.items():
            rc = p.wait()
            new = sorted(set(rd.iterdir()) - before, key=lambda x: x.stat().st_mtime)
            rec = {"cond": cond, "arch": arch, "rc": rc, "run": str(new[-1].relative_to(ROOT)) if new else None,
                   "ok": False, "rerun_after_crash": attempt == 2}
            if new and (new[-1] / "result.json").exists():
                r = json.loads((new[-1] / "result.json").read_text())
                err = str(r.get("error") or "")
                rec.update(ok=not err.startswith(("api:", "cache_miss", "draft:")), error=r.get("error"),
                           calls=r.get("n_llm_calls"), wall_s=round(r.get("latency_ms", 0) / 1000),
                           cost_high=round(cost(r["usage"]), 4))
            with open(LEDGER, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(json.dumps(rec), flush=True)


def main() -> int:
    e = env()
    for cond in CONDITIONS:
        t0 = time.time()
        run_cond(cond, e)
        print(f"[condition] {cond}: {int(time.time() - t0)} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
