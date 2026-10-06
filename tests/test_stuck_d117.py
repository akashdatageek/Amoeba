"""D117 Stage B — the stuck watch: after each step attempt plain code looks for the five stuck signals, marks a step
that did not end done STUCK, diagnoses one cause from adapt.yaml and logs it (trace, step_N.json, result field,
hash-chained events.jsonl). No fix yet. The same functions read stored run folders (scripts/stuck_report.py).
Offline, with the mock LLM."""
import json

from amoeba.adapt.evidence import verify
from amoeba.adapt.stuck import diagnose, is_stuck, norm_error, owes_file, repeated_errors, step_signals
from amoeba.interp.plan_runner import PlanOptions
from scripts.run_task import cli_plan_options, parse_args
from scripts.stuck_report import report, run_stuck
from tests.test_contract import run, worker

FAIL = {"agent": "A", "tool": "pool:fx", "ok": False}


def meta(**kw):
    return {"step": 1, "status": "incomplete", "status_reason": "", "roles": ["Cost Analyst"], "checks": [], **kw}


def signals(m, **kw):
    return [s["signal"] for s in step_signals(m, **kw)]


def test_the_same_error_twice_in_a_row_is_a_signal_digits_aside():
    calls = [{**FAIL, "result": "error: timeout after 30 s"}, {**FAIL, "result": "error: timeout after 31 s"}]
    assert norm_error("Error: line 12") == norm_error("error:   line 9") and len(repeated_errors(calls)) == 1
    other = [{**FAIL, "result": "error: timeout"}, {**FAIL, "result": "error: 404 not found"}]
    apart = [calls[0], {"agent": "A", "tool": "pool:fx", "ok": True, "result": "95"}, calls[1]]
    assert repeated_errors(other) == [] and repeated_errors(apart) == []
    assert signals(meta(tool_calls=calls)) == ["repeated_error"]


def test_each_of_the_other_signals():
    failed = [{"name": "format", "pass": False, "detail": "no table"}]
    assert signals(meta(checks=failed, retried=True)) == ["checks_after_retry"]
    assert signals(meta(status_reason="max_turns", turns=6)) == ["max_turns"]
    assert signals(meta(blocked=["web_search"])) == ["capability_unfilled"]
    asked = [{"name": "fx_api", "for_role": "Cost Analyst", "status": "unfilled", "reason": "no candidate"}]
    s = step_signals(meta(), unfilled=asked + [{**asked[0], "for_role": "Someone Else"}])
    assert [x["signal"] for x in s] == ["capability_unfilled"] and len(s[0]["evidence"]) == 1
    owes = meta(output_spec="the costs as costs.xlsx", files_made=[])
    assert owes_file(owes) and signals(owes) == []                     # one attempt: nothing to compare yet
    assert signals(owes, previous=meta(files_made=[])) == ["no_file_change"]
    assert signals(owes, files_unchanged=True) == ["no_file_change"]
    assert signals(owes, previous=meta(files_made=[{"path": "a.csv", "size": 3}])) == []


def test_a_step_that_ended_done_is_not_stuck():
    m = meta(status="done", tool_calls=[{**FAIL, "result": "x"}, {**FAIL, "result": "x"}])
    assert step_signals(m) and not is_stuck(m, step_signals(m))


def test_diagnose_picks_one_cause_in_the_table_order_with_its_allowed_edits():
    m = meta(blocked=["web_search"], status_reason="max_turns",
             tool_calls=[{**FAIL, "result": "x"}, {**FAIL, "result": "x"}])
    d = diagnose(step_signals(m))
    assert d["cause"] == "capability" and d["signals"] == ["repeated_error", "max_turns", "capability_unfilled"]
    assert "grant_tool" in d["allowed_edits"] and "prefer_model" not in d["allowed_edits"]   # model edits are off
    t = diagnose(step_signals(meta(tool_calls=m["tool_calls"])))
    assert t["cause"] == "tool_error" and t["allowed_edits"] == ["add_role_rule", "grant_tool",
                                                                 "set_run_option:max_turns"]
    assert len(diagnose(step_signals(meta(checks=[{"name": f"c{i}", "pass": False} for i in range(20)])))
               ["evidence"]) == 8


def test_the_live_watch_logs_a_stuck_step(task, envelope, trace, tools, tmp_path):
    llm, cfg, by, ep = run(task, envelope, trace, tools, worker(), tmp_path=tmp_path,
                           options=PlanOptions(contract="on", adapt="on"))
    one = by[1]
    assert one["status"] == "partial" and one["stuck"]["cause"] == "capability"
    assert "lacked: web_search" in one["stuck"]["evidence"]
    assert "stuck" not in by[3] or by[3]["status"] != "done"
    [ev] = [e for e in trace.events("stuck") if e["amoeba.step"] == 1]
    assert ev["amoeba.cause"] == "capability" and "grant_tool" in ev["amoeba.allowed_edits"]
    rows = [json.loads(l) for l in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert {r["event"] for r in rows} == {"stuck"} and rows[0]["data"]["step"] == 1
    assert len(rows) == len(ep.stuck) and verify(tmp_path)["ok"]
    saved = json.loads((tmp_path / "artifacts" / "step_1.json").read_text())
    assert saved["stuck"]["cause"] == "capability"


def test_off_watches_nothing(task, envelope, trace, tools, tmp_path):
    llm, cfg, by, ep = run(task, envelope, trace, tools, worker(), tmp_path=tmp_path)
    assert "stuck" not in by[1] and trace.events("stuck") == [] and not (tmp_path / "events.jsonl").exists()


def test_the_flag_is_on_from_the_cli_and_off_in_the_library():
    assert parse_args(["--toy"]).adapt == "on" and cli_plan_options(parse_args(["--toy"])).adapt == "on"
    assert cli_plan_options(parse_args(["--toy", "--adapt", "off"])).adapt == "off"
    assert PlanOptions().adapt == "off"


def test_the_report_reads_stored_runs_the_same_way(tmp_path):
    run_dir = tmp_path / "eval" / "set1" / "r1"
    art = run_dir / "artifacts"
    art.mkdir(parents=True)
    (run_dir / "result.json").write_text("{}")
    (run_dir / "capability_requests.json").write_text(json.dumps(
        [{"name": "fx_api", "for_role": "Cost Analyst", "status": "unfilled"}]))
    (art / "step_1.json").write_text(json.dumps(meta(tool_calls=[])))                       # capability (asked)
    (art / "step_2.json").write_text(json.dumps(meta(step=2, roles=["Writer"], status="done", tool_calls=[])))
    owes = meta(step=3, roles=["Writer"], output_spec="out.xlsx", files_made=[])
    (art / "step_3.first.json").write_text(json.dumps(owes))
    (art / "step_3.json").write_text(json.dumps(owes))                                     # redone, no new file
    recs = run_stuck(run_dir)
    assert [(r["step"], r["attempt"], r["cause"]) for r in recs] == [(1, 1, "capability"), (2, 1, None),
                                                                     (3, 1, None), (3, 2, "claimed_file_missing")]
    r = report([str(tmp_path / "eval")])
    s = r["sets"]["eval/set1"]
    assert (s["runs"], s["attempts"], s["stuck"], s["no_tool_calls"]) == (1, 4, 2, 2)
    assert dict(r["total"]["causes"]) == {"capability": 1, "claimed_file_missing": 1}
