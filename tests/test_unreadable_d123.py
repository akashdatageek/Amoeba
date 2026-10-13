"""D123 — a reply plain code cannot read no longer ends the run: a required heading glued onto a sentence is read
by plain code (no repair call), a reply still unreadable after the repair call fails only that turn and is a stuck
signal for Box 4 (cause `format`), and a run that stops anyway (Box 4 gave up, a parse error outside a helper turn,
or a bug in our code) keeps the finished steps as a partial answer. Offline, with the mock LLM."""
import pytest

from amoeba.adapt.stuck import diagnose, step_signals
from amoeba.interp.plan_runner import PlanRunner
from amoeba.task.parsers import ParseError, parse_sections, unglue
from tests.test_fixes_d117 import good, reply, run
from tests.test_plan_runner import step_no

GLUED = ("<thought>plan</thought>## Thought\nLet's start with the math verification.## CurrentStep\nStep 4\n"
         "## Action\nFinal Output\n## ActionInput\nOUT-2\nVerdict: PASS")
BROKEN = "## Thought\nI will check the figures now and write the verdict."      # no CurrentStep/Action/ActionInput


def test_unglue_puts_a_glued_required_heading_on_its_own_line_and_nothing_else():
    assert "CurrentStep" not in parse_sections(GLUED)                       # D84a: a mid-line '##' is text
    assert parse_sections(unglue(GLUED, ["CurrentStep"]))["CurrentStep"] == "Step 4"
    quoted = "Write a section headed '## Assumptions' at the end.\n## Action\nx"
    assert unglue(quoted, ["Assumptions"]) == quoted                       # text follows the heading: stays text
    assert unglue("a.## Verdict\nPASS", ["CurrentStep"]) == "a.## Verdict\nPASS"   # only the keys asked for


def counted(script):
    calls = {}

    def f(messages, seed):
        n = step_no(messages)
        calls[n] = calls.get(n, 0) + 1
        return script(n, calls[n])
    return f, calls


def test_a_glued_heading_is_read_by_plain_code_without_a_repair_call(task, envelope, trace, tools):
    glued = lambda n: good(n).replace("ok\n\n## CurrentStep", "Let's start with the math verification.## CurrentStep")
    f, calls = counted(lambda n, k: glued(n) if n == "2" else good(n))
    _, _, ep = run(task, envelope, trace, tools, f)
    assert ep.error is None and calls["2"] == 1                             # one call, no repair
    assert trace.events("sections_unglued")[0]["amoeba.sections"] == ["CurrentStep"]


def test_an_unreadable_reply_fails_only_that_turn(task, envelope, trace, tools, tmp_path):
    f, calls = counted(lambda n, k: BROKEN if n == "2" and k <= 2 else good(n))   # the reply and its repair
    _, _, ep = run(task, envelope, trace, tools, f, tmp_path)
    assert ep.error is None and ep.answer                                   # the run went on to the answer
    ev = trace.events("unreadable_reply")
    assert len(ev) == 1 and ev[0]["amoeba.step"] == 2 and "CurrentStep" in ev[0]["amoeba.missing"]
    meta = next(s for s in ep.steps if s["step"] == 2)
    assert meta["status"] == "done" and len(meta["unreadable_turns"]) == 1 and not meta.get("stuck")


def test_the_stuck_watch_names_format_only_when_the_step_did_not_finish():
    bad = [{"agent": "Auditor", "turn": 5, "why": "error: your reply could not be read (missing sections ['CurrentStep'])"}]
    meta = {"step": 4, "status": "incomplete", "status_reason": "max_turns; unreadable replies: 1",
            "unreadable_turns": bad, "finished": False}
    d = diagnose(step_signals(meta))
    assert d["cause"] == "format" and d["signals"] == ["unreadable_reply", "max_turns"]
    assert d["allowed_edits"][0] == "set_run_option:max_turns" and "add_role_rule" in d["allowed_edits"]
    assert step_signals({**meta, "finished": True, "status_reason": "mislabelled citation"}) == []


def test_box4_tries_more_turns_then_stops_with_the_finished_steps(task, envelope, trace, tools, tmp_path):
    f, _ = counted(lambda n, k: BROKEN if n == "3" else good(n))           # step 3 never writes a readable reply
    _, _, ep = run(task, envelope, trace, tools, f, tmp_path)
    assert ep.stuck[0]["cause"] == "format" and ep.stuck[0]["step"] == 3
    assert trace.events("fix_try")[0]["amoeba.fix"] == "set_run_option:max_turns"
    assert ep.error.startswith("stuck: step 3 (format)")
    report = (tmp_path / "adapt_report.md").read_text()
    assert ep.answer.startswith(report) and "# Partial answer" in ep.answer
    assert "## Step 1:" in ep.answer and "## Step 2:" in ep.answer and "**Steps that did not run:** 4" in ep.answer
    assert "**Steps that ran but did not finish:** 3 (incomplete)" in ep.answer


def stop_at_step(exc):
    orig = PlanRunner.run_step

    def run_step(self, step, wave, deps, **kw):
        if step.index == 2:                                                # step 3
            raise exc
        return orig(self, step, wave, deps, **kw)
    return run_step


def test_a_parse_error_outside_a_helper_turn_keeps_the_finished_steps(task, envelope, trace, tools, tmp_path,
                                                                     monkeypatch):
    monkeypatch.setattr(PlanRunner, "run_step", stop_at_step(ParseError("no verdict block")))
    f, _ = counted(lambda n, k: good(n))
    _, _, ep = run(task, envelope, trace, tools, f, tmp_path)
    assert ep.error.startswith("parse: no verdict block: stopped with step(s) 3, 4 not run")
    assert ep.answer.startswith("# Partial answer") and "## Step 1:" in ep.answer and "## Step 2:" in ep.answer
    assert (tmp_path / "artifacts" / "answer.md").read_text().startswith("# Partial answer")


def test_a_bug_in_our_code_is_raised_after_the_finished_steps_are_saved(task, envelope, trace, tools, tmp_path,
                                                                       monkeypatch):
    monkeypatch.setattr(PlanRunner, "run_step", stop_at_step(KeyError("oops")))
    f, _ = counted(lambda n, k: good(n))
    with pytest.raises(KeyError):
        run(task, envelope, trace, tools, f, tmp_path)
    assert trace.events("crash")[0]["error.type"] == "KeyError" and trace.events("crash")[0]["amoeba.steps"] == [1, 2]
    saved = (tmp_path / "artifacts" / "answer.md").read_text()
    assert "an error in Amoeba's code: KeyError" in saved and "## Step 2:" in saved
