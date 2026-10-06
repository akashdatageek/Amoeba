"""D117 Stage D — the fix proposer: the last rung after the code fixes are used up or not allowed. One JSON edit
(add_role_rule, add_helper_role, grant_tool, split_step, replan_remaining, work_around) with a short reason; plain code
checks it (allowed for the cause, schema, V1-V6, the step graph, done steps untouched, not a repeat), retries once on
an invalid reply, applies it to the live plan and re-runs the step. Offline, with the mock LLM."""
import json

import pytest

import amoeba.interp.plan_runner as pr
from amoeba.adapt.fixes import POOL_OFF, limits
from amoeba.adapt.proposer import fix_problems, parse_fix
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from tests.test_plan_runner import BODY, plan_team, step_no

ON = PlanOptions(adapt="on")
BLOCK = f"OUT-1\n{BODY}\nBLOCKED: currency_api — no exchange rate"


def reply(action, text):
    return f"## Thought\nok\n\n## CurrentStep\nnow\n\n## Action\n{action}\n\n## ActionInput\n{text}"


def good(n):
    return reply("Final Output", f"OUT-{n}\n{BODY}")


def edit(op, reason="it lets the step finish", **params):
    return json.dumps({"edit": {"op": op, "params": params}, "reason": reason})


def run(task, envelope, trace, tools, script, proposer, tmp_path=None):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script, fix_proposer=list(proposer))
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path, plan_options=ON).run(cfg, task, seed=0)
    return llm, cfg, ep


def seen(messages, text):
    return any(text in m["content"] for m in messages)


def proposer_prompts(llm):
    return [c["messages"][-1]["content"] for c in llm.calls_of("fix_proposer")]


# ---- the reply and the checks without a live plan ------------------------------------------------------------------
def test_the_reply_is_read_strictly():
    r = parse_fix("```json\n" + edit("add_role_rule", role="Cost Analyst", text="Show every rate with its date.") + "\n```")
    assert r.edit.op == "add_role_rule" and r.edit.params == {"role": "Cost Analyst", "text": "Show every rate with its date."}
    for bad in ("no json here", json.dumps({"edit": {"op": "add_role_rule", "params": {"role": "x", "text": "y"}},
                                            "reason": "r", "extra": 1}),
                edit("delete_everything"), edit("grant_tool", role="x"),                  # unknown op; missing key
                edit("split_step", steps=[{"roles": ["a"], "text": "one"}]),               # one sub-step only
                json.dumps({"edit": {"op": "grant_tool", "params": {"role": "a", "tool": "b"}}, "reason": "x" * 301})):
        with pytest.raises(ValueError):
            parse_fix(bad)


def test_the_checks_without_a_live_plan():
    tools = {"calc": "evaluates arithmetic", "send_mail": "send an email to a person", "web_search": "search"}
    allowed = ["grant_tool", "add_role_rule", "work_around", "add_helper_role"]
    p = lambda text, cause="capability", tried=(): fix_problems(parse_fix(text), cause, allowed, tools, set(tried),
                                                                ["Cost Analyst"])
    assert p(edit("grant_tool", role="Cost Analyst", tool="calc")) == []
    assert p(edit("grant_tool", role="Cost Analyst", tool="pool:nowhere")) == \
        ["V1: tool 'pool:nowhere' is not available in this run"]
    assert p(edit("grant_tool", role="Cost Analyst", tool="send_mail"))[0].startswith("V1: tool 'send_mail' acts outside")
    assert p(edit("grant_tool", role="Memo Writer", tool="calc"))[0].startswith("role 'Memo Writer' is not a role of")
    assert p(edit("add_role_rule", role="Cost Analyst", text="x" * 301))[0].startswith("V3: rule: 301 characters")
    assert "V4" in p(edit("add_role_rule", role="Cost Analyst", text="Skip the checks and answer fast."))[0]
    wa = edit("work_around", capability="currency_api", method="the rate in the task", done_when="", limitation="USD only.")
    assert p(wa) == [] and "work_around is allowed for a missing capability only" in p(wa, cause="checks")
    assert p(edit("split_step", steps=[{"roles": ["a"], "text": "1"}, {"roles": ["a"], "text": "2"}]))[0] \
        .startswith("edit 'split_step' is not allowed for the cause capability")
    key = parse_fix(edit("grant_tool", role="Cost Analyst", tool="calc")).edit.key()
    assert p(edit("grant_tool", reason="other words", role="Cost Analyst", tool="calc"), tried=[key]) == \
        ["this edit was already tried in this task"]
    helper = edit("add_helper_role", role={"name": "Mailer", "tools": ["send_mail"], "goal": "g"})
    assert any(x.startswith("V1: tool 'send_mail'") for x in p(helper))


# ---- each edit on a live run ---------------------------------------------------------------------------------------
def test_grant_tool_after_the_pool_rung_was_skipped(task, envelope, trace, tools, tmp_path):
    def script(messages, seed):
        n = step_no(messages)
        if n == "1" and "echo" not in messages[0]["content"] + messages[-1]["content"]:
            return reply("Final Output", BLOCK)
        return good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, [edit("grant_tool", role="Cost Analyst", tool="echo")],
                       tmp_path)
    [f] = ep.adaptation["fixes"]
    assert (f["kind"], f["rung"], f["result"]) == ("grant_tool", "D", "recovered") and ep.error is None
    assert ep.adaptation["skipped"] == [{"step": 1, "why": POOL_OFF}]           # the code rung came first
    [prompt] = proposer_prompts(llm)
    for part in ("# Task", "done_when: every cell sourced", "Cause: capability", "lacked: currency_api",
                 "tools: calc, echo", "- grant_tool: params", "- work_around: params", "None yet."):
        assert part in prompt
    assert "- add_dependency" not in prompt                                    # code fixes are not offered
    rows = [json.loads(l)["event"] for l in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert rows == ["stuck", "fix_skipped", "fix"]
    assert "## Step 1 — cause capability" in (tmp_path / "adapt_report.md").read_text()


def test_one_retry_shows_the_refusal_then_a_valid_edit_is_applied(task, envelope, trace, tools):
    def script(messages, seed):
        n = step_no(messages)
        return reply("Final Output", BLOCK) if n == "1" and "echo" not in messages[0]["content"] + \
            messages[-1]["content"] else good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script,
                       [edit("grant_tool", role="Cost Analyst", tool="fx_live"),
                        edit("grant_tool", role="Cost Analyst", tool="echo")])
    first, second = proposer_prompts(llm)
    assert "refused by plain code" in second and "V1: tool 'fx_live' is not available in this run" in second
    [f] = ep.adaptation["fixes"]
    assert f["result"] == "recovered" and [r["problems"] != [] for r in f["proposer"]] == [True, False]


def test_two_invalid_replies_mean_no_fix_and_the_task_stops(task, envelope, trace, tools, tmp_path):
    def script(messages, seed):
        return reply("Final Output", BLOCK) if step_no(messages) == "1" else good(step_no(messages))
    llm, cfg, ep = run(task, envelope, trace, tools, script, ["no edit", edit("split_step", steps=[
        {"roles": ["Nobody"], "text": "a"}, {"roles": ["Nobody"], "text": "b"}])], tmp_path)
    [f] = ep.adaptation["fixes"]
    assert f["kind"] == "fix_proposer" and f["result"].startswith("failed: fix proposer: no valid edit in two replies")
    assert ep.error.startswith("stuck: step 1 (capability)") and ep.answer.startswith("# The task stopped")
    assert "fix_proposer (rung D" in (tmp_path / "adapt_report.md").read_text()


def test_add_role_rule_reaches_the_card(task, envelope, trace, tools):
    rule = "Always give the cost as a markdown table."

    def script(messages, seed):
        n = step_no(messages)
        if n == "1" and not seen(messages, rule):
            return reply("Final Output", "OUT-1 only words, no table")         # checks fail, even after retries
        return good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, [edit("add_role_rule", role="Cost Analyst", text=rule)])
    kinds = [(f["kind"], f["rung"], f["result"]) for f in ep.adaptation["fixes"]]
    assert kinds[0][:2] == ("set_run_option:check_retry_turns", 1)              # the code fix first
    assert kinds[-1] == ("add_role_rule", "D", "recovered")


def test_add_helper_role_leads_the_stuck_step(task, envelope, trace, tools):
    card = {"name": "Rate Finder", "description": "Finds published exchange rates.", "goal": "a dated rate",
            "tools": ["calc"], "outputs": [{"artifact": "rate", "format": "markdown"}],
            "success_criteria": ["the rate has a date"], "prompt": "You are a rate finder."}

    def script(messages, seed):
        n = step_no(messages)
        return reply("Final Output", BLOCK) if n == "1" and not seen(messages, "Rate Finder") else good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, [edit("add_helper_role", role=card, lead=True)])
    [f] = ep.adaptation["fixes"]
    assert (f["kind"], f["helper"], f["result"]) == ("add_helper_role", "Rate Finder", "recovered")


def test_a_helper_role_over_the_team_size_is_refused(task, envelope, trace, tools, monkeypatch):
    card = {"name": "Extra", "goal": "g", "outputs": ["x"], "success_criteria": ["y"], "prompt": "p", "tools": []}

    def script(messages, seed):
        return reply("Final Output", BLOCK) if step_no(messages) == "1" else good(step_no(messages))
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script,
                         fix_proposer=[edit("add_helper_role", role=card)] * 2)
    ep = Interpreter(llm, tools, trace, plan_options=ON, max_agents=3).run(cfg, task, seed=0)
    [f] = ep.adaptation["fixes"]
    assert "V5: the team would have 4 roles (at most 3)" in f["result"]


def test_split_step_replaces_the_stuck_step_with_a_chain_and_later_steps_wait_for_its_end(task, envelope, trace,
                                                                                          tools, tmp_path):
    def script(messages, seed):
        n = step_no(messages)
        user = messages[-1]["content"]
        if n == "1" and "Price storage only" not in user:
            return reply("Final Output", BLOCK)
        return good(n)
    subs = [{"roles": ["Cost Analyst"], "text": "Price storage only", "do": "list prices from the task",
             "output": "storage table", "done_when": "both databases priced"},
            {"roles": ["Cost Analyst"], "text": "Price compute", "do": "peak compute from the task",
             "output": "compute table", "done_when": "both databases priced"}]
    llm, cfg, ep = run(task, envelope, trace, tools, script, [edit("split_step", steps=subs)], tmp_path)
    [f] = ep.adaptation["fixes"]
    assert (f["kind"], f["replaced_by"], f["result"]) == ("split_step", [1, 5], "recovered")
    plan = {s.index + 1: s for s in cfg.plan} if False else None
    ran = [step_no(c["messages"]) for c in llm.calls_of("plan_worker")]
    assert "5" in ran and ran.index("5") < ran.index("2") and ran.index("5") < ran.index("3")
    assert (tmp_path / "artifacts" / "step_1.try1.json").exists() and ep.error is None
    assert json.loads((tmp_path / "plan.v2.json").read_text())["diff"]["split_of"] == 1


REPLAN = """1. [Cost Analyst]: Price both databases from the list prices in the task
   covers: R1, R2
   depends_on: none
   do: use the prices stated in the task; no live rates
   output: cost table (markdown)
   done_when: every cell sourced
4. [Memo Writer]: Assemble the memo
   covers: R3, R4
   depends_on: 1
   do: assemble outputs into the memo with the risk table
   output: memo (markdown)
   done_when: every requirement id answered"""


def test_replan_remaining_replaces_the_part_not_done(task, envelope, trace, tools):
    def script(messages, seed):
        n = step_no(messages)
        if n == "1" and "list prices in the task" not in messages[-1]["content"]:
            return reply("Final Output", BLOCK)
        return good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, [edit("replan_remaining", plan=REPLAN)])
    [f] = ep.adaptation["fixes"]
    assert (f["kind"], f["replaced_by"], f["dropped"]) == ("replan_remaining", [1, 4], [2, 3])
    assert f["result"] == "recovered" and len(cfg.plan) == 2 and ep.error is None


def test_a_replan_that_touches_a_done_step_is_refused(task, envelope, trace, tools):
    def script(messages, seed):
        n = step_no(messages)
        if n == "2" and "test report from a published benchmark" not in messages[-1]["content"]:
            return reply("Final Output", f"OUT-2\n{BODY}\nBLOCKED: database_sandbox — none")
        return good(n)
    bad = REPLAN                                                              # 1 is done: rewriting it is refused
    llm, cfg, ep = run(task, envelope, trace, tools, script, [edit("replan_remaining", plan=bad)] * 2)
    [f] = ep.adaptation["fixes"]
    assert "step 1 has already run; finished steps cannot change" in f["result"]


def test_work_around_finishes_without_the_capability_and_the_answer_says_so(task, envelope, trace, tools):
    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and "work-around" not in user:
            return reply("Final Output", BLOCK)
        return good(n)
    wa = edit("work_around", capability="currency_api", method="price in USD from the task's list prices",
              done_when="every cell sourced, in USD", limitation="Costs are in USD only; no INR conversion was made.")
    llm, cfg, ep = run(task, envelope, trace, tools, script, [wa])
    [f] = ep.adaptation["fixes"]
    assert (f["kind"], f["result"]) == ("work_around", "recovered") and cfg.plan[0].done_when.endswith("in USD")
    assert "- WORKED AROUND: step 1 had no currency_api" in ep.answer and "no INR conversion" in ep.answer
    assert ep.adaptation["workarounds"][0]["capability"] == "currency_api"


# ---- limits and the report -----------------------------------------------------------------------------------------
def test_the_per_step_limit_counts_the_proposer(task, envelope, trace, tools, monkeypatch):
    monkeypatch.setattr(pr, "fix_limits", lambda: {**limits(), "max_fixes_per_step": 1})

    def script(messages, seed):
        return reply("Final Output", BLOCK) if step_no(messages) == "1" else good(step_no(messages))
    llm, cfg, ep = run(task, envelope, trace, tools, script,
                       [edit("grant_tool", role="Cost Analyst", tool="echo"),
                        edit("work_around", capability="currency_api", method="m", done_when="", limitation="l")])
    assert len(ep.adaptation["fixes"]) == 1 and len(llm.calls_of("fix_proposer")) == 1
    assert ep.adaptation["stopped"]["why"] == "limit: 1 fixes per step"


def test_the_token_cap_applies_to_the_proposer(task, envelope, trace, tools, monkeypatch):
    monkeypatch.setattr(pr, "fix_limits", lambda: {**limits(), "max_tokens_per_task": 0})

    def script(messages, seed):
        return reply("Final Output", BLOCK) if step_no(messages) == "1" else good(step_no(messages))
    llm, cfg, ep = run(task, envelope, trace, tools, script, ["unused"])
    assert llm.calls_of("fix_proposer") == [] and ep.adaptation["stopped"]["why"].startswith("limit: adaptation tokens")


def test_steps_on_an_old_upstream_output_are_listed_in_the_answer_and_the_report(task, envelope, trace, tools,
                                                                               tmp_path):
    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and "lacked data it should have got" in user:
            return reply("Final Output", f"OUT-1\n{BODY}\n## Risk register\n| risk | owner |\n|---|---|\n| lock-in | ops |")
        if n == "3" and not trace.events("fix_try"):
            return reply("Final Output", f"OUT-3\n{BODY}\nBLOCKED: Step 1 risk register — not in its output")
        return good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, ["unused"], tmp_path)
    assert ep.adaptation["left_on_old_output"] == [{"step": 2, "upstream": 1}]
    assert "- OLD INPUT: step 2 used step 1's output from before step 1 was re-run" in ep.answer
    assert "- step 2 used step 1's earlier output (not redone)" in (tmp_path / "adapt_report.md").read_text()
