"""scripts/eval_draft.py — Box 2 evaluation, offline."""
import csv
import json

from amoeba.task.models import Task
from scripts.eval_draft import attempt, main, summarise
from tests.conftest import fx, mock

# a real failure shape: a {placeholder} inside a role prompt cuts the copied non-greedy regex short (environment.py:62)
BRACES = fx("draft_round_ok").replace('"You are a Calculator.', '"You are a Calculator. Evaluate {expression}.')


def test_attempt_ok_and_regex_loss(tmp_path, task, envelope):
    ok = attempt(task, 0, mock(planner=[fx("draft_round_ok")]), envelope, tmp_path, 0)
    assert ok["ok"] and ok["rounds"] == 1 and ok["roster"] == 2 and ok["calls"] == 3
    assert ok["roles_regex"] == ok["roles_balanced"] == ["Calculator", "Writer"] and ok["lost_to_regex"] == []
    assert ok["request_names"] == ["web_search"] and ok["ok_with_balanced_parse"]
    bad = attempt(task, 1, mock(planner=[BRACES]), envelope, tmp_path, 0)
    assert not bad["ok"] and bad["error"].startswith("draft: roster size 1")
    assert bad["roles_regex"] == ["Writer"] and bad["lost_to_regex"] == ["Calculator"]
    assert bad["ok_with_balanced_parse"] and bad["rounds"] == 1
    assert (tmp_path / "planner" / f"{task.id}.1.txt").read_text() == BRACES
    assert [r["kind"] for r in json.loads((tmp_path / "replies" / f"{task.id}.1.json").read_text())] == \
        ["planner", "agent_observer", "plan_observer"]
    rows = summarise([ok, bad])
    assert rows[-1]["task_id"] == "ALL" and rows[-1]["ok"] == 1 and rows[-1]["ok_with_balanced_parse"] == 2
    assert rows[-1]["errors"] == "roster size 1 x1"


def test_main_writes_summary_csv(tmp_path, monkeypatch):
    tasks = tmp_path / "t.jsonl"
    tasks.write_text("\n".join(json.dumps(Task(id=f"t{i}", prompt=p).model_dump()) for i, p in
                               enumerate(["Compute 26 * 28 + 6. Reply with just the number."])) + "\n")
    out = tmp_path / "out"
    assert main(["--tasks", str(tasks), "--repeats", "2", "--out", str(out)]) == 0   # offline stand-in AI
    rows = list(csv.DictReader(open(out / "summary.csv")))
    assert [r["task_id"] for r in rows] == ["t0", "ALL"] and rows[0]["attempts"] == "2" and rows[0]["ok"] == "2"
    assert len((out / "attempts.jsonl").read_text().splitlines()) == 2
