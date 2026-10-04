"""D99 — memory, three kinds, each with its own write rule (offline): recipe lines carry provenance (hypothesis,
Gate row, date) and only a Gate accept writes a version; user `standards:` count only when the user wrote or approved
them, the loop only PROPOSES a line (same feedback item failing in ≥3 practice runs across ≥2 families), approval is
scripts/approve_memory.py and is logged in events.jsonl; Box 1 and Box 2 read approved standards; no agent can write a
memory file."""
import json
from pathlib import Path

import pytest
import yaml

from amoeba.adapt.evidence import EvidenceLog, verify
from amoeba.adapt.monitor import PracticeRecord
from amoeba.adapt.recipe import Edit, apply_edit, seed_recipe
from amoeba.localtools.gate import inside, screen_command
from amoeba.localtools.toolbox import load_local_config
from amoeba.memory.context import (approve_standard, context_text, load_context, propose_standards, read_proposals,
                                   standards_slots)
from amoeba.memory.recipes import RecipeStore

RULE = Edit(op="add_planner_rule", params={"text": "End the answer with a short section headed Assumptions."})


def rec(order, family, items):
    return PracticeRecord(order=order, task_id=f"t{order}", family=family, score=0.5, failed_items=items)


# ---- recipe memory ---------------------------------------------------------------------------------------------------
def test_every_recipe_line_carries_provenance_and_the_gate_row(tmp_path):
    a = seed_recipe("calc")
    b = apply_edit(a, RULE, hypothesis_id="h7")
    b = apply_edit(b, Edit(op="set_run_option", params={"name": "max_turns", "value": 6}), hypothesis_id="h7")
    assert set(b.provenance) == {"L1", "run_options.max_turns"} and b.provenance["L1"]["hypothesis_id"] == "h7"
    assert b.provenance["L1"]["gate_row"] is None and b.provenance["L1"]["date"]
    assert b.hash() == apply_edit(apply_edit(a, RULE), Edit(op="set_run_option",
                                                            params={"name": "max_turns", "value": 6})).hash()
    store = RecipeStore(tmp_path / "recipes")
    store.ensure_seed("calc")
    b = b.model_copy(update={"version": 2, "parent_version": 1})
    with pytest.raises(PermissionError):                                    # only a Gate accept writes
        store.commit(b, {"event": "decision", "decision": "reject", "hypothesis_id": "h7"})
    store.commit(b, {"event": "decision", "decision": "accept", "hypothesis_id": "h7", "ts": "2026-10-04T04:00:00",
                     "gate_version": "v3"})
    cur = store.current("calc")
    assert cur.provenance["L1"]["gate_row"] == "ledger.jsonl decision h7 2026-10-04T04:00:00"
    assert cur.provenance["run_options.max_turns"]["gate_version"] == "v3"
    c = apply_edit(cur, Edit(op="remove_planner_rule", params={"id": "L1"}), hypothesis_id="h8")
    assert "L1" not in c.provenance


def test_the_size_caps_still_hold():
    from amoeba.adapt.recipe import validate_recipe
    r = seed_recipe("calc")
    for i in range(9):
        r = apply_edit(r, Edit(op="add_planner_rule", params={"text": f"Lesson number {i} about checking figures."}))
    assert any(v.rule == "V3" or "8" in v.detail for v in validate_recipe(r))


# ---- user memory -----------------------------------------------------------------------------------------------------
def test_proposals_only_above_the_threshold(tmp_path):
    ev = EvidenceLog(tmp_path)
    recs = [rec(1, "calc", ["assumptions"]), rec(2, "calc", ["assumptions"]), rec(3, "calc", ["assumptions"])]
    assert propose_standards(recs, tmp_path, ev) == []                     # 3 runs, 1 family
    recs2 = [rec(1, "calc", ["assumptions"]), rec(2, "research", ["assumptions"])]
    assert propose_standards(recs2, tmp_path, ev) == []                    # 2 families, 2 runs
    recs3 = recs + [rec(4, "research", ["assumptions", "units"])]
    new = propose_standards(recs3, tmp_path, ev)
    assert [p["item"] for p in new] == ["assumptions"] and new[0]["id"] == "P1"
    assert new[0]["runs"] == [1, 2, 3, 4] and new[0]["families"] == ["calc", "research"]
    assert propose_standards(recs3, tmp_path, ev) == []                    # once per item
    assert [r["event"] for r in ev.rows()] == ["memory_proposal"] and verify(tmp_path)["ok"]


def test_nothing_enters_user_memory_without_approval(tmp_path):
    ctx = tmp_path / "user.yaml"
    ctx.write_text("organisation: Example Co\nstandards:\n  - Prices are quoted in euros.\n"
                   "  - {text: 'Copied proposal, never approved.', proposal: P9}\n")
    assert load_context(ctx)["standards"] == ("Prices are quoted in euros.",)
    root = tmp_path / "loop"
    propose_standards([rec(i, f, ["assumptions"]) for i, f in enumerate(["calc", "calc", "research"], 1)], root)
    assert load_context(ctx)["standards"] == ("Prices are quoted in euros.",)   # a proposal changes nothing
    from scripts.approve_memory import main
    assert main(["--root", str(root), "--id", "P1", "--context", str(ctx),
                 "--text", "Answers end with an Assumptions section."]) == 0
    assert load_context(ctx)["standards"] == ("Prices are quoted in euros.", "Answers end with an Assumptions section.")
    data = yaml.safe_load(ctx.read_text())
    assert data["organisation"] == "Example Co" and data["standards"][-1]["proposal"] == "P1"
    row = EvidenceLog(root).rows()[-1]
    assert row["event"] == "memory_approval" and row["data"]["proposal"] == "P1" and verify(root)["ok"]
    with pytest.raises(ValueError):
        approve_standard(ctx, read_proposals(root)[0])                   # approved once


def test_box_1_and_box_2_read_approved_standards(tmp_path):
    ctx = tmp_path / "user.yaml"
    ctx.write_text("role: analyst\nstandards:\n  - Answers end with an Assumptions section.\n")
    c = load_context(ctx)
    assert "- standard: Answers end with an Assumptions section." in context_text(c)
    slots = standards_slots(c)
    assert set(slots) == {"planner", "plan_observer"} and "Assumptions section" in slots["planner"]
    assert standards_slots(load_context(None)) == {} and context_text(load_context(None)) == "None given."


def test_a_run_puts_the_standards_into_the_planner_prompt_and_none_change_nothing(tmp_path):
    from tests.test_recipe_hook_d82 import run
    ctx = tmp_path / "user.yaml"
    ctx.write_text("standards:\n  - Answers end with an Assumptions section.\n")
    m, r, d = run(tmp_path, "std", context=load_context(ctx))
    for kind in ("planner", "plan_observer"):
        assert "- Answers end with an Assumptions section." in m.calls_of(kind)[0]["messages"][-1]["content"], kind
    assert any('"user_standards"' in l for l in (d / "trace.jsonl").read_text().splitlines())
    m0, _, _ = run(tmp_path, "none")
    m1, _, _ = run(tmp_path, "plain", context=load_context(None))
    assert [c["messages"] for c in m0.calls] == [c["messages"] for c in m1.calls]


# ---- agents cannot write memory ----------------------------------------------------------------------------------------
def test_agents_cannot_write_any_memory_file(tmp_path):
    root = tmp_path / "eval" / "loop" / "m2"
    ws = root / "practice" / "01-p1" / "run-x" / "workspace"
    ws.mkdir(parents=True)
    memory = [root / "recipes" / "index.json", root / "recipes" / "calc" / "v2.yaml", root / "events.jsonl",
              root / "memory_proposals.jsonl", root / "ledger.jsonl", tmp_path / "user.yaml"]
    for m in memory:
        assert inside(str(m), ws) is None, m                              # Write / Edit: outside_workspace
        assert screen_command(f"echo x >> {m}", ws), m                    # Bash: path outside the workspace
    assert screen_command("echo x >> ../../../recipes/index.json", ws)
    s = load_local_config()["sandbox"]           # the sandbox's own paths only: no host folder is mounted into it
    assert set(s["read_write"]) <= {"/sandbox", "/tmp", "/dev/null"} and not any(
        p.startswith(("/home", "/root", "/var", "/workspace")) for p in s["read_only"])
