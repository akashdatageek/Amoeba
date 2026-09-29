"""D76 — step endings and evidence size: a helper's last turn must end with a written conclusion (only Final Output
offered, asked once more if it still requests a tool, which is never run); an output that is only a search query or
a tool request fails a `conclusion` check by code; a verify step gets its producers' raw results as the excerpts
that bear on their claims, capped at 20,000 characters with a marker. Offline, with the mock LLM."""
import json
import re

from amoeba.interp.plan_runner import EVIDENCE_CAP, LAST_TURN_AGAIN, LAST_TURN_NOTE, claim_terms, excerpt, no_conclusion
from amoeba.interp.runtime import Interpreter
from amoeba.task.models import Task
from amoeba.tools.web import web_registry
from scripts.run_task import run_one
from tests.conftest import fx, mock
from tests.test_plan_runner import BODY, plan_team, step_no

APPROVE = fx("observer_d24_approve")


def reply(action, text):
    return f"## Thought\nt\n\n## CurrentStep\nt\n\n## Action\n{action}\n\n## ActionInput\n{text}\n"


def test_the_bmv_step_that_ended_on_a_search_query_has_no_conclusion():
    assert no_conclusion('"Hammond" BMV hours "Monday" site:in.gov', [])
    assert no_conclusion("Indiana BMV Hammond hours", ["Indiana BMV Hammond hours"])        # its own last request
    assert no_conclusion("", []) and no_conclusion("## Action\nweb_search", [])
    assert not no_conclusion("The Hammond branch is closed on Mondays [S1]; it opens Tuesday at 8:30 AM.", [])
    assert not no_conclusion(BODY, ["RDS price"])


def test_the_last_turn_offers_only_final_output_and_never_runs_a_tool(task, envelope, trace, tools):
    seen = []

    def searcher(messages, seed):
        user = messages[-1]["content"]
        seen.append(user)
        if LAST_TURN_AGAIN in user:                     # asked once more: it concludes from what it has
            return reply("Final Output", f"OUT-{step_no(messages)}\n{BODY}")
        return reply("calc", "2 + 2")                   # otherwise it keeps asking for a tool
    llm, cfg = plan_team(task, envelope, trace, plan_worker=searcher)
    ep = Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    last = [u for u in seen if "THIS IS YOUR LAST TURN" in u]
    listed = [u for u in last if "You can use:" in u]                       # the summariser's prompt lists no tools
    assert listed and all("You can use: ['Final Output']" in u for u in listed) and LAST_TURN_NOTE in last[0]
    one = [e for e in trace.spans("execute_tool")]
    turns = cfg.agents[cfg.plan[0].agent_ids[0]].limits.max_turns
    assert len([s for s in ep.steps if s["step"] == 1]) >= 1
    assert trace.events("last_turn_forced")[0]["amoeba.asked_for"] == "calc"
    assert len(one) <= 4 * (turns - 1)                  # no tool call on any last turn
    step1 = json.loads(json.dumps(ep.steps[0]))
    assert "conclusion" not in [c["name"] for c in step1["checks"] if not c["pass"]]


def test_a_step_that_ends_on_a_query_fails_its_conclusion_check(tmp_path, envelope):
    def asker(messages, seed):
        return reply("web_search", '"Hammond" BMV hours "Monday" site:in.gov')
    llm = mock(planner=[fx("draft_d24_full")], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=asker)
    from tests.test_web_tools import FakeProvider
    r = run_one(Task(prompt="Is the branch open today?"), "plan", llm, envelope, web_registry(FakeProvider()), tmp_path,
                draft_prompts="d24")
    meta = json.loads((tmp_path / r.run_id / "artifacts" / "step_1.json").read_text())
    assert meta["status"] == "incomplete"
    assert any(c["name"] == "conclusion" and not c["pass"] and c["source"] == "code" for c in meta["checks"])


def test_verify_evidence_is_the_relevant_excerpts_capped_at_20000_characters():
    claims = "- Hours from [S13]: Mon Closed, Tue 8:30 am - 6:30 pm [S13]\n- Holiday: none on 28 September [S6]"
    wanted = claim_terms(claims)
    page = "\n".join(["Highland BMV Office @ 7931 Indianapolis Boulevard"] + [f"Unrelated line {i} about parking"
                                                                               for i in range(40)]
                     + ["Sun Closed Mon Closed Tue 8:30 am - 6:30 pm Wed 8:30 am - 5:00 pm"])
    cut = excerpt(page, wanted)
    assert cut.startswith("Highland BMV Office") and "Tue 8:30 am - 6:30 pm" in cut and "Unrelated line 7" not in cut
    assert "[…]" in cut
    nothing = excerpt("x " * 500, wanted)
    assert nothing.endswith("nothing in it matches the claims checked …]") and len(nothing) < 400


def test_the_raw_evidence_given_to_a_verify_step_is_capped(tmp_path, envelope, trace, tools, task):
    from amoeba.interp.plan_runner import PlanRunner
    llm, cfg = plan_team(task, envelope, trace, plan_worker=lambda m, s: reply("Final Output", BODY))
    runner = PlanRunner(Interpreter(llm, tools, trace), cfg, task, None, None, None)
    big = "Tue 8:30 am - 6:30 pm Mon Closed " * 400                        # every piece matches the claims
    runner.artifacts = {1: {"text": "Mon Closed; Tue 8:30 am - 6:30 pm [S1]",
                            "meta": {"tool_results": [{"agent": "A", "tool": "fetch_url", "input": f"u{i}",
                                                       "result": big} for i in range(4)]}}}
    runner.upstream = lambda n: [1]
    text = runner.raw_results_text(2)
    assert len(text) < EVIDENCE_CAP + 300 and re.search(r"characters of raw evidence left out: cap 20,000", text)
