"""D119 — fault injection (test-only): the flag is refused without AMOEBA_TEST_FAULTS=1 and hidden from --help; each
fault fires at its point of the plan runner, the same way with --adapt off and on; the stuck watch's diagnosis and the
first fix on a scripted reply are the expected ones; result.json records the faults. Offline, with the mock LLM."""
import pytest

from amoeba.adapt.faults import (CAUSES, CHECK_NAME, EXPECTED, INJECTED_ERROR, Faults, check_flag, has_source_table,
                                 parse_fault, pick_step)
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from scripts import run_task
from tests.test_fixes_d117 import BODY, fake_stock, fixed, good, reply
from tests.test_plan_runner import plan_team, step_no

ENV = {"AMOEBA_TEST_FAULTS": "1"}


def run(task, envelope, trace, tools, script, faults, adapt="on", tmp_path=None, stock=None):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script, fix_proposer=["I cannot see a fix."] * 4)
    for a in cfg.agents.values():          # the fixture's helpers ask for web_search; only the injected fault stays
        a.missing_tools = []
    cfg.meta["capability_requests"] = []
    opts = PlanOptions(adapt=adapt, contract="on", faults=tuple(faults))     # contract on, as the CLI
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path, plan_options=opts, stock=stock).run(cfg, task, seed=0)
    return llm, cfg, ep


def prompts(llm, n):
    return [c["messages"][-1]["content"] for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == str(n)]


# ---- the flag -------------------------------------------------------------------------------------------------------
def test_no_fault_by_default_and_the_flag_is_refused_without_the_variable():
    assert PlanOptions().faults == () and not Faults(())
    assert check_flag([], "plan", env={}) == ()
    with pytest.raises(SystemExit, match="AMOEBA_TEST_FAULTS=1"):
        check_flag(["tool_error:1"], "plan", env={})
    with pytest.raises(SystemExit, match="--topology plan"):
        check_flag(["tool_error:1"], "flat", env=ENV)
    with pytest.raises(SystemExit, match="cause one of"):
        check_flag(["typo:1"], "plan", env=ENV)
    assert check_flag(["tool_error:auto", "missing_input:3:120"], "plan", env=ENV) == \
        ("tool_error:auto:3", "missing_input:3:120")


def test_run_task_refuses_the_flag_and_hides_it(monkeypatch, capsys):
    monkeypatch.delenv("AMOEBA_TEST_FAULTS", raising=False)
    with pytest.raises(SystemExit):
        run_task.parse_args(["--toy", "--topology", "plan", "--inject-fault", "tool_error:1"])
    monkeypatch.setenv("AMOEBA_TEST_FAULTS", "1")
    a = run_task.parse_args(["--toy", "--topology", "plan", "--inject-fault", "capability:auto"])
    assert a.inject_fault == ("capability:auto:0",) and run_task.cli_plan_options(a).faults == ("capability:auto:0",)
    with pytest.raises(SystemExit) as e:
        run_task.parse_args(["--help"])
    assert e.value.code == 0 and "inject" not in capsys.readouterr().out


def test_the_spec_and_the_auto_step():
    f = parse_fault("missing_input_b:auto")
    assert (f.cause, f.step, f.n) == ("missing_input_b", None, 200) and set(EXPECTED) == set(CAUSES)
    steps = [{"n": 1, "deps": [], "tools": [], "summary": False, "verify": False},
             {"n": 2, "deps": [1], "tools": ["calc"], "summary": False, "verify": False},
             {"n": 3, "deps": [1, 2], "tools": ["calc"], "summary": False, "verify": True},
             {"n": 4, "deps": [2], "tools": [], "summary": True, "verify": False}]
    assert [pick_step(c, steps) for c in ("tool_error", "capability", "missing_input", "max_turns", "checks")] == \
        [2, 2, 2, 1, 1]
    assert pick_step("tool_error", steps[:1]) is None
    assert has_source_table("| figure | Source |\n|---|---|\n| 3 | [S1] |") and not has_source_table(BODY)


# ---- each fault -------------------------------------------------------------------------------------------------------
def calc_until_it_works(messages, seed):
    """Calls calc until a call returns a number, then finishes (also on the last turn: it never gives up)."""
    n, user = step_no(messages), messages[-1]["content"]
    if n == "1" and ">Result:\n2" not in user:
        return reply("calc", "1 + 1")
    return good(n)


def test_tool_error_is_diagnosed_and_more_turns_recovers_it(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, calc_until_it_works, ["tool_error:auto:7"], tmp_path=tmp_path)
    [f] = ep.faults
    assert (f["cause"], f["step"], f["fired"], f["tools"]) == ("tool_error", 1, 7, ["calc"])
    assert ep.stuck[0]["step"] == 1 and ep.stuck[0]["cause"] == "tool_error" == f["expected"]["diagnosis"]
    [fix] = ep.adaptation["fixes"]
    assert (fix["kind"], fix["result"]) == (f["expected"]["first_fix"], "recovered")
    assert INJECTED_ERROR.format(tool="calc") in prompts(llm, 1)[1]
    assert [e["amoeba.call"] for e in trace.events("fault_fired")] == list(range(1, 8))


def test_the_same_fault_fires_with_adapt_off(task, envelope, trace, tools):
    llm, cfg, ep = run(task, envelope, trace, tools, calc_until_it_works, ["tool_error:1:7"], adapt="off")
    # four calls fail; on the fifth, last turn the helper asks for calc again and is not run (D76); no fix
    assert ep.faults[0]["fired"] == 4 and not trace.events("fix_try")
    assert ep.steps[0]["status"] == "incomplete"


def blocked_without_calc(messages, seed):
    n, user = step_no(messages), messages[-1]["content"]
    if n == "1" and "Tool calc is unavailable this run" in user:
        return reply("Final Output", f"OUT-1\n{BODY}\nBLOCKED: calc — it was taken away")
    return good(n)


def test_capability_is_diagnosed_and_a_grant_from_the_registry_ends_it(task, envelope, trace, tools):
    calls = []
    llm, cfg, ep = run(task, envelope, trace, tools, blocked_without_calc, ["capability:auto"],
                       stock=fake_stock(calls))
    [f] = ep.faults
    assert (f["step"], f["tool"], f["cleared"]) == (1, "calc", "granted back")
    assert ep.stuck[0]["cause"] == "capability" and ep.adaptation["fixes"][0]["kind"] == "grant_tool"
    assert ep.adaptation["fixes"][0]["attached"] == ["calc"] and ep.adaptation["recovered_steps"] == [1]
    assert calls == []                                       # the registry has it: no pool step
    analyst = next(a for a in cfg.agents.values() if a.name == "Cost Analyst")
    assert "calc" in analyst.tools and "calc" not in analyst.missing_tools     # step 3 has it again


def test_capability_with_adapt_off_hides_the_tool_for_its_step_only(task, envelope, trace, tools):
    llm, cfg, ep = run(task, envelope, trace, tools, blocked_without_calc, ["capability:1"], adapt="off")
    first, third = prompts(llm, 1)[0], prompts(llm, 3)[0]
    assert "Tool calc is unavailable this run" in first and "Tool calc is unavailable" not in third
    assert ep.steps[0]["status"] == "partial" and ep.faults[0]["fired"] == 1 and not ep.faults[0]["cleared"]
    assert any(s["step"] == 3 and s["status"] == "done" for s in ep.steps)


TAIL = "TAIL-MARK"


def long_output(n):
    return reply("Final Output", f"OUT-{n}\n{BODY}\n" + "padding words " * 30 + TAIL)


def needs_the_tail(messages, seed):
    n, user = step_no(messages), messages[-1]["content"]
    if n == "1":
        return long_output(1)
    if n == "2" and TAIL not in user:
        return reply("Final Output", f"OUT-2\n{BODY}\nBLOCKED: Step 1 figures — the input is cut off")
    return good(n)


def test_missing_input_is_diagnosed_and_passing_it_in_full_ends_it(task, envelope, trace, tools):
    llm, cfg, ep = run(task, envelope, trace, tools, needs_the_tail, ["missing_input:auto"])
    [f] = ep.faults
    assert (f["step"], f["upstream"], f["cleared"]) == (2, 1, "passed in full")
    assert ep.stuck[0]["cause"] == "missing_input" and ep.stuck[0]["upstream"] == [1]
    [fix] = ep.adaptation["fixes"]
    assert fix["kind"] == "add_dependency" and fix["result"] == "recovered"
    assert TAIL not in prompts(llm, 2)[0] and TAIL in prompts(llm, 2)[-1]


def needs_the_tail_b(messages, seed):
    n, user = step_no(messages), messages[-1]["content"]
    if n == "1":
        return long_output(1)
    if n == "2" and TAIL not in user:
        return reply("Final Output", f"OUT-2\n{BODY}\nBLOCKED: Step 1 {TAIL} — not in its output")
    return good(n)


def test_missing_input_b_cuts_the_saved_output_and_a_rerun_of_the_upstream_ends_it(task, envelope, trace, tools,
                                                                                    tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, needs_the_tail_b, ["missing_input_b:2"], tmp_path=tmp_path)
    [f] = ep.faults
    assert (f["upstream"], f["fired"], f["cleared"]) == (1, 1, "upstream re-run")
    assert (tmp_path / "artifacts" / "step_1.try1.md").read_text().strip() == long_output(1).split(
        "## ActionInput\n")[1][:200].strip()
    assert ep.stuck[0]["cause"] == "missing_input"
    assert [x["kind"] for x in ep.adaptation["fixes"]] == ["rerun_upstream"] == [f["expected"]["first_fix"]]
    assert ep.adaptation["recovered_steps"] == [2]


def calls_twice_then_finishes(messages, seed):
    n, user = step_no(messages), messages[-1]["content"]
    if n == "1" and user.count(">Result:") < 2:
        return reply("calc", "1 + 1")
    return good(n)


def test_max_turns_gives_two_turns_without_a_forced_end_until_a_fix_sets_the_turns(task, envelope, trace, tools):
    llm, cfg, ep = run(task, envelope, trace, tools, calls_twice_then_finishes, ["max_turns:1"])
    [f] = ep.faults
    assert ep.stuck[0]["cause"] == "max_turns" and f["cleared"] == "turns set by a fix"
    [fix] = ep.adaptation["fixes"]
    assert (fix["kind"], fix["result"]) == ("set_run_option:max_turns", "recovered")
    assert len(prompts(llm, 1)) == 2 + 3                      # two turns, then the fixed attempt's three


def no_source_table(messages, seed):
    return good(step_no(messages))


def test_checks_adds_a_check_that_fails_until_the_output_has_a_source_table(task, envelope, trace, tools):
    llm, cfg, ep = run(task, envelope, trace, tools, no_source_table, ["checks:1"], adapt="off")
    s1 = next(s for s in ep.steps if s["step"] == 1)
    assert [c["name"] for c in s1["checks"] if not c["pass"]] == [CHECK_NAME] and s1["status"] == "incomplete"
    assert any("Source column" in p for p in prompts(llm, 1)[1:])   # the retry turn shows it
    assert all(c["name"] != CHECK_NAME for s in ep.steps if s["step"] != 1 for c in s["checks"])


def test_with_adapt_on_the_checks_fault_is_diagnosed_checks(task, envelope, trace, tools):
    llm, cfg, ep = run(task, envelope, trace, tools, no_source_table, ["checks:1"])
    assert ep.stuck[0]["cause"] == "checks"
    assert ep.adaptation["fixes"][0]["kind"] == "set_run_option:check_retry_turns"


def test_a_fault_with_no_step_to_act_on_is_logged_and_does_nothing(task, envelope, trace, tools):
    llm, cfg, ep = run(task, envelope, trace, tools, no_source_table, ["capability:2"], adapt="off")
    assert ep.faults[0]["cleared"] == "not armed: step 2 holds no tool" and trace.events("fault_unarmed")
    assert ep.error is None


def test_without_a_fault_nothing_changes(task, envelope, trace, tools):
    llm, cfg, ep = run(task, envelope, trace, tools, no_source_table, [])
    assert ep.faults == [] and not trace.events("fault_armed") and ep.error is None
