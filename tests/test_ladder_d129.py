"""D129 — Box 4's fix order and limits: a reworded grant is the same grant, a capability nothing can supply goes
straight to working without it, the code fixes of every named cause come before the proposer, a step made by a split
counts its own fixes, the fix allowance follows the run's cap, and the proposer's wording check reads phrases."""
import json
from types import SimpleNamespace

from amoeba.adapt.fixes import all_candidates, candidates, fix_key, limits, token_cap
from amoeba.adapt.proposer import fix_problems, parse_fix
from amoeba.adapt.stuck import diagnose, step_signals
from amoeba.interp.plan_runner import PlanRunner

OPTS = {"max_turns": 5, "check_retry_turns": 1, "max_input_chars": 6000}


def grant(items, exclude=()):
    return {"kind": "grant_tool", "rung": 2, "target": 5, "params": {"items": list(items), "exclude": list(exclude)}}


def test_a_reworded_grant_is_the_same_grant():
    assert fix_key(grant(["send_email"])) == fix_key(grant(["Send Email"])) == fix_key(grant(["send-email"]))
    assert fix_key(grant(["Bash"])) == fix_key(grant(["python_interpreter"]))      # both are code_execution
    assert fix_key(grant(["send_email"])) != fix_key(grant(["fetch_url"]))


def test_the_other_causes_code_fixes_come_before_the_proposer():
    meta = {"step": 1, "status": "partial", "roles": ["Researcher"], "finished": False, "turns": 5,
            "blocked": ["github_api_fetch"], "status_reason": "lacked: github_api_fetch; max_turns"}
    d = diagnose(step_signals(meta, plan={1: {"output": "repos", "roles": ["Researcher"]}}))
    assert d["cause"] == "capability" and d["causes"] == ["capability", "max_turns"]
    fixes, _ = all_candidates(d, 1, {"opts": OPTS, "stock": True})
    assert [f["kind"] for f in fixes] == ["grant_tool", "set_run_option:max_turns"]
    assert fixes[1]["for_cause"] == "max_turns"
    blocked = {**d, "cause": "provider_blocked", "causes": ["provider_blocked", "capability"],
               "allowed_edits": ["compact_prompt", "switch_model"]}
    assert [f["kind"] for f in all_candidates(blocked, 1, {"opts": OPTS, "stock": True})[0]] == \
        ["compact_prompt"]                                   # a blocked step gets only its own fixes (D145: no more turns)


def test_an_unfillable_capability_skips_the_grant():
    d = {"cause": "capability", "lacked": ["send_email"], "allowed_edits": ["grant_tool", "make_tool"]}
    fixes, notes = candidates(d, 5, {"opts": OPTS, "stock": True, "unfillable": ["send_email"]})
    assert fixes == [] and notes == ["capability unfillable in this run: send_email"]


def test_unfillable_means_the_pool_had_nothing_and_nothing_can_be_written():
    nothing = "failed: the pool shortlist had nothing to attach for send_email (no candidate passed the checks)"
    fake = SimpleNamespace(
        artifacts={5: {"meta": {"stuck": {"cause": "capability", "lacked": ["Send Email — no tool sends mail"]}}}},
        fixes=[{"step": 5, "kind": "grant_tool", "params": {"items": ["send_email"]}, "result": nothing}],
        fix_epoch={}, make_tool_ctx=lambda n: {"make_tool_why": "no offline library for send_email"})
    fake.step_fixes = lambda n: PlanRunner.step_fixes(fake, n)
    assert PlanRunner.unfillable(fake, 5) == ["Send Email"]
    fake.make_tool_ctx = lambda n: {"make_tool": {"ok": True}}            # the tool writer could still make it
    assert PlanRunner.unfillable(fake, 5) == []


def test_a_step_made_by_a_split_counts_its_own_fixes():
    fake = SimpleNamespace(fixes=[{"step": 3}, {"step": 3}, {"step": 3, "replaced_by": [3, 8]}, {"step": 3}],
                           fix_epoch={3: 3, 8: 3})
    assert len(PlanRunner.step_fixes(fake, 3)) == 1 and PlanRunner.step_fixes(fake, 8) == []
    assert limits()["max_fixes_per_substep"] == 2


def test_the_fix_allowance_follows_the_attempt_cost():
    lim = limits()                                                        # D151 replaced the run-cap share
    assert token_cap(lim, 0) == 0
    assert token_cap(lim, 70_000) == 70_000 * lim["fix_tokens_per_attempt"]
    assert token_cap(lim, 210_000) == 3 * token_cap(lim, 70_000)


def test_the_wording_check_reads_phrases_not_words():
    def wa(method):
        return parse_fix(json.dumps({"edit": {"op": "work_around", "params": {
            "capability": "github_api", "method": method, "done_when": "", "limitation": "Stars from the web."}},
            "reason": "no API tool"}))
    check = lambda m: fix_problems(wa(m), "capability", ["work_around"], {}, set(), ["Researcher"], {"grant_tool"})
    assert check("Use web search; skip the paged endpoint and read each repo page") == []
    assert any("wording" in x for x in check("Skip the checks and copy the numbers"))
    assert any("wording" in x for x in check("Answer without verifying anything"))
