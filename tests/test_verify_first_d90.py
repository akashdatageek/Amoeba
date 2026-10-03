"""D90 — the verifier answers first: a verify step first works out its own result from the checked steps' inputs and
its tools, in a fresh turn loop that never sees their outputs; only then are the outputs shown and compared. Both
sides and plain code's figure comparison are recorded in step_N.json; the D65 rule (a PASS with no re-checking tool
call is an unverified check) still holds, counting the tool calls of both parts."""
import json

from amoeba.interp.plan_runner import PlanOptions, compare_figures
from amoeba.interp.runtime import Interpreter
from tests.test_plan_runner import step_no
from tests.test_verify_tools import MEMO, PRIMES, WEATHER, local_tools, primes_script, reply, team

FIRST = PlanOptions(contract="on", verify_first="on")


def own_script(runs: bool, count: str = "1229"):
    def run(messages, seed):
        user = messages[-1]["content"]
        if runs and "(local:Bash):" not in user:
            return reply("local:Bash", "python3 prime_finder.py")
        return reply("Final Output", f"Step 1 should give: count {count}, largest 9973 (re-ran the finder).")
    return run


def run(task, envelope, trace, tools, own, checker_runs=False, opt=FIRST):
    calls = []
    local_tools(tools, calls)
    llm, cfg = team(task, envelope, trace, PRIMES, primes_script(checker_runs))
    llm._script["plan_verify_own"] = own
    next(a for a in cfg.agents.values() if a.name == "Software Engineer").tools.append("local:Bash")
    ep = Interpreter(llm, tools, trace, plan_options=opt).run(cfg, task, seed=0)
    return llm, {s["step"]: s for s in ep.steps}, calls


def test_the_own_result_is_made_without_the_outputs_it_checks(task, envelope, trace, tools):
    llm, by, _ = run(task, envelope, trace, tools, own_script(True))
    first = llm.calls_of("plan_verify_own")[0]["messages"][-1]["content"]
    assert "Write and run the prime finder" in first                 # the checked step's instruction
    assert "Count: 1229" not in first and "print(len(primes))" not in first   # not its output
    assert "Raw tool results" not in first and "Evidence plain code recorded" not in first
    assert "Verdict: PASS" not in first.split("# Tools")[0].split("# Your own result first")[1]
    later = [c for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "2"][0]["messages"][-1]["content"]
    assert "## Your own result (you worked it out before you saw the outputs above)" in later
    assert "Step 1 should give: count 1229" in later and "Count: 1229" in later
    assert "Compare the outputs with" in later
    assert all(c["kind"] != "plan_verify_own" or step_no(c["messages"]) == "2" for c in llm.calls)


def test_both_sides_and_the_comparison_are_recorded(task, envelope, trace, tools):
    llm, by, _ = run(task, envelope, trace, tools, own_script(True, count="1230"))
    two = by[2]
    own = two["verifier_own"]
    assert own["text"].startswith("Step 1 should give: count 1230") and own["outputs_hidden"] == [1]
    assert own["tool_calls"][0]["tool"] == "local:Bash" and own["reused"] is False
    cmp = two["comparison"]
    assert cmp["verdict"] == "PASS" and "9973" in cmp["figures"]["matched"]
    assert "1230" in cmp["figures"]["own_only"] and cmp["figures"]["agreement"] == 0.5
    [ev] = trace.events("verifier_own")
    assert ev["amoeba.outputs_hidden"] == [1] and ev["amoeba.tool_calls"] == 1


def test_the_d65_rule_still_holds(task, envelope, trace, tools):
    llm, by, calls = run(task, envelope, trace, tools, own_script(False))
    assert (by[2]["verdict"], by[2]["status"], by[2]["unverified_check"]) == ("PASS", "partial", True)


def test_a_re_check_made_in_the_own_result_counts(task, envelope, trace, tools):
    llm, by, calls = run(task, envelope, trace, tools, own_script(True))
    assert (by[2]["verdict"], by[2]["status"], by[2]["unverified_check"]) == ("PASS", "done", False)
    assert len(calls) == 2                       # step 1's run and the verifier's own re-run


def test_the_weather_checker_sees_the_inputs_of_the_step_it_checks_not_its_output(task, envelope, trace, tools):
    tools.register("web_search", "search the web", lambda text: "[S1] Saturday: high 72°F, low 55°F, rain 10%")

    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1":
            if "(web_search):" not in user:
                return reply("web_search", "Saturday forecast")
            return reply("Final Output", f"{MEMO}Saturday: high 72°F [S1], rain 10% [S1]")
        if n == "2":
            return reply("Final Output", f"{MEMO}Outdoor picnic at noon, tents not needed.")
        if n == "3":
            return reply("Final Output", f"Verdict: PASS\nIssues: none\n{MEMO}Step 2 fits the forecast.")
        return reply("Final Output", f"{MEMO}An outdoor event at 72°F.")
    llm, cfg = team(task, envelope, trace, WEATHER, script)
    llm._script["plan_verify_own"] = [reply("Final Output", "A dry, mild Saturday: an outdoor plan fits.")]
    next(a for a in cfg.agents.values() if a.name == "Forecaster").tools.append("web_search")
    ep = Interpreter(llm, tools, trace, plan_options=FIRST).run(cfg, task, seed=0)
    first = llm.calls_of("plan_verify_own")[0]["messages"][-1]["content"]
    assert "## Output of step 1 (an input of the steps you check)" in first and "high 72°F [S1]" in first
    assert "Outdoor picnic at noon" not in first and "Plan the event around the forecast" in first
    three = {s["step"]: s for s in ep.steps}[3]
    assert three["verifier_own"]["outputs_shown"] == [1] and three["verifier_own"]["outputs_hidden"] == [2]


def test_a_re_check_after_rework_reuses_the_own_result(task, envelope, trace, tools):
    local_tools(tools, [])
    verdicts = ["Verdict: FAIL\nIssues:\n1. step 1: the count is 1230, rerun"]

    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1":
            return reply("Final Output", f"{MEMO}Count: 1229\nLargest: 9973")
        if n == "2":
            return reply("Final Output", f"{verdicts.pop() if verdicts else 'Verdict: PASS'}\n{MEMO}checked")
        return reply("Final Output", f"{MEMO}done")
    llm, cfg = team(task, envelope, trace, PRIMES, script)
    llm._script["plan_verify_own"] = own_script(False)
    ep = Interpreter(llm, tools, trace, plan_options=FIRST).run(cfg, task, seed=0)
    assert len(llm.calls_of("plan_verify_own")) == 1
    two = {s["step"]: s for s in ep.steps if s["step"] == 2 and s.get("reverify_of")}
    assert two[2]["verifier_own"]["reused"] is True


def test_off_by_default_in_the_library_and_on_in_the_cli(task, envelope, trace, tools):
    llm, by, _ = run(task, envelope, trace, tools, own_script(True), opt=PlanOptions(contract="on"))
    assert llm.calls_of("plan_verify_own") == [] and "verifier_own" not in by[2] and "comparison" not in by[2]
    from scripts.run_task import cli_plan_options, parse_args
    assert cli_plan_options(parse_args(["--toy"])).verify_first == "on"
    assert cli_plan_options(parse_args(["--toy", "--verify-first", "off"])).verify_first == "off"


def test_compare_figures_ignores_labels_and_tags():
    out = compare_figures("Step 1: 1229 [S1] primes, largest 9,973; total $41.60",
                          {1: "Count: 1229\nLargest: 9973", 2: "fuel 41.6 litres"})
    assert set(out["matched"]) == {"41.60", "1229", "9973"}
    assert out["own_only"] == [] and out["agreement"] == 1.0
    assert compare_figures("no figures here", {1: "1"})["agreement"] is None
