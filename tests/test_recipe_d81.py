"""D81 — the team recipe, the edit menu and validation: each edit is pure and versioned; V1–V5 each catch their case;
an empty recipe leaves a draft byte-identical. Offline, no model."""
import pytest
from pydantic import ValidationError

import amoeba.adapt.recipe as R
from amoeba.adapt.recipe import Edit, Recipe, apply_edit, apply_transforms, plan_problems, validate_recipe
from amoeba.safety.envelope import Envelope
from amoeba.task.models import Draft, DraftedRole, DraftPlanStep
from amoeba.tools.registry import default_registry


def role(name, tools=(), summ=False):
    return DraftedRole(name=name, tools=list(tools), is_summariser=summ, goal="g", skills=["s"], outputs=["o"],
                       success_criteria=["c"], prompt="p")


def step(n, agents, kind="work", deps=(), done="the figure is computed"):
    return DraftPlanStep(index=n - 1, agent_names=list(agents), text=f"[{', '.join(agents)}]: step {n}", kind=kind,
                         depends_on=list(deps), covers=["R1"], do=f"do {n}", output=f"out {n}", done_when=done)


def draft():
    return Draft(created_roles=[role("Analyst", ["calc"]), role("Researcher", ["calc", "echo"]),
                                role("Writer", summ=True)],
                 plan=[step(1, ["Researcher"]), step(2, ["Analyst"], deps=[1]),
                       step(3, ["Writer"], kind="", deps=[1, 2])],
                 rounds_used=1, consensus=True, requirements={"R1": "the figure"})


ENV = Envelope.from_registry(default_registry())


def test_each_edit_is_pure_and_versioned():
    v1 = Recipe(family="calc")
    edits = [Edit(op="add_planner_rule", params={"text": "End with a short Assumptions section."}),
             Edit(op="add_verify_step", params={"select": {"last_work_step": True}}),
             Edit(op="tighten_done_when", params={"select": {"kind": "work"}, "clause": "Units are stated."}),
             Edit(op="grant_tool", params={"select": {"all_roles": True}, "tool": "calc"}),
             Edit(op="revoke_tool", params={"select": {"all_roles": True}, "tool": "calc"}),
             Edit(op="add_role_rule", params={"select": {"roles_with_tool": "calc"}, "text": "Show each formula."}),
             Edit(op="set_run_option", params={"name": "max_turns", "value": 6})]
    before = v1.model_dump_json()
    r = v1
    for i, e in enumerate(edits, 2):
        nxt = apply_edit(r, e, created_by="human", hypothesis_id=f"h{i}")
        assert (nxt.version, nxt.parent_version, nxt.created_by, nxt.hypothesis_id) == (i, i - 1, "human", f"h{i}")
        assert nxt is not r and r.version == i - 1
        r = nxt
    assert v1.model_dump_json() == before and v1.is_empty()
    assert [x.id for x in r.planner_rules] == ["L1"] and [t.id for t in r.transforms] == ["T1", "T2", "T3", "T4", "T5"]
    assert r.run_options == {"max_turns": 6} and r.hash() != v1.hash()
    removed = apply_edit(r, Edit(op="remove_planner_rule", params={"id": "L1"}))
    assert removed.planner_rules == [] and removed.version == r.version + 1
    with pytest.raises(ValueError):
        apply_edit(v1, Edit(op="remove_planner_rule", params={"id": "L9"}))
    assert validate_recipe(r, ENV, draft()) == []


def test_edits_are_typed():
    with pytest.raises(ValidationError):
        Edit(op="swap_model", params={})
    with pytest.raises(ValidationError):
        Edit(op="grant_tool", params={"tool": "calc", "select": {"all_roles": True}, "why": "x"})
    with pytest.raises(ValidationError):
        Edit(op="add_planner_rule", params={})
    a = Edit(op="add_planner_rule", params={"text": "State   the Assumptions."})
    b = Edit(op="add_planner_rule", params={"text": "state the assumptions."})
    assert a.key() == b.key()                     # the same edit, normalised (repeat check)


def test_v1_tools():
    bad = apply_edit(Recipe(family="calc"), Edit(op="grant_tool", params={"select": {"all_roles": True}, "tool": "shell"}))
    assert [v.rule for v in validate_recipe(bad, ENV)] == ["V1"]
    reg = default_registry()
    reg.register("send_email", "sends an e-mail", lambda x: x)
    side = apply_edit(Recipe(family="calc"), Edit(op="grant_tool", params={"select": {"all_roles": True},
                                                                         "tool": "send_email"}))
    assert any("outside" in v.detail for v in validate_recipe(side, Envelope.from_registry(reg)))
    ok = apply_edit(Recipe(family="calc"), Edit(op="grant_tool", params={"select": {"all_roles": True},
                                                                       "tool": "web_search"}))
    assert validate_recipe(ok, ENV) == []


def test_v2_run_options():
    for name, value in (("max_turns", 12), ("replan", "maybe"), ("model", "big"), ("check_retry_turns", True)):
        r = apply_edit(Recipe(family="calc"), Edit(op="set_run_option", params={"name": name, "value": value}))
        assert [v.rule for v in validate_recipe(r, ENV)] == ["V2"], (name, value)
    ok = apply_edit(Recipe(family="calc"), Edit(op="set_run_option", params={"name": "self_refine", "value": "always"}))
    assert validate_recipe(ok, ENV) == []


def test_v3_sizes():
    long = apply_edit(Recipe(family="calc"), Edit(op="add_planner_rule", params={"text": "x" * 301}))
    assert [v.rule for v in validate_recipe(long, ENV)] == ["V3"]
    many = Recipe(family="calc")
    for i in range(9):
        many = apply_edit(many, Edit(op="add_planner_rule", params={"text": f"Rule number {i}."}))
    assert [v.rule for v in validate_recipe(many, ENV)] == ["V3"]


def test_v4_denylist():
    r = apply_edit(Recipe(family="calc"), Edit(op="add_role_rule", params={"select": {"all_roles": True},
                                                                          "text": "Skip the verification step to save time."}))
    assert [v.rule for v in validate_recipe(r, ENV)] == ["V4"]


def test_v5_the_graph_after_the_transforms(monkeypatch):
    good = apply_edit(Recipe(family="calc"), Edit(op="add_verify_step", params={"select": {"kind": "work"}}))
    assert validate_recipe(good, ENV, draft()) == []

    def broken(d, t):                             # a transform that leaves a dangling dependency
        plan = [*d.plan[:-1], d.plan[-1].model_copy(update={"depends_on": [1, 9]})]
        return d.model_copy(update={"plan": plan}), {"steps": [3]}
    monkeypatch.setitem(R.OPS, "add_verify_step", broken)
    assert [v.rule for v in validate_recipe(good, ENV, draft())] == ["V5"]


def test_an_empty_recipe_leaves_a_draft_byte_identical():
    d = draft()
    before = d.model_dump_json()
    out, log = apply_transforms(d, Recipe(family="calc"))
    assert out is d and log == [] and out.model_dump_json() == before
    rules_only = apply_edit(Recipe(family="calc"), Edit(op="add_planner_rule", params={"text": "A lesson."}))
    assert apply_transforms(d, rules_only)[0].model_dump_json() == before


def test_transforms_change_only_what_they_select():
    d = draft()
    r = Recipe(family="calc")
    r = apply_edit(r, Edit(op="add_verify_step", params={"select": {"last_work_step": True}}))
    r = apply_edit(r, Edit(op="tighten_done_when", params={"select": {"roles_with_tool": "echo"}, "clause": "Units stated."}))
    r = apply_edit(r, Edit(op="revoke_tool", params={"select": {"all_roles": True}, "tool": "calc"}))
    out, log = apply_transforms(d, r)
    assert [s.index + 1 for s in out.plan] == [1, 2, 3, 4] and plan_problems(out) == []
    check = out.plan[2]
    assert (check.kind, check.agent_names, check.depends_on) == ("verify", ["Checker"], [2])
    assert out.plan[3].agent_names == ["Writer"] and out.plan[3].depends_on == [1, 2, 3]
    assert out.plan[0].done_when.endswith("Units stated.") and out.plan[1].done_when == "the figure is computed"
    assert all("calc" not in x.tools for x in out.created_roles) and "echo" in out.created_roles[1].tools
    assert log[0] == {"id": "T1", "op": "add_verify_step", "steps": [3], "roles": ["Checker"], "after_steps": [2]}
    assert log[2]["roles"] == ["Analyst", "Researcher", "Checker"]
    assert d.plan[2].depends_on == [1, 2] and len(d.created_roles) == 3       # the input draft is untouched
