"""D157 — task input files: a task may name files; run_task copies them into the run's workspace/inputs/ (read-only,
like sources/), lists them with their sizes in Box 1's and Box 2's prompts and on every helper's role card, and Box 2
checks that every given file is named by a step. Offline: the mock LLM."""
import json
import stat

from amoeba.localtools.gate import protected_command, protected_path
from amoeba.task.inputs import copy_inputs, inputs_text
from amoeba.task.models import Draft, Task
from amoeba.task.quality import HARD_CHECKS, input_files_named
from scripts.run_task import run_one
from tests.conftest import fx, mock


def given(tmp_path):
    src = tmp_path / "given"
    src.mkdir()
    (src / "zones.csv").write_text("zone,area\nA,10\nB,20\n")
    (src / "red.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 100)
    return [str(src / "zones.csv"), str(src / "red.png")]


def test_a_task_may_name_files_and_old_tasks_have_none(tmp_path):
    assert Task(prompt="x").files == []
    t = Task.model_validate_json(json.dumps({"prompt": "x", "files": given(tmp_path)}))
    assert [p.rsplit("/", 1)[-1] for p in t.files] == ["zones.csv", "red.png"]


def test_copied_read_only_and_listed_with_sizes(tmp_path):
    ws = tmp_path / "run" / "workspace"
    rows = copy_inputs(given(tmp_path), ws)
    assert [r["path"] for r in rows] == ["inputs/zones.csv", "inputs/red.png"]
    assert rows[0]["size"] == len("zone,area\nA,10\nB,20\n") and rows[1]["size"] == 108
    for r in rows:
        p = ws / r["path"]
        assert p.is_file() and not p.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    text = inputs_text(rows)
    assert "inputs/zones.csv (20 bytes)" in text and "inputs/red.png (108 bytes)" in text and "read-only" in text
    assert inputs_text([]) == ""


def test_a_missing_file_stops_the_run_before_any_call(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        copy_inputs([str(tmp_path / "nope.csv")], tmp_path / "ws")


def test_writes_into_inputs_are_refused_reading_and_copying_from_it_are_not(tmp_path):
    assert protected_path(tmp_path / "inputs" / "zones.csv", tmp_path)
    for c in ("echo x > inputs/zones.csv", "rm inputs/red.png", "cp a.csv inputs/zones.csv", "sed -i s/A/B/ inputs/z"):
        assert protected_command(c), c
    for c in ("cat inputs/zones.csv", "cp inputs/zones.csv work.csv", "python3 read.py inputs/red.png"):
        assert protected_command(c) is None, c


def test_the_planner_the_reader_and_every_helper_see_the_files(tmp_path, envelope, tools):
    from tests.test_interpret_d77 import entities
    llm = mock(interpreter=lambda m, s: entities(0.9, 0.05, 0.05), planner=[fx("draft_round_ok")],
               plan_worker=["## Thought\nok\n\n## Final_Output\n396\n"] * 9)
    task = Task(prompt="Compute 17 * 23 + 5 using zones.csv and red.png.", files=given(tmp_path))
    r = run_one(task, "plan", llm, envelope, tools, tmp_path / "runs", interpret=True)
    run = tmp_path / "runs" / r.run_id
    assert (run / "workspace" / "inputs" / "zones.csv").read_text().startswith("zone,area")
    kinds = {}
    for c in llm.calls:
        kinds.setdefault(c["kind"], []).append(json.dumps(c["messages"]))
    for kind in ("interpreter", "planner", "plan_worker"):
        assert kinds.get(kind), kind
        assert all("inputs/zones.csv (20 bytes)" in m and "inputs/red.png (108 bytes)" in m for m in kinds[kind]), kind
    res = json.loads((run / "result.json").read_text())
    assert res["input_files"] == [{"path": "inputs/zones.csv", "size": 20}, {"path": "inputs/red.png", "size": 108}]
    assert res.get("files_created", []) == [] or all(not f["path"].startswith("inputs/") for f in res["files_created"])


def plan(*texts):
    from amoeba.task.models import DraftPlanStep
    return Draft(created_roles=[], plan=[DraftPlanStep(index=i, text=t, agent_names=["A"]) for i, t in enumerate(texts)],
                 rounds_used=1, consensus=True)


def test_box2_checks_that_a_step_names_each_given_file():
    assert "input_files_named" in HARD_CHECKS
    files = ["inputs/zones.csv", "inputs/red.png"]
    ok = input_files_named(plan("Read inputs/zones.csv and red.png", "Write the answer"), files)
    assert ok["ok"] is True
    bad = input_files_named(plan("Read zones.csv", "Write the answer"), files)
    assert bad["ok"] is False and bad["not_named"] == ["inputs/red.png"]
    assert input_files_named(plan("x"), [])["ok"] is None              # no files given: n/a


def test_the_cli_takes_files_for_a_free_text_task():
    from scripts.run_task import parse_args
    assert parse_args(["x", "--file", "a.csv", "--file", "b.png"]).file == ["a.csv", "b.png"]
    assert parse_args(["x"]).file == []


def test_in_sandbox_mode_the_files_go_into_the_sandbox_read_only(tmp_path):
    from amoeba.interp.trace import TraceWriter
    from amoeba.localtools.toolbox import LocalSetup, LocalToolbox

    class Box:
        def __init__(self):
            self.calls = []

        def exec(self, cmd, stdin=None, timeout_s=60):
            self.calls.append((cmd, stdin))
            return type("R", (), {"exit_code": 0})()

    b = LocalToolbox(LocalSetup(env={}), tmp_path / "run", TraceWriter(None))
    copy_inputs(given(tmp_path), b.workspace)
    b.box = Box()
    b._push_given()
    sent = {c[0][2].split("cat > ")[1].split(" ")[0]: c[1] for c in b.box.calls}
    assert set(sent) == {"/sandbox/workspace/inputs/zones.csv", "/sandbox/workspace/inputs/red.png"}
    assert sent["/sandbox/workspace/inputs/zones.csv"].startswith(b"zone,area")
    assert all("chmod 0444" in c[0][2] for c in b.box.calls)
    assert b._snapshot() == {}                                   # given files are never counted as made
