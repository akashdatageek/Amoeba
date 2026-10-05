"""D114 — context size as recipe run options (offline): max_input_chars and max_summary_input_chars are whitelisted
with ranges in adapt.yaml; a recipe value inside the range passes validation and reaches the plan runner (a CLI flag
given explicitly still wins); a value outside is a V2 violation; the Diagnoser lets the loop propose them for the
checks and feedback causes; --option-defaults takes them as integers."""
import json

from amoeba.adapt.diagnoser import _allowed
from amoeba.adapt.recipe import Edit, adapt_config, apply_edit, overlay_run_options, seed_recipe, validate_recipe
from amoeba.interp.plan_runner import PlanOptions
from amoeba.safety.envelope import Envelope
from amoeba.task.models import Task
from amoeba.tools.registry import default_registry
from scripts.run_task import parse_args, run_one
from tests.conftest import mock
from tests.test_plan_runner import APPROVE, DIAMOND, finish


def with_option(name, value):
    return apply_edit(seed_recipe("calc"), Edit(op="set_run_option", params={"name": name, "value": value}))


def test_whitelisted_with_ranges():
    ro = adapt_config()["recipe"]["run_options"]
    assert ro["max_input_chars"] == {"min": 3000, "max": 20000}
    assert ro["max_summary_input_chars"] == {"min": 15000, "max": 60000}
    assert validate_recipe(with_option("max_input_chars", 12000)) == []
    assert validate_recipe(with_option("max_summary_input_chars", 45000)) == []
    for name, bad in (("max_input_chars", 100), ("max_input_chars", 50000), ("max_summary_input_chars", "lots")):
        [v] = validate_recipe(with_option(name, bad))
        assert v.rule == "V2", (name, bad)


def test_the_recipe_value_reaches_the_plan_runner_unless_the_cli_set_it():
    r = with_option("max_input_chars", 12000)
    opts, _, applied, over = overlay_run_options(PlanOptions(), r)
    assert opts.max_input_chars == 12000 and applied == {"max_input_chars": 12000} and over == []
    opts, _, applied, over = overlay_run_options(PlanOptions(), r, {"--max-input-chars"})
    assert opts.max_input_chars == 6000 and over == ["max_input_chars"]


def test_a_run_records_the_tuned_context_size(tmp_path):
    reg = default_registry()
    m = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=finish)
    r = run_one(Task(id="t", prompt="Compute 17 * 23 + 5.", family="calc"), "plan", m, Envelope.from_registry(reg), reg,
                tmp_path, draft_prompts="d24", plan_options=PlanOptions(),
                recipe=with_option("max_summary_input_chars", 45000))
    res = json.loads((tmp_path / r.run_id / "result.json").read_text())
    assert res["recipe"]["run_options"] == {"max_summary_input_chars": 45000}
    graph = [json.loads(l) for l in (tmp_path / r.run_id / "trace.jsonl").read_text().splitlines()
             if '"plan_graph"' in l][0]
    assert "45000" in json.dumps(graph)


def test_the_loop_may_propose_them_and_defaults_take_integers():
    assert "set_run_option:max_input_chars" in _allowed("checks")
    assert {"set_run_option:max_input_chars", "set_run_option:max_summary_input_chars"} <= set(_allowed("feedback"))
    a = parse_args(["x", "--option-defaults", "max_input_chars=8000"])
    assert a.max_input_chars == 8000
    a = parse_args(["x", "--option-defaults", "max_input_chars=8000", "--max-input-chars", "5000"])
    assert a.max_input_chars == 5000                                   # an explicit flag wins over a default
