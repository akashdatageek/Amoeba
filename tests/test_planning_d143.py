"""D143 — planning v2 under code control: the planning tier, the best draft published (not the last), only blocking
issues sent back, the plan diff between rounds, and the planner's reading revision accepted only by code's rules.
Offline (MockLLMClient)."""
import json

import pytest

from amoeba.interp.trace import TraceWriter
from amoeba.llm.client import MockLLMClient
from amoeba.task.draft import draft_team
from amoeba.task.interpret import enforce_opening, opening_line, task_note
from amoeba.task.models import Task
from amoeba.task.planning import check_revision, draft_score, plan_diff, resolve_tier
from amoeba.task.schemas import PlanOut
from tests.test_protocol_v2_all_d141 import _plan

SIMPLE = "Compute 17 * 23 + 5."
RESEARCH = ("Find the current diesel prices in five EU countries, cite sources, and deliver an xlsx table and a docx "
            "memo.")


def v2_trace():
    t = TraceWriter(None, episode_id="ep-d143")
    t.protocol = "v2"
    return t


def task(prompt=SIMPLE):
    return Task(id="t", prompt=prompt, family="x")


def review(verdict="REVISE", blocking=(), minor=()):
    return {"verdict": verdict, "issues": [{"severity": "blocking", "problem": p, "fix": "fix it"} for p in blocking]
            + [{"severity": "minor", "problem": p, "fix": "maybe"} for p in minor]}


# ---- the tier ----------------------------------------------------------------------------------------------------
def test_tiers_by_code():
    assert resolve_tier("auto", "v2", SIMPLE)[0] == "light"
    assert resolve_tier("auto", "v2", "Estimate the monthly cost, compare the two vans, list the main risks, recommend one, and deliver a short memo.")[0] == "standard"
    assert resolve_tier("auto", "v2", RESEARCH)[0] == "full"                 # web research and two files
    assert resolve_tier("auto", "v2", "Draft the reply and email it to the client.")[0] == "full"   # outside action
    assert resolve_tier("auto", "legacy", SIMPLE) == ("full", resolve_tier("auto", "legacy", SIMPLE)[1])
    assert resolve_tier("auto", "legacy", SIMPLE)[1]["how"] == "legacy auto"
    assert resolve_tier("light", "legacy", RESEARCH)[0] == "light"           # an explicit tier wins


def test_light_runs_the_planner_only(envelope):
    llm = MockLLMClient(script={"planner": [_plan()]})
    d = draft_team(task(), llm, envelope, v2_trace())
    assert [c["kind"] for c in llm.calls] == ["planner"] and d.planning_tier == "light" and d.consensus


def test_standard_runs_the_plan_observer_only(envelope):
    llm = MockLLMClient(script={"planner": [_plan()], "plan_observer": [review("APPROVE")]})
    d = draft_team(task(), llm, envelope, v2_trace(), planning_tier="standard")
    assert [c["kind"] for c in llm.calls] == ["planner", "plan_observer"] and d.planning_tier == "standard"


def test_legacy_auto_is_full_and_unchanged(task, envelope, trace):
    from tests.conftest import fx, mock
    d = draft_team(task, mock(planner=[fx("draft_round_ok")]), envelope, trace)
    assert d.planning_tier == "full" and d.published_round is None


def test_the_cli_flag():
    from scripts.run_task import parse_args
    a = parse_args(["--planning-tier", "light", "--topology", "plan", "--toy"])
    assert a.planning_tier == "light"


# ---- the best draft ------------------------------------------------------------------------------------------------
def test_score_order():
    assert draft_score(0, 3, 1) < draft_score(1, 0, 3)          # HARD checks first
    assert draft_score(0, 1, 1) < draft_score(0, 2, 3)          # then blocking issues
    assert draft_score(0, 1, 3) < draft_score(0, 1, 1)          # then the later round


def test_the_best_round_is_published_and_only_blocking_issues_go_back(envelope):
    p1, p2, p3 = _plan(), _plan(), _plan()
    p2["plan"] = p2["plan"] + [dict(p2["plan"][0], number=3, title="Extra", depends_on=[1])]
    p3["givens"] = ["changed"]
    llm = MockLLMClient(script={
        "planner": [p1, p2, p3],
        "agent_observer": [review(blocking=["role A lacks a goal"], minor=["MINOR-WORDING"]),
                           review(blocking=["x", "y", "z"]), review(blocking=["x", "y"])],
        "plan_observer": [review(minor=["MINOR-STYLE"]), review(), review()]})
    tr = v2_trace()
    d = draft_team(task(RESEARCH), llm, envelope, tr)
    assert d.planning_tier == "full" and d.rounds_used == 3 and not d.consensus
    assert d.published_round == 1 and d.published_score == {"hard_failed": d.rounds[0].score["hard_failed"],
                                                            "blocking": 1}
    assert [r.score["blocking"] for r in d.rounds] == [1, 3, 2]
    assert len(d.plan) == 2                                    # round 1's plan, not round 3's
    second = llm.calls_of("planner")[1]["messages"][-1]["content"]
    assert "role A lacks a goal" in second and "MINOR-WORDING" not in second and "MINOR-STYLE" not in second
    assert "MINOR-WORDING" in d.rounds[0].agent_observer_raw  # minor issues are recorded
    assert '"requirements"' in second                          # the previous PlanOut, as JSON
    assert d.rounds[1].plan_diff["steps_added"] == [3] and d.rounds[0].plan_diff is None
    assert tr.events("draft_published")[0]["amoeba.round"] == 1


def test_plan_diff():
    a, b = PlanOut.model_validate(_plan()), _plan()
    b["requirements"].append({"id": "R2", "text": "a chart"})
    b["plan"][0]["do"] = "use calc twice"
    diff = plan_diff(a, PlanOut.model_validate(b))
    assert diff["requirements_added"] == ["R2"] and diff["steps_changed"] == [1] and not diff["steps_removed"]


# ---- the reading revision -------------------------------------------------------------------------------------------
INTERP = {"entities": [], "ambiguous": [], "gap": 0.3, "question": None,
          "working": [{"entity": "Springfield", "reading": "Springfield, Illinois", "why": "capital", "confidence": 0.5,
                       "lead": 0.1, "settled": "assumed", "alternatives": ["Springfield, Missouri"]}]}
REV = {"entity": "Springfield", "from_reading": "Springfield, Illinois", "to_reading": "Springfield, Missouri",
       "reason": "the task names the Missouri zoo", "evidence": ["task text"]}


@pytest.mark.parametrize("rev,search,approved,ok,why", [
    (REV, "", True, True, "alternatives"),
    (REV, "", None, True, "alternatives"),                                      # no observer ran (light tier)
    (REV, "", False, False, "did not approve"),
    (dict(REV, to_reading="Springfield, Oregon"), "", True, False, "no fetched"),
    (dict(REV, to_reading="Springfield, Oregon", evidence=["P2"]), "[P2] Oregon zoo page", True, True, "P2"),
    (dict(REV, to_reading="Springfield, Oregon", evidence=["P9"]), "[P2] Oregon zoo page", True, False, "no fetched"),
    (dict(REV, from_reading="Springfield, Ohio"), "", True, False, "not the working reading"),
    (dict(REV, entity="Shelbyville"), "", True, False, "not in Box 1"),
])
def test_revision_rules(rev, search, approved, ok, why):
    r = check_revision(rev, INTERP, search, approved)
    assert r["accepted"] is ok and why in r["why"]


def run_revision(envelope, approve: bool, lessons=None):
    p = _plan()
    p["reading_revision"] = REV
    llm = MockLLMClient(script={"planner": [p], "agent_observer": [review("APPROVE")],
                                "plan_observer": [review("APPROVE" if approve else "REVISE", blocking=[] if approve
                                                         else ["reading not supported"])]})
    tr = v2_trace()
    d = draft_team(task("Plan a visit to Springfield's zoo with sources and a docx and an xlsx."), llm, envelope, tr,
                   interpretation=json.loads(json.dumps(INTERP)), max_rounds=1, planning_tier="full",
                   lessons=lessons)
    return d, tr, llm


def test_an_accepted_revision_changes_the_reading_and_the_opening_line(envelope):
    d, tr, llm = run_revision(envelope, approve=True)
    assert d.reading_revision["accepted"]
    w = d.interpretation["working"][0]
    assert w["reading"] == "Springfield, Missouri" and w["settled"] == "revised"
    assert w["alternatives"] == ["Springfield, Illinois"]
    line = opening_line(d.interpretation)
    assert line == ('I read "Springfield" as Springfield, Missouri because the task names the Missouri zoo; '
                    'Springfield, Illinois is not available.')
    assert "revised by the planner" in task_note(d.interpretation)
    answer, added = enforce_opening("## Answer\nGo on Monday.", d.interpretation)
    assert answer.startswith(line) and added["opening_line_added"]
    assert "reading_revision" in llm.calls_of("plan_observer")[0]["messages"][-1]["content"]   # the observer sees it


def test_a_refused_revision_leaves_the_reading(envelope):
    d, tr, _ = run_revision(envelope, approve=False)
    assert d.reading_revision["accepted"] is False
    assert d.interpretation["working"][0]["reading"] == "Springfield, Illinois"
    assert tr.events("reading_revision_refused")
