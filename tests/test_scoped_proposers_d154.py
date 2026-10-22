"""D154 — Box 4's scoped round: two scoped fix proposers, a probe of each edit from the same starting state, a
plain-code pick, full rollback of the loser, and the two new edits. Offline (MockLLMClient)."""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

import amoeba.adapt.probe as probe_mod
from amoeba.adapt.faults import Faults
from amoeba.adapt.probe import Snapshot, pick, round_flags, scopes_for
from amoeba.adapt.proposer import fix_problems, parse_fix
from amoeba.interp.plan_runner import PlanOptions, PlanRunner
from amoeba.interp.runtime import Interpreter
from tests.test_plan_runner import plan_team, step_no
from tests.test_proposer_d117 import good, reply

SCOPED = PlanOptions(adapt="on", failed_step="run", proposer="scoped")
QUOTE = "turns used"                       # always in the last attempt the proposer is shown


def edit(op, because=QUOTE, **params):
    return json.dumps({"edit": {"op": op, "params": params}, "reason": "it lets the step finish", "because": because})


def stall_until(word):
    """Step 1 calls calc forever (cause max_turns) until `word` is in its prompt; the others finish."""
    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and word not in user:
            return reply("calc", "1 + 1")
        return good(n)
    return script


def run(task, envelope, trace, tools, script, inv=None, dom=None, opts=SCOPED, tmp_path=None, **more):
    kw = {k: v for k, v in (("fix_proposer_inv", inv), ("fix_proposer_dom", dom)) if v is not None}
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script, **kw, **more)
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path, plan_options=opts).run(cfg, task, seed=0)
    return llm, cfg, ep


def rounds(ep):
    return [f for f in ep.adaptation["fixes"] if f.get("round")]


RULE_OK = edit("add_role_rule", role="Cost Analyst", text="FINISH NOW with your Final Output.")
RULE_NO = edit("add_role_rule", role="Cost Analyst", text="Price from the task's list prices.")


# ---- B1: two scoped proposers ---------------------------------------------------------------------------------------
def test_two_scoped_calls_with_their_own_prompts(task, envelope, trace, tools):
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("FINISH NOW"), [RULE_OK], [RULE_NO])
    inv, dom = llm.calls_of("fix_proposer_inv"), llm.calls_of("fix_proposer_dom")
    assert len(inv) == 1 and len(dom) == 1 and not llm.calls_of("fix_proposer")
    assert "SCOPE: HOW THE TEAM WORKS" in inv[0]["messages"][-1]["content"]
    assert "SCOPE: WHAT AN EXPERT WOULD KNOW" in dom[0]["messages"][-1]["content"]
    assert "add_watch_rule" in inv[0]["messages"][-1]["content"] and \
        "add_watch_rule" not in dom[0]["messages"][-1]["content"]


def test_a_scope_with_no_allowed_edit_makes_no_call(task, envelope, trace, tools, monkeypatch):
    assert scopes_for(["set_run_option:max_turns", "add_watch_rule"]) == {"inv": ["add_watch_rule"]}
    monkeypatch.setattr(PlanRunner, "allowed_edits", lambda self, n, d, ops=(): ["add_role_rule", "add_watch_rule"]
                        if "add_watch_rule" in ops else ["add_role_rule"])
    monkeypatch.setattr(probe_mod, "scopes_for", lambda allowed: {"inv": ["add_watch_rule"]})
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("WRAP"),
                       [edit("add_watch_rule", after_calls=5, unless="tool_called:echo", text="WRAP up now.")])
    assert llm.calls_of("fix_proposer_inv") and not llm.calls_of("fix_proposer_dom")


def test_an_unquoted_or_refused_candidate_leaves_one_probe(task, envelope, trace, tools):
    bad = edit("add_role_rule", because="words the proposer was never shown", role="Cost Analyst", text="x y z")
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("FINISH NOW"), [RULE_OK], [bad])
    [r] = rounds(ep)
    assert [p["scope"] for p in r["round"]["probes"]] == ["inv"]
    dom = next(c for c in r["round"]["candidates"] if c["scope"] == "dom")
    assert dom["op"] is None and any("because" in x for x in dom["refusals"])
    assert len(llm.calls_of("fix_proposer_dom")) == 2                    # the single retry, then no candidate


def test_an_edit_that_touches_a_check_is_refused():
    r = parse_fix(edit("add_role_rule", role="A", text="Remove the contract check on figures."), scoped=True)
    probs = fix_problems(r, "checks", ["add_role_rule"], {}, set(), ["A"])
    assert any(p.startswith("checks:") for p in probs)
    ok = parse_fix(edit("add_role_rule", role="A", text="Read the whole table before writing."), scoped=True)
    assert not fix_problems(ok, "checks", ["add_role_rule"], {}, set(), ["A"])


# ---- B2: probe, compare, pick ---------------------------------------------------------------------------------------
def test_the_done_candidate_wins_and_the_loser_is_undone(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("FINISH NOW"), [RULE_OK], [RULE_NO],
                       tmp_path=tmp_path)
    [r] = rounds(ep)
    rnd = r["round"]
    assert (r["kind"], r["result"], rnd["pick"]) == ("add_role_rule", "recovered", "inv")
    assert [p["samples"] for p in rnd["probes"]] == [1, 1] and all("tokens" in p for p in rnd["probes"])
    analyst = next(a for a in cfg.agents.values() if a.name == "Cost Analyst")
    assert "FINISH NOW with your Final Output." in analyst.constraints
    assert "Price from the task's list prices." not in analyst.constraints          # the loser is rolled back
    files = {p.name for p in (tmp_path / "artifacts").iterdir()}
    assert {"step_1.probe-inv.json", "step_1.probe-dom.json", "step_1.json"} <= files


def test_the_pick_rules():
    p = lambda scope, status, cleared=(), new=(), tokens=10, limited=False: {
        "scope": scope, "status": status, "cleared": list(cleared), "new": list(new), "tokens": tokens,
        "limited": limited, "op": "add_role_rule"}
    w, why, base = pick([p("inv", "done", new=["x"]), p("dom", "done", tokens=99)])
    assert w["scope"] == "dom" and "fewer new signals" in why                  # done, fewer new signals first
    w, why, base = pick([p("inv", "done", tokens=50), p("dom", "done", tokens=5)])
    assert w["scope"] == "dom"                                                 # then fewer tokens
    w, why, base = pick([p("inv", "partial", limited=True), p("dom", "partial", cleared=["a"])])
    assert w["scope"] == "inv" and "limitation" in why
    w, why, base = pick([p("inv", "partial", cleared=["a"], new=["b"]), p("dom", "partial", cleared=["a", "c"])])
    assert w is None and base["scope"] == "dom"                                # the best non-done becomes the base
    w, why, base = pick([p("inv", "partial"), p("dom", "partial", new=["z"])])
    assert w is None and base is None and "original state" in why


def test_complementary_and_shared_failure():
    p = lambda cleared, new: {"cleared": cleared, "new": new, "status": "partial", "limited": False}
    assert round_flags([p(["a"], []), p(["b"], [])]) == {"complementary": True}
    assert round_flags([p([], ["checks_after_retry"]), p([], ["checks_after_retry", "x"])]) == \
        {"shared_failure": "checks_after_retry"}


def test_a_non_done_base_is_kept_for_the_next_rung(task, envelope, trace, tools, monkeypatch):
    def fake_pick(probes):
        return None, "none recovered: base", probes[1]
    monkeypatch.setattr(probe_mod, "pick", fake_pick)
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("NEVER"), [RULE_OK], [RULE_NO])
    r = rounds(ep)[0]
    assert r["result"].startswith("failed") and r["round"]["base"] == "dom"
    analyst = next(a for a in cfg.agents.values() if a.name == "Cost Analyst")
    assert "Price from the task's list prices." in analyst.constraints          # the base's edit stays
    assert "FINISH NOW with your Final Output." not in analyst.constraints


def test_stop_on_first_done_both_settings(task, envelope, trace, tools, monkeypatch):
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("FINISH NOW"), [RULE_OK], [RULE_NO])
    assert len(rounds(ep)[0]["round"]["probes"]) == 2                         # default false: both run
    monkeypatch.setattr(probe_mod, "scope_config", lambda: {"scoped": True, "stop_on_first_done": True})
    from amoeba.interp.trace import TraceWriter
    llm, cfg, ep = run(task, envelope, TraceWriter(None, episode_id="s"), tools, stall_until("FINISH NOW"),
                       [RULE_OK], [RULE_NO])
    assert [p["scope"] for p in rounds(ep)[0]["round"]["probes"]] == ["inv"]


# ---- rollback, in full ------------------------------------------------------------------------------------------------
def fake_runner(task, envelope, trace, tmp_path):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=lambda m, s: "x")
    steps = {s.index + 1: s for s in cfg.plan}
    ws = tmp_path / "workspace"
    (ws / "sources").mkdir(parents=True)
    (ws / "data.csv").write_text("a,b\n")
    (ws / "sources" / "S1_page.txt").write_text("page")
    local = SimpleNamespace(workspace=ws, files={"data.csv": {"path": "data.csv", "step": 1}}, _seen={"data.csv": 1},
                            box=None, setup=SimpleNamespace(mode="inprocess"))
    art = tmp_path / "artifacts"
    art.mkdir()
    (art / "step_1.json").write_text('{"try": "stuck"}')
    return SimpleNamespace(agents=cfg.agents, cfg=cfg, steps=steps, artifacts={1: {"meta": {"status": "partial"}}},
                           step_opts={}, waived={}, provided={}, done_when_kept={}, tool_guidance={}, watch_rules={},
                           models_tried={}, attached_ids={}, proposer_gave_up={}, ledger={}, contract_results={},
                           helpers_added=0, fix_keys=set(), workarounds=[], faults=Faults(("tool_error:1:3",)),
                           dir=art, local=local)


def test_a_probe_is_undone_in_full(task, envelope, trace, tmp_path):
    r = fake_runner(task, envelope, trace, tmp_path)
    snap = Snapshot.take(r, 1)
    analyst = next(a for a in r.agents.values() if a.name == "Cost Analyst")
    before = (list(analyst.tools), list(analyst.missing_tools), list(analyst.constraints), list(r.steps[1].agent_ids))
    analyst.tools.append("echo")
    analyst.missing_tools.append("pdf_reader")
    analyst.constraints = [*analyst.constraints, "a probe rule"]
    helper = analyst.model_copy(update={"agent_id": "new-helper", "name": "Helper"})
    r.agents["new-helper"] = helper
    r.steps[1].agent_ids = [*r.steps[1].agent_ids, "new-helper"]
    r.steps[1].done_when = "narrower"
    r.step_opts[1] = {"max_turns": 9}
    r.tool_guidance[1] = {"calc": "digits only"}
    r.watch_rules[1] = [{"after_calls": 5, "unless": "file_written", "text": "write it"}]
    r.helpers_added, r.waived[1] = 1, {"currency_api"}
    r.faults.faults[0].fired = 3
    (r.local.workspace / "data.csv").write_text("changed")
    (r.local.workspace / "new.xlsx").write_bytes(b"x")
    (r.dir / "step_1.json").write_text('{"try": "probe"}')
    (r.local.workspace / "sources" / "S2_new.txt").write_text("fetched during the probe")
    snap.restore()
    assert (list(analyst.tools), list(analyst.missing_tools), list(analyst.constraints),
            list(r.steps[1].agent_ids)) == before
    assert "new-helper" not in r.agents and "new-helper" not in r.cfg.agents
    assert r.steps[1].done_when != "narrower" and r.step_opts == {} and r.tool_guidance == {} and r.watch_rules == {}
    assert (r.helpers_added, r.waived) == (0, {}) and r.faults.faults[0].fired == 0
    assert (r.local.workspace / "data.csv").read_text() == "a,b\n" and not (r.local.workspace / "new.xlsx").exists()
    assert json.loads((r.dir / "step_1.json").read_text()) == {"try": "stuck"}
    assert (r.local.workspace / "sources" / "S2_new.txt").exists()            # sources/ is read-only input: kept


def test_the_sandbox_falls_back_to_single_and_logs_why(task, envelope, trace, tools, monkeypatch):
    monkeypatch.setattr(probe_mod, "fallback_reason", lambda r: "the workspace of a probe cannot be undone")
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("FINISH NOW"),
                       fix_proposer=[json.dumps({"edit": {"op": "add_role_rule", "params": {
                           "role": "Cost Analyst", "text": "FINISH NOW please."}}, "reason": "r"})])
    assert trace.events("scoped_fallback") and llm.calls_of("fix_proposer")
    assert not llm.calls_of("fix_proposer_inv")


# ---- budget ---------------------------------------------------------------------------------------------------------
def test_a_round_is_one_try_with_tokens_per_probe(task, envelope, trace, tools):
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("FINISH NOW"), [RULE_OK], [RULE_NO])
    fixes = [f for f in ep.adaptation["fixes"] if f["rung"] == "D"]
    assert len(fixes) == 1 and len(fixes[0]["round"]["probes"]) == 2
    assert fixes[0]["tokens"] >= sum(p["tokens"] for p in fixes[0]["round"]["probes"]) > 0


@pytest.mark.parametrize("cause_word,expect", [("max_turns", "inv")])
def test_with_one_probe_left_the_scope_follows_the_cause(task, envelope, trace, tools, monkeypatch, cause_word,
                                                          expect):
    monkeypatch.setattr(probe_mod, "probes_affordable", lambda r, n, lim: 1)
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("FINISH NOW"), [RULE_OK], [RULE_NO])
    assert rounds(ep)[0]["round"]["scopes"] == [expect] and not llm.calls_of("fix_proposer_dom")


# ---- plan edits are not probed ---------------------------------------------------------------------------------------
def test_a_split_is_applied_only_after_the_other_probe_failed(task, envelope, trace, tools, tmp_path):
    subs = [{"roles": ["Cost Analyst"], "text": "Price storage only", "do": "list prices", "output": "storage table",
             "done_when": "priced"},
            {"roles": ["Cost Analyst"], "text": "Price compute", "do": "compute", "output": "compute table",
             "done_when": "priced"}]

    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and "Price storage only" not in user and "Price compute" not in user:
            return reply("calc", "1 + 1")
        return good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, [edit("split_step", steps=subs)], [RULE_NO],
                       tmp_path=tmp_path)
    r = rounds(ep)[0]
    assert [p["scope"] for p in r["round"]["probes"]] == ["dom"]               # the split was not probed
    assert r["kind"] == "split_step" and r["replaced_by"] == [1, 5] and "not probed" in r["round"]["pick_reason"]


# ---- B3: the two new edits -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("v2", [False, True])
def test_a_watch_rule_warns_once_and_is_rolled_back_when_it_loses(task, envelope, trace, tools, v2):
    opts = PlanOptions(adapt="on", failed_step="run", proposer="scoped", native_tools="on" if v2 else "off",
                       protocol="v2" if v2 else "legacy")
    watch = edit("add_watch_rule", after_calls=5, unless="tool_called:echo", text="WRAP-UP-NOTE stop calling calc.")
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("FINISH NOW"), [watch], [RULE_OK], opts=opts)
    r = rounds(ep)[0]
    assert r["round"]["pick"] == "dom"
    inv_turns = [c for c in llm.calls if c["kind"] == "plan_worker" and "WRAP-UP-NOTE" in json.dumps(c["messages"])]
    assert inv_turns                                                      # the note reached the helper in the probe
    assert len(trace.events("watch_rule")) == 1                           # once per attempt, and only in the probe
    later = [c for c in llm.calls if c["kind"] == "plan_worker" and step_no(c["messages"]) != "1"]
    assert later and not [c for c in later if "WRAP-UP-NOTE" in json.dumps(c["messages"])]


@pytest.mark.parametrize("v2", [False, True])
def test_tool_guidance_reaches_the_tool_section_and_is_rolled_back(task, envelope, trace, tools, v2, monkeypatch):
    monkeypatch.setattr(PlanRunner, "allowed_edits", lambda self, n, d, ops=(): ["add_role_rule", "add_tool_guidance"])
    monkeypatch.setattr(probe_mod, "scopes_for", lambda allowed: {"inv": ["add_tool_guidance"],
                                                                 "dom": ["add_role_rule"]})
    opts = PlanOptions(adapt="on", failed_step="run", proposer="scoped", native_tools="on" if v2 else "off",
                       protocol="v2" if v2 else "legacy")

    def script(messages, seed):                    # the same failing calc call twice: cause tool_error
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and "FINISH NOW" not in user:
            return reply("calc", "2x")
        return good(n)
    guide = edit("add_tool_guidance", tool="calc", text="GUIDE-LINE write plain digits.")
    llm, cfg, ep = run(task, envelope, trace, tools, script, [guide], [RULE_OK], opts=opts)
    r = rounds(ep)[0]
    assert r["round"]["pick"] == "dom"
    seen = [c for c in llm.calls if c["kind"] == "plan_worker" and "GUIDE-LINE" in json.dumps(
        [c["messages"], c.get("tools")])]
    assert seen                                                           # in the prompt (text) or the tool spec
    after = [c for c in llm.calls if c["kind"] == "plan_worker" and step_no(c["messages"]) == "2"]
    assert after and not [c for c in after if "GUIDE-LINE" in json.dumps([c["messages"], c.get("tools")])]


def test_a_tool_guidance_for_a_tool_the_step_does_not_hold_is_refused():
    r = parse_fix(edit("add_tool_guidance", tool="web_search", text="x"), scoped=True)
    assert any("not held" in p for p in fix_problems(r, "tool_error", ["add_tool_guidance"], {}, set(), ["A"],
                                                      held={"calc"}))


# ---- faults ---------------------------------------------------------------------------------------------------------
def test_both_probes_face_the_same_fault(task, envelope, trace, tools, tmp_path, monkeypatch):
    monkeypatch.setattr(PlanRunner, "allowed_edits", lambda self, n, d, ops=(): ["add_role_rule"])
    opts = PlanOptions(adapt="on", failed_step="run", proposer="scoped", faults=("tool_error:1:30",), contract="on")

    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and "FINISH NOW" not in user:
            return reply("calc", "1 + 1")
        if n == "1" and "calc said" not in json.dumps(messages):
            return reply("calc", "2 + 2")
        return good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, [RULE_OK], [RULE_OK.replace("FINISH NOW",
                                                                                      "FINISH NOW, really,")],
                       opts=opts, tmp_path=tmp_path)
    probes = [json.loads((tmp_path / "artifacts" / f"step_1.probe-{s}.json").read_text()) for s in ("inv", "dom")]
    injected = [sum("injected fault" in (c.get("result") or "") for c in p.get("meta", p)["tool_calls"])
                for p in probes]
    assert injected[0] == injected[1] > 0


# ---- B5: the ablation arm --------------------------------------------------------------------------------------------
def test_fix_pick_llm_records_the_pick_and_the_checks_verdict(task, envelope, trace, tools):
    opts = PlanOptions(adapt="on", failed_step="run", proposer="scoped", fix_pick="llm")
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("FINISH NOW"), [RULE_OK], [RULE_NO], opts=opts,
                       fix_picker=["PICK: B"])
    lp = rounds(ep)[0]["round"]["llm_pick"]
    assert lp == {"picked": "dom", "code_pick": "inv", "verdict": "incomplete"}
    assert len(llm.calls_of("fix_picker")) == 1


def test_the_round_is_logged_once_in_events_jsonl(task, envelope, trace, tools, tmp_path):
    run(task, envelope, trace, tools, stall_until("FINISH NOW"), [RULE_OK], [RULE_NO], tmp_path=tmp_path)
    rows = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]
    [row] = [x for x in rows if x.get("event") == "box4_round"]
    data = row["data"]
    assert data["pick"] == "inv" and {"scope", "op", "status", "tokens", "turns", "cleared", "new",
                                      "files_changed"} <= set(data["probes"][0])


# ---- the existing Box 4 tests in every mode ----------------------------------------------------------------------------
BOX4 = ["tests/test_diagnosis_d128.py", "tests/test_failed_step_d133.py", "tests/test_fixes_d117.py",
        "tests/test_ladder_d129.py", "tests/test_proposer_d117.py", "tests/test_stage_e_d117.py",
        "tests/test_stuck_d117.py", "tests/test_toolmaker_d125.py", "tests/test_workaround_d124.py",
        "tests/test_fix_tries_d150.py", "tests/test_faults_d119.py", "tests/test_budgets_d151.py",
        "tests/test_diagnosis_d149.py", "tests/test_checks_kept_d155.py"]
LEGACY_ONLY = ["tests/test_ladder_d145.py"]    # in v2 a blocked turn is retried compact inside the call (D139)


@pytest.mark.skipif(bool(os.environ.get("AMOEBA_TEST_PROTOCOL") or os.environ.get("AMOEBA_TEST_PROPOSER")),
                    reason="already inside a mode re-run")
@pytest.mark.parametrize("env,files", [({"AMOEBA_TEST_PROPOSER": "scoped"}, BOX4 + LEGACY_ONLY),
                                       ({"AMOEBA_TEST_PROTOCOL": "v2"}, BOX4),
                                       ({"AMOEBA_TEST_PROPOSER": "scoped", "AMOEBA_TEST_PROTOCOL": "v2"}, BOX4)])
def test_the_box4_tests_pass_in_every_mode(env, files):
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *files],
                         env={**os.environ, **env}, capture_output=True, text=True, timeout=900)
    assert out.returncode == 0, out.stdout[-3000:]


# ---- B5: the per-scope summary and the proposer arms ------------------------------------------------------------------
def test_stuck_report_has_a_per_scope_summary(task, envelope, trace, tools, tmp_path):
    from scripts.stuck_report import scope_summary
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("FINISH NOW"), [RULE_OK], [RULE_NO])
    run_dir = tmp_path / "set" / "run1"
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text(json.dumps({"adaptation": ep.adaptation}, default=str))
    sc = scope_summary([str(tmp_path)])
    assert sc["rounds"] == 1 and sc["fallbacks_to_single"] == 0
    assert sc["scopes"]["inv"] == {"candidates": 1, "probes": 1, "recoveries": 1, "signals_cleared": 1,
                                   "tokens": sc["scopes"]["inv"]["tokens"]} and sc["scopes"]["inv"]["tokens"] > 0
    assert sc["scopes"]["dom"]["probes"] == 1 and sc["scopes"]["dom"]["recoveries"] == 0


def test_stage_e_compares_the_two_proposers_on_one_draft(tmp_path):
    from scripts.stage_e import arm_command, arm_record
    t, runs, picks, first = tmp_path / "t.jsonl", tmp_path / "r", tmp_path / "p.json", tmp_path / "single_run"
    single = arm_command("single", t, 0, runs, picks, None, ["--local-tools-mode", "inprocess"])
    scoped = arm_command("scoped", t, 0, runs, picks, first, ["--local-tools-mode", "inprocess"])
    assert single[single.index("--adapt") + 1] == "on" and single[single.index("--proposer") + 1] == "single"
    assert "--drafts-from" not in single and scoped[scoped.index("--drafts-from") + 1] == str(first)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "result.json").write_text(json.dumps({"adaptation": {"scoped_fallbacks": [{"step": 1}]}}))
    assert arm_record(run_dir, ["--local-tools-mode", "inprocess"]) == {"local_tools_mode": "inprocess",
                                                                        "scoped_fallbacks": 1}


def test_the_summary_says_which_proposer_ran_and_counts_fallbacks(task, envelope, trace, tools):
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("FINISH NOW"), [RULE_OK], [RULE_NO])
    assert ep.adaptation["proposer"] == "scoped" and ep.adaptation["scoped_fallbacks"] == []


def test_a_sub_step_or_an_edit_that_carries_checks_is_refused():
    sub = {"roles": ["A"], "text": "t", "checks": [{"name": "output_present"}]}
    with pytest.raises(Exception):
        parse_fix(edit("split_step", steps=[sub, dict(sub)]), scoped=True)
    with pytest.raises(Exception):
        parse_fix(edit("add_role_rule", role="A", text="x", checks=[]), scoped=True)
