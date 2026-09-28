"""D65 — check steps can really check: a verify step gets the tools to re-check (calc, web, local run/read), the raw
tool results of every step it builds on, and a PASS with no re-checking tool call on code, files or cited figures
is an unverified check (partial). Cases: bench5 primes (a checker that passed on reading the code) and round-1
weather (a checker that depended on step 2 and never saw step 1's forecast)."""
import json

from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from tests.test_plan_runner import APPROVE, step_no
from tests.conftest import mock
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate

ON = PlanOptions(contract="on")


def role(name, summ=False):
    return json.dumps({"name": name, "description": name, "goal": f"{name} work", "tools": [],
                       "outputs": ["memo"], "success_criteria": ["correct"], "is_summariser": summ,
                       "prompt": f"You are the {name}."})


def draft(roles, steps):
    return (f"## Thought\nok\n\n## Requirements:\nR1: do the task\n\n## Givens and Assumptions:\n- given: the task\n\n"
            f"## Selected Roles List:\n```\nNone\n```\n\n## Created Roles List:\n```\n{','.join(roles)}\n```\n\n"
            f"## Execution Plan:\n{steps}\n\n## Capability Requests:\n```\nNone\n```\n\n## Risks and Decisions:\n- none\n\n"
            "## RoleFeedback\nNone.\n\n## PlanFeedback\nNone.\n")


def step(n, who, title, kind, deps):
    return (f"{n}. [{who}]: {title}\n   kind: {kind}\n   covers: R1\n   depends_on: {deps}\n   do: {title}\n"
            f"   output: memo: result\n   done_when: done")


PRIMES = draft([role("Software Engineer"), role("QA Engineer"), role("Technical Writer", True)],
               "\n".join([step(1, "Software Engineer", "Write and run the prime finder", "work", "none"),
                          step(2, "QA Engineer", "Verify the count and the largest prime", "verify", "1"),
                          step(3, "Technical Writer", "Assemble the report", "work", "2")]))
WEATHER = draft([role("Forecaster"), role("Event Planner"), role("Checker"), role("Writer", True)],
                "\n".join([step(1, "Forecaster", "Fetch the Saturday forecast", "work", "none"),
                           step(2, "Event Planner", "Plan the event around the forecast", "work", "1"),
                           step(3, "Checker", "Verify the plan against the forecast", "verify", "2"),
                           step(4, "Writer", "Write the answer", "work", "3")]))
MEMO = "# Result\n## Details\n"


def reply(action, text):
    return f"## Thought\nok\n\n## CurrentStep\nnow\n\n## Action\n{action}\n\n## ActionInput\n{text}"


def team(task, envelope, trace, text, script):
    llm = mock(planner=[text], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=script)
    return llm, instantiate(draft_team(task, llm, envelope, trace, prompts="d24"), "plan", task, envelope)


def local_tools(tools, calls):
    def bash(text):
        calls.append(text)
        return "[local:Bash] [S1] (cite a fact from this result by its [S1])\nCount: 1229\nMax Prime: 9973"
    tools.register("local:Bash", "local tool Bash", bash)
    tools.register("local:Read", "local tool Read", lambda text: "[local:Read]\nprint(len(primes))")


def primes_script(checker_runs: bool):
    def run(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1":
            if "(local:Bash):" not in user:
                return reply("local:Bash", "python3 prime_finder.py")
            return reply("Final Output", f"{MEMO}```python\nprint(len(primes))\n```\nCount: 1229 [S1]\nLargest: 9973 [S1]")
        if n == "2":
            if checker_runs and "(local:Bash):" not in user:
                return reply("local:Bash", "python3 prime_finder.py")
            return reply("Final Output", f"Verdict: PASS\nIssues: none\n{MEMO}Step 1: 1229 and 9973 hold.")
        return reply("Final Output", f"{MEMO}1229 primes; the largest is 9973 (step 2).")
    return run


def run_primes(task, envelope, trace, tools, checker_runs):
    calls = []
    local_tools(tools, calls)
    llm, cfg = team(task, envelope, trace, PRIMES, primes_script(checker_runs))
    engineer = next(a for a in cfg.agents.values() if a.name == "Software Engineer")
    engineer.tools.append("local:Bash")
    ep = Interpreter(llm, tools, trace, plan_options=ON).run(cfg, task, seed=0)
    return llm, {s["step"]: s for s in ep.steps}, calls


def test_the_checker_gets_tools_and_the_raw_results_it_checks(task, envelope, trace, tools):
    llm, by, calls = run_primes(task, envelope, trace, tools, checker_runs=False)
    prompt = [c for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "2"][0]["messages"][-1]["content"]
    assert "'calc'" in prompt and "'local:Bash'" in prompt and "'local:Read'" in prompt
    assert "## Raw tool results of the steps you check" in prompt and "Count: 1229\nMax Prime: 9973" in prompt
    assert "re-run the code a step wrote or open the file it made" in prompt
    [ev] = trace.events("verifier_tools")
    assert ev["amoeba.upstream"] == [1] and ev["amoeba.granted"][0]["agent"] == "QA Engineer"


def test_a_pass_without_re_checking_is_an_unverified_check(task, envelope, trace, tools):
    llm, by, calls = run_primes(task, envelope, trace, tools, checker_runs=False)
    two = by[2]
    assert (two["verdict"], two["status"], two["unverified_check"]) == ("PASS", "partial", True)
    assert "unverified check: PASS with no re-checking tool call on code of step 1" in \
        two["status_reason"]


def test_a_pass_after_re_running_the_code_is_done(task, envelope, trace, tools):
    llm, by, calls = run_primes(task, envelope, trace, tools, checker_runs=True)
    assert (by[2]["verdict"], by[2]["status"], by[2]["unverified_check"]) == ("PASS", "done", False)
    assert len(calls) == 2 and by[2]["tool_calls"][0]["tool"] == "local:Bash"


def test_the_weather_checker_sees_step_1_forecast_through_step_2(task, envelope, trace, tools):
    forecast = "[S1] National Weather Service, Saturday: high 72°F, low 55°F, rain 10%"
    tools.register("web_search", "search the web", lambda text: forecast)

    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1":
            if "(web_search):" not in user:
                return reply("web_search", "Saturday forecast")
            return reply("Final Output", f"{MEMO}Saturday: high 72°F [S1], rain 10% [S1]")
        if n == "3":
            return reply("Final Output", f"Verdict: PASS\nIssues: none\n{MEMO}Step 2 fits the forecast.")
        return reply("Final Output", f"{MEMO}An outdoor event at 72°F (step {int(n) - 1}).")
    llm, cfg = team(task, envelope, trace, WEATHER, script)
    next(a for a in cfg.agents.values() if a.name == "Forecaster").tools.append("web_search")
    ep = Interpreter(llm, tools, trace, plan_options=ON).run(cfg, task, seed=0)
    prompt = [c for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "3"][0]["messages"][-1]["content"]
    assert "### Step 1 · Forecaster → web_search" in prompt and "high 72°F, low 55°F, rain 10%" in prompt
    assert "'web_search'" in prompt                                   # it may re-check the cited figure


def test_with_the_contract_off_the_checker_is_unchanged(task, envelope, trace, tools):
    local_tools(tools, [])
    llm, cfg = team(task, envelope, trace, PRIMES, primes_script(False))
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions()).run(cfg, task, seed=0)
    prompt = [c for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "2"][0]["messages"][-1]["content"]
    assert "Raw tool results" not in prompt and trace.events("verifier_tools") == []
