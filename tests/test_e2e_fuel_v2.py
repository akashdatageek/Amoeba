"""Phase G (audit) — an offline end-to-end mock run of the fuel-surcharge task's plan (eval/manual/probe_box4/d97f9e59)
under --protocol v2, with scripted replies. It shows, in one run:
  * Box 2 keeps the best draft, not the last (round 1 of 2);
  * the planner's reading revision is accepted on a plan-search source [P1], and the opening line says why;
  * Box 3 runs the plan's typed checks (D142);
  * a failed check that survives its retry turn feeds Box 4, whose fix recovers the step;
  * a long step's transcript is compacted (D144);
  * a step that never finishes leaves its dependents skipped, and the run ends without a crash.
"""
import glob
import json
from pathlib import Path

from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from amoeba.interp.trace import TraceWriter
from amoeba.llm.client import MockLLMClient
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from amoeba.task.interpret import opening_line
from amoeba.task.models import Task
from tests.test_fixes_d117 import BODY, reply
from tests.test_plan_runner import step_no

PLAN = json.loads(Path(glob.glob("eval/manual/probe_box4/d97f9e59*/plan.json")[0]).read_text())
TASK = Task(id="fuel", prompt="Weekly diesel fuel surcharge for an Indiana carrier: EIA prices, ATRI costs, workbook, "
                              "chart, memo, with sources.", family="research")
LESSONS = {"planner": "Planning search findings:\n[P1] EIA weekly retail diesel prices: there is no Indiana series; "
                      "the Midwest (PADD 2) series is the nearest published one."}
CHECKS = {2: [{"name": "output_has_table", "params": {"min_rows": 1}, "covers": ["R1"]}],
          4: [{"name": "output_mentions", "params": {"terms": ["ATRI", "marginal cost"]}, "covers": ["R4", "R5"]}],
          8: [{"name": "verdict_present", "params": {}, "covers": ["R2", "R3"]}],
          11: [{"name": "output_mentions", "params": {"terms": ["surcharge"]},
                "covers": [f"R{i}" for i in range(1, 17)]}]}
REVISION = {"entity": "weekly retail on-highway diesel price for Indiana",
            "from_reading": "An EIA Indiana state-level weekly series, if one exists",
            "to_reading": "The EIA Midwest (PADD 2) weekly No. 2 diesel retail price, labelled as a proxy",
            "reason": "EIA publishes no Indiana weekly diesel series", "evidence": ["P1"]}


def role_out(r: dict) -> dict:
    outs = [o if isinstance(o, dict) else {"artifact": str(o), "format": "text"} for o in r.get("outputs") or []]
    return {"name": r["name"], "seniority": r.get("seniority") or "senior", "description": r.get("description") or "",
            "goal": r.get("goal") or "", "responsibilities": r.get("responsibilities") or [],
            "skills": r.get("skills") or [], "tools": r.get("tools") or [], "inputs": r.get("inputs") or [],
            "outputs": [{"artifact": o.get("artifact", ""), "format": o.get("format", "")} for o in outs],
            "success_criteria": r.get("success_criteria") or [], "constraints": r.get("constraints") or [],
            "covers": r.get("covers") or [], "is_summariser": bool(r.get("is_summariser")),
            "prompt": r.get("prompt") or r.get("description") or "work"}


def plan_out(revision: bool) -> dict:
    """The saved fuel draft as the typed PlanOut a v2 planner returns (with the D142 checks added)."""
    out = {"requirements": [{"id": k, "text": v} for k, v in PLAN["requirements"].items()],
           "givens": PLAN["givens"], "open_questions": [], "risks": PLAN["risks"],
           "roles": [role_out(r) for r in PLAN["created_roles"]], "capability_requests": [],
           "plan": [{"number": s["index"] + 1, "roles": s["agent_names"], "title": s["title"],
                     "kind": s["kind"] or "work", "covers": s["covers"], "depends_on": s["depends_on"],
                     "do": s["do"], "output": s["output"], "done_when": s["done_when"],
                     "checks": CHECKS.get(s["index"] + 1, [])} for s in PLAN["plan"]]}
    if revision:
        out["reading_revision"] = REVISION
    return out


def review(verdict, blocking=0):
    return {"verdict": verdict, "issues": [{"severity": "blocking", "problem": f"issue {i}", "fix": "fix"}
                                           for i in range(blocking)]}


def test_the_fuel_plan_end_to_end_under_v2(envelope, tools, tmp_path):
    trace = TraceWriter(None, episode_id="fuel-e2e")
    trace.protocol = "v2"
    interp = json.loads(json.dumps(PLAN["interpretation"]))
    llm = MockLLMClient(script={"planner": [plan_out(True), plan_out(False)],
                                "agent_observer": [review("REVISE", 1), review("REVISE", 3)],
                                "plan_observer": [review("APPROVE"), review("REVISE", 1)]})
    d = draft_team(TASK, llm, envelope, trace, interpretation=interp, lessons=LESSONS, max_rounds=2,
                   planning_tier="full")
    # Box 2: the best draft (round 1: one blocking issue) is published, not round 2 (four)
    assert d.rounds_used == 2 and d.published_round == 1 and d.published_score["blocking"] == 1
    # the reading revision of round 1 is accepted on the plan-search source [P1]
    assert d.reading_revision["accepted"] and d.reading_revision["why"] == "cites P1"
    w = next(x for x in d.interpretation["working"] if x["entity"] == REVISION["entity"])
    assert w["settled"] == "revised" and "PADD 2" in w["reading"]
    assert "because EIA publishes no Indiana weekly diesel series; An EIA Indiana state-level weekly series, if one " \
           "exists is not available." in opening_line(d.interpretation)
    assert d.quality["checks"]["requirements_checked"]["ok"] and d.quality["checks"]["checks_valid"]["ok"]

    cfg = instantiate(d, "plan", TASK, envelope)
    assert [s.checks for s in cfg.plan if s.checks][0] == CHECKS[2]
    finals = {"4": 0}

    def worker(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and user.count("(calc)") < 4:                      # a long step: four tool calls
            return reply("calc", f"{user.count('(calc)') + 1} * 2.5")
        if n == "3":                                                   # never finishes: its dependents are skipped
            return reply("Print", "still cross-checking")
        if n == "4":                                                   # fails its check twice, then recovers
            finals["4"] += 1
            body = "ATRI 2025: total marginal cost $2.26 per mile, fuel $0.48 [S1]" if finals["4"] > 2 else \
                "Found a cost report [S1]"
            return reply("Final Output", f"{body}\n{BODY}")
        return reply("Final Output", f"OUT-{n} surcharge\n{BODY}")
    run_llm = MockLLMClient(script={"plan_worker": worker, "plan_summariser": worker,
                                    "plan_critic": ["## Verdict\nAGREE\n\n## Issues\nnone\n"],
                                    "fix_proposer": ["I cannot see a fix."]})
    opts = PlanOptions(protocol="v2", native_tools="on", adapt="on")              # failed_step: dependents
    ep = Interpreter(run_llm, tools, trace, run_dir=str(tmp_path), plan_options=opts).run(cfg, TASK, seed=0)
    steps = {m["step"]: m for m in ep.steps}

    # Box 3 ran the typed checks
    assert steps[2]["contract_checks"][0]["pass"] is True
    # step 4's check failed after its retry turn, fed Box 4 (cause checks), and the fix recovered it
    four = [s for s in ep.stuck if s["step"] == 4]
    assert four and four[0]["cause"] == "checks" and "contract:output_mentions" in " ".join(four[0]["evidence"])
    fix = next(f for f in ep.adaptation["fixes"] if f["step"] == 4)
    assert fix["result"] == "recovered" and steps[4]["status"] == "done" and steps[4]["contract_checks"][0]["pass"]
    # step 1's transcript was compacted
    assert steps[1]["context"]["chars_saved"] > 0
    # step 3 never finished: Box 4 tried, the task kept going, and the steps built on it were skipped
    assert steps[3]["status"] == "incomplete" and ep.adaptation["kept_going"][0]["step"] == 3
    skipped = sorted(k for k, m in steps.items() if m.get("blocked_upstream"))
    assert 5 in skipped and 11 in skipped and 4 not in skipped
    assert ep.answer                                                   # plain code assembled an answer; no crash
    assert trace.events("step_skipped") and trace.events("contract_checks")
