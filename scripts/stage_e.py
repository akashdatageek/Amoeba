"""D117 Stage E — the pair runner: the same task and seed with --adapt off, then --adapt on.

For each task and seed the off arm runs first and drafts (Boxes 1–2); the on arm reuses that run's plan.json
(`--drafts-from <off run>`), and both share one `--picks-file`, so the team, the plan, the interpretation and the pool
picks are the same and the arms differ only in Box 3. Everything after `--` is passed to run_task for both arms
unchanged. A pair whose arm already has a result.json is not run again (resumable). Each arm is logged to
<out>/pairs.jsonl: task, seed, arm, run folder, exit code, start and end.

    python -m scripts.stage_e --tasks tasks/probe_hard.jsonl --ids probe-h1-freight,probe-h2-income \\
        --seeds 0 --out eval/stage_e/pilot -- --topology plan --llm openai ...
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ARMS = ("off", "on")


# box: stage_e
def one_task_file(tasks: Path, task_id: str, out: Path) -> Path:
    """A tasks file holding only `task_id` (run_task runs every task of its --tasks file)."""
    line = next((l for l in tasks.read_text(encoding="utf-8").splitlines()
                 if l.strip() and json.loads(l).get("id") == task_id), None)
    if line is None:
        raise SystemExit(f"task {task_id!r} is not in {tasks}")
    path = out / "tasks" / f"{task_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(line + "\n", encoding="utf-8")
    return path


# box: stage_e
def run_dir_of(runs: Path) -> Path | None:
    """The one run folder an arm wrote (the newest with a result.json)."""
    found = sorted((p for p in runs.glob("*") if (p / "result.json").exists()), key=lambda p: p.stat().st_mtime)
    return found[-1] if found else None


# box: stage_e
def arm_command(arm: str, task_file: Path, seed: int, runs: Path, picks: Path, off_run: Path | None,
                passthrough: list[str], python: str = sys.executable) -> list[str]:
    cmd = [python, "-m", "scripts.run_task", "--tasks", str(task_file), "--seed", str(seed), "--adapt", arm,
           "--runs-dir", str(runs), "--picks-file", str(picks), *passthrough]
    if arm == "on":
        cmd += ["--drafts-from", str(off_run)]
    return cmd


# box: stage_e
def run_pairs(tasks: Path, ids: list[str], seeds: list[int], out: Path, passthrough: list[str],
              python: str = sys.executable) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    log, rows = out / "pairs.jsonl", []
    picks = out / "picks.json"
    for task_id in ids:
        task_file = one_task_file(tasks, task_id, out)
        for seed in seeds:
            off_run = None
            for arm in ARMS:
                runs = out / arm / f"{task_id}.s{seed}"
                done = run_dir_of(runs)
                if done is not None:
                    off_run = done if arm == "off" else off_run
                    print(f"== skip {task_id} seed {seed} {arm}: {done.name} exists", flush=True)
                    continue
                if arm == "on" and off_run is None:
                    print(f"== skip {task_id} seed {seed} on: the off arm left no run to reuse", flush=True)
                    continue
                runs.mkdir(parents=True, exist_ok=True)
                start = datetime.now(timezone.utc).isoformat(timespec="seconds")
                print(f"== start {task_id} seed {seed} {arm} {start}", flush=True)
                t0 = time.monotonic()
                rc = subprocess.call(arm_command(arm, task_file, seed, runs, picks, off_run, passthrough, python))
                run = run_dir_of(runs)
                row = {"task": task_id, "seed": seed, "arm": arm, "run": str(run.resolve()) if run else None, "rc": rc,
                       "start": start, "end": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "wall_s": round(time.monotonic() - t0, 1)}
                rows.append(row)
                with open(log, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row) + "\n")
                print(f"== done {task_id} seed {seed} {arm} rc={rc} {row['wall_s']}s", flush=True)
                if arm == "off":
                    off_run = run
    return rows


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    passthrough = argv[argv.index("--") + 1:] if "--" in argv else []
    own = argv[:argv.index("--")] if "--" in argv else argv
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--tasks", required=True)
    p.add_argument("--ids", required=True, help="comma-separated task ids")
    p.add_argument("--seeds", default="0", help="comma-separated seeds")
    p.add_argument("--out", required=True)
    a = p.parse_args(own)
    for flag in ("--adapt", "--drafts-from", "--runs-dir", "--seed", "--tasks", "--picks-file"):
        if flag in passthrough:
            raise SystemExit(f"{flag} is set by the pair runner; leave it out of the pass-through flags")
    run_pairs(Path(a.tasks), a.ids.split(","), [int(s) for s in a.seeds.split(",")], Path(a.out), passthrough)


if __name__ == "__main__":
    main()
