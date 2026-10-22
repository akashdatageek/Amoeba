"""D168 — "helped" is measured against a control. A scoped round adds a control probe: the same snapshot, no edit, the
step re-run once, measured and undone. An edit helped only when it did better than the control (it ends done and the
control did not, or it cleared a signal the control did not clear and added none the control did not add); as well
as the control is no_effect; with no control the verdict is `uncontrolled`, which promotion ignores. The control is
never picked and counts as a probe for the allowance. adapt.yaml probe.control: auto | always | sampled | off.
Offline (MockLLMClient)."""
import pytest

import amoeba.adapt.probe as probe_mod
from amoeba.adapt.lessons import LessonLibrary, round_verdicts
from amoeba.adapt.rounds import read_rounds
from amoeba.interp.plan_runner import PlanOptions, PlanRunner
from amoeba.interp.runtime import Interpreter
from scripts import promote as P
from tests.test_lessons_d163 import p, row
from tests.test_plan_runner import plan_team, step_no
from tests.test_proposer_d117 import good, reply
from tests.test_scoped_proposers_d154 import edit

RULE_A = edit("add_role_rule", role="Cost Analyst", text="RULE-A: finish with your output.")
RULE_B = edit("add_role_rule", role="Cost Analyst", text="RULE-B: finish with your output.")


def clears_on_rerun(edits_break=False):
    """Step 1 lacks an item on its first attempt only; any later attempt finishes (a plain re-run clears it). With
    edits_break, an attempt whose prompt holds a rule still lacks it and lacks a second item."""
    state = {"starts": 0}

    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n != "1":
            return good(n)
        if "BLOCKED: alpha" not in user:                # the first turn of an attempt (a retry turn sees its reply)
            state["starts"] += 1
        if edits_break and "RULE-" in user:
            return reply("Final Output", "OUT-1\nBLOCKED: alpha — not found\nBLOCKED: gamma — not found")
        if state["starts"] == 1:
            return reply("Final Output", "OUT-1\nBLOCKED: alpha — not found")
        return good(n)
    return script


@pytest.fixture
def one_edit(monkeypatch):
    """No code fix and only the proposers' add_role_rule, and each BLOCKED item is one stuck signal (as in D165's test)."""
    import amoeba.interp.plan_runner as runner_mod
    monkeypatch.setattr(runner_mod, "all_candidates", lambda d, n, ctx, config=None: ([], []))   # no code fix
    monkeypatch.setattr(PlanRunner, "allowed_edits", lambda self, n, d, ops=(): ["add_role_rule"])
    monkeypatch.setattr(probe_mod, "signal_names", lambda meta: sorted((meta or {}).get("blocked") or []))


def run(task, envelope, trace, tools, tmp_path, worker, **opt):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=worker, fix_proposer_inv=[RULE_A],
                         fix_proposer_dom=[RULE_B], reflector=["NO_ENTRY"])
    for a in cfg.agents.values():
        a.missing_tools = []
    cfg.meta["capability_requests"] = []
    opts = PlanOptions(adapt="on", failed_step="run", proposer="scoped", contract="on", **opt)
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path, plan_options=opts).run(cfg, task, seed=0)
    return llm, ep, [r for r in read_rounds(tmp_path) if r["kind"] == "round"]


def test_a_step_that_clears_on_a_plain_rerun_gives_no_effect_for_both_edits(task, envelope, trace, tools, tmp_path,
                                                                             one_edit):
    llm, ep, [rnd, *_] = run(task, envelope, trace, tools, tmp_path, clears_on_rerun(), lessons_write="on",
                             lessons_dir=str(tmp_path / "lib"))
    assert rnd["control"]["status"] == "done" and rnd["control"]["op"] == "none"
    assert [p["status"] for p in rnd["probes"]] == ["done", "done"]
    assert {v["scope"]: v["verdict"] for v in round_verdicts(rnd)} == {"inv": "no_effect", "dom": "no_effect"}
    assert "step_1.probe-control.json" in {x.name for x in (tmp_path / "artifacts").iterdir()}
    assert LessonLibrary(tmp_path / "lib").lessons() == [] and not llm.calls_of("reflector")   # nothing helped


def test_the_control_is_undone_and_never_picked(task, envelope, trace, tools, tmp_path, one_edit):
    llm, ep, rounds = run(task, envelope, trace, tools, tmp_path, clears_on_rerun(edits_break=True),
                          lessons_write="on", lessons_dir=str(tmp_path / "lib"))
    first = rounds[0]
    assert first["control"]["status"] == "done" and all(p["status"] != "done" for p in first["probes"])
    assert first["pick"] is None and first["step_status"] != "done"           # the control's done state was undone
    assert {v["scope"]: v["verdict"] for v in round_verdicts(first)} == {"inv": "hurt", "dom": "hurt"}


def test_budgets_count_the_control(task, envelope, trace, tools, tmp_path, one_edit, monkeypatch):
    llm, ep, [rnd, *_] = run(task, envelope, trace, tools, tmp_path / "a", clears_on_rerun(), lessons_write="on",
                             lessons_dir=str(tmp_path / "lib"))
    [fix] = [f for f in ep.adaptation["fixes"] if f.get("round")][:1]
    assert rnd["control"]["tokens"] > 0
    assert fix["tokens"] >= rnd["control"]["tokens"] + sum(p["tokens"] for p in rnd["probes"])
    monkeypatch.setattr(probe_mod, "probe_room", lambda r, n, lim: 2)       # room for the two edits only
    llm, ep, [rnd, *_] = run(task, envelope, trace, tools, tmp_path / "b", clears_on_rerun(), lessons_write="on",
                             lessons_dir=str(tmp_path / "lib2"))
    assert rnd["control"] is None and "2 probes" in rnd["control_skipped"]
    assert {v["verdict"] for v in round_verdicts(rnd)} == {"uncontrolled"}


def test_the_setting_and_its_default(task, envelope, trace, tools, tmp_path, one_edit, monkeypatch):
    llm, ep, [rnd, *_] = run(task, envelope, trace, tools, tmp_path / "off", clears_on_rerun())   # writing off
    assert rnd["control"] is None and rnd["control_skipped"] == "probe.control auto: lesson writing is off"
    monkeypatch.setattr(probe_mod, "control_config", lambda: {"control": "off", "control_rate": 0.5})
    llm, ep, [rnd, *_] = run(task, envelope, trace, tools, tmp_path / "x", clears_on_rerun(), lessons_write="on",
                             lessons_dir=str(tmp_path / "lib"))
    assert rnd["control"] is None and rnd["control_skipped"] == "probe.control off"
    assert probe_mod.control_config()["control"] in ("auto", "off")
    rate = lambda r: probe_mod.control_wanted(type("R", (), {"opt": PlanOptions(lessons_write="on"),
                                                             "ep": type("E", (), {"seed": 0})(),
                                                             "task": type("T", (), {"id": "t"})()})(), 1, 1,
                                              {"control": "sampled", "control_rate": r})
    assert rate(1.0) is None and rate(0.0).startswith("probe.control sampled")


def test_the_controlled_verdict_rules_and_promotion_ignores_uncontrolled(tmp_path):
    c = lambda **kw: dict(p(**kw), scope="control", op="none")
    rv = lambda probe, ctl: round_verdicts(dict(row(probe), control=ctl))[0]["verdict"]
    assert rv(p("done"), c()) == "helped"                                  # done, the control not
    assert rv(p("done"), c(status="done")) == "no_effect"                  # the control did as well
    assert rv(p(cleared=["a", "b"]), c(cleared=["a"])) == "helped"         # cleared one the control did not
    assert rv(p(cleared=["a"]), c(cleared=["a"])) == "no_effect"
    assert rv(p(cleared=["a"], new=["z"]), c()) == "confounded"
    assert rv(p(new=["z"]), c()) == "hurt" and rv(p(new=["z"]), c(new=["z"])) == "no_effect"
    assert rv(p("done"), None) == "uncontrolled"
    lib = LessonLibrary(tmp_path)
    fam = None
    for k in range(4):
        [v] = round_verdicts(row(p("done"), task_id=f"t{k}", control=None))   # no control: uncontrolled
        fam = lib.record(v, "general", f"t{k}", f"r{k}")
        if k == 0:
            lid = lib.add_lesson(fam["id"], "cue", "add_role_rule (inv): a rule.", "low", "r0", first=v,
                                 task_id="t0")["id"]
        else:
            lib.record_use(lid, v, "general", f"t{k}", f"r{k}")
    lib.set_status(lid, "approved")
    les = lib.lesson(lid)
    assert les["counts"]["helped"] == 0 and les["uncontrolled"]["helped"] == 4
    assert fam["counts"]["helped"] == 4 and fam["uncontrolled"] == 4        # the family: every verdict (reports)
    assert P.candidates(lib) == []                                         # promotion ignores uncontrolled counts
