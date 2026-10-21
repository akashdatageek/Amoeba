"""D138 — Box 3 correctness bugs found by the Oct 15 audit (B1–B10), one test each (B3 and B7 also in
tests/test_plan_runner.py and tests/test_collab.py). Offline."""
from types import SimpleNamespace

from amoeba.interp.plan_runner import (ANSWER_CHARS, PlanOptions, PlanRunner, answer_like, rechecks,
                                       writes_files)
from amoeba.interp.runtime import Interpreter
from amoeba.task.deliverables import final_findings
from amoeba.task.models import Episode
from tests.test_fixes_d117 import BODY, good, reply
from tests.test_plan_runner import FULL, plan_team, step_no

# step 3 needs only step 2, the summariser's step 4 only step 1: when step 2 fails, step 3 is skipped and the
# summariser still reads every artifact, the skipped one included
SKIP_PLAN = (FULL.replace("   depends_on: 1, 2\n", "   depends_on: 2\n")
             .replace("   covers: R4\n   depends_on: 3", "   covers: R4\n   depends_on: 1"))


def test_b1_a_skipped_step_does_not_crash_the_summariser(task, envelope, trace, tools):
    llm, cfg = plan_team(task, envelope, trace, text=SKIP_PLAN,
                         plan_worker=lambda m, s: "" if step_no(m) == "2" else good(step_no(m)))
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions(failed_step="dependents")).run(cfg, task, seed=0)
    by = {m["step"]: m for m in ep.steps}
    assert by[3]["blocked_upstream"] == [2] and by[3]["provenance"]["cited"] == 0
    assert by[4]["turns"] >= 1 and "OUT-4" in (ep.answer or "")           # the summariser ran


def test_b2_a_rework_with_no_new_final_output_keeps_the_earlier_one(task, envelope, trace, tools):
    calls = {"1": 0}

    def script(messages, seed):
        n = step_no(messages)
        if n == "1":
            calls["1"] += 1
            if calls["1"] > 1:                                               # the refine turn(s): only notes
                return reply("Print", "still looking")
        return good(n)
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script)
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions(self_refine="always")).run(cfg, task, seed=0)
    one = next(m for m in ep.steps if m["step"] == 1)
    assert one["rework_no_output"] == ["refine"] and one["status"] == "done"
    assert trace.events("rework_no_output")[0]["amoeba.step"] == 1
    two = [c for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "3"][0]
    assert "OUT-1" in two["messages"][-1]["content"] and "still looking" not in two["messages"][-1]["content"]


def test_b3_a_step_with_only_notes_counts_as_no_output_and_its_dependents_wait(task, envelope, trace, tools):
    def script(messages, seed):
        n = step_no(messages)
        return reply("Print", "a note") if n == "2" else good(n)
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script)
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions()).run(cfg, task, seed=0)
    by = {m["step"]: m for m in ep.steps}
    assert by[2]["no_final_output"] is True and by[2]["last_message"] == "a note"
    assert by[4]["blocked_upstream"] == [2]                                  # D133 sees step 2's missing output


def test_b4_native_short_text_is_not_the_step_output(task, envelope, trace, tools):
    seen = {"n": 0}

    def script(messages, seed):
        n = step_no(messages)
        if n == "1":
            seen["n"] += 1
            if seen["n"] == 1:
                return "Let me look at this first."                        # no call, short, not the last turn
        return good(n)
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script)
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions(native_tools="on")).run(cfg, task, seed=0)
    one = next(m for m in ep.steps if m["step"] == 1)
    assert trace.events("native_text_no_action") and one["turns"] >= 2
    assert "Call one of your tools" in [c for c in llm.calls_of("plan_worker")
                                        if step_no(c["messages"]) == "1"][1]["messages"][-1]["content"]
    assert answer_like("x" * (ANSWER_CHARS + 1)) and answer_like("## Result\nok") and \
        answer_like("| a | b |\n|---|---|\n| 1 | 2 |") and not answer_like("Let me look at this first.")


def test_b5_a_step_without_a_file_tool_is_told_to_list_missing_files():
    fc = {"unmet": [], "requirements": {}, "files_missing": ["memo.docx"], "undated": []}
    assert "List each missing file under Limitations as not made." in final_findings(fc, can_make_files=False)[0]
    assert "Make them if the work allows" in final_findings(fc)[0]
    assert not writes_files([SimpleNamespace(tools=[])]) and writes_files([SimpleNamespace(tools=["local:Write"])])


def test_b6_a_corrected_dispute_figure_marks_its_consumers_stale(task, envelope, trace, tools, monkeypatch):
    from tests.test_disputes_d109 import resolver, run
    calls = []
    orig = PlanRunner.mark_stale
    monkeypatch.setattr(PlanRunner, "mark_stale", lambda self, r, v: (calls.append((list(r), v)), orig(self, r, v)))
    run(task, envelope, trace, tools, resolver("calc", "750 * 2", "1500", "calc 750 * 2 = 1500"))
    assert ([1], 2) in calls                                                 # the producer, by the verify step


def test_b8_find_tool_and_failed_calls_are_not_rechecks():
    calls = [{"tool": "find_tool", "ok": True}, {"tool": "calc", "ok": False}, {"tool": "Print", "ok": True}]
    assert rechecks(calls) == []
    assert rechecks(calls + [{"tool": "fetch_url", "ok": True}]) == [{"tool": "fetch_url", "ok": True}]


def test_b9_a_verifier_gets_the_full_text_of_a_capped_input(task, envelope, trace, tools, tmp_path):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=lambda m, s: good(step_no(m)))
    interp = Interpreter(llm, tools, trace, plan_options=PlanOptions(max_input_chars=600))
    runner = PlanRunner(interp, cfg, task, Episode(episode_id="e", team_id="t", task_id=task.id),
                        options=PlanOptions(max_input_chars=600))
    runner.local = SimpleNamespace(workspace=tmp_path)
    long_text = "HEAD " + "x " * 2000 + " TAIL"
    runner.artifacts[1] = {"text": long_text, "meta": {"roles": ["Cost Analyst"], "status": "done"}}
    text = runner.inputs_text([1], 3, evidence=True)
    assert "inputs/step_1.md" in text and (tmp_path / "inputs" / "step_1.md").read_text() == long_text
    assert "inputs/step_1.md" not in runner.inputs_text([1], 3, evidence=False)


def test_b10_the_library_default_is_dependents():
    assert PlanOptions().failed_step == "dependents"
    assert BODY                                                              # (the shared fixture still imports)
