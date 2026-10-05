"""D109 — the verifier's blind result against the worker's figures (offline, mock LLM): plain code pairs the figures
by label and compares them with the rubric's tolerance; a disagreement makes the verify step `disputed` and earns the
producers one rework turn with both values shown; resolved, the step goes on; still there, the step is partial, both
values go into the answer's Limitations, and a PASS verdict never overrides it. Off, nothing changes."""
from amoeba.interp.disputes import disputed_figures, labelled_figures
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from tests.test_plan_runner import step_no
from tests.test_verify_tools import MEMO, PRIMES, local_tools, reply, team

ON = PlanOptions(contract="on", verify_first="on", disputes="on")

H3_OWN = """## Result
- BEV purchase price: $350,000 [S1]
- Electricity rate: $0.12 per kWh [S2]
- Diesel total cost of ownership: $476,000
- 45W credit: $0 (not available after Sep 30 2025)"""
H3_WORK = """| Item | Value |
| BEV truck purchase price | $250,000 [S2] |
| Electricity rate | $0.09/kWh |
| Diesel total cost of ownership | $476,000 |
| BEV total cost of ownership | $608,600 |
In 2026 the fleet has 4 trucks."""


def test_figures_are_paired_by_label_with_the_rubric_tolerance():
    got = disputed_figures(H3_OWN, {3: H3_WORK})
    assert [(x["label"], x["verifier"], x["worker"], x["step"]) for x in got] == [
        ("bev purchase price", "$350,000", "$250,000", 3), ("electricity rate", "$0.12", "$0.09", 3)]
    assert disputed_figures("Electricity rate: $0.091 per kWh", {1: "Electricity rate: $0.09/kWh"}) == []  # ≤ 5%
    assert disputed_figures("Count: 1230", {1: "Count: 1229"}) == []                     # within the tolerance
    assert disputed_figures("Count: 1500", {1: "Count: 1229"})[0]["worker"] == "1229"
    assert disputed_figures("Truck range: 250", {1: "The fleet has 400 parking spaces"}) == []   # other label
    labels = [f["label"] for f in labelled_figures("In 2026 we buy 4 trucks; step 3 gives price $80,000")]
    assert labels == [["price"]]                                                  # no years, no counts


def worker(fixed: bool):
    def run(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1":
            if "(local:Bash):" not in user:
                return reply("local:Bash", "python3 prime_finder.py")
            count = "1500" if fixed and "DISPUTED count" in user else "1229"
            return reply("Final Output", f"{MEMO}Count: {count} [S1]\nLargest: 9973 [S1]")
        if n == "2":
            return reply("Final Output", f"Verdict: PASS\nIssues: none\n{MEMO}Step 1 holds.")
        return reply("Final Output", f"{MEMO}The count and the largest prime (step 2).\n\n## Limitations\n- none")
    return run


def own(messages, seed):
    user = messages[-1]["content"]
    if "(local:Bash):" not in user:
        return reply("local:Bash", "python3 prime_finder.py")
    return reply("Final Output", "Step 1 should give: Count: 1500, Largest: 9973.")


def run(task, envelope, trace, tools, fixed, opt=ON):
    local_tools(tools, [])
    llm, cfg = team(task, envelope, trace, PRIMES, worker(fixed))
    llm._script["plan_verify_own"] = own
    next(a for a in cfg.agents.values() if a.name == "Software Engineer").tools.append("local:Bash")
    ep = Interpreter(llm, tools, trace, plan_options=opt).run(cfg, task, seed=0)
    return llm, ep


def test_a_disagreement_earns_one_rework_with_both_values_then_stays_partial(task, envelope, trace, tools):
    llm, ep = run(task, envelope, trace, tools, fixed=False)
    rework = [c for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "1"
              and "DISPUTED count" in c["messages"][-1]["content"]]
    assert rework and "says 1229" in rework[0]["messages"][-1]["content"] \
        and "says 1500" in rework[0]["messages"][-1]["content"]                            # both values shown
    two = [s for s in ep.steps if s["step"] == 2]
    assert two[0]["status"] == "disputed" and two[0]["dispute"]["state"] == "disputed"
    last = two[-1]
    assert last["status"] == "partial" and last["dispute"]["state"] == "unresolved"
    assert last["verdict"] == "DISPUTED" and last["verdict_model"] == "PASS"            # a PASS cannot override it
    assert "disputed after rework" in last["status_reason"]
    assert "DISPUTED: count — step 1 gives 1229" in ep.answer and "gives 1500" in ep.answer
    assert len(llm.calls_of("plan_verify_own")) == 2                                     # made once (2 turns), reused
    assert [e["amoeba.round"] for e in trace.events("disputed")] == [1, 2]


def test_a_rework_that_settles_it_clears_the_dispute(task, envelope, trace, tools):
    llm, ep = run(task, envelope, trace, tools, fixed=True)
    last = [s for s in ep.steps if s["step"] == 2][-1]
    assert last["dispute"]["state"] == "resolved" and last["verdict"] == "PASS"
    assert "disput" not in last["status_reason"]           # (the D65 rule may still flag the reused re-check)
    assert "DISPUTED" not in ep.answer


def test_off_changes_nothing(task, envelope, trace, tools):
    llm, ep = run(task, envelope, trace, tools, fixed=False, opt=PlanOptions(contract="on", verify_first="on"))
    two = [s for s in ep.steps if s["step"] == 2]
    assert len(two) == 1 and two[0]["status"] == "done" and "dispute" not in two[0]
    assert "disputes" not in two[0]["comparison"] and not trace.events("disputed")
