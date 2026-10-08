"""D110 — every web-sourced figure in the final answer carries its source's date (offline, mock LLM): a figure whose
line cites a web source and states no date (and whose source entry has none) is undated; undated figures earn the
answer step a refine turn; those still undated after it are listed in Limitations by plain code; off, nothing
changes."""
from amoeba.interp.dates import undated_figures
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from amoeba.tools.web import WebTools, register_web_tools
from tests.test_plan_runner import BODY, plan_team, step_no
from tests.test_web_tools import FakeProvider

ON = PlanOptions(dated="on")


def test_what_counts_as_dated():
    t = """# Memo
- BEV purchase price: $250,000 [S2]
- Diesel price $4.10/gal as of Sep 2026 [S3]
- 2023 median income $80,610 [S1]
- Electricity rate $0.09/kWh [S4]
- Total cost $608,600 (calculated)
- Local tool result 42 [S9]

## Sources
- [S4] EIA Electric Power Monthly (published Aug 2026)
- [S2] Fleet news article

## Limitations
- prices change 5% [S2]
"""
    got = undated_figures(t, {"S1", "S2", "S3", "S4"})
    assert [(u["figure"], u["sources"]) for u in got] == [("$250,000", ["S2"])]


def worker(fixes: bool):
    def run(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n != "4":
            return f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\nOUT-{n}\n{BODY}"
        dated = fixes and "carry no date" in user
        line = "The BEV price is $250,000 [S1]" + (" (published March 2026)" if dated else "")
        return (f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\nOUT-{n}\n{BODY}"
                f"\n{line}\n")
    return run


def run(task, envelope, trace, tools, fixes, opt=ON):
    web = WebTools(FakeProvider())
    register_web_tools(tools, web)
    web.begin_step(0, trace)
    web.web_search("BEV truck price")                      # S1..S3 exist as web sources of the run
    llm, cfg = plan_team(task, envelope, trace, plan_worker=worker(fixes))
    ep = Interpreter(llm, tools, trace, plan_options=opt).run(cfg, task, seed=0)
    return llm, ep


def test_an_undated_figure_earns_the_refine_turn_and_a_fixed_one_passes(task, envelope, trace, tools):
    llm, ep = run(task, envelope, trace, tools, fixes=True)
    asks = [c for c in llm.calls_of("plan_summariser") if step_no(c["messages"]) == "4"
            and "carry no date" in c["messages"][-1]["content"]]
    assert asks and "$250,000 [S1]" in asks[0]["messages"][-1]["content"]
    assert "(published March 2026)" in ep.answer and "UNDATED" not in ep.answer
    assert not trace.events("undated_figures")


def test_still_undated_after_the_turn_goes_into_limitations(task, envelope, trace, tools):
    llm, ep = run(task, envelope, trace, tools, fixes=False)
    assert "- UNDATED: $250,000 [S1] — the source's date (publication or data period) is not stated" in ep.answer
    [ev] = trace.events("undated_figures")
    assert ev["amoeba.count"] == 1


def test_off_changes_nothing(task, envelope, trace, tools):
    llm, ep = run(task, envelope, trace, tools, fixes=False, opt=PlanOptions())
    assert "UNDATED" not in ep.answer and not any("carry no date" in c["messages"][-1]["content"]
                                                   for c in llm.calls_of("plan_worker"))
