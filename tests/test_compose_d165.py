"""D165 — compose: when the two probes of a scoped round were complementary (each cleared a different signal) and
neither recovered the step, a third probe applies both edits from the same starting state. Plain code keeps it when
it ends done, or when it clears more signals than either probe alone and adds none; otherwise today's pick stands.
Plan edits are never composed. Off by default (adapt.yaml compose.enabled). Offline (MockLLMClient)."""
import json

import pytest

import amoeba.adapt.probe as probe_mod
from amoeba.adapt.lessons import LessonLibrary, key_of
from amoeba.adapt.rounds import read_rounds
from amoeba.interp.plan_runner import PlanOptions, PlanRunner
from amoeba.interp.runtime import Interpreter
from tests.test_plan_runner import plan_team, step_no
from tests.test_proposer_d117 import good, reply
from tests.test_scoped_proposers_d154 import edit

RULE_A = edit("add_role_rule", role="Cost Analyst", text="RULE-A: find the first figure.")
RULE_B = edit("add_role_rule", role="Cost Analyst", text="RULE-B: find the second figure.")


def worker(messages, seed):
    """Step 1 lacks two things, one per rule; with both rules it finishes. The others finish at once."""
    n, text = step_no(messages), json.dumps(messages)
    if n != "1":
        return good(n)
    missing = [x for x, rule in (("alpha", "RULE-A"), ("beta", "RULE-B")) if rule not in text]
    if not missing:
        return good(n)
    return reply("Final Output", "OUT-1\n" + "\n".join(f"BLOCKED: {x} — not found" for x in missing))


@pytest.fixture
def two_signals(monkeypatch):
    """Each BLOCKED item is one stuck signal (the test reads the step's own blocked list as its signals)."""
    monkeypatch.setattr(PlanRunner, "allowed_edits", lambda self, n, d, ops=(): ["add_role_rule"])
    monkeypatch.setattr(probe_mod, "signal_names", lambda meta: sorted((meta or {}).get("blocked") or []))


def run(task, envelope, trace, tools, tmp_path, enabled=True, monkeypatch=None, **opt):
    if monkeypatch is not None:
        monkeypatch.setattr(probe_mod, "compose_config", lambda: {"enabled": enabled})
    llm, cfg = plan_team(task, envelope, trace, plan_worker=worker, fix_proposer_inv=[RULE_A],
                         fix_proposer_dom=[RULE_B])
    for a in cfg.agents.values():
        a.missing_tools = []
    cfg.meta["capability_requests"] = []
    opts = PlanOptions(adapt="on", failed_step="run", proposer="scoped", contract="on", **opt)
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path, plan_options=opts).run(cfg, task, seed=0)
    return llm, cfg, ep


def test_compose_is_off_by_default():
    assert probe_mod.compose_config()["enabled"] is False


def test_complementary_edits_are_composed_and_the_composed_state_is_kept(task, envelope, trace, tools, tmp_path,
                                                                         two_signals, monkeypatch):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, monkeypatch=monkeypatch,
                       lessons_write="on", lessons_dir=str(tmp_path / "lib"))
    [row] = [r for r in read_rounds(tmp_path) if r["kind"] == "round"]
    assert row["flags"].get("complementary") is True
    assert [p["scope"] for p in row["probes"]] == ["inv", "dom", "compose"]
    comp = row["probes"][2]
    assert comp["status"] == "done" and [x["scope"] for x in comp["composed_of"]] == ["inv", "dom"]
    assert row["pick"] == "compose" and row["step_status"] == "done"
    analyst = next(a for a in cfg.agents.values() if a.name == "Cost Analyst")
    assert {"RULE-A: find the first figure.", "RULE-B: find the second figure."} <= set(analyst.constraints)
    [fix] = [f for f in ep.adaptation["fixes"] if f.get("round")]
    assert (fix["result"], fix["kind"]) == ("recovered", "compose")
    assert len(llm.calls_of("fix_proposer_inv")) == 1 and len(llm.calls_of("fix_proposer_dom")) == 1   # no new call
    files = {p.name for p in (tmp_path / "artifacts").iterdir()}
    assert "step_1.probe-compose.json" in files
    lib = LessonLibrary(tmp_path / "lib")
    inv, dom = (lib.get(key_of(row["cause"], "add_role_rule", s)) for s in ("inv", "dom"))
    assert inv["counts"]["helped"] == 1 and inv["counts"]["confounded"] == 1     # its own probe, then the compose
    assert dom["counts"]["helped"] == 1 and dom["counts"]["confounded"] == 1


def test_with_compose_off_the_round_is_as_before(task, envelope, trace, tools, tmp_path, two_signals, monkeypatch):
    llm, cfg, ep = run(task, envelope, trace, tools, tmp_path, enabled=False, monkeypatch=monkeypatch)
    [row] = [r for r in read_rounds(tmp_path) if r["kind"] == "round"][:1]
    assert row["flags"].get("complementary") is True and [p["scope"] for p in row["probes"]] == ["inv", "dom"]
    assert row["pick"] is None                                       # neither ended done: today's base, no winner


def test_the_keep_rule():
    keep = probe_mod.keep_composed
    a = {"status": "partial", "cleared": ["x"], "new": []}
    b = {"status": "partial", "cleared": ["y"], "new": []}
    assert keep({"status": "done", "cleared": [], "new": ["z"]}, [a, b])
    assert keep({"status": "partial", "cleared": ["x", "y"], "new": []}, [a, b])
    assert not keep({"status": "partial", "cleared": ["x", "y"], "new": ["z"]}, [a, b])
    assert not keep({"status": "partial", "cleared": ["x"], "new": []}, [a, b])


def test_plan_edits_are_never_composed():
    assert probe_mod.composable([{"reply": type("R", (), {"edit": type("E", (), {"op": "split_step"})})}]) is False
