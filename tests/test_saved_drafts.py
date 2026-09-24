"""D45 — reuse saved Box 2 drafts (eval_draft folders and run folders); no drafting call is made."""
import json

import pytest

from amoeba.task.draft import draft_team
from amoeba.task.saved_drafts import load_saved_drafts, pick
from scripts.run_task import main, run_one
from tests.conftest import fx, mock

APPROVE = fx("observer_d24_approve")


def a_draft(task, envelope, trace):
    return draft_team(task, mock(planner=[fx("draft_d24_full")], agent_observer=[APPROVE], plan_observer=[APPROVE]),
                      envelope, trace, prompts="d24")


def eval_draft_folder(tmp_path, task, envelope, trace):
    """The shape scripts/eval_draft.py writes: drafts/<task>.<rep>.json, a failed attempt included."""
    d = tmp_path / "cmp-model-d24" / "drafts"
    d.mkdir(parents=True)
    good = a_draft(task, envelope, trace).model_dump(mode="json")
    (d / f"{task.id}.0.json").write_text(json.dumps(good))
    (d / f"{task.id}.1.json").write_text(json.dumps({"error": "draft: roster size 1", "rounds": []}))
    (d / f"{task.id}.2.json").write_text(json.dumps({**good, "rounds_used": 2}))
    return d.parent


def test_eval_draft_folders_load_directly_and_skip_failed_drafts(tmp_path, task, envelope, trace):
    saved = load_saved_drafts(eval_draft_folder(tmp_path, task, envelope, trace))
    xs = saved[task.id]
    assert [x.source for x in xs] == [f"cmp-model-d24/drafts/{task.id}.0", f"cmp-model-d24/drafts/{task.id}.2"]
    assert pick(saved, task.id, 1).draft.rounds_used == 2 and pick(saved, task.id, 2) is None
    assert xs[0].draft.created_roles[0].name == "Cost Analyst"


@pytest.mark.parametrize("topology", ["flat", "plan", "boss_reviewers"])
def test_a_reused_draft_makes_no_drafting_call(tmp_path, task, envelope, trace, tools, topology):
    saved = load_saved_drafts(eval_draft_folder(tmp_path, task, envelope, trace))
    llm = mock(worker=[fx("worker_final_output")], plan_worker=[fx("worker_final_output")], solver=["396"],
               critic=["Action: Agree\nAction Input: fine."])
    r = run_one(task, topology, llm, envelope, tools, tmp_path / "runs", saved_draft=pick(saved, task.id, 0))
    kinds = {c["kind"] for c in llm.calls}
    assert not kinds & {"planner", "agent_observer", "plan_observer"}
    assert r.draft_source == f"cmp-model-d24/drafts/{task.id}.0"
    saved_json = json.loads((tmp_path / "runs" / r.run_id / "result.json").read_text())
    assert saved_json["draft_source"] == r.draft_source
    assert json.loads((tmp_path / "runs" / r.run_id / "plan.json").read_text())["created_roles"]


def test_run_folders_load_too_in_start_order(tmp_path, task, envelope, tools):
    llm = mock(planner=[fx("draft_d24_full")], agent_observer=[APPROVE], plan_observer=[APPROVE],
               worker=[fx("worker_final_output")])
    first = run_one(task, "flat", llm, envelope, tools, tmp_path, draft_prompts="d24")
    second = run_one(task, "flat", llm, envelope, tools, tmp_path, draft_prompts="d24")
    saved = load_saved_drafts(tmp_path)
    assert [x.source for x in saved[task.id]] == [first.run_id, second.run_id]
    assert [x.source for x in load_saved_drafts(tmp_path / first.run_id)[task.id]] == [first.run_id]


def test_cli_reuses_the_picked_draft_and_skips_tasks_without_one(tmp_path, capsys):
    from amoeba.task.source import ToyTaskSource
    t = ToyTaskSource(0, 2).tasks()
    d = tmp_path / "saved" / "drafts"
    d.mkdir(parents=True)
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text("\n".join(x.model_dump_json() for x in t))
    # a saved draft for the first task only, made by the offline stand-in
    main(["--tasks", str(tasks), "--runs-dir", str(tmp_path / "first")])
    first = json.loads(next((tmp_path / "first").glob("*/result.json")).read_text())
    run = next(p for p in (tmp_path / "first").iterdir() if json.loads((p / "result.json").read_text())["task_id"] == t[0].id)
    (d / f"{t[0].id}.0.json").write_text((run / "plan.json").read_text())
    capsys.readouterr()
    assert main(["--tasks", str(tasks), "--drafts-from", str(tmp_path / "saved"), "--runs-dir", str(tmp_path / "r")]) == 0
    out = capsys.readouterr().out
    assert f"{t[1].id}: no saved draft #0" in out and "rounds=" in out
    [res] = [json.loads(p.read_text()) for p in (tmp_path / "r").glob("*/result.json")]
    assert res["draft_source"] == f"saved/drafts/{t[0].id}.0" and res["score"] == 1.0 and first
