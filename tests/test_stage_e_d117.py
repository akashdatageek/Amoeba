"""D117 Stage E — the pair runner and its report, offline: a toy task with the mock LLM, --adapt off then on (the on
arm reuses the off arm's draft), and the report of the folder."""
import json
import sys

from amoeba.task.source import ToyTaskSource
from scripts.stage_e import arm_command, run_pairs
from scripts.stage_e_report import report


def test_the_on_arm_reuses_the_off_arm_and_only_adapt_differs(tmp_path):
    off = arm_command("off", tmp_path / "t.jsonl", 2, tmp_path / "r", tmp_path / "p.json", None, ["--topology", "plan"])
    on = arm_command("on", tmp_path / "t.jsonl", 2, tmp_path / "r", tmp_path / "p.json", tmp_path / "offrun",
                     ["--topology", "plan"])
    assert off[off.index("--adapt") + 1] == "off" and on[on.index("--adapt") + 1] == "on"
    assert on[-2:] == ["--drafts-from", str(tmp_path / "offrun")] and "--drafts-from" not in off
    strip = lambda c: [x for i, x in enumerate(c) if x not in ("off", "on") and c[i - 1] != "--drafts-from"
                       and x != "--drafts-from"]
    assert strip(off) == strip(on)


def test_a_pilot_folder_runs_and_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(__import__("pathlib").Path(__file__).resolve().parents[1])
    task = ToyTaskSource(0, 1).tasks()[0]
    tasks = tmp_path / "toy.jsonl"
    tasks.write_text(json.dumps({"id": "toy-1", "prompt": task.prompt, "ground_truth": task.ground_truth}) + "\n")
    out = tmp_path / "pilot"
    rows = run_pairs(tasks, ["toy-1"], [0], out, ["--topology", "plan", "--llm", "mock"], python=sys.executable)
    assert [(r["arm"], r["rc"]) for r in rows] == [("off", 0), ("on", 0)]
    on = json.loads(open(f"{rows[1]['run']}/result.json").read())
    assert on["draft_source"] == rows[0]["run"].rsplit("/", 1)[1]              # the off arm's draft, reused
    assert run_pairs(tasks, ["toy-1"], [0], out, ["--topology", "plan", "--llm", "mock"]) == []   # resumable
    md, data = report(out)
    assert {r["arm"]: r["outcome"] for r in data["records"]} == {"off": "done", "on": "done"}
    assert "| toy-1 | 0 | on | done |" in md and data["arms"]["on"]["runs"] == 1
    assert "No step was recovered." in md


def test_an_answer_with_a_partial_last_step_is_done_with_limitation(tmp_path):
    from scripts.stage_e_report import run_record
    run = tmp_path / "run"
    (run / "artifacts").mkdir(parents=True)
    (run / "result.json").write_text(json.dumps({"status": "agent_error", "error": "partial", "answer": "# Answer",
                                                 "usage": {"tokens": 10}}))
    (run / "artifacts" / "step_1.json").write_text(json.dumps(
        {"step": 1, "status": "partial", "status_reason": "mislabelled citation: '0%' not in S2", "checks": []}))
    r = run_record({"task": "t", "seed": 0, "arm": "on", "run": str(run), "rc": 0})
    assert r["outcome"] == "done with limitation" and r["not_done"] == {"mislabelled citation": 1} and not r["problems"]
    (run / "result.json").write_text(json.dumps({"status": "agent_error", "error": "parse: no sections", "answer": None}))
    assert run_record({"task": "t", "seed": 0, "arm": "on", "run": str(run), "rc": 0})["outcome"] == "failed"
