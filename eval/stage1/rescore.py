"""Part 2: score finished Stage 1 runs again with the current frozen judge, without re-running the team.

    python eval/stage1/rescore.py <run dir> [<run dir> ...]

The run's sim_score.json is kept as sim_score.<old judge hash, 12 chars>.json and a new sim_score.json is written
with today's judge hash (the rubric grader fix, 90f03af, changed it). The task comes from the run's own result.json
task id, looked up in tasks/stage1_dev.jsonl and tasks/stage1_replay.jsonl.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from amoeba.eval.judge import judge_hash  # noqa: E402
from amoeba.eval.sim_score import score_run  # noqa: E402
from amoeba.task.models import Task  # noqa: E402

TASKS = {t.id: t for f in ("tasks/stage1_dev.jsonl", "tasks/stage1_replay.jsonl")
         for t in (Task.model_validate(json.loads(l)) for l in (ROOT / f).open(encoding="utf-8") if l.strip())}


def rescore(run: Path, judge: str) -> dict:
    res = json.loads((run / "result.json").read_text(encoding="utf-8"))
    old = run / "sim_score.json"
    if old.exists():
        prev = json.loads(old.read_text(encoding="utf-8"))
        if prev.get("judge_hash") == judge:
            return prev
        old.rename(run / f"sim_score.{(prev.get('judge_hash') or 'none')[:12]}.json")
    return score_run(run, TASKS[res["task_id"]], int(res.get("seed") or 0), judge)


if __name__ == "__main__":
    judge = judge_hash()["sha256"]
    for d in map(Path, sys.argv[1:]):
        got = rescore(d, judge)
        print(f"{d.parent.name}/{d.name[:8]} {got['score']} {[(p['name'], p['score']) for p in got['parts']]}")
