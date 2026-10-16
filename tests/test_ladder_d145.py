"""D145 — the Box 4 ladder: provider_blocked rungs (compact prompt, another model, stop naming the categories), no
re-granting a held tool (it becomes tool_error), requests per step, replan_remaining keeps independent steps and must
pass the HARD checks, the proposer key per step, max_input_chars for a capped missing input, and the summary lines.
Offline."""
from amoeba.adapt.fixes import candidates
from amoeba.adapt.proposer import FixEdit
from amoeba.adapt.stuck import diagnose, open_requests, step_signals
from amoeba.interp.plan_runner import PLAN_MAX_TURNS, PlanOptions, PlanRunner
from amoeba.interp.runtime import Interpreter
from amoeba.llm.client import ChatResponse
from amoeba.task.models import Episode
from scripts.run_task import adapt_summary_lines
from tests.test_fixes_d117 import good
from tests.test_plan_runner import plan_team, step_no

ON = PlanOptions(adapt="on", failed_step="run")
BLOCKED = ChatResponse(content="", finish_reason="refusal", refusal_category="cyber")


def test_defaults():
    from amoeba.adapt.config import adapt_config
    cfg = adapt_config()
    assert cfg["limits"]["run_options"]["max_turns"] == {"min": 3, "max": 12} and PLAN_MAX_TURNS == 6
    assert cfg["adapt"]["more_turns"] == 3
    assert cfg["diagnoser"]["allowed_edits"]["provider_blocked"] == ["compact_prompt", "switch_model"]


def test_a_blocked_step_is_retried_with_the_compact_prompt(task, envelope, trace, tools):
    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and "Skills:" in user:              # the full role card: the service blocks it
            return BLOCKED
        return good(n)
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script)
    ep = Interpreter(llm, tools, trace, plan_options=ON).run(cfg, task, seed=0)
    assert ep.stuck[0]["cause"] == "provider_blocked"
    [f] = ep.adaptation["fixes"]
    assert (f["kind"], f["result"]) == ("compact_prompt", "recovered")
    assert ep.error is None


def test_a_step_still_blocked_stops_and_names_the_categories(task, envelope, trace, tools, tmp_path):
    def script(messages, seed):
        return BLOCKED if step_no(messages) == "1" else good(step_no(messages))
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script)
    ep = Interpreter(llm, tools, trace, run_dir=str(tmp_path),
                     plan_options=PlanOptions(adapt="on")).run(cfg, task, seed=0)   # dependents: still stops
    assert [f["kind"] for f in ep.adaptation["fixes"]] == ["compact_prompt"]
    assert ep.adaptation["stopped"]["categories"] == ["cyber"]
    assert "Refusal categories:** cyber" in (tmp_path / "adapt_report.md").read_text()
    assert len([m for m in ep.steps if m["step"] != 1]) == 0        # nothing after it ran


def test_a_held_tool_is_tool_error_not_capability():
    meta = {"step": 1, "status": "partial", "roles": ["Analyst"], "finished": True, "turns": 3,
            "blocked": ["calc"], "status_reason": "lacked: calc",
            "tool_calls": [{"tool": "calc", "ok": False, "result": "error: bad expression 2x"}]}
    sig = step_signals(meta, plan={1: {"output": "x", "roles": ["Analyst"]}}, held={"calc": "calc"})
    assert [s["signal"] for s in sig] == ["held_tool_failed"]
    assert sig[0]["evidence"] == ["tool held but failed: calc — error: bad expression 2x"]
    assert diagnose(sig)["cause"] == "tool_error"
    d = {"cause": "capability", "lacked": ["calc", "pdf_reader"], "allowed_edits": ["grant_tool"]}
    fixes, notes = candidates(d, 1, {"stock": True, "held": {"calc"}})
    assert fixes[0]["params"]["items"] == ["pdf_reader"] and any("not granted again" in x for x in notes)
    assert candidates({**d, "lacked": ["calc"]}, 1, {"stock": True, "held": {"calc"}})[0] == []


def test_a_request_for_a_held_tool_is_not_open():
    reqs = [{"name": "python_interpreter", "for_role": "A", "status": "unfilled"},
            {"name": "pdf_reader", "for_role": "A", "status": "unfilled"}]
    left = open_requests(reqs, {"A": {"local:Bash"}}, lambda role, name: name == "python_interpreter")
    assert [q["name"] for q in left] == ["pdf_reader"]


def test_the_proposer_key_names_the_step():
    e = FixEdit(op="add_role_rule", params={"role": "A", "text": "Use calc."})
    assert e.key(1) != e.key(2) and e.key(1) == e.key(1)


def test_a_capped_missing_input_gets_more_input():
    d = {"cause": "missing_input", "upstream": [], "allowed_edits": ["set_run_option:max_input_chars"]}
    fixes, _ = candidates(d, 2, {"capped": True, "opts": {"max_input_chars": 6000}})
    assert [(f["kind"], f["params"]) for f in fixes] == [("set_run_option:max_input_chars", {"max_input_chars": 12000})]


def runner(task, envelope, trace, tools):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=lambda m, s: good(step_no(m)))
    i = Interpreter(llm, tools, trace, plan_options=PlanOptions(replan_method="off"))
    pr = PlanRunner(i, cfg, task, Episode(episode_id="e", team_id=cfg.team_id, task_id=task.id), None, i.plan_options)
    pr.answer_n = None                       # set by run(); this test checks the plan edit only
    return pr, cfg


def test_replan_remaining_drops_only_the_stuck_steps_dependents(task, envelope, trace, tools):
    pr, cfg = runner(task, envelope, trace, tools)
    role = pr.agents[cfg.plan[1].agent_ids[0]].name
    new = f"5. [{role}]: redo step 2\n   kind: work\n   covers: R2, R4\n   depends_on: 1\n   do: d\n   output: o\n   done_when: w"
    dec = {"decision": "REVISE_REMAINING", "steps": new, "role": "", "requests": "", "reason": "r", "unmet": ""}
    _, legacy = pr.validate_decision(dec)
    errors, change = pr.validate_decision(dec, stuck=2)
    assert legacy["drop"] == [1, 2, 3, 4] and change["drop"] == [2, 4]          # step 3 does not build on step 2
    assert pr.replan_hard_problems(change) == []                                # R2 and R4 still covered
    narrow = new.replace("covers: R2, R4", "covers: R2")
    problems = pr.replan_hard_problems(pr.validate_decision({**dec, "steps": narrow}, stuck=2)[1])
    assert any("no step covers R4" in p for p in problems)


def test_summary_lines():
    lines = adapt_summary_lines({"make_tool_unavailable": ["tool writer: no code runner (local tools are off)"],
                                 "kept_going": [{"step": 2, "cause": "checks"}], "usd_limit_enforced": False})
    assert lines[0].endswith("(local tools are off)") and "kept going without step 2" in lines[1]
    assert "USD limit not enforced" in lines[2]
    assert adapt_summary_lines(None) == []
