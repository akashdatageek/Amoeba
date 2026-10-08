"""D117 Stage C — code fixes for a stuck step, cheapest first (no AI): missing input (add the dependency / pass the
artifact; re-run the upstream step once), more turns, more retry turns, attach the missing tool from the pool
shortlist; limits; never a repeated fix; the stop report. Offline, with the mock LLM."""
import json

import pytest

import amoeba.interp.plan_runner as pr
from amoeba.adapt.evidence import verify
from amoeba.adapt.fixes import POOL_OFF, candidates, fix_key, holds, limits
from amoeba.adapt.stuck import classify_lacked, diagnose, step_signals
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from amoeba.pool.stock import stock_toolbox
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from amoeba.task.models import run_status
from amoeba.tools.registry import default_registry
from tests.conftest import fx, mock
from tests.test_plan_runner import BODY, step_no, plan_team
from tests.test_pool import CAP, SEARCH, cache, req, setup  # noqa: F401  (cache is a fixture)

ON = PlanOptions(adapt="on")


@pytest.fixture
def stop_on(monkeypatch):
    """The stop rule on, whatever adapt.yaml says (it is off until Stage D, by the user's decision)."""
    monkeypatch.setattr(pr, "fix_limits", lambda: {**limits(), "stop_when_exhausted": True})


def reply(action: str, text: str) -> str:
    return f"## Thought\nok\n\n## CurrentStep\nnow\n\n## Action\n{action}\n\n## ActionInput\n{text}"


def good(n):
    return reply("Final Output", f"OUT-{n}\n{BODY}")


NO_EDIT = "I cannot see a fix."          # a reply with no JSON edit: the proposer gives no fix (twice: no fix)


def run(task, envelope, trace, tools, script, tmp_path=None, stock=None, setup_cfg=None, proposer=(NO_EDIT,)):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script, fix_proposer=list(proposer))
    if setup_cfg:
        setup_cfg(cfg)
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path, plan_options=ON, stock=stock).run(cfg, task, seed=0)
    return llm, cfg, ep


def fixed(trace) -> bool:
    return bool(trace.events("fix_try"))


# ---- the parts ------------------------------------------------------------------------------------------------------
def test_a_lacked_item_is_a_missing_input_or_a_capability():
    plan = {1: {"output": "framework data table (name, stars)", "roles": ["Scout"]},
            2: {"output": "chart", "roles": ["Analyst"]}, 3: {"output": "memo", "roles": ["Writer"]}}
    kind = lambda x, deps=(2,): classify_lacked(x, 3, plan, list(deps))
    assert kind("github_api_tool")["kind"] == "capability" and kind("network access")["kind"] == "capability"
    assert kind("Step 1 Data") == {"item": "Step 1 Data", "kind": "missing_input", "upstream": [1]}
    assert kind("Framework Data Table")["upstream"] == [1]                       # the earlier step's planned output
    assert kind("Input from Scout")["upstream"] == [1]                           # another step's role
    assert kind("Files (.xlsx) — not provided by previous steps (Step 2 failed)")["upstream"] == [2]
    m = {"step": 3, "status": "partial", "roles": ["Writer"], "depends_on": [2], "checks": [],
         "blocked": ["Step 1 Data", "pdf_reader"]}
    d = diagnose(step_signals(m, plan=plan))
    assert d["cause"] == "missing_input" and d["upstream"] == [1] and "capability_unfilled" in d["signals"]
    assert d["allowed_edits"][:3] == ["add_dependency", "rerun_upstream", "set_run_option:max_input_chars"]


def test_the_candidates_cheapest_first():
    d = {"cause": "missing_input", "upstream": [1], "missing": ["Framework Data Table"],
         "allowed_edits": ["add_dependency", "rerun_upstream"]}
    ctx = {"deps": [2], "steps": {1: {"status": "done", "text": "| framework | stars |\n|---|---|\n| a | 3 |"}}}
    assert holds("Framework Data Table", ctx["steps"][1]["text"]) is False      # "data" is generic; "table" is not
    ctx["steps"][1]["text"] += "\nFramework data table above."
    [a], _ = candidates(d, 3, ctx)
    assert (a["kind"], a["params"]) == ("add_dependency", {"from": 1, "mode": "added"})
    [b], _ = candidates({**d, "missing": ["risk register"]}, 3, ctx)
    assert (b["kind"], b["target"], b["params"]["then"]) == ("rerun_upstream", 1, 3)
    assert candidates({**d, "missing": ["risk register"]}, 3, {**ctx, "upstream_rerun": {1}})[0] == []   # once
    opts = {"max_turns": 5, "check_retry_turns": 2, "max_input_chars": 6000}
    [t], _ = candidates({"cause": "max_turns", "allowed_edits": ["set_run_option:max_turns"]}, 2, {"opts": opts})
    assert t["params"] == {"max_turns": 8} and t["rung"] == 1                   # 5 + 3, the range's maximum
    chk = {"cause": "checks", "allowed_edits": ["set_run_option:check_retry_turns", "set_run_option:max_input_chars"]}
    assert [f["params"] for f in candidates(chk, 2, {"opts": opts, "capped": True})[0]] == \
        [{"check_retry_turns": 3}, {"max_input_chars": 12000}]
    cap = {"cause": "capability", "lacked": ["fx_api"], "allowed_edits": ["grant_tool"]}
    assert candidates(cap, 2, {"stock": False}) == ([], [POOL_OFF])
    [g], _ = candidates(cap, 2, {"stock": True, "attached": ["io.x/a"]})
    assert g["params"] == {"items": ["fx_api"], "exclude": ["io.x/a"]} and g["rung"] == 2
    assert candidates({"cause": "claimed_file_missing", "allowed_edits": []}, 2, {})[0] == []
    assert fix_key(t) == fix_key(dict(t)) and limits()["max_fixes_per_step"] == 3


def test_the_stop_rule_is_on_again_with_stage_d():
    assert limits()["stop_when_exhausted"] is True


def test_stuck_is_a_run_status():
    assert run_status("stuck: step 1 (capability) — capability fix unavailable: pool off") == "stuck"


# ---- rung 1 ---------------------------------------------------------------------------------------------------------
def test_more_turns_recovers_a_step_that_ran_out_of_turns(task, envelope, trace, tools, tmp_path):
    def script(messages, seed):
        n = step_no(messages)
        return good(n) if n != "1" or fixed(trace) else reply("calc", "1 + 1")
    llm, cfg, ep = run(task, envelope, trace, tools, script, tmp_path)
    [f] = ep.adaptation["fixes"]
    assert (f["cause"], f["kind"], f["params"], f["result"]) == ("max_turns", "set_run_option:max_turns",
                                                                 {"max_turns": 8}, "recovered")
    assert ep.adaptation["recovered_steps"] == [1] and ep.error is None and f["tokens"] > 0
    assert (tmp_path / "artifacts" / "step_1.try1.json").exists()                 # the attempt it replaced
    assert json.loads((tmp_path / "artifacts" / "step_1.json").read_text())["fix_of"]["kind"] == \
        "set_run_option:max_turns"
    assert [r["event"] for r in map(json.loads, (tmp_path / "events.jsonl").read_text().splitlines())] == \
        ["stuck", "fix"] and verify(tmp_path)["ok"]


def test_more_retry_turns_for_checks_that_still_fail(task, envelope, trace, tools):
    def script(messages, seed):
        n = step_no(messages)
        return good(n) if n != "1" or fixed(trace) else reply("Final Output", "OUT-1 only words, no table")
    llm, cfg, ep = run(task, envelope, trace, tools, script)
    [f] = ep.adaptation["fixes"]
    assert (f["cause"], f["kind"], f["result"]) == ("checks", "set_run_option:check_retry_turns", "recovered")
    retry = [e for e in trace.events("refine") if e["amoeba.step"] == 1]
    assert retry and ep.error is None


# ---- missing input --------------------------------------------------------------------------------------------------
def test_a_done_upstream_step_that_was_not_passed_is_added_and_only_the_stuck_step_reruns(task, envelope, trace,
                                                                                        tools):
    def script(messages, seed):
        n = step_no(messages)
        if n == "3" and not fixed(trace):
            return reply("Final Output", f"OUT-3\n{BODY}\nBLOCKED: Step 2 Data — the test report was not given")
        return good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script)
    [f] = ep.adaptation["fixes"]
    assert (f["cause"], f["kind"], f["params"], f["result"]) == ("missing_input", "add_dependency",
                                                                 {"from": 2, "mode": "added"}, "recovered")
    assert cfg.plan[2].depends_on == [1, 2]
    again = [c["messages"][-1]["content"] for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "3"][-1]
    assert "## Step 2 (" in again and "lacked an input: Step 2 Data" in again
    ran = [step_no(c["messages"]) for c in llm.calls_of("plan_worker")]
    assert ran.count("1") == 1 and ran.count("2") == 1                            # nothing done is redone


def test_an_upstream_output_without_the_data_is_rerun_once_with_it_in_done_when(task, envelope, trace, tools,
                                                                              tmp_path):
    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and "lacked data it should have got" in user:
            return reply("Final Output", f"OUT-1\n{BODY}\n## Risk register\n| risk | owner |\n|---|---|\n| lock-in | ops |")
        if n == "3" and not fixed(trace):
            return reply("Final Output", f"OUT-3\n{BODY}\nBLOCKED: Step 1 risk register — not in its output")
        return good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, tmp_path)
    [f] = ep.adaptation["fixes"]
    assert (f["kind"], f["target"], f["result"], f["upstream_status"]) == ("rerun_upstream", 1, "recovered", "done")
    assert "it must include: Step 1 risk register" in cfg.plan[0].done_when
    assert f["left_on_old_output"] == [2]                     # step 2 used the old output and is not redone
    assert (tmp_path / "artifacts" / "step_1.try1.json").exists()
    ran = [step_no(c["messages"]) for c in llm.calls_of("plan_worker")]
    assert ran.count("2") == 1 and ran.count("1") == 2


# ---- rung 2 ---------------------------------------------------------------------------------------------------------
def fake_stock(calls, attach=True):
    def stock(reqs, cfg, reg, **kw):
        calls.append({"names": [q.name for q in reqs], **kw})
        attached = []
        if attach:
            reg = reg.copy()
            reg.register("pool:fx", "pool tool fx", lambda text: "[S1] pool:fx · rate:\n95.82")
            for a in cfg.agents.values():
                if a.name == reqs[0].for_role:
                    a.tools.append("pool:fx")
            attached = [{"id": "io.example/fx", "kind": "tool", "as": "pool:fx"}]
        for q in reqs:
            q.status = "filled" if attach else "unfilled"
        return reg, {"attached": attached}
    return stock


def test_the_missing_tool_is_attached_from_the_shortlist_by_plain_code(task, envelope, trace, tools):
    calls = []

    def script(messages, seed):
        n = step_no(messages)
        if n == "1" and not fixed(trace):
            return reply("Final Output", f"OUT-1\n{BODY}\nBLOCKED: currency_api — no exchange rate")
        return good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, stock=fake_stock(calls))
    [f] = ep.adaptation["fixes"]
    assert (f["kind"], f["rung"], f["attached"], f["result"]) == ("grant_tool", 2, ["pool:fx"], "recovered")
    assert calls == [{"names": ["currency_api"], "code_pick": True, "exclude": set()}]
    again = [c["messages"] for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "1"][-1]
    assert any("pool:fx" in m["content"] for m in again) and ep.error is None


def test_a_registry_tool_is_granted_without_the_pool_step(task, envelope, trace, tools):
    calls = []

    def script(messages, seed):
        n = step_no(messages)
        if n == "1" and not fixed(trace):
            return reply("Final Output", f"OUT-1\n{BODY}\nBLOCKED: calc — nothing to compute with")
        return good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, stock=fake_stock(calls))
    assert ep.adaptation["fixes"][0]["attached"] == ["calc"] and calls == []


def test_an_empty_shortlist_is_one_failed_fix_never_repeated_then_the_task_stops(task, envelope, trace, tools,
                                                                                tmp_path, stop_on):
    calls = []

    def script(messages, seed):
        n = step_no(messages)
        return reply("Final Output", f"OUT-1\n{BODY}\nBLOCKED: currency_api — none") if n == "1" else good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, tmp_path, stock=fake_stock(calls, attach=False))
    f, d = ep.adaptation["fixes"]
    assert f["result"].startswith("failed: the pool shortlist had nothing") and len(calls) == 1
    assert d["kind"] == "fix_proposer" and d["result"].startswith("failed: fix proposer: no valid edit in two replies")
    assert ep.error.startswith("stuck: step 1 (capability)") and run_status(ep.error) == "stuck"
    report = (tmp_path / "adapt_report.md").read_text()
    assert "**Cause:** capability" in report and "grant_tool" in report and "failed: the pool shortlist" in report


# ---- pool off, limits, stop -----------------------------------------------------------------------------------------
def test_with_the_pool_off_the_capability_rung_is_skipped_and_the_task_stops_with_a_report(task, envelope, trace,
                                                                                          tools, tmp_path, stop_on):
    def script(messages, seed):
        n = step_no(messages)
        return reply("Final Output", f"OUT-1\n{BODY}\nBLOCKED: currency_api — none") if n == "1" else good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, tmp_path)
    [d] = ep.adaptation["fixes"]                       # the code rung is skipped; the proposer gives no fix
    assert d["rung"] == "D" and len(llm.calls_of("fix_proposer")) == 2          # one retry on an invalid reply
    assert ep.adaptation["skipped"] == [{"step": 1, "why": POOL_OFF}]
    assert ep.error.startswith(f"stuck: step 1 (capability) — {POOL_OFF}; fix proposer: no valid edit")
    assert ep.answer.startswith("# The task stopped: a step stayed stuck") and POOL_OFF in ep.answer
    assert {step_no(c["messages"]) for c in llm.calls_of("plan_worker")} == {"1"}    # nothing after it ran
    assert (tmp_path / "adapt_report.md").read_text() == ep.answer
    assert [e["amoeba.why"] for e in trace.events("fix_skipped")] == [POOL_OFF]


def test_the_token_cap_stops_further_fixes(task, envelope, trace, tools, monkeypatch):
    monkeypatch.setattr(pr, "fix_limits", lambda: {**limits(), "max_tokens_per_task": 1})

    def script(messages, seed):
        n = step_no(messages)
        return good(n) if n != "1" else reply("calc", "1 + 1")              # never finishes
    llm, cfg, ep = run(task, envelope, trace, tools, script)
    assert len(ep.adaptation["fixes"]) == 1 and ep.adaptation["stopped"]["why"].startswith("limit: adaptation tokens")


def test_the_per_task_cap(task, envelope, trace, tools, monkeypatch):
    monkeypatch.setattr(pr, "fix_limits", lambda: {**limits(), "max_fixes_per_task": 0})

    def script(messages, seed):
        n = step_no(messages)
        return good(n) if n != "1" else reply("calc", "1 + 1")
    llm, cfg, ep = run(task, envelope, trace, tools, script)
    assert ep.adaptation["fixes"] == [] and ep.adaptation["stopped"]["why"] == "limit: 0 fixes per task"


def test_with_stop_off_the_task_goes_on(task, envelope, trace, tools, monkeypatch):
    monkeypatch.setattr(pr, "fix_limits", lambda: {**limits(), "stop_when_exhausted": False})

    def script(messages, seed):
        n = step_no(messages)
        return reply("Final Output", f"OUT-1\n{BODY}\nBLOCKED: currency_api — none") if n == "1" else good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script)
    assert {step_no(c["messages"]) for c in llm.calls_of("plan_worker")} >= {"1", "2", "3"}
    assert ep.adaptation["stopped"]["step"] == 1 and not ep.answer.startswith("# The task stopped")


# ---- the toolbox picks by code -------------------------------------------------------------------------------------
def test_the_toolbox_takes_the_first_vetted_candidate_not_given_before(cache, task, envelope, trace):  # noqa: F811
    llm = mock(planner=[fx(CAP)])                                              # no pool_picker reply: no AI pick
    cfg = instantiate(draft_team(task, llm, envelope, trace), "flat", task, envelope)
    q = req("web_search", what="search the web")
    stock_toolbox([q], cfg, default_registry(), llm, trace, setup(cache), code_pick=True)
    assert (q.status, q.pool_id) == ("filled", SEARCH) and llm.calls_of("pool_picker") == []
    q2 = req("web_search", what="search the web")
    stock_toolbox([q2], cfg, default_registry(), llm, trace, setup(cache), code_pick=True, exclude={SEARCH})
    assert q2.pool_id != SEARCH and trace.events("pool_pick_code")[-1]["amoeba.excluded"] == [SEARCH]
