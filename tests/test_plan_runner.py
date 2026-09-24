"""D31 — the plan topology: steps run over the depends_on graph and see only the artifacts they depend on."""
import json
import re

import pytest

from amoeba.config.schema import PlanStep
from amoeba.interp.plan_runner import PLAN_MAX_TOKENS, PlanGraphError, relink, waves
from amoeba.interp.runtime import Interpreter
from amoeba.llm.toy_mock import toy_mock_client
from amoeba.task.draft import DraftError, draft_team
from amoeba.task.instantiate import instantiate
from amoeba.task.models import Task
from amoeba.task.source import ToyTaskSource
from amoeba.tools.registry import default_registry
from scripts.run_task import run_one
from tests.conftest import fx, mock

APPROVE = fx("observer_d24_approve")
FULL = fx("draft_d24_full")
# 1 -> 2, 1 -> 3, 2 -> 4, 3 -> 4
DIAMOND = (FULL.replace("   covers: R3\n   depends_on: none", "   covers: R3\n   depends_on: 1")
           .replace("   depends_on: 1, 2\n", "   depends_on: 1\n")
           .replace("   covers: R4\n   depends_on: 3", "   covers: R4\n   depends_on: 2, 3"))


def step_no(messages) -> str:
    return re.search(r"# Your step \(step (\d+)\)", messages[-1]["content"]).group(1)


BODY = ("Verdict: PASS\nIssues: none\n\n## Result\nBuilt on step 1, step 2 and step 3.\n\n## Figures\n"
        "| item | value |\n|---|---|\n| storage | 10 TB |\n\n- first point\n- second point\n")


def finish(messages, seed):
    """A helper whose output passes the D34 checks: headings, a table, a list, figures, its inputs named."""
    n = step_no(messages)
    return f"## Thought\nDone.\n\n## CurrentStep\nstep {n}\n\n## Action\nFinal Output\n\n## ActionInput\nOUT-{n}\n{BODY}"


def plan_team(task, envelope, trace, text=DIAMOND, **script):
    llm = mock(planner=[text], agent_observer=[APPROVE], plan_observer=[APPROVE], **script)
    return llm, instantiate(draft_team(task, llm, envelope, trace, prompts="d24"), "plan", task, envelope)


def steps(deps: dict[int, list[int]]) -> list[PlanStep]:
    return [PlanStep(index=n - 1, agent_ids=["a"], text=f"step {n}", depends_on=d) for n, d in deps.items()]


# ---- the graph ----------------------------------------------------------------------------------------------------
def test_waves_of_a_diamond():
    assert waves(steps({1: [], 2: [1], 3: [1], 4: [2, 3]})) == [[1], [2, 3], [4]]


def test_a_plan_without_depends_on_is_a_chain():
    assert waves(steps({1: [], 2: [], 3: []})) == [[1], [2], [3]]


@pytest.mark.parametrize("deps,msg", [({1: [2], 2: [1]}, "cycle"), ({1: [], 2: [7]}, "unknown step")])
def test_bad_graphs_are_rejected(deps, msg):
    with pytest.raises(PlanGraphError, match=msg):
        waves(steps(deps))


def test_dependency_on_a_dropped_step_is_relinked():
    kept = steps({1: [], 2: [1], 4: [1, 3]})
    written = {1: [], 2: [1], 3: [2], 4: [1, 3]}          # step 3 was dropped by Box 2 (it named no known role)
    out, events = relink(kept, written)
    assert [s.depends_on for s in out] == [[], [1], [1, 2]]
    assert events == [{"amoeba.step": 4, "amoeba.missing_step": 3, "amoeba.replaced_by": [2]}]


# ---- running it ---------------------------------------------------------------------------------------------------
def test_diamond_runs_in_order_and_steps_see_only_their_inputs(task, envelope, trace, tools, tmp_path):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=finish)
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path).run(cfg, task, seed=0)
    assert [(s["step"], s["wave"], s["received"], s["status"]) for s in ep.steps] == [
        (1, 1, [], "done"), (2, 2, [1], "done"), (3, 2, [1], "done"), (4, 3, [2, 3], "done")]
    assert ep.answer.startswith("OUT-4\n") and ep.error is None
    seen = {}
    for c in llm.calls_of("plan_worker"):
        seen.setdefault(step_no(c["messages"]), []).append(c["messages"][-1]["content"])
    inputs = {n: re.search(r"# Inputs: .*?\n(.*?)\n\n# Work done", ps[0], re.S).group(1) for n, ps in seen.items()}
    assert "None: this step starts from the task alone." in inputs["1"]
    assert "OUT-1" in inputs["3"] and "OUT-2" not in inputs["3"]          # 3 depends on 1 only
    assert "OUT-1" in inputs["2"] and "OUT-3" not in inputs["2"]
    # step 4 is the summariser's: it assembles from every step's output (D35), with the plan's deliverables
    [summ] = llm.calls_of("plan_summariser")
    sp = summ["messages"][-1]["content"]
    assert all(f"OUT-{k}" in sp for k in (1, 2, 3)) and "R4: deliver a recommendation memo with a risk table" in sp
    assert "## Step 1 (Cost Analyst), status: done; figures:" in sp and "Compute 17 * 23 + 5" in sp
    assert "Constraints: 12-person team" in seen["1"][0]
    assert all(c["max_tokens"] == PLAN_MAX_TOKENS for c in llm.calls if c["kind"].startswith("plan_"))
    # the multi-role step records both helpers, in turn order
    three = ep.steps[2]
    assert [c["agent"] for c in three["contributions"]] == ["Cost Analyst", "Schema Engineer"]   # roster order
    # artifacts on disk: the text and its metadata
    meta = json.loads((tmp_path / "artifacts" / "step_3.json").read_text())
    assert meta["roles"] == ["Cost Analyst", "Schema Engineer"] and meta["covers"] == ["R2", "R3"]
    assert meta["output_spec"] == "reconciled figures" and meta["sources"] == []
    assert (tmp_path / "artifacts" / "step_4.md").read_text().startswith("OUT-4\n")
    ev = trace.events("plan_graph")[0]
    assert ev["amoeba.waves"] == [[1], [2, 3], [4]] and ev["amoeba.max_turns"] == 5


def test_a_cycle_is_rejected_before_any_box3_call(task, envelope, trace):
    cyc = DIAMOND.replace("   covers: R1, R2\n   depends_on: none", "   covers: R1, R2\n   depends_on: 4")
    llm = mock(planner=[cyc], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=finish)
    with pytest.raises(DraftError, match="V8 plan: cycle"):
        instantiate(draft_team(task, llm, envelope, trace, prompts="d24"), "plan", task, envelope)
    assert llm.calls_of("plan_worker") == []


def test_step_that_never_finishes_is_max_turns(task, envelope, trace, tools):
    stall = lambda m, s: "## Thought\nhm\n\n## CurrentStep\nthink\n\n## Action\nPrint\n\n## ActionInput\nthinking\n"
    llm, cfg = plan_team(task, envelope, trace, plan_worker=stall)
    ep = Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    assert (ep.steps[0]["status"], ep.steps[0]["status_reason"], ep.steps[0]["turns"]) == ("incomplete", "max_turns", 5)
    assert ep.error == "incomplete"


def test_toy_tasks_with_a_d19_draft_run_as_a_chain(tmp_path, envelope, tools):
    for t in ToyTaskSource(0, 5).tasks():
        r = run_one(t, "plan", toy_mock_client(), envelope, tools, tmp_path)
        assert r.score == 1.0 and r.error is None
        saved = json.loads((tmp_path / r.run_id / "artifacts" / "step_2.json").read_text())
        assert saved["received"] == [1] and saved["status"] == "done"


def test_a_markdown_answer_is_not_cut_at_its_first_heading(task, envelope, trace, tools):
    memo = "# Memo\n\n**To:** leadership\n\n### 1. Summary\nPostgreSQL.\n\n### 2. Risks\n| risk | owner |"
    reply = lambda m, s: f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\n{memo}\n"
    llm, cfg = plan_team(task, envelope, trace, plan_worker=reply)
    ep = Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    assert ep.answer == memo                       # flat would publish only "# Memo ... leadership"


# ---- D34: done_when checks, one retry, verification and rework ----------------------------------------------------
def scripted(per_step):
    """A plan helper whose reply depends on the step and on how often that step was asked before."""
    seen = {}

    def reply(messages, seed):
        n = step_no(messages)
        seen[n] = seen.get(n, 0) + 1
        body = per_step(n, seen[n], messages[-1]["content"])
        return f"## Thought\nok\n\n## CurrentStep\nstep {n}\n\n## Action\nFinal Output\n\n## ActionInput\n{body}"
    reply.seen = seen
    return reply


def test_a_failed_check_gets_one_retry_with_the_reason(task, envelope, trace, tools):
    # step 1's output line asks for a "cost table"; its first answer has none
    w = scripted(lambda n, k, p: "Prices: about 10 TB of storage, cost unknown." if (n, k) == ("1", 1) else f"OUT-{n}\n{BODY}")
    llm, cfg = plan_team(task, envelope, trace, plan_worker=w)
    ep = Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    one = ep.steps[0]
    assert one["retried"] and one["status"] == "done" and w.seen["1"] == 2
    [ev] = trace.events("check_retry")
    assert ev["amoeba.step"] == 1 and ev["amoeba.failed_checks"] == ["format_table"]
    second = [c for c in llm.calls_of("plan_worker") if "(step 1)" in c["messages"][-1]["content"]][1]
    assert "Plain code checked this step's output and it failed: the output line asks for a table" in \
        second["messages"][-1]["content"]


def test_a_step_that_still_fails_is_incomplete_and_the_next_step_sees_it(task, envelope, trace, tools):
    w = scripted(lambda n, k, p: "No table here, only words." if n == "1" else f"OUT-{n}\n{BODY}")
    llm, cfg = plan_team(task, envelope, trace, plan_worker=w)
    ep = Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    one = ep.steps[0]
    assert (one["status"], one["retried"], w.seen["1"]) == ("incomplete", True, 2)
    assert one["status_reason"].startswith("checks failed: format_table")
    step2 = [c for c in llm.calls_of("plan_worker") if "(step 2)" in c["messages"][-1]["content"]][0]
    assert "## Step 1 (Cost Analyst), status: incomplete" in step2["messages"][-1]["content"]


def test_a_fail_verdict_reworks_each_producer_once(task, envelope, trace, tools, tmp_path):
    def body(n, k, prompt):
        if n == "3":
            return f"Verdict: FAIL\nIssues:\n1. Step 1: the storage price has no source.\n\n{BODY}"
        return f"OUT-{n}.{k}\n{BODY}"
    w = scripted(body)
    llm, cfg = plan_team(task, envelope, trace, plan_worker=w)
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path).run(cfg, task, seed=0)
    # D38: after the rework the verifier checks once more (it fails again here; no second rework)
    assert [(s["step"], bool(s["rework_of"]), bool(s.get("reverify_of"))) for s in ep.steps] == [
        (1, False, False), (2, False, False), (3, False, False), (1, True, False), (3, False, True), (4, False, False)]
    three = next(s for s in ep.steps if s["step"] == 3)
    assert three["verification"] and three["verdict"] == "FAIL" and "no source" in three["issues"]
    again = [s for s in ep.steps if s["step"] == 3][-1]
    assert (again["verdict_first"], again["verdict_after_rework"], again["verdict"]) == ("FAIL", "FAIL", "FAIL")
    redo = next(s for s in ep.steps if s["step"] == 1 and s["rework_of"])
    assert redo["rework_of"]["by_step"] == 3
    assert w.seen == {"1": 2, "2": 1, "3": 4, "4": 1}          # step 3 (two helpers) checks twice, never a 3rd time
    rework_prompt = [c for c in llm.calls_of("plan_worker") if "(step 1)" in c["messages"][-1]["content"]][1]
    assert "REWORK: verification step 3 found issues" in rework_prompt["messages"][-1]["content"]
    assert "OUT-1.1" in rework_prompt["messages"][-1]["content"]          # it sees its earlier output
    [step4] = llm.calls_of("plan_summariser")
    assert "OUT-1.2" in step4["messages"][-1]["content"]                  # the summariser sees the reworked version
    assert "OUT-1.1" not in step4["messages"][-1]["content"]
    [ev] = trace.events("rework")
    assert (ev["amoeba.step"], ev["amoeba.by_step"]) == (1, 3)
    assert (tmp_path / "artifacts" / "step_1.first.md").read_text().startswith("OUT-1.1")
    assert (tmp_path / "artifacts" / "step_1.md").read_text().startswith("OUT-1.2")


def test_verification_prompt_asks_for_a_verdict(task, envelope, trace, tools):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=finish)
    Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    prompts = {step_no(c["messages"]): c["messages"][-1]["content"] for c in llm.calls_of("plan_worker")}
    assert 'You are VERIFYING the outputs' in prompts["3"] and "You are VERIFYING" not in prompts["2"]


# ---- D35: the summariser only assembles -----------------------------------------------------------------------
def test_a_new_number_in_the_summary_is_flagged(tmp_path, envelope):
    def reply(messages, seed):
        n = step_no(messages)
        body = (f"# Memo\n\n## Answer\nStorage 10 TB; total cost 4,321 USD per month.\n\n## Limitations\n- step 2 is blocked"
                if n == "4" else f"OUT-{n}\n{BODY}")
        return f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\n{body}"
    llm = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=reply)
    r = run_one(Task(prompt="Compute 17 * 23 + 5."), "plan", llm, envelope, default_registry(), tmp_path,
                draft_prompts="d24")
    saved = json.loads((tmp_path / r.run_id / "result.json").read_text())
    assert {k: saved["summary_check"][k] for k in ("new_number_in_summary", "new_numbers", "limitations_section")} == \
        {"new_number_in_summary": 1, "new_numbers": ["4321"], "limitations_section": True}
    prompt = llm.calls_of("plan_summariser")[0]["messages"][-1]["content"]
    assert "add no new analysis, no new facts and no new numbers" in prompt and '"## Limitations"' in prompt


# ---- D36: BLOCKED policy ------------------------------------------------------------------------------------------
def test_a_blocked_part_makes_the_step_partial_and_reaches_the_limitations(tmp_path, envelope):
    def reply(messages, seed):
        n = step_no(messages)
        if n == "2":
            body = (f"OUT-2\n{BODY}\nBLOCKED: database_sandbox — the load test at 5,000 queries/min was not run.")
        elif n == "4":
            body = "# Memo\n\n## Answer\nStorage 10 TB.\n\n## Limitations\n- step 2 could not load-test."
        else:
            body = f"OUT-{n}\n{BODY}"
        return f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\n{body}"
    llm = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=reply)
    r = run_one(Task(prompt="Compute 17 * 23 + 5."), "plan", llm, envelope, default_registry(), tmp_path,
                draft_prompts="d24")
    two = json.loads((tmp_path / r.run_id / "artifacts" / "step_2.json").read_text())
    assert (two["status"], two["blocked"], two["blocked_canonical"]) == ("partial", ["database_sandbox"],
                                                                          ["database_sandbox"])
    assert two["status_reason"] == "lacked: database_sandbox"
    saved = json.loads((tmp_path / r.run_id / "result.json").read_text())
    assert saved["blocked_capabilities"] == {"database_sandbox": 1}
    assert saved["summary_check"]["limitations_added_by_code"] == ["database_sandbox"]
    assert saved["answer"].rstrip().endswith("- BLOCKED: database_sandbox (the team had no such capability; added by "
                                             "plain code)")
    summ = llm.calls_of("plan_summariser")[0]["messages"][-1]["content"]
    assert "## Step 2 (Schema Engineer), status: partial (lacked: database_sandbox); lacked: database_sandbox" in summ
    assert [s["step"] for s in r_steps(tmp_path, r)] == [1, 2, 3, 4]            # the run went on


def r_steps(tmp_path, r):
    return [json.loads(p.read_text()) for p in sorted((tmp_path / r.run_id / "artifacts").glob("step_*.json"))]


def test_limitations_that_name_the_gap_are_left_alone(task, envelope, trace, tools):
    def reply(messages, seed):
        n = step_no(messages)
        body = {"2": f"OUT-2\n{BODY}\nBLOCKED: Database Sandbox — no load test",
                "4": "# Memo\n\n## Limitations\n- No database sandbox, so the schemas were not load-tested."}.get(
            n, f"OUT-{n}\n{BODY}")
        return f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\n{body}"
    llm, cfg = plan_team(task, envelope, trace, plan_worker=reply)
    ep = Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    four = ep.steps[-1]
    assert four["summary_check"]["blocked_capabilities"] == ["database_sandbox"]
    assert four["summary_check"]["limitations_added_by_code"] == [] and "added by plain code" not in ep.answer


def test_a_helper_that_only_answers_blocked_leaves_the_step_incomplete(task, envelope, trace, tools):
    def reply(messages, seed):
        n = step_no(messages)
        if n == "1":
            return "## Thought\nno\n\n## CurrentStep\nw\n\n## Action\nBLOCKED: web_search\n\n## ActionInput\n\n"
        return f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\nOUT-{n}\n{BODY}"
    llm, cfg = plan_team(task, envelope, trace, plan_worker=reply)
    ep = Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    one = ep.steps[0]
    assert (one["status"], one["blocked"]) == ("incomplete", ["web_search"]) and len(ep.steps) == 4


def test_a_short_answer_that_repeats_its_input_passes_the_checks():
    steps_ = {1: {"text": "SUSNESNOC", "meta": {"visible_source_ids": [], "roles": ["Solver"]}}}
    two = PlanStep(index=1, agent_ids=["a"], text="[Language Expert]: restate", depends_on=[1])
    from amoeba.interp.plan_runner import step_checks
    assert all(c["pass"] for c in step_checks(two, "SUSNESNOC\n\n(as computed)", [1], steps_))
    assert not all(c["pass"] for c in step_checks(two, "something else entirely", [1], steps_))


def test_a_verdict_that_turns_pass_after_rework_is_what_the_summariser_sees(task, envelope, trace, tools, tmp_path):
    def body(n, k, prompt):
        if n == "3":
            verdict = "PASS\nIssues: none" if "RE-CHECK" in prompt else "FAIL\nIssues:\n1. Step 1: no source."
            return f"Verdict: {verdict}\n\n{BODY}"
        return f"OUT-{n}.{k}\n{BODY}"
    llm, cfg = plan_team(task, envelope, trace, plan_worker=scripted(body))
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path).run(cfg, task, seed=0)
    last3 = [s for s in ep.steps if s["step"] == 3][-1]
    assert (last3["verdict_first"], last3["verdict_after_rework"], last3["verdict"]) == ("FAIL", "PASS", "PASS")
    [ev] = trace.events("reverify")
    assert ev["amoeba.reworked"] == [1]
    summ = llm.calls_of("plan_summariser")[0]["messages"][-1]["content"]
    assert "verdict: PASS (after rework; first verdict FAIL)" in summ
    assert (tmp_path / "artifacts" / "step_3.first.md").exists()


# ---- D39: stale inputs after a rework -----------------------------------------------------------------------------
def fail_then_pass(n, k, prompt):
    """Step 3 checks step 1: FAIL first, PASS on the re-check."""
    if n == "3":
        verdict = "PASS\nIssues: none" if "RE-CHECK" in prompt else "FAIL\nIssues:\n1. Step 1: no source."
        return f"Verdict: {verdict}\n\n{BODY}"
    return f"OUT-{n}.{k}\n{BODY}"


def test_a_step_built_on_a_reworked_step_is_marked_stale(task, envelope, trace, tools, tmp_path):
    w = scripted(fail_then_pass)
    llm, cfg = plan_team(task, envelope, trace, plan_worker=w)
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path).run(cfg, task, seed=0)
    two = [s for s in ep.steps if s["step"] == 2][-1]
    assert (two["stale"], two["stale_because"]) == (True, [1]) and w.seen["2"] == 1       # not re-run by default
    [ev] = trace.events("stale")
    assert (ev["amoeba.step"], ev["amoeba.because_reworked"], ev["amoeba.will_rerun"]) == (2, [1], False)
    assert json.loads((tmp_path / "artifacts" / "step_2.json").read_text())["stale"] is True
    summ = llm.calls_of("plan_summariser")[0]["messages"][-1]["content"]
    assert "STALE: built on step(s) 1 before their rework" in summ
    assert not [s for s in ep.steps if s["step"] == 3][-1]["stale"]          # the verifier re-checked instead


def test_rerun_stale_reruns_each_stale_step_once(task, envelope, trace, tools):
    from amoeba.interp.plan_runner import PlanOptions
    w = scripted(fail_then_pass)
    llm, cfg = plan_team(task, envelope, trace, plan_worker=w)
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions(rerun_stale=True)).run(cfg, task, seed=0)
    two = [s for s in ep.steps if s["step"] == 2]
    assert len(two) == 2 and two[-1]["rerun_of_stale"] == {"because_reworked": [1]} and two[-1]["stale"] is False
    assert w.seen["2"] == 2
    assert "OUT-1.2" in [c for c in llm.calls_of("plan_worker") if "(step 2)" in c["messages"][-1]["content"]][-1][
        "messages"][-1]["content"]                                               # the re-run sees the reworked step 1
    assert "STALE" not in llm.calls_of("plan_summariser")[0]["messages"][-1]["content"]
    assert trace.events("plan_graph")[0]["amoeba.options.rerun_stale"] is True
