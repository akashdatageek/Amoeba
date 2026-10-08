"""D108 — a re-plan must change the method that failed (offline, mock LLM): a step a re-plan adds or rewrites for a
failed step (same requirements, or the same role doing nearly the same thing) must state a different tool, source
type or a decomposed query; one that repeats the method makes the decision rejected and logged; the observer is
shown how each failed step worked; off, nothing changes."""
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.replan_method import method_change, replaces
from tests.test_replan import BLOCKED_1, decision, run, worker

ON = PlanOptions(replan="on", replan_method="on")
STEP = ("5. [Cost Analyst]: Price both databases\n   kind: work\n   covers: R1\n   depends_on: none\n"
        "   do: {do}\n   output: price table\n   done_when: both priced\n   feeds: 3")
REPEAT = STEP.format(do="price both databases")
CHANGED = STEP.format(do="read the official price list data file (csv) of each database separately")


def blocked(n):
    return BLOCKED_1 if n == "1" else ""


def test_a_repeated_method_is_rejected_and_logged(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(blocked), [decision("ADD_STEP", REPEAT)],
                       options=ON)
    prompt = llm.calls_of("replanner")[0]["messages"][-1]["content"]
    assert "# How the failed steps worked (plain code)" in prompt and "- step 1 (Cost Analyst): tools" in prompt
    [val] = trace.events("replan_validated")
    assert not val["amoeba.accepted"] and "step 5 repeats the method of failed step 1" in val["amoeba.errors"][0]
    [m] = trace.events("replan_method")
    assert m["amoeba.replaces"] == 1 and m["amoeba.changes"] == []
    assert 5 not in [s["step"] for s in ep.steps] and ep.replan["rejected"] == 1


def test_a_changed_method_is_accepted(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(blocked), [decision("ADD_STEP", CHANGED)],
                       options=ON)
    [val] = trace.events("replan_validated")
    assert val["amoeba.accepted"], val["amoeba.errors"]
    [m] = trace.events("replan_method")
    assert {"source type data", "source type official", "decomposed query"} <= set(m["amoeba.changes"])
    assert 5 in [s["step"] for s in ep.steps]


def test_off_changes_nothing(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(blocked), [decision("ADD_STEP", REPEAT)],
                       options=PlanOptions(replan="on"))
    [val] = trace.events("replan_validated")
    assert val["amoeba.accepted"] and not trace.events("replan_method")
    assert "How the failed steps worked" not in llm.calls_of("replanner")[0]["messages"][-1]["content"]


def test_the_rules():
    failed = {2: {"step": 2, "roles": ["Researcher"], "tools": ["web_search"], "source_types": [],
                  "sites": ["news.example.com"], "queries": ["US Indiana median household income 2015 2023"],
                  "covers": ["R1"], "text": "nominal income table"}}
    same = {"number": 7, "roles": ["Researcher"], "text": "7. [Researcher]: Search again for the income figures",
            "fields": {"covers": ["R1"], "do": "search for US and Indiana median household income 2015-2023"}}
    assert replaces(same, failed) == 2 and method_change(same, failed[2], {"web_search", "fetch_url"}) == []
    fetch = {**same, "fields": {"covers": ["R1"], "do": "fetch_url the census.gov historical income table"}}
    assert method_change(fetch, failed[2], {"web_search", "fetch_url"}) == [
        "tool fetch_url", "source type official", "site census.gov"]
    other = {**same, "fields": {"covers": ["R4"], "do": "write the memo"}, "text": "7. [Writer]: Write the memo",
             "roles": ["Writer"]}
    assert replaces(other, failed) is None                                   # not a replacement: no check
