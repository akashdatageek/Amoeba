"""D74 — citation check by code: a quoted phrase or specific fact tagged [S#] must be in the text the team was shown
for S#; otherwise it is a mislabelled citation (step partial, named in Limitations). Offline."""
import json
import re

from amoeba.interp.citecheck import mislabelled_citations, times_in
from amoeba.task.models import Task
from amoeba.tools.web import web_registry
from scripts.run_task import run_one
from tests.conftest import fx, mock
from tests.test_plan_runner import BODY

# The BMV run (bench5b follow-up): what the checker was shown for S6 and S7, shortened
S6 = ("Bureau of Motor Vehicles: BMV Holiday Schedule\n| Veterans Day | Wednesday | November 11, 2026 | "
      "| Thanksgiving Day | Thursday | November 26, 2026 | | Christmas Day | Friday | December 25, 2026 |")
S7 = ("IN.gov | Business Owner's Guide\nOffice Hours are 8:00 a.m. - 4:30 p.m. M-F ###### Anderson ###### Auburn "
      "###### Gary ###### Hammond ###### Indianapolis East")
S13 = "Highland BMV Office @ 7931 Indianapolis Boulevard. Sun Closed Mon Closed Tue 8:30 am - 6:30 pm Wed 8:30 am - 5:00 pm"


def test_the_bmv_checker_hours_tagged_with_the_holiday_page_are_flagged():
    for line in ("Confirmed Hours: 8:00 a.m. - 4:30 p.m. [S6]", "Confirmed Hours: 8:00 AM – 4:30 PM [S6]"):
        [x] = [m for m in mislabelled_citations(line, {"S6": S6, "S7": S7, "S13": S13}) if m["kind"] == "time"][:1]
        assert x["source"] == "S6" and x["claim"] in ("4:30pm", "8:00am") and x["found_in"] == ["S7"]
        assert {m["claim"] for m in mislabelled_citations(line, {"S6": S6, "S7": S7}) if m["kind"] == "time"} == \
            {"8:00am", "4:30pm"}


def test_claims_that_are_in_their_source_pass():
    text = "\n".join([
        "- Hours from [S13]: Tue 8:30 am - 6:30 pm, Mon Closed [S13]",       # the times are in S13
        "- Hammond branch office hours listed as 8:00 a.m. - 4:30 p.m. M-F [S7]",
        "- Christmas Day is Friday, December 25, 2026 [S6]",
        "Diesel is $6.47 per gallon [S1]",                                   # rounded from 6.4709
        "The page says \"Office Hours are 8:00 a.m. - 4:30 p.m.\" [S7]",     # a quote that is there
    ])
    assert mislabelled_citations(text, {"S1": "Diesel | Current Avg. | $6.4709", "S6": S6, "S7": S7, "S13": S13}) == []


def test_quotes_numbers_and_what_is_left_out():
    contents = {"S1": "The fee is $25 per violation. Appeals within 10 calendar days."}
    bad = mislabelled_citations('The page says "appeals within 14 days" and the fee is $35 [S1]', contents)
    assert [(x["kind"], x["claim"]) for x in bad] == [("quote", "appeals within 14 days"), ("number", "$35")]
    # a number given in the task, a computed value, today's date parts, labels and unknown sources are not checked
    ok = "Step 2 found 50 tenants x $25 = $1,250 on 28 September 2026 [S1]; uptime 99.99% [S9]"
    assert mislabelled_citations(ok, contents, exempt={"50", "28", "2026"}, exact=[1250.0]) == []
    assert times_in("open 08:30 to 17:00, or 9 AM") == {"8:30", "5:00pm", "9:00am"}


def worker(messages, seed):
    user = messages[-1]["content"]
    n = re.search(r"# Your step \(step (\d+)\)", user).group(1)
    if n == "1" and "[S1]" not in user:
        return "## Thought\ns\n\n## CurrentStep\ns\n\n## Action\nweb_search\n\n## ActionInput\nbranch hours\n"
    body = BODY + ("\nThe branch opens at 8:00 AM and closes at 4:30 PM [S1].\n" if n == "1" else "")
    return f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\n{body}\n"


class HoursProvider:
    name = "fake"

    def search(self, query, max_results):
        return [{"title": "Holiday schedule", "url": "https://ex.com/holidays", "snippet": "Christmas Day, Dec 25"},
                {"title": "State offices", "url": "https://ex.com/offices", "snippet": "Office Hours are 8:00 a.m. - 4:30 p.m. M-F"}]

    def fetch(self, url):
        return {"url": url, "title": "Page", "text": "nothing"}


def test_a_plan_step_with_a_mislabelled_citation_is_partial_and_named_in_limitations(tmp_path, envelope):
    approve = fx("observer_d24_approve")
    llm = mock(planner=[fx("draft_d24_full")], agent_observer=[approve], plan_observer=[approve], plan_worker=worker)
    r = run_one(Task(prompt="When is the branch open?"), "plan", llm, envelope, web_registry(HoursProvider()), tmp_path,
                draft_prompts="d24")
    meta = json.loads((tmp_path / r.run_id / "artifacts" / "step_1.json").read_text())
    assert meta["status"] == "partial" and "mislabelled citation" in meta["status_reason"]
    assert {x["claim"] for x in meta["mislabelled_citations"]} == {"8:00am", "4:30pm"}
    assert all(x["found_in"] == ["S2"] for x in meta["mislabelled_citations"])
    assert "Mislabelled citation: step 1 cites S1 for '8:00am', which S1 does not contain; it is in S2" in r.answer
