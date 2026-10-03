"""D93 — Diagnoser provenance: every counted signal is observed (written by the runner: tool calls, files, source
matches, rubric results, turn caps, format checks) or declared (written by the model: BLOCKED / NOT NEEDED, [S#] tags,
verifier verdicts, rework). Alarms and the chosen cause use observed signals only; declared ones are supporting
evidence. Offline, plain code."""
import json

from amoeba.adapt.architect import diagnosis_text
from amoeba.adapt.diagnoser import diagnose, provenance_of, run_signals
from amoeba.adapt.monitor import LoopState, PracticeRecord, monitor, practice_record
from amoeba.adapt.recipe import EDIT_OPS
from amoeba.adapt.stream import StreamTask
from tests.test_diagnoser_d86 import NUM, alarm_of, stream


def run(tmp, order, score, step=None, hall=0, failed=()):
    d = tmp / f"run{order}"
    (d / "artifacts").mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({"score": score, "error": None, "rubric": {"items": [
        {"name": i, "pass": False} for i in failed]}, "provenance": {"total": {"hallucinated_citations": hall}},
        "summary_check": {}}))
    (d / "plan.json").write_text(json.dumps({"created_roles": [{"name": "Analyst", "tools": ["calc"]}],
                                             "plan": [{"index": 0, "kind": "work", "do": "compute it"}]}))
    s = {"step": 1, "roles": ["Analyst"], "causes": [], "blocked_canonical": [], "contract_missing": [], "unused": [],
         **(step or {})}
    (d / "artifacts" / "step_1.json").write_text(json.dumps(s))
    t = StreamTask(id=f"p{order}", prompt=f"Practice task {order}.", family="calc", split="practice", phase="pre",
                   order=order, rubric=NUM)
    return practice_record(t, d)


BLOCKED = {"causes": ["capability"], "blocked_canonical": ["web_search"]}
LACKED = {"causes": ["capability"], "contract_missing": ["web_search"]}


def test_the_provenance_table():
    assert provenance_of("feedback:assumptions section") == "observed"
    assert provenance_of("unverified_check") == provenance_of("mislabelled_citations") == "observed"
    assert provenance_of("hallucinated_citations") == provenance_of("blocked_canonical") == "declared"
    assert provenance_of("verdict_fail") == provenance_of("not_needed") == "declared"
    assert provenance_of("cause:capability_blocked") == "declared" and provenance_of("cause:max_turns") == "observed"


def test_a_blocked_line_alone_is_a_declared_capability(tmp_path):
    r = run(tmp_path, 1, 1.0, BLOCKED)
    assert r.causes == [] and r.declared == ["capability"]
    r2 = run(tmp_path, 2, 1.0, LACKED)
    assert r2.causes == ["capability"] and r2.declared == []
    sig = run_signals(tmp_path / "run1", [])
    assert "capability" not in sig["by_cause"] and sig["declared"]["capability"]


def test_declared_signals_raise_no_cause_alarm(tmp_path):
    recs = [run(tmp_path, i, 1.0) for i in range(1, 7)] + [run(tmp_path, i, 1.0, BLOCKED) for i in range(7, 10)]
    assert all(monitor(recs[:k], LoopState(family="calc")) is None for k in range(1, len(recs) + 1))
    recs2 = [run(tmp_path / "b", i, 1.0) for i in range(1, 7)] + [run(tmp_path / "b", i, 1.0, LACKED)
                                                                  for i in range(7, 10)]
    alarm = next(a for k in range(1, 10) if (a := monitor(recs2[:k], LoopState(family="calc"))))
    assert alarm.kind == "cause" and alarm.signals == ["capability"]


def test_a_score_drop_with_only_declared_signals_names_no_cause(tmp_path):
    recs = [run(tmp_path, i, 1.0) for i in range(1, 9)]
    recs += [run(tmp_path, i, 0.4, {"verification": True, "verdict": "FAIL"}, hall=3) for i in range(9, 12)]
    alarm, upto = alarm_of(recs)
    d = diagnose(alarm, upto, stream())
    assert d.cause == "alarm_only" and d.allowed_edits == list(EDIT_OPS) and d.evidence == []
    assert "no observed cause" in d.symptom and "declared only: checks, honesty" in d.symptom
    assert any("hallucinated_citations 3" in e for e in d.supporting)
    assert d.declared_shares["honesty"]["window"] > 0 and d.shares["honesty"]["window"] == 0.0
    assert d.provenance["hallucinated_citations"] == "declared" and d.counts["hallucinated_citations"] == 3


def test_observed_signals_choose_the_cause_and_declared_ones_support_it(tmp_path):
    mis = {"mislabelled_citations": [{"source": "S1", "claim": "42"}]}
    recs = [run(tmp_path, i, 1.0) for i in range(1, 9)]
    recs += [run(tmp_path, i, 0.4, mis, hall=2) for i in range(9, 12)]
    alarm, upto = alarm_of(recs)
    d = diagnose(alarm, upto, stream())
    assert d.cause == "honesty" and all("mislabelled_citations" in e for e in d.evidence)
    assert d.supporting and all("hallucinated_citations" in e for e in d.supporting)
    text = diagnosis_text(d)
    assert "supporting (declared by the team's model, not checked by code)" in text


def test_feedback_is_observed_and_beats_a_rising_declared_signal(tmp_path):
    recs = [run(tmp_path, i, 1.0) for i in range(1, 9)]
    recs += [run(tmp_path, i, 0.5, BLOCKED, failed=["assumptions section"]) for i in range(9, 12)]
    alarm, upto = alarm_of(recs)
    d = diagnose(alarm, upto, stream())
    assert d.cause == "feedback" and d.shares["capability"]["window"] == 0.0
    assert d.declared_shares["capability"]["window"] > 0
