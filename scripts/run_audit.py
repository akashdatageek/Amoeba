"""D92 — the final audit: the one script that reads a stream's audit set (tasks/audit/stream_<name>.audit.jsonl).

No loop component reads that file (the stream loader refuses it; a test enforces it). This script is used once per
thesis claim: it refuses a claim id that eval/audit/<stream>/audit_log.jsonl already holds, logs the claim before any
run (statement, recipe stores and hashes, task ids), runs Amoeba on the audit tasks with recipe store A (default: the
seed recipe) and recipe store B, and logs the result (per-task means, mean d, the one-sided permutation p of Gate v3).

    python -m scripts.run_audit --stream m2 --family calc --claim C1 \
        --statement "the loop's final calc recipe beats the seed recipe on unseen post-shift tasks" \
        --recipes-b eval/loop/m2/recipes --env-file keys.env --llm openai --profile gemma-api ...
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Literal

from amoeba.adapt.experimenter import Job, SubprocessRunner, experiment_flags
from amoeba.adapt.gate import permutation_greater
from amoeba.adapt.recipe import adapt_config, load_recipe, seed_recipe, write_store
from amoeba.task.models import Task

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "tasks" / "audit"


# box: gate
class AuditTask(Task):
    split: Literal["audit"]
    phase: Literal["pre", "post"]

    def as_task(self) -> Task:
        return Task(**self.model_dump(include=set(Task.model_fields)))


# box: gate
def audit_path(stream: str) -> Path:
    return AUDIT_DIR / f"stream_{stream}.audit.jsonl"


# box: gate
def load_audit(stream: str, family: str | None = None, path: Path | None = None) -> list[AuditTask]:
    p = path or audit_path(stream)
    tasks = [AuditTask.model_validate_json(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [t for t in tasks if family in (None, t.family)]


# box: gate
class AuditLog:
    """eval/audit/<stream>/audit_log.jsonl: append-only; one claim id is used once."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def used(self, claim: str) -> bool:
        return any(r.get("claim") == claim for r in self.rows())

    def append(self, row: dict) -> dict:
        row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **row}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row


# box: gate
def run_audit(stream: str, family: str, claim: str, statement: str, runner, out: Path, store_b: Path,
              store_a: Path | None = None, repeats: int = 3, tasks: list[AuditTask] | None = None) -> dict:
    """Arm A (store_a, or the seed recipe) against arm B (store_b) on the audit tasks, `repeats` seeds each."""
    out = Path(out)
    log = AuditLog(out / "audit_log.jsonl")
    if log.used(claim):
        raise SystemExit(f"claim {claim!r} already used the audit set (see {log.path}); one use per claim (D92)")
    tasks = tasks if tasks is not None else load_audit(stream, family)
    rec_a = (load_recipe(store_a, family) if store_a else None) or seed_recipe(family)
    rec_b = load_recipe(store_b, family) or seed_recipe(family)
    folder = out / claim
    sa, sb = write_store(folder / "recipes_A", [rec_a]), write_store(folder / "recipes_B", [rec_b])
    log.append({"event": "claim", "claim": claim, "statement": statement, "family": family,
                "recipe_A": {"version": rec_a.version, "hash": rec_a.hash()},
                "recipe_B": {"version": rec_b.version, "hash": rec_b.hash()},
                "tasks": [t.id for t in tasks], "repeats": repeats})
    jobs = [Job(arm=arm, task=t, k=k, seed=k, store=store, out=folder / "runs" / arm / f"{t.id}.k{k}",
                namespace=f"{stream}-audit-{claim}-{arm}-{t.id}-k{k}")
            for t in tasks for k in range(repeats) for arm, store in (("A", sa), ("B", sb))]
    recs = runner.run(jobs)
    by = {(r.arm, r.task_id, r.k): r for r in recs}
    task_d, rows = {}, []
    for t in tasks:
        a = [by[("A", t.id, k)].score or 0.0 for k in range(repeats)]
        b = [by[("B", t.id, k)].score or 0.0 for k in range(repeats)]
        task_d[t.id] = round(mean(b) - mean(a), 6)
        rows.append({"task": t.id, "scores_A": a, "scores_B": b})
    d = list(task_d.values())
    result = {"event": "result", "claim": claim, "n_tasks": len(tasks), "repeats": repeats,
              "mean_A": round(mean(s for r in rows for s in r["scores_A"]), 4) if rows else None,
              "mean_B": round(mean(s for r in rows for s in r["scores_B"]), 4) if rows else None,
              "mean_task_d": round(mean(d), 4) if d else None, "p_permutation": permutation_greater(d) if d else None,
              "task_d": task_d, "scores": rows, "errors": sum(bool(r.error) for r in recs),
              "runs": f"{claim}/runs/"}
    return log.append(result)


# box: gate
def main(argv=None) -> int:
    from scripts.run_experiment import load_env, option_defaults
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stream", required=True)
    p.add_argument("--family", required=True)
    p.add_argument("--claim", required=True, help="the thesis claim's id (used once)")
    p.add_argument("--statement", required=True, help="the claim in one sentence, logged before any run")
    p.add_argument("--recipes-b", required=True, help="recipe store of arm B")
    p.add_argument("--recipes-a", default=None, help="recipe store of arm A (default: the seed recipe)")
    p.add_argument("--repeats", type=int, default=None)
    p.add_argument("--parallel", type=int, default=4)
    p.add_argument("--env-file", action="append", default=[])
    args, passthrough = p.parse_known_args(argv)
    out = ROOT / "eval" / "audit" / args.stream
    runner = SubprocessRunner([*experiment_flags(), *option_defaults(), *passthrough], env=load_env(args.env_file),
                              parallel=args.parallel, scratch=out / "jobs")
    repeats = args.repeats or adapt_config().get("experiment", {}).get("repeats", 3)
    row = run_audit(args.stream, args.family, args.claim, args.statement, runner, out, Path(args.recipes_b),
                    Path(args.recipes_a) if args.recipes_a else None, repeats)
    print(json.dumps({k: v for k, v in row.items() if k != "scores"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
