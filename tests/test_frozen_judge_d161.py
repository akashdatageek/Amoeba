"""D161 — the frozen judge and the scorer slot: the judge files are hashed at run start and the hash is in
result.json; runs whose judge hashes differ are refused for comparison; a pluggable per-task scorer writes
sim_score.json (only a deterministic stand-in exists). General: nothing here names a niche. Offline."""
import json
import shutil
from pathlib import Path

import pytest

from amoeba.eval.judge import JudgeMismatch, frozen_paths, judge_hash, same_judge
from amoeba.eval.sim_score import SCORERS, StandInScorer, score_run
from amoeba.task.models import Task
from scripts.run_task import main, parse_args

ROOT = Path(__file__).resolve().parents[1]


def test_the_frozen_list_names_the_judge():
    paths = frozen_paths()
    for p in ("amoeba/checks", "amoeba/task/quality.py", "amoeba/task/evaluate.py", "amoeba/eval"):
        assert p in paths, p


def copy_judge(tmp_path):
    for p in frozen_paths():
        src = ROOT / p
        if src.is_dir():
            shutil.copytree(src, tmp_path / p, ignore=shutil.ignore_patterns("__pycache__"))
        elif src.is_file():
            (tmp_path / p).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, tmp_path / p)
    shutil.copytree(ROOT / "amoeba" / "config", tmp_path / "amoeba" / "config", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def test_changing_a_frozen_file_changes_the_hash_and_the_comparison_refuses(tmp_path):
    root = copy_judge(tmp_path)
    before = judge_hash(root)
    assert before == judge_hash(root) and len(before["sha256"]) == 64
    (root / "amoeba" / "task" / "quality.py").write_text("# changed\n" + (root / "amoeba/task/quality.py").read_text())
    after = judge_hash(root)
    assert after["sha256"] != before["sha256"]
    assert [x["path"] for x in after["paths"] if x["sha256"] != next(
        y["sha256"] for y in before["paths"] if y["path"] == x["path"])] == ["amoeba/task/quality.py"]
    same_judge([{"judge_hash": before["sha256"]}, {"judge_hash": before["sha256"]}])           # the same: fine
    with pytest.raises(JudgeMismatch):
        same_judge([{"judge_hash": before["sha256"]}, {"judge_hash": after["sha256"]}])
    with pytest.raises(JudgeMismatch):
        same_judge([{"judge_hash": before["sha256"]}, {}])                                      # unknown: refused


def test_a_file_outside_the_judge_does_not_change_the_hash(tmp_path):
    root = copy_judge(tmp_path)
    before = judge_hash(root)["sha256"]
    (root / "amoeba" / "config" / "adapt.yaml").write_text("changed: true\n")
    assert judge_hash(root)["sha256"] == before


def test_the_stand_in_scorer_is_deterministic(tmp_path):
    (tmp_path / "result.json").write_text(json.dumps({"answer": "The answer is 396."}))
    sim = {"scorer": "standin", "expected": 396, "baseline": 0.5}
    a = StandInScorer().score(tmp_path, sim, seed=3)
    assert a == StandInScorer().score(tmp_path, sim, seed=3)
    assert (a["score"], a["baseline"], round(a["delta"], 6), a["seed"]) == (1.0, 0.5, 0.5, 3)
    (tmp_path / "result.json").write_text(json.dumps({"answer": "about 400"}))
    near = StandInScorer().score(tmp_path, sim, seed=3)
    assert 0.98 < near["score"] < 1.0
    (tmp_path / "result.json").write_text(json.dumps({"answer": "no number"}))
    assert StandInScorer().score(tmp_path, sim, seed=3)["score"] == 0.0
    assert "standin" in SCORERS


def test_score_run_writes_sim_score_json_with_the_judge_hash(tmp_path):
    (tmp_path / "result.json").write_text(json.dumps({"answer": "396"}))
    task = Task(prompt="Compute 17 * 23 + 5.", sim={"scorer": "standin", "expected": 396})
    out = score_run(tmp_path, task, seed=0, judge="abc")
    assert json.loads((tmp_path / "sim_score.json").read_text()) == out
    assert out["judge_hash"] == "abc" and out["scorer"] == "standin"
    assert score_run(tmp_path, Task(prompt="x"), seed=0, judge="abc") is None      # no scorer: no file written
    with pytest.raises(ValueError):
        score_run(tmp_path, Task(prompt="x", sim={"scorer": "nope"}), seed=0, judge="abc")


def test_task_sets_and_the_sim_field_are_read_from_jsonl():
    t = Task.model_validate_json(json.dumps({"prompt": "x", "set": "replay", "sim": {"scorer": "standin",
                                                                                   "expected": 1}}))
    assert t.task_set == "replay" and t.sim.expected == 1
    assert Task(prompt="x").task_set is None and Task(prompt="x").sim is None
    rows = [json.loads(l) for l in (ROOT / "tasks" / "general_example.jsonl").read_text().splitlines() if l.strip()]
    assert {r["set"] for r in rows} == {"stream", "replay"} and all(r["sim"]["scorer"] == "standin" for r in rows)


def test_a_toy_run_writes_the_same_sim_score_twice_and_the_hash(tmp_path, capsys):
    tasks = tmp_path / "t.jsonl"
    tasks.write_text(json.dumps({"id": "toy", "prompt": "Compute 17 * 23 + 5. Reply with just the number.",
                                 "ground_truth": "396", "set": "replay",
                                 "sim": {"scorer": "standin", "expected": 396, "baseline": 0.25}}) + "\n")
    scores = []
    for k in (1, 2):
        runs = tmp_path / f"runs{k}"
        assert main(["--tasks", str(tasks), "--topology", "flat", "--sim-seed", "7", "--runs-dir", str(runs)]) == 0
        run = next(runs.iterdir())
        res = json.loads((run / "result.json").read_text())
        sim = json.loads((run / "sim_score.json").read_text())
        assert res["judge_hash"] == judge_hash()["sha256"] == sim["judge_hash"] and res["sim_score"] == sim
        scores.append((sim["score"], sim["seed"], sim["delta"]))
    assert scores[0] == scores[1] and scores[0][1] == 7
    assert parse_args(["x"]).sim_seed is None
