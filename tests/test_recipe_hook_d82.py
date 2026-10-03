"""D82 — the recipe hook in Boxes 2 and 3: the lessons reach the d24 prompts; an empty recipe leaves a Phase 1 run
unchanged; transforms change only the selected steps and roles; run options overlay the defaults (an explicit CLI
flag wins); with --drafts-from only transforms and run options apply; the baselines never get a recipe. Offline."""
import json

import pytest

from amoeba.adapt.recipe import Edit, apply_edit, lessons_text, load_recipe, seed_recipe, write_store
from amoeba.interp.plan_runner import PlanOptions
from amoeba.task.models import Task
from amoeba.task.saved_drafts import load_saved_drafts, pick
from amoeba.tools.registry import default_registry
from scripts.run_task import parse_args, run_one
from tests.conftest import mock
from tests.test_plan_runner import APPROVE, DIAMOND, finish

TASK = Task(id="calc-x", prompt="Compute 17 * 23 + 5.", family="calc")
RULE = "End the answer with a short section headed Assumptions that lists every assumption made."


def llm():
    return mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=finish)


def run(tmp_path, name, recipe=None, envelope=None, **kw):
    from amoeba.safety.envelope import Envelope
    m = llm()
    r = run_one(TASK, "plan", m, envelope or Envelope.from_registry(default_registry()), default_registry(),
                tmp_path / name, draft_prompts="d24", recipe=recipe, plan_options=PlanOptions(), **kw)
    return m, r, tmp_path / name / r.run_id


def with_rule():
    return apply_edit(seed_recipe("calc"), Edit(op="add_planner_rule", params={"text": RULE}), created_by="human")


def test_an_empty_recipe_leaves_a_phase1_run_unchanged(tmp_path):
    m0, r0, d0 = run(tmp_path, "none")
    m1, r1, d1 = run(tmp_path, "empty", recipe=seed_recipe("calc"))
    assert [c["messages"] for c in m0.calls] == [c["messages"] for c in m1.calls]      # every prompt, byte for byte
    assert r0.answer == r1.answer and r0.score == r1.score and r0.n_llm_calls == r1.n_llm_calls
    assert (d0 / "plan.json").read_text() == (d1 / "plan.json").read_text()
    assert not (d1 / "draft.json").exists()
    a, b = (json.loads((d / "result.json").read_text()) for d in (d0, d1))
    noise = {"run_id", "team_id", "latency_ms", "recipe"}
    assert {k: v for k, v in a.items() if k not in noise} == {k: v for k, v in b.items() if k not in noise}
    assert "recipe" not in a and b["recipe"]["version"] == 1 and b["recipe"]["transforms_applied"] == []


def test_the_lessons_reach_the_d24_prompts_of_the_planner_and_both_observers(tmp_path):
    m, r, d = run(tmp_path, "rule", recipe=with_rule())
    for kind in ("planner", "agent_observer", "plan_observer"):
        text = m.calls_of(kind)[0]["messages"][-1]["content"]
        assert "# Lessons for this kind of task" in text and f"- L1: {RULE}" in text, kind
    assert "every lesson is followed by the plan, or the plan says why not" in \
        m.calls_of("plan_observer")[0]["messages"][-1]["content"]
    # Box 3 helpers are not shown the rule itself; it acts through the plan the Planner wrote
    assert all(RULE not in c["messages"][-1]["content"] for c in m.calls if c["kind"] in ("plan_worker", "plan_summariser"))
    rec = json.loads((d / "result.json").read_text())["recipe"]
    assert rec["rules_applied"] is True and rec["rules"] == [{"id": "L1", "text": RULE}]
    assert lessons_text(seed_recipe("calc")) == {}


def test_transforms_change_only_the_selected_steps_and_roles(tmp_path):
    r = seed_recipe("calc")
    r = apply_edit(r, Edit(op="add_role_rule", params={"select": {"roles_with_tool": "calc"}, "text": "Show each formula."}))
    r = apply_edit(r, Edit(op="tighten_done_when", params={"select": {"last_work_step": True}, "clause": "Units are stated."}))
    m0, r0, d0 = run(tmp_path, "none")
    m, res, d = run(tmp_path, "tx", recipe=r)
    before, after = (json.loads((x / f).read_text()) for x, f in ((d0, "plan.json"), (d, "plan.json")))
    box2 = json.loads((d / "draft.json").read_text())
    assert box2["plan"] == before["plan"] and "recipe_applied" not in box2      # draft.json = Box 2's own draft
    changed = [i for i, (x, y) in enumerate(zip(before["plan"], after["plan"])) if x != y]
    applied = after["recipe_applied"]["transforms"]
    assert [s + 1 for s in changed] == applied[1]["steps"] and len(applied[1]["steps"]) == 1
    assert after["plan"][changed[0]]["done_when"].endswith("Units are stated.")
    roles = {x["name"]: x for x in after["created_roles"]}
    with_calc = [n for n, x in roles.items() if "calc" in x["tools"]]
    assert sorted(applied[0]["roles"]) == sorted(with_calc)
    assert all(("Show each formula." in x["constraints"]) == (n in with_calc) for n, x in roles.items())
    team = (d / "team.yaml").read_text()
    assert "Show each formula." in team
    assert json.loads((d / "result.json").read_text())["recipe"]["transforms_applied"] == applied
    # the role card the helpers see carries the new constraint
    assert any("Show each formula." in c["messages"][-1]["content"] for c in m.calls if c["kind"] == "plan_worker")


def test_run_options_overlay_the_defaults_and_an_explicit_cli_flag_wins(tmp_path):
    r = apply_edit(seed_recipe("calc"), Edit(op="set_run_option", params={"name": "self_refine", "value": "always"}))
    r = apply_edit(r, Edit(op="set_run_option", params={"name": "max_turns", "value": 4}))
    m, res, d = run(tmp_path, "opt", recipe=r)
    graph = [json.loads(l) for l in (d / "trace.jsonl").read_text().splitlines() if '"plan_graph"' in l][0]
    assert graph["amoeba.options.self_refine"] == "always" and graph["amoeba.max_turns"] == 4
    rec = json.loads((d / "result.json").read_text())["recipe"]
    assert rec["run_options"] == {"self_refine": "always", "max_turns": 4} and rec["run_options_overridden_by_cli"] == []
    m2, res2, d2 = run(tmp_path, "cli", recipe=r, cli_explicit=frozenset({"--self-refine"}))
    graph2 = [json.loads(l) for l in (d2 / "trace.jsonl").read_text().splitlines() if '"plan_graph"' in l][0]
    assert graph2["amoeba.options.self_refine"] == "off"           # the CLI's value (PlanOptions default here)
    assert json.loads((d2 / "result.json").read_text())["recipe"]["run_options_overridden_by_cli"] == ["self_refine"]
    assert parse_args(["x", "--topology", "plan", "--self-refine", "always"]).explicit >= {"--self-refine"}


def test_with_drafts_from_only_transforms_and_run_options_apply(tmp_path):
    m0, r0, d0 = run(tmp_path, "src")
    saved = pick(load_saved_drafts(tmp_path / "src"), TASK.id, 0)
    r = apply_edit(with_rule(), Edit(op="add_role_rule", params={"select": {"all_roles": True}, "text": "Show each formula."}))
    m, res, d = run(tmp_path, "reuse", recipe=r, saved_draft=saved)
    assert not m.calls_of("planner")                                   # no drafting call: the rule cannot act
    rec = json.loads((d / "result.json").read_text())["recipe"]
    assert rec["rules_applied"] is False and "planner rules need a fresh draft" in rec["rules_note"]
    assert rec["transforms_applied"][0]["roles"]                       # the transform did act
    # the arm-B pattern of D83: a run that applied transforms leaves draft.json, which is what a reuse picks
    again = pick(load_saved_drafts(tmp_path / "reuse"), TASK.id, 0)
    assert again.draft.model_dump_json() == saved.draft.model_dump_json()


def test_the_baselines_never_get_a_recipe(tmp_path):
    from amoeba.safety.envelope import Envelope
    with pytest.raises(ValueError, match="plan runner only"):
        run_one(TASK, "flat", llm(), Envelope.from_registry(default_registry()), default_registry(), tmp_path,
                recipe=seed_recipe("calc"))
    with pytest.raises(SystemExit):
        parse_args(["x", "--topology", "boss_reviewers", "--recipes", "somewhere"])


def test_the_store_gives_the_current_recipe_of_the_family(tmp_path):
    v2 = with_rule()
    write_store(tmp_path / "store", [v2])
    got = load_recipe(tmp_path / "store", "calc")
    assert got == v2 and load_recipe(tmp_path / "store", "code") is None and load_recipe(tmp_path / "none", "calc") is None
    idx = json.loads((tmp_path / "store" / "index.json").read_text())
    assert idx["calc"]["current"] == 2 and idx["calc"]["history"][0]["parent"] == 1
