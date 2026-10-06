"""D105 + D110 (amended) — the final-answer requirement check (offline, mock LLM): after the summariser, each Box 2
requirement is checked against the FINAL answer and each promised file against the workspace; missing items earn the
answer step one refine turn; what is still missing goes into Limitations, and the run ends `no_deliverable` when a core
deliverable is missing (no answer content, a promised file never made, more than half of the requirements unmet);
result.json's requirement_status (and the re-plan's requirement status) is the final-answer result, not the steps'
claims. Off, and for the baselines, nothing changes."""
import json

from amoeba.safety.envelope import Envelope
from amoeba.task.deliverables import (answer_content, check_deliverables, final_check, promised_files,
                                      requirement_check)
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
    m = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=worker,
             plan_summariser=worker)
    reg = default_registry()
    from amoeba.interp.plan_runner import PlanOptions
    with_llm = kw.pop("_with_llm", False)
    r = run_one(Task(id="t", prompt="Compute 17 * 23 + 5."), kw.pop("topology", "plan"), m,
                Envelope.from_registry(reg), reg, tmp_path / name, draft_prompts="d24",
                plan_options=kw.pop("plan_options", PlanOptions()),
                **kw)
    out = r, json.loads((tmp_path / name / r.run_id / "result.json").read_text())
    return (m, *out) if with_llm else out


def empty(messages, seed):
    n = step_no(messages)
    text = "# Result\nAll done, see the steps above.\n\n## Limitations\n- none" if n == "4" else f"OUT-{n}\n{BODY}"
    return f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\n{text}"


def test_a_run_without_answer_content_ends_no_deliverable(tmp_path, monkeypatch):
    monkeypatch.setattr("amoeba.task.deliverables.MIN_ANSWER_CHARS", 10_000)    # this answer now counts as empty
    m, r, res = run3(tmp_path, "empty", summariser(list(R)))
    assert res["status"] == "no_deliverable" and res["error"] == "no_deliverable: no answer content"
    assert res["deliverables"]["answer_chars"] < 10_000 and res["deliverables"]["checked_files"] is False
    monkeypatch.undo()
    m, r, res = run3(tmp_path, "full", summariser(list(R)))
    assert res["status"] == "ok" and res["error"] is None and res["deliverables"]["ok"] is True


def test_off_and_the_baselines_change_nothing(tmp_path):
    r, res = run(tmp_path, "off", finish)
    assert res["error"] is None and "deliverables" not in res
    assert parse_args(["x"]).deliverable_check == "on"


R = {"R1": "gather current benchmark results for PostgreSQL and MongoDB",
     "R2": "estimate the monthly cost for 50 tenants at 200 GB each",
     "R3": "prototype and test the event schema in both databases",
     "R4": "deliver a recommendation memo with a risk table"}
COVER = {"R1": "Current benchmark results: PostgreSQL 41k tps, MongoDB 38k tps (gathered by step 1).",
         "R2": "Estimated monthly cost for 50 tenants at 200 GB each: about 2,300 USD.",
         "R3": "We prototyped and tested the event schema in both databases (step 3).",
         "R4": "Recommendation memo: choose PostgreSQL; the risk table lists 3 risks."}


def test_requirements_against_the_final_answer():
    full = "\n".join(COVER.values())
    assert all(requirement_check(r, t, full, None)["status"] == "met" for r, t in R.items())
    part = requirement_check("R4", R["R4"], COVER["R2"], None)
    assert part["status"] == "missing" and "recom" in part["terms_missing"]
    blocked = requirement_check("R1", R["R1"], "BLOCKED: benchmark results for PostgreSQL and MongoDB — no web", None)
    assert blocked["status"] == "blocked"
    filed = requirement_check("R5", "a CSV file of the costs", full, ["notes.txt"])
    assert filed["status"] == "missing" and filed["files_missing"] == ["a csv file"]
    fc = final_check(COVER["R2"], R, {}, None)
    assert fc["unmet"] == ["R1", "R3", "R4"] and fc["core_missing"][-1] == "requirements not met: R1, R3, R4"
    fc = final_check("\n".join(v for k, v in COVER.items() if k != "R4"), R, {}, None)
    assert fc["unmet"] == ["R4"] and fc["core_missing"] == []                # one of four: Limitations, not core


def summariser(covered, fixes=False):
    def run(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        keys = list(R) if fixes and "is not met in the final answer" in user else covered
        extra = "\n".join(COVER[k] for k in keys)
        return f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\nOUT-{n}\n{BODY}\n{extra}\n"
    return run


def test_unmet_requirements_earn_the_refine_turn_and_a_fixed_answer_passes(tmp_path):
    m, r, res = run3(tmp_path, "fix", summariser(["R2"], fixes=True))
    asks = [c for c in m.calls_of("plan_summariser") if "is not met in the final answer" in c["messages"][-1]["content"]]
    assert len(asks) == 1 and "requirement R1" in asks[0]["messages"][-1]["content"]
    assert res["status"] == "ok" and res["requirement_status"] == {k: "met" for k in R}
    assert res["deliverables"]["unmet"] == [] and "NOT MET" not in res["answer"]


def test_still_unmet_goes_to_limitations_and_core_misses_end_no_deliverable(tmp_path):
    m, r, res = run3(tmp_path, "core", summariser(["R2"]))
    assert res["status"] == "no_deliverable" and res["error"] == "no_deliverable: requirements not met: R1, R3, R4"
    assert res["requirement_status"]["R1"] == "missing" and res["requirement_status"]["R2"] == "met"
    assert "- NOT MET: R1 — gather current benchmark results" in res["answer"]
    m, r, res = run3(tmp_path, "one", summariser(["R1", "R2", "R3"]))
    assert res["status"] != "no_deliverable" and res["requirement_status"]["R4"] == "missing"
    assert "- NOT MET: R4 — deliver a recommendation memo" in res["answer"]


def run3(tmp_path, name, worker, **kw):
    """The summariser covers some requirements; the other steps pass their checks."""
    def script(messages, seed):
        return worker(messages, seed) if step_no(messages) == "4" else finish(messages, seed)
    return run(tmp_path, name, script, deliverable_check=True, _with_llm=True, **kw)


def test_the_requirement_status_is_the_final_answer_result_not_the_steps_claims(tmp_path):
    from amoeba.interp.plan_runner import PlanOptions
    m, r, res = run3(tmp_path, "rp", summariser(["R2"]), plan_options=PlanOptions(replan="on"))
    req = res["replan"]["requirements"]
    assert req["R1"]["status"] == "not met" and req["R1"]["steps_claim"] == "met" and req["R1"]["final_answer"] == "missing"
    assert req["R2"]["status"] == "met"


def test_a_bare_value_is_an_answer():
    """A task that asks only for a value gets a bare value; that is content, not no_deliverable (was 80 characters)."""
    from amoeba.task.deliverables import answer_content, final_check
    assert answer_content("734") == 3
    assert final_check("734", {}, {}, None)["core_missing"] == []
    assert final_check("## Limitations\n- BLOCKED: web_search", {}, {}, None)["core_missing"] == ["no answer content"]
