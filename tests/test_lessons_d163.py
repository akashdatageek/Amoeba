"""D163 — verdicts by plain code, the reflector, and one lesson library shared by every task (keyed by
(cause, op, scope); the niche of each count is recorded, never used to split). Offline: the mock LLM and fault
injection; the library is written to a temporary folder."""
import json
import multiprocessing
from types import SimpleNamespace

import pytest

from amoeba.adapt.lessons import (LessonLibrary, key_of, learn_from_round, lesson_problems, parse_reflection,
                                  round_verdicts, verdict)
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from amoeba.interp.trace import TraceWriter
from scripts.lessons import main as lessons_cli
from tests.test_plan_runner import plan_team
from tests.test_scoped_proposers_d154 import RULE_NO, RULE_OK, stall_until

TASK_ID = "task-0001"


def p(status="incomplete", cleared=(), new=(), limited=False, **kw):
    return {"scope": "inv", "op": "add_role_rule", "status": status, "cleared": list(cleared), "new": list(new),
            "limited": limited, "kept": [], "tokens": 10, "samples": 1, **kw}


def test_the_verdict_rules():
    assert verdict(p("done")) == "helped"
    assert verdict(p(limited=True)) == "helped"
    assert verdict(p(cleared=["max_turns"])) == "helped"
    assert verdict(p(new=["repeated_error"])) == "hurt"
    assert verdict(p()) == "no_effect"
    assert verdict(p(cleared=["a"], new=["b"])) == "confounded"
    assert verdict(p("done", composed_of=[{"scope": "inv", "op": "x"}, {"scope": "dom", "op": "y"}])) == "confounded"


def test_a_lesson_with_task_facts_denied_wording_or_too_long_is_refused():
    task = "Estimate the weekly fuel cost of a van in Hamburg that drives 120 km a day."
    ok = "When a step keeps calling one tool without finishing, add_role_rule (inv): tell the role to stop and report."
    assert lesson_problems("A step loops on one tool call until its turns run out.", ok, task) == []
    assert any("facts" in x for x in lesson_problems("cue", "Price the van in Hamburg first.", task))
    assert any("facts" in x for x in lesson_problems("cue", "Stop after 120 attempts.", task))
    assert any("denied" in x for x in lesson_problems("cue", "Skip the check and finish.", task))
    assert any("characters" in x for x in lesson_problems("cue", "x" * 301, task))
    assert parse_reflection("NO_ENTRY") is None
    assert parse_reflection('{"cue": "a", "lesson": "b", "confidence": "high"}')["lesson"] == "b"
    with pytest.raises(ValueError):
        parse_reflection("I think the lesson is to try harder.")


def row(*probes, cause="tool_error", niche="general", task_id=TASK_ID):
    return {"kind": "round", "task_id": task_id, "niche": niche, "step": 1, "cause": cause, "signals": ["x"],
            "edits": [], "probes": list(probes), "pick": "inv", "pick_reason": "", "step_status": "done"}


def test_the_library_counts_every_verdict_and_a_repeat_updates_the_same_entry(tmp_path):
    lib = LessonLibrary(tmp_path)
    for v in round_verdicts(row(p("done"), dict(p(new=["e"]), scope="dom"))):
        lib.record(v, "general", TASK_ID, "run1")
    for v in round_verdicts(row(p(cleared=["x"]), niche="calc", task_id="task-0002")):
        lib.record(v, "calc", "task-0002", "run2")
    inv = lib.get(key_of("tool_error", "add_role_rule", "inv"))
    dom = lib.get(key_of("tool_error", "add_role_rule", "dom"))
    assert len(lib.entries()) == 2                                       # a repeat updates, it does not add
    assert inv["counts"]["helped"] == 2 and inv["by_niche"] == {
        "general": {"helped": 1, "hurt": 0, "no_effect": 0, "confounded": 0},
        "calc": {"helped": 1, "hurt": 0, "no_effect": 0, "confounded": 0}}
    assert inv["task_ids"] == [TASK_ID, "task-0002"] and "status" not in inv     # D167: a family has no status
    assert dom["counts"]["hurt"] == 1 and not lib.lessons(dom["id"])
    assert len(lib.evidence(inv["id"])) == 2 and (tmp_path / inv["id"] / "edit.json").exists()
    assert "Helped 2, hurt 0" in (tmp_path / inv["id"] / "EXPERIENCE.md").read_text()


def _write_many(root, n):
    lib = LessonLibrary(root)
    for _ in range(n):
        [v] = round_verdicts(row(p("done")))
        lib.record(v, "general", TASK_ID, "runX")


def test_two_writers_on_the_same_key_lose_no_count(tmp_path):
    procs = [multiprocessing.Process(target=_write_many, args=(tmp_path, 25)) for _ in range(2)]
    for x in procs:
        x.start()
    for x in procs:
        x.join(30)
    [entry] = LessonLibrary(tmp_path).entries()
    assert entry["counts"]["helped"] == 50 and len(LessonLibrary(tmp_path).evidence(entry["id"])) == 50


def fake_runner(tmp_path, lib_dir):
    return SimpleNamespace(opt=SimpleNamespace(lessons_write="on", lessons_dir=str(lib_dir)), run_dir=tmp_path / "run",
                           ep=SimpleNamespace(episode_id="ep"))


def test_a_hurt_probe_raises_hurt_without_a_lesson_or_a_call(tmp_path):
    out = learn_from_round(fake_runner(tmp_path, tmp_path / "lib"), row(p(new=["repeated_error"])))
    assert out == {"verdicts": [{"id": key_of("tool_error", "add_role_rule", "inv"), "op": "add_role_rule",
                                 "scope": "inv", "verdict": "hurt"}], "lesson": None, "skipped": None}
    [e] = LessonLibrary(tmp_path / "lib").entries()
    assert e["counts"]["hurt"] == 1 and LessonLibrary(tmp_path / "lib").lessons() == []


LESSON = json.dumps({"cue": "A step keeps calling one tool and never ends with its output.",
                     "lesson": "add_role_rule (inv): tell the looping role to stop and give its final output.",
                     "confidence": "medium"})


def fault_run(task, envelope, trace, tools, run_dir, lib, reflector=(LESSON,), opts=None):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=stall_until("FINISH NOW"), fix_proposer_inv=[RULE_OK],
                         fix_proposer_dom=[RULE_NO], reflector=list(reflector))
    for a in cfg.agents.values():
        a.missing_tools = []
    cfg.meta["capability_requests"] = []
    opts = opts or PlanOptions(adapt="on", failed_step="run", proposer="scoped", faults=("tool_error:1:30",),
                               contract="on", lessons_write="on", lessons_dir=str(lib))
    ep = Interpreter(llm, tools, trace, run_dir=run_dir, plan_options=opts).run(cfg, task, seed=0)
    return llm, ep


def test_three_runs_with_the_same_fault_leave_one_entry_helped_three_times(task, envelope, tools, tmp_path):
    lib = tmp_path / "lib"
    for k in range(3):
        llm, ep = fault_run(task, envelope, TraceWriter(None, episode_id=f"e{k}"), tools, tmp_path / f"run{k}", lib)
        assert len(llm.calls_of("reflector")) == 1
    entries = {e["id"]: e for e in LessonLibrary(lib).entries()}
    inv = entries[key_of("tool_error", "add_role_rule", "inv")]
    assert inv["counts"]["helped"] == 3 and inv["run_ids"] == ["run0", "run1", "run2"]
    [les] = LessonLibrary(lib).lessons(inv["id"])         # D167: the same text three times is one lesson ...
    assert les["lesson"].startswith("add_role_rule (inv)") and les["status"] == "unreviewed"
    assert les["counts"]["helped"] == 1                   # ... counted once: the round that wrote it (none cited it)
    assert entries[key_of("tool_error", "add_role_rule", "dom")]["counts"]["no_effect"] == 3
    prompt = llm.calls_of("reflector")[0]["messages"][-1]["content"]
    assert "no score, no rubric and no answer key" in prompt and "tools: " in prompt and "skills: " in prompt


def test_a_refused_lesson_is_asked_once_more_then_dropped(task, envelope, trace, tools, tmp_path):
    bad = json.dumps({"cue": "Compute 17 * 23 + 5 again.", "lesson": "add_role_rule: skip the check.",
                      "confidence": "high"})
    llm, ep = fault_run(task, envelope, trace, tools, tmp_path / "run", tmp_path / "lib", reflector=[bad, bad])
    calls = llm.calls_of("reflector")
    assert len(calls) == 2 and "refused by plain code" in calls[1]["messages"][-1]["content"]
    assert LessonLibrary(tmp_path / "lib").lessons() == []
    assert [e["amoeba.attempt"] for e in trace.events("reflector_reply")] == [1, 2]


def test_no_entry_writes_no_lesson_but_keeps_the_counts(task, envelope, trace, tools, tmp_path):
    llm, ep = fault_run(task, envelope, trace, tools, tmp_path / "run", tmp_path / "lib", reflector=["NO_ENTRY"])
    inv = LessonLibrary(tmp_path / "lib").get(key_of("tool_error", "add_role_rule", "inv"))
    assert inv["counts"]["helped"] == 1 and not LessonLibrary(tmp_path / "lib").lessons() and \
        len(llm.calls_of("reflector")) == 1


def test_with_writing_off_nothing_is_written_and_no_call_is_made(task, envelope, trace, tools, tmp_path):
    opts = PlanOptions(adapt="on", failed_step="run", proposer="scoped", faults=("tool_error:1:30",), contract="on")
    llm, ep = fault_run(task, envelope, trace, tools, tmp_path / "run", tmp_path / "lib", opts=opts)
    assert not llm.calls_of("reflector") and not (tmp_path / "lib").exists()
    assert PlanOptions().lessons_write == "off"


def test_the_reflector_is_skipped_when_the_cap_would_not_hold_it(task, envelope, trace, tools, tmp_path,
                                                                    monkeypatch):
    import amoeba.adapt.lessons as L
    monkeypatch.setattr(L, "reflector_affordable", lambda r, est: "the run cap would not hold the reflector")
    llm, ep = fault_run(task, envelope, trace, tools, tmp_path / "run", tmp_path / "lib")
    assert not llm.calls_of("reflector") and ep.error is None
    [s] = trace.events("reflector_skipped")
    assert "run cap" in s["amoeba.why"]
    rows = [json.loads(x) for x in (tmp_path / "run" / "events.jsonl").read_text().splitlines()]
    assert any(r["event"] == "reflector_skipped" for r in rows)


def test_the_cli_lists_shows_approves_and_rejects(tmp_path, capsys):
    lib = LessonLibrary(tmp_path)
    [v] = round_verdicts(row(p("done")))
    fam = lib.record(v, "general", TASK_ID, "run1")
    e = lib.add_lesson(fam["id"], "a cue", "add_role_rule (inv): a lesson", "low", "run1")
    assert lessons_cli(["--root", str(tmp_path), "list"]) == 0 and e["id"] in capsys.readouterr().out
    assert lessons_cli(["--root", str(tmp_path), "show", e["id"]]) == 0 and "a lesson" in capsys.readouterr().out
    assert lessons_cli(["--root", str(tmp_path), "approve", e["id"]]) == 0
    assert lib.get(e["id"])["status"] == "approved"
    assert lessons_cli(["--root", str(tmp_path), "reject", e["id"]]) == 0
    assert lib.get(e["id"])["status"] == "rejected"
    assert lessons_cli(["--root", str(tmp_path), "show", "nope"]) == 1
    assert lessons_cli(["--root", str(tmp_path), "approve", fam["id"]]) == 1      # D167: a family has no status
