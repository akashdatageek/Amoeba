"""D109 (amended) — the disagreement resolver (offline, mock LLM): plain code pairs the verifier's blind figures with
the worker's by label (rubric tolerance); each disagreement goes to one fresh resolver call that settles it against the
source text or a re-run, and plain code checks the evidence (a quote in the source, or the value in the resolver's own
tool output); a settled value that differs replaces the wrong one in the producer's output; an unresolved one makes
the step partial, never PASS, and goes into Limitations; every dispute and resolution is logged. Off, nothing
changes."""
from amoeba.interp.disputes import (disputed_figures, disputes_text, labelled_figures, parse_resolution,
                                     replace_figure, settle)
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


def worker(messages, seed):
    n, user = step_no(messages), messages[-1]["content"]
    if n == "1":
        if "(local:Bash):" not in user:
            return reply("local:Bash", "python3 prime_finder.py")
        return reply("Final Output", f"{MEMO}Count: 1229 [S1]\nLargest: 9973 [S1]")
    if n == "2":
        return reply("Final Output", f"Verdict: PASS\nIssues: none\n{MEMO}Step 1 holds.")
    return reply("Final Output", f"{MEMO}The count and the largest prime (step 2).\n\n## Limitations\n- none")


def own(messages, seed):
    user = messages[-1]["content"]
    if "(local:Bash):" not in user:
        return reply("local:Bash", "python3 prime_finder.py")
    return reply("Final Output", "Step 1 should give: Count: 1500, Largest: 9973.")


def resolver(tool, tool_input, value, evidence):
    """A resolver that runs one tool, then writes its block."""
    def run(messages, seed):
        if "## Figure 1: count" not in messages[-1]["content"]:
            raise AssertionError("the resolver is shown the disputed figure")
        if tool and f"({tool}):" not in messages[-1]["content"]:
            return reply(tool, tool_input)
        return reply("Final Output", f"## Figure 1\nValue: {value}\nEvidence: {evidence}\nVerdict: WORKER")
    return run


def run(task, envelope, trace, tools, resolve=None, opt=ON):
    local_tools(tools, [])
    llm, cfg = team(task, envelope, trace, PRIMES, worker)
    llm._script["plan_verify_own"] = own
    if resolve is not None:
        llm._script["plan_resolve"] = resolve
    next(a for a in cfg.agents.values() if a.name == "Software Engineer").tools.append("local:Bash")
    ep = Interpreter(llm, tools, trace, plan_options=opt).run(cfg, task, seed=0)
    return llm, ep


def two(ep):
    return [s for s in ep.steps if s["step"] == 2][-1]


def test_settle_parse_and_replace():
    disputes = [{"label": "count", "worker": "1229", "verifier": "1500", "step": 1, "worker_line": "Count: 1229 [S1]",
                 "verifier_line": "Count: 1500"}]
    src = {"S1": "Count: 1229\nMax Prime: 9973"}
    reply_text = '## Figure 1\nValue: 1229\nEvidence: "Count: 1229" [S1]\nVerdict: WORKER'
    [r] = settle(reply_text, disputes, src, [])
    assert (r["verdict"], r["evidence_kind"], r["value"]) == ("worker", "source", "1229")
    [r] = settle(reply_text.replace("1229", "1500"), disputes, src, [])
    assert r["verdict"] == "unresolved" and r["value"] is None                   # the quote is not in the source
    [r] = settle("## Figure 1\nValue: 1500\nEvidence: ran the count\nVerdict: CHECK", disputes, src, ["1500"])
    assert (r["verdict"], r["evidence_kind"]) == ("verifier", "command")
    [r] = settle("no blocks at all", disputes, src, ["1500"])
    assert r["verdict"] == "unresolved"
    assert parse_resolution(reply_text) == {1: {"value": "1229", "evidence": '"Count: 1229" [S1]', "verdict": "WORKER"}}
    assert replace_figure("A\nCount: 1229 [S1]\nB", "Count: 1229 [S1]", "1229", "1500") == \
        ("A\nCount: 1500 [S1]\nB", True)
    assert "## Figure 1: count" in disputes_text(disputes, src) and "[S1] Count: 1229" in disputes_text(disputes, src)


def test_a_rerun_that_backs_the_worker_settles_it(task, envelope, trace, tools):
    llm, ep = run(task, envelope, trace, tools, resolver("local:Bash", "python3 prime_finder.py", "1229",
                                                         "python3 prime_finder.py printed Count: 1229"))
    assert len(llm.calls_of("plan_resolve")) == 2                                # one fresh call: a tool turn, then the blocks
    t = two(ep)
    assert t["dispute"]["state"] == "resolved" and t["verdict"] == "PASS" and "disput" not in t["status_reason"]
    [r] = t["dispute"]["resolutions"]
    assert (r["verdict"], r["evidence_kind"], r["replaced"]) == ("worker", "command", False)
    assert "DISPUTED" not in ep.answer
    [ev] = trace.events("dispute_resolution")
    assert ev["amoeba.verdict"] == "worker" and trace.events("disputed")


def test_a_settled_new_value_replaces_the_wrong_one(task, envelope, trace, tools):
    llm, ep = run(task, envelope, trace, tools, resolver("calc", "750 * 2", "1500", "calc 750 * 2 = 1500"))
    [r] = two(ep)["dispute"]["resolutions"]
    assert (r["verdict"], r["replaced"]) == ("verifier", True)
    one = next(s for s in reversed(ep.steps) if s["step"] == 1)
    assert one["resolved_figures"][0]["value"] == "1500"
    writer = [c for c in llm.calls_of("plan_summariser")] or [c for c in llm.calls_of("plan_worker")
                                                                if step_no(c["messages"]) == "3"]
    assert "Count: 1500 [S1]" in writer[-1]["messages"][-1]["content"]            # later steps see the settled value


def test_unresolved_stays_partial_never_pass_and_goes_to_limitations(task, envelope, trace, tools):
    llm, ep = run(task, envelope, trace, tools, resolver(None, "", "1500", '"the count is 1500" [S1]'))
    t = two(ep)
    assert t["status"] == "partial" and t["dispute"]["state"] == "unresolved"
    assert t["verdict"] == "DISPUTED" and t["verdict_model"] == "PASS"            # a PASS cannot override it
    assert "disputed, unresolved: count" in t["status_reason"]
    assert "DISPUTED: count — step 1 gives 1229" in ep.answer and "gives 1500" in ep.answer


def test_off_changes_nothing(task, envelope, trace, tools):
    llm, ep = run(task, envelope, trace, tools, opt=PlanOptions(contract="on", verify_first="on"))
    t = [s for s in ep.steps if s["step"] == 2]
    assert len(t) == 1 and t[0]["status"] == "done" and "dispute" not in t[0]
    assert "disputes" not in t[0]["comparison"] and not trace.events("disputed") and not llm.calls_of("plan_resolve")
