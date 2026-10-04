"""D86 — Box 5, the Diagnoser (tier 0): run-record fixtures give the expected cause; a cause that was always there does
not explain an alarm; the allowed edits come from the table in adapt.yaml; examples are practice tasks only;
--diagnoser none gives the alarm only with every edit allowed. Offline, plain code."""
import json

from amoeba.adapt.diagnoser import diagnose, diagnose_none
from amoeba.adapt.monitor import LoopState, PracticeRecord, monitor
from amoeba.adapt.recipe import EDIT_OPS
from amoeba.adapt.stream import Stream, StreamTask

NUM = {"expected_numbers": [{"name": "total", "value": 42, "unit": "", "tolerance": 0}]}
POST = {**NUM, "required_deliverables": [{"name": "assumptions section", "any_of": ["(?im)^#+ assumptions"]}]}


def stream(n=12):
    return Stream(name="fx", tasks=[StreamTask(id=f"p{i}", prompt=f"Practice task {i}.", family="calc",
                                               split="practice", phase="pre" if i <= 8 else "post", order=i,
                                               rubric=NUM if i <= 8 else POST) for i in range(1, n + 1)]
                  + [StreamTask(id="h1", prompt="A held-out task.", family="calc", split="heldout", phase="post",
                                rubric=POST)],
                  shifts=[{"after": 8, "family": "calc", "kind": "feedback", "items": ["assumptions section"]}])


def run(tmp, order, score, failed=(), causes=(), hall=0):
    d = tmp / f"run{order}"
    (d / "artifacts").mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({"score": score, "error": None,
                                               "provenance": {"total": {"hallucinated_citations": hall}},
                                               "summary_check": {}}))
    (d / "plan.json").write_text(json.dumps({"created_roles": [{"name": "Analyst", "tools": ["calc"]},
                                                               {"name": "Writer", "tools": []}],
                                             "plan": [{"index": 0, "kind": "work", "do": "compute it",
                                                       "output": "the figures", "done_when": "figures computed"},
                                                      {"index": 1, "kind": "", "do": "write the answer",
                                                       "output": "the answer", "done_when": "answer written"}]}))
    (d / "artifacts" / "step_1.json").write_text(json.dumps({"step": 1, "roles": ["Analyst"], "causes": list(causes)}))
    (d / "artifacts" / "step_2.json").write_text(json.dumps({"step": 2, "roles": ["Writer"], "causes": []}))
    return PracticeRecord(order=order, task_id=f"p{order}", family="calc", run_dir=str(d), score=score,
                          failed_items=list(failed), causes=list(causes))


def alarm_of(records):
    for k in range(1, len(records) + 1):
        a = monitor(records[:k], LoopState(family="calc"))
        if a:
            return a, records[:k]


def test_the_feedback_shift_is_diagnosed_as_feedback_even_with_a_steady_cause(tmp_path):
    # every run, before and after the shift, has a "checks" cause on step 1: it was always there
    recs = [run(tmp_path, i, 1.0, causes=["checks"]) for i in range(1, 9)]
    recs += [run(tmp_path, i, 0.75, failed=["assumptions section"], causes=["checks"]) for i in range(9, 12)]
    alarm, upto = alarm_of(recs)
    d = diagnose(alarm, upto, stream())
    assert d.cause == "feedback" and d.symptom == "feedback: assumptions section missing in 2/3 runs"
    assert d.allowed_edits == ["add_planner_rule", "tighten_done_when", "add_role_rule"]
    assert d.shares["checks"] == {"window": 1.0, "reference": 1.0} and d.shares["feedback"]["reference"] == 0.0
    assert d.counts["feedback:assumptions section"] == 2 and d.counts["cause:checks"] == 3
    assert all("rubric failed item 'assumptions section'" in e for e in d.evidence)
    assert [e["task"] for e in d.examples] == ["Practice task 9.", "Practice task 10."]   # runs showing it first
    assert all("held-out" not in json.dumps(e) for e in d.examples)


def test_a_rising_cause_is_named_with_its_table_edits_and_where(tmp_path):
    recs = [run(tmp_path, i, 1.0) for i in range(1, 7)]
    recs += [run(tmp_path, i, 0.6, causes=["max_turns"]) for i in range(7, 10)]
    alarm, upto = alarm_of(recs)
    d = diagnose(alarm, upto, stream())
    assert d.cause == "max_turns" and d.allowed_edits == ["add_planner_rule", "set_run_option:max_turns"]
    assert d.where == {"step_kind": "work", "roles_with_tool": "calc"}
    assert d.evidence[0].endswith("causes max_turns (kind work, roles ['Analyst'])")
    assert d.examples[0]["do"] == "compute it" and d.examples[0]["step"] == 1


def test_diagnoser_none_is_the_alarm_only(tmp_path):
    recs = [run(tmp_path, i, 1.0) for i in range(1, 9)] + [run(tmp_path, i, 0.5) for i in range(9, 11)]
    alarm, _ = alarm_of(recs)
    d = diagnose_none(alarm)
    assert d.cause == "alarm_only" and d.allowed_edits == [e for e in EDIT_OPS if e != "prefer_model"] and d.evidence == [] and d.examples == []
