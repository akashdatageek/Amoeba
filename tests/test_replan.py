"""D63 — the Action Observer: plain code decides WHEN (a trigger after a wave), the AI proposes WHAT (one typed
decision), plain code decides WHETHER (validation) and applies it. Offline, with the mock LLM."""
import json

from amoeba.interp.plan_runner import PlanOptions, parse_decision
from amoeba.interp.runtime import Interpreter
from scripts.run_task import cli_plan_options, parse_args
from tests.test_plan_runner import BODY, plan_team, step_no

ON = PlanOptions(replan="on")
BLOCKED_1 = "\nBLOCKED: web_search — no live prices, so the storage price could not be checked\n"


def reply(action, text):
    return f"## Thought\nok\n\n## CurrentStep\nnow\n\n## Action\n{action}\n\n## ActionInput\n{text}"


def worker(per_step=None):
    """Every step passes its checks; per_step(n) adds text to step n's output (e.g. a BLOCKED line)."""
    def run(messages, seed):
        n = step_no(messages)
        return reply("Final Output", f"OUT-{n}\n{BODY}{(per_step or (lambda n: ''))(n)}")
    return run


def decision(kind, steps="None", role="None", unmet="None", requests="None", reason="a reason"):
    return (f"## Thought\nthinking\n\n## Decision\n{kind}\n\n## Reason\n{reason}\n\n## Steps\n{steps}\n\n"
            f"## Role\n{role}\n\n## Unmet\n{unmet}\n\n## Capability Requests\n{requests}\n")


ADD5 = ("5. [Cost Analyst]: Estimate prices from published figures\n   kind: work\n   covers: R2\n   depends_on: 1\n"
        "   do: use calc on the published list prices; label every figure an estimate\n   output: cost table\n"
        "   done_when: every cell labelled\n   feeds: 3")


def run(task, envelope, trace, tools, tmp_path, script, observer, options=ON, stock=None):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script, replanner=observer)
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path, plan_options=options, stock=stock).run(cfg, task, seed=0)
    return llm, cfg, ep


def test_no_trigger_means_no_observer_call(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(), [decision("CONTINUE")])
    assert llm.calls_of("replanner") == [] and trace.events("replan_trigger") == []
    assert ep.replan["calls"] == 0 and ep.replan["plan_versions"] == 1
    assert (tmp_path / "plan.v1.json").exists() and not (tmp_path / "plan.v2.json").exists()
    assert set(ep.replan["requirements"]) == {"R1", "R2", "R3", "R4"}


def test_with_replan_off_nothing_changes(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(lambda n: BLOCKED_1 if n == "1" else ""),
                       [decision("ADD_STEP", ADD5)], options=PlanOptions())
    assert llm.calls_of("replanner") == [] and ep.replan == {} and not (tmp_path / "plan.v1.json").exists()
    assert "MISSING INPUT" not in llm.calls_of("plan_worker")[1]["messages"][-1]["content"]


def test_a_missing_capability_triggers_one_call_and_an_accepted_step_runs(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(lambda n: BLOCKED_1 if n == "1" else ""),
                       [decision("ADD_STEP", ADD5, reason="estimate from published list prices with calc")])
    [call] = llm.calls_of("replanner")
    prompt = call["messages"][-1]["content"]
    assert "step 1 is partial: lacked web_search" in prompt and "1. [Cost Analyst]: Price both databases — status: " \
        "partial" in prompt and "2. [Schema Engineer]: Prototype and test — status: not run" in prompt
    assert "- calc: held by Cost Analyst" in prompt and "OUT-1" in prompt
    [trig] = trace.events("replan_trigger")
    assert trig["amoeba.kinds"] == ["missing_capability"] and trig["amoeba.wave"] == 1
    [val] = trace.events("replan_validated")
    assert val["amoeba.accepted"] and val["amoeba.changes"]["steps_added"] == [5]
    order = [(s["step"], s["wave"]) for s in ep.steps]
    assert order == [(1, 1), (2, 2), (5, 2), (3, 3), (4, 4)]          # 3 waits for 5 (feeds); 4 waits for all
    assert ep.replan["accepted"] == 1 and ep.replan["steps_added"] == 1 and ep.replan["plan_versions"] == 2
    v2 = json.loads((tmp_path / "plan.v2.json").read_text())
    assert v2["diff"]["steps_added"] == [5] and [s["number"] for s in v2["steps"]] == [1, 2, 3, 4, 5]
    assert next(s for s in v2["steps"] if s["number"] == 3)["depends_on"] == [1, 5]
    assert ep.replan["requirements"]["R1"]["status"] == "partly"      # only the partial step 1 covers R1
    assert ep.replan["requirements"]["R3"] == {"status": "met", "steps": [2, 3]}


def test_changing_a_finished_step_is_rejected_and_the_plan_stays(task, envelope, trace, tools, tmp_path):
    bad = ADD5.replace("5. [Cost Analyst]", "1. [Cost Analyst]")
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(lambda n: BLOCKED_1 if n == "1" else ""),
                       [decision("REVISE_REMAINING", bad)])
    [val] = trace.events("replan_validated")
    assert not val["amoeba.accepted"] and any("step 1 has already run" in e for e in val["amoeba.errors"])
    assert [s["step"] for s in ep.steps] == [1, 2, 3, 4] and ep.replan["rejected"] == 1
    assert not (tmp_path / "plan.v2.json").exists()


def test_a_new_step_may_not_depend_on_a_step_that_has_not_run(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(lambda n: BLOCKED_1 if n == "1" else ""),
                       [decision("ADD_STEP", ADD5.replace("depends_on: 1", "depends_on: 2"))])
    [val] = trace.events("replan_validated")
    assert not val["amoeba.accepted"] and "neither finished nor new" in val["amoeba.errors"][0]


def test_an_unreadable_reply_counts_as_continue(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(lambda n: BLOCKED_1 if n == "1" else ""),
                       ["I think the plan is fine, really."])
    [d] = ep.replan["decisions"]
    assert (d["decision"], d["accepted"], d["errors"]) == ("CONTINUE", True, ["unreadable reply: treated as CONTINUE"])
    assert [s["step"] for s in ep.steps] == [1, 2, 3, 4]


def test_drop_step_lists_the_requirement_as_not_met(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(lambda n: BLOCKED_1 if n == "1" else ""),
                       [decision("DROP_STEP", "step: 2", unmet="R3 — no database sandbox, so nothing can be tested")])
    assert [s["step"] for s in ep.steps] == [1, 3, 4]
    assert ep.replan["requirements"]["R3"]["status"] == "not met"
    assert "- NOT MET: R3 — prototype and test the event schema in both databases" in ep.answer
    three = json.loads((tmp_path / "plan.v2.json").read_text())["steps"][1]
    assert three["number"] == 3 and three["depends_on"] == [1]                 # relinked past the dropped step 2


def test_the_answer_step_cannot_be_dropped(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(lambda n: BLOCKED_1 if n == "1" else ""),
                       [decision("DROP_STEP", "step: 4", unmet="R4")])
    assert "writes the final answer" in trace.events("replan_validated")[0]["amoeba.errors"][0]


def test_reassign_gives_a_waiting_step_to_another_role(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(lambda n: BLOCKED_1 if n == "1" else ""),
                       [decision("REASSIGN_STEP", "step: 2\nrole: Cost Analyst")])
    two = next(s for s in ep.steps if s["step"] == 2)
    assert two["roles"] == ["Cost Analyst"]


ROLE = ('{"name": "Price Researcher", "goal": "published list prices", "description": "finds list prices", '
        '"skills": ["pricing"], "tools": ["calc", "price_api"], "outputs": ["price table"], '
        '"success_criteria": ["every price labelled"], "prompt": "You find published list prices."}')


def test_add_role_needs_a_complete_card(task, envelope, trace, tools, tmp_path):
    thin = '{"name": "Price Researcher", "tools": []}'
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(lambda n: BLOCKED_1 if n == "1" else ""),
                       [decision("ADD_ROLE", ADD5.replace("[Cost Analyst]", "[Price Researcher]"), role=thin)])
    assert "incomplete role card: no goal, outputs, success_criteria, prompt" in \
        trace.events("replan_validated")[0]["amoeba.errors"][0]


def test_add_role_joins_the_team_and_its_request_goes_through_the_toolbox(task, envelope, trace, tools, tmp_path):
    asked = []

    def stock(requests, cfg, reg):
        asked.extend((q.name, q.for_role) for q in requests)
        for q in requests:
            q.status, q.reason = "unfilled", "no_candidates"
        return reg, {}
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(lambda n: BLOCKED_1 if n == "1" else ""),
                       [decision("ADD_ROLE", ADD5.replace("[Cost Analyst]", "[Price Researcher]"), role=ROLE)],
                       stock=stock)
    assert asked == [("price_api", "Price Researcher")]
    five = next(s for s in ep.steps if s["step"] == 5)
    assert five["roles"] == ["Price Researcher"] and ep.replan["roles_added"] == 1
    assert any(q["name"] == "price_api" and q["source"] == "replan" for q in cfg.meta["capability_requests"])
    v2 = json.loads((tmp_path / "plan.v2.json").read_text())
    assert v2["diff"]["role_added"] == "Price Researcher"
    assert next(r for r in v2["roles"] if r["name"] == "Price Researcher")["missing_tools"] == ["price_api"]


def test_a_missing_input_line_is_a_trigger(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path,
                       worker(lambda n: "\nMISSING INPUT: the measured p95 latency — step 2" if n == "3" else ""),
                       [decision("CONTINUE")])
    [trig] = trace.events("replan_trigger")
    assert trig["amoeba.kinds"] == ["missing_input"] and trig["amoeba.wave"] == 2
    three = [c for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "3"][0]
    assert "MISSING INPUT: <what>" in three["messages"][-1]["content"]


def test_a_verify_step_still_failing_is_a_trigger(task, envelope, trace, tools, tmp_path):
    verify = open("tests/fixtures/draft_d24_full.txt").read().replace(
        "3. [Schema Engineer, Cost Analyst]: Cross-check numbers\n",
        "3. [Schema Engineer, Cost Analyst]: Cross-check numbers\n   kind: verify\n")

    def script(messages, seed):
        n = step_no(messages)
        if n == "3":
            return reply("Final Output", f"Verdict: FAIL\nIssues:\n1. Step 1: the price has no source.\n\n{BODY}")
        return reply("Final Output", f"OUT-{n}\n{BODY}")
    llm, cfg = plan_team(task, envelope, trace, text=verify, plan_worker=script, replanner=[decision("CONTINUE")])
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path, plan_options=ON).run(cfg, task, seed=0)
    [trig] = trace.events("replan_trigger")
    assert trig["amoeba.kinds"] == ["verify_fail"] and "still says FAIL after rework" in trig["amoeba.triggers"][0]
    assert len(llm.calls_of("replanner")) == 1


def test_a_tool_the_plan_never_named_is_a_trigger_for_a_helper_whose_step_waits(task, envelope, trace, tools,
                                                                               tmp_path):
    tools.register("local:Bash", "local tool", lambda text: "ok")
    llm, cfg = plan_team(task, envelope, trace, plan_worker=worker(), replanner=[decision("CONTINUE")])
    engineer = next(a for a in cfg.agents.values() if a.name == "Schema Engineer")
    engineer.tools.append("local:Bash")          # stocked for its database_sandbox request, a name the plan never used
    engineer.pool.append({"kind": "tool", "id": "local:Bash", "name": "local:Bash", "source": "local",
                          "request": "database_sandbox", "text": "runs a shell command"})
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path, plan_options=ON).run(cfg, task, seed=0)
    [trig] = trace.events("replan_trigger")
    assert trig["amoeba.kinds"] == ["new_tool"] and "Schema Engineer now hold(s) local:Bash" in trig["amoeba.triggers"][0]


def test_at_most_two_replans_per_run(task, envelope, trace, tools, tmp_path):
    every = lambda n: f"\nBLOCKED: tool_{n} — missing\n" if n != "4" else ""
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(every), [decision("CONTINUE")])
    assert len(llm.calls_of("replanner")) == 2 and ep.replan["calls"] == 2
    assert [e["amoeba.called"] for e in trace.events("replan_trigger")] == [True, True]


def test_parse_decision_and_the_cli_flag():
    d = parse_decision("<thought>hmm</thought>\n## Decision\nadd_step\n\n## Reason\nbecause\n\n## Steps\nNone\n")
    assert (d["decision"], d["reason"], d["steps"], d["readable"]) == ("ADD_STEP", "because", "", True)
    assert parse_decision("nothing")["decision"] == "CONTINUE"
    assert parse_args(["--toy"]).replan == "off" and cli_plan_options(parse_args(["--toy", "--replan", "on"])).replan == "on"


REVISE_RENUMBERED = (   # the smoke run's shape: the old answer step 4 becomes a work step, the writer moves to 5
    "2. [Cost Analyst]: Confirm the prices\n   kind: work\n   covers: R2\n   depends_on: 1\n   do: re-check\n"
    "   output: prices\n   done_when: confirmed\n\n"
    "3. [Schema Engineer]: Prototype and test\n   kind: work\n   covers: R3\n   depends_on: 2\n   do: test\n"
    "   output: report\n   done_when: tested\n\n"
    "4. [Cost Analyst]: Cross-check numbers\n   kind: verify\n   covers: R2, R3\n   depends_on: 3\n   do: check\n"
    "   output: verdict\n   done_when: checked\n\n"
    "5. [Memo Writer]: Assemble the memo\n   kind: work\n   covers: R1, R2, R3, R4\n   depends_on: 4\n"
    "   do: assemble\n   output: memo\n   done_when: written")


def test_a_revision_that_moves_the_answer_step_is_accepted_and_its_new_step_writes_the_answer(
        task, envelope, trace, tools, tmp_path):
    """Smoke-run defect: the old answer step 4 was made to wait for the new step 5, which waits for 4 — a cycle,
    and the revision was rejected. The answer step is now found again in the proposed plan."""
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(lambda n: BLOCKED_1 if n == "1" else ""),
                       [decision("REVISE_REMAINING", REVISE_RENUMBERED), decision("CONTINUE")])
    [val, *_] = trace.events("replan_validated")
    assert val["amoeba.accepted"], val["amoeba.errors"]
    assert [s["step"] for s in ep.steps] == [1, 2, 3, 4, 5]
    assert ep.answer.startswith("OUT-5") and len(llm.calls_of("plan_summariser")) == 1
    assert ep.replan["requirements"]["R2"]["steps"] == [2, 4]          # the producers, not the answer step


def test_a_granted_web_tool_is_never_announced_as_unavailable(task, envelope, trace, tools, tmp_path):
    """Smoke-run defect: fetch_url was granted (D32) but still on the role's missing tools, so the prompt said it
    was unavailable and the helper wrote BLOCKED: fetch_url."""
    from amoeba.tools.web import WEB_TOOLS
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, worker(), [decision("CONTINUE")])
    for a in cfg.agents.values():
        a.missing_tools = [*a.missing_tools, "fetch_url"]
        a.tools = [*a.tools, *WEB_TOOLS]
    from amoeba.interp.runtime import with_unavailable
    assert all("fetch_url is unavailable" not in with_unavailable(a) for a in cfg.agents.values())
