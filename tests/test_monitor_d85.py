"""D85 — Box 4, the Monitor: run-record fixtures give the expected alarm; no alarm before 4 reference runs, during a
dwell or a cool-down; the reference restarts after an accept. Offline, plain code."""
import json

from amoeba.adapt.monitor import Alarm, LoopState, PracticeRecord, monitor, practice_record
from amoeba.adapt.stream import StreamTask


def rec(order, score, failed=(), causes=()):
    return PracticeRecord(order=order, task_id=f"t{order}", family="calc", run_dir=f"runs/r{order}", score=score,
                          failed_items=list(failed), causes=list(causes))


PRE = [rec(i, 1.0) for i in range(1, 9)]
POST = [rec(i, 0.75, failed=["assumptions section"]) for i in range(9, 17)]


def first_alarm(records, state=None):
    state = state or LoopState(family="calc")
    for k in range(1, len(records) + 1):
        a = monitor(records[:k], state)
        if a:
            return a
    return None


def test_the_feedback_shift_raises_an_alarm_within_three_tasks():
    a = first_alarm(PRE + POST)
    assert a.at_order == 10 and a.kind == "score"                     # window [8, 9, 10] = 1.0, .75, .75
    assert a.before == 1.0 and a.after == round((1 + .75 + .75) / 3, 4)
    assert a.signals == ["feedback:assumptions section"] and a.window == ["r8", "r9", "r10"]
    assert a.reference_orders == [1, 2, 3, 4, 5, 6, 7]


def test_a_cause_alarm_without_a_score_drop():
    runs = [rec(i, 1.0) for i in range(1, 7)] + [rec(i, 1.0, causes=["checks"]) for i in range(7, 10)]
    a = first_alarm(runs)
    assert a.kind == "cause" and a.signals == ["checks"] and (a.before, a.after) == (0.0, 0.6667) and a.at_order == 8


def test_stable_scores_and_noise_raise_nothing():
    wobbly = [rec(i, s) for i, s in enumerate([1, .9, 1, .95, 1, .9, 1, .95, 1, .92], 1)]
    assert first_alarm(wobbly) is None


def test_no_alarm_before_four_reference_runs():
    assert first_alarm([rec(1, 1.0), rec(2, 1.0), rec(3, 0.5), rec(4, 0.5), rec(5, 0.5)]) is None


def test_dwell_cooldown_and_the_reference_after_an_accept():
    assert monitor(PRE + POST[:2], LoopState(family="calc", quiet_until=10)) is None       # quiet
    assert monitor(PRE + POST[:3], LoopState(family="calc", quiet_until=10)) is not None   # order 11 may alarm
    # after an accept at order 10 the reference restarts at 11: the post-shift level is the new normal
    after = PRE + POST
    assert monitor(after, LoopState(family="calc", reference_from=11, quiet_until=14)) is None


def test_practice_record_reads_the_run_folder(tmp_path):
    d = tmp_path / "run"
    (d / "artifacts").mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({"score": 0.75, "error": None, "rubric": {"items": [
        {"name": "total", "pass": True}, {"name": "assumptions section", "pass": False}]}}))
    (d / "artifacts" / "step_1.json").write_text(json.dumps({"causes": ["checks", "made_up"]}))
    t = StreamTask(id="m", prompt="p", family="calc", split="practice", phase="post", order=9,
                   rubric={"expected_numbers": []})
    r = practice_record(t, d, recipe_version=2)
    assert (r.order, r.score, r.failed_items, r.causes, r.recipe_version) == (9, 0.75, ["assumptions section"],
                                                                              ["checks"], 2)
