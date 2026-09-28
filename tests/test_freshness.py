"""D67 — freshness. For a task that asks for today's, the current or the latest value, a step with web tools is asked
for the most recent official figure, its date and one more search when it is dated; plain code adds "possibly not
the latest" to Limitations when the newest as-of date is more than 3 days old. Case: bench5 diesel ($6.29 as of
Sep 14, 2026, used on Sep 28)."""
from datetime import date

from amoeba.interp.freshness import dates_in, stale_figure, time_sensitive
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from amoeba.task.models import Task
from tests.test_plan_runner import BODY, plan_team, step_no

DIESEL = Task(id="bench5-diesel", prompt="Find today's average US diesel price from a cited source. Then compute fuel "
              "cost at 6.5 mpg for Chicago–Indianapolis 185 miles.")
RUN_DAY = date(2026, 9, 28)


def test_which_tasks_and_which_dates():
    assert time_sensitive(DIESEL.prompt) and time_sensitive("Who is the current CEO of Maersk?")
    assert not time_sensitive("What is the monthly payment on a $250,000 loan?")
    assert [d.isoformat() for d, _ in dates_in("as of Sep 14, 2026; 2026-09-21; 9/7/26")] == \
        ["2026-09-14", "2026-09-21", "2026-09-07"]
    assert stale_figure(["CEO since January 1, 2023"], RUN_DAY) is None           # a start date is the fact itself
    assert stale_figure(["Price $6.53 as of 2026-09-26"], RUN_DAY) is None           # 2 days old: fine


def run(envelope, trace, tools, dated):
    def script(messages, seed):
        n = step_no(messages)
        extra = f"\nPrice: $6.29/gal\nDate: {dated}" if n == "1" else ""
        return f"## Thought\nok\n\n## CurrentStep\nc\n\n## Action\nFinal Output\n\n## ActionInput\nOUT-{n}\n{BODY}{extra}"
    llm, cfg = plan_team(DIESEL, envelope, trace, plan_worker=script)
    next(a for a in cfg.agents.values() if a.name == "Cost Analyst").tools.append("web_search")
    interp = Interpreter(llm, tools, trace, plan_options=PlanOptions())
    interp.today = RUN_DAY
    return llm, interp.run(cfg, DIESEL, seed=0)


def test_a_figure_dated_two_weeks_back_is_named_in_limitations(envelope, trace, tools):
    llm, ep = run(envelope, trace, tools, "September 14, 2026")
    assert "- Possibly not the latest (dated September 14, 2026, 14 days before this run)" in ep.answer
    one = [c for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "1"][0]["messages"][-1]["content"]
    assert "Find the most recent official figure and write its date" in one        # the researcher is asked
    two = [c for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "2"][0]["messages"][-1]["content"]
    assert "most recent official figure" not in two                                 # a step with no web tools is not
    [ev] = trace.events("freshness")
    assert ev["amoeba.days"] == 14


def test_a_recent_figure_adds_nothing(envelope, trace, tools):
    llm, ep = run(envelope, trace, tools, "September 27, 2026")
    assert "Possibly not the latest" not in ep.answer and trace.events("freshness") == []
