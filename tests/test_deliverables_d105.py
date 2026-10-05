"""D105 — a run whose required deliverables are missing ends `no_deliverable`, not "no error" (offline, mock LLM):
an answer without content, or a file the plan promised (by name or by kind) that the workspace never got, sets
error 'no_deliverable: …' and status no_deliverable; result.json records what was checked. Off, and for the
baselines, nothing changes."""
import json

from amoeba.safety.envelope import Envelope
from amoeba.task.deliverables import answer_content, check_deliverables, promised_files
from amoeba.task.models import Task, run_status
from amoeba.tools.registry import default_registry
from scripts.run_task import parse_args, run_one
from tests.conftest import mock
from tests.test_plan_runner import APPROVE, BODY, DIAMOND, finish, step_no

TEXT = "The 2023 real median income was $80,610 in the US and $67,173 in Indiana, both in 2023 dollars [S1]."


def test_promised_files_by_name_and_by_kind():
    got = promised_files({"step 3 output": "income_real.csv with one row per year",
                          "step 4 output": "a PNG chart of both series", "requirement R2": "an Excel workbook"})
    assert [(g["name"], g["kind"]) for g in got] == [("income_real.csv", "csv"), (None, "png"), (None, "xlsx")]
    assert promised_files({"step 1 output": "a table in the answer"}) == []


def test_the_check():
    plan = {"step 3 output": "income_real.csv", "step 4 output": "a PNG chart"}
    ok = check_deliverables(TEXT, plan, [{"path": "income_real.csv"}, {"path": "chart.png"}])
    assert ok["ok"] and ok["missing"] == []
    renamed = check_deliverables(TEXT, plan, [{"path": "real_income.csv"}, {"path": "chart.png"}])
    assert renamed["ok"]                                                  # same kind, another name: made
    miss = check_deliverables(TEXT, plan, [{"path": "notes.txt"}])
    assert miss["missing"] == ["income_real.csv", "a png file"] and not miss["ok"]
    assert check_deliverables(TEXT, plan, None)["ok"]                     # no local tools: files not checked
    blocked = "# Result\nBLOCKED: no data for the CPI series\nBLOCKED: no chart\n\n## Limitations\n- everything"
    assert answer_content(blocked) == 0 and not check_deliverables(blocked, {}, None)["ok"]
    assert run_status("no_deliverable: no answer content") == "no_deliverable"


def run(tmp_path, name, worker, **kw):
    m = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=worker)
    reg = default_registry()
    from amoeba.interp.plan_runner import PlanOptions
    r = run_one(Task(id="t", prompt="Compute 17 * 23 + 5."), kw.pop("topology", "plan"), m,
                Envelope.from_registry(reg), reg, tmp_path / name, draft_prompts="d24", plan_options=PlanOptions(),
                **kw)
    return r, json.loads((tmp_path / name / r.run_id / "result.json").read_text())


def empty(messages, seed):
    n = step_no(messages)
    text = "# Result\nAll done, see the steps above.\n\n## Limitations\n- none" if n == "4" else f"OUT-{n}\n{BODY}"
    return f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\n{text}"


def test_a_run_without_answer_content_ends_no_deliverable(tmp_path, monkeypatch):
    monkeypatch.setattr("amoeba.task.deliverables.MIN_ANSWER_CHARS", 10_000)    # this answer now counts as empty
    r, res = run(tmp_path, "empty", finish, deliverable_check=True)
    assert res["status"] == "no_deliverable" and res["error"] == "no_deliverable: no answer content"
    assert res["deliverables"]["answer_ok"] is False and res["deliverables"]["checked_files"] is False
    monkeypatch.undo()
    r, res = run(tmp_path, "full", finish, deliverable_check=True)
    assert res["status"] == "ok" and res["error"] is None and res["deliverables"]["ok"] is True


def test_off_and_the_baselines_change_nothing(tmp_path):
    r, res = run(tmp_path, "err", empty, deliverable_check=True)
    assert res["error"] == "incomplete" and "deliverables" not in res     # an earlier error is kept as it was
    r, res = run(tmp_path, "off", finish)
    assert res["error"] is None and "deliverables" not in res
    assert parse_args(["x"]).deliverable_check == "on"
