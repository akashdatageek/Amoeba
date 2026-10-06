"""D98 — `prefer_model {role, model}` as a recipe edit (built, OFF by default; mock models, no network): it sets the
router's choice (3c) for one role, never bypasses the allowlist or the hard filters, is allowed only for the causes
max_turns / checks / capability (never feedback, adapt.yaml), and is refused by V6 while --allow-model-edits is off.
Recipes without a preference keep their hash. (D117 removed the Gate tests.)"""
import pytest

from amoeba.adapt.recipe import Edit, Recipe, adapt_config, apply_edit, validate_recipe
from amoeba.llm.router import CallSpec, NoModelAvailable
from amoeba.safety.envelope import Envelope
from amoeba.tools.registry import default_registry
from tests.test_router_d97 import entry, router

ENV = Envelope.from_registry(default_registry())
PREF = Edit(op="prefer_model", params={"role": "verifier", "model": "gemma-4-31b"})


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("AMOEBA_ALLOW_MODEL_EDITS", "1")


def test_off_by_default_and_the_flag_turns_it_on(monkeypatch):
    monkeypatch.delenv("AMOEBA_ALLOW_MODEL_EDITS", raising=False)
    assert adapt_config()["recipe"]["allow_model_edits"] is False
    r = apply_edit(Recipe(family="calc"), PREF)
    assert r.model_prefs == {"verifier": "gemma-4-31b"}
    assert [v.rule for v in validate_recipe(r, ENV)] == ["V6"]
    monkeypatch.setenv("AMOEBA_ALLOW_MODEL_EDITS", "1")
    assert validate_recipe(r, ENV) == []


def test_unknown_roles_and_models_are_refused(on):
    r = apply_edit(Recipe(family="calc"), Edit(op="prefer_model", params={"role": "boss", "model": "gpt-x"}))
    details = " ".join(v.detail for v in validate_recipe(r, ENV))
    assert "unknown role 'boss'" in details and "'gpt-x' is not in the model registry" in details


def test_the_recipe_hash_is_unchanged_without_a_preference():
    a = Recipe(family="calc")
    assert "model_prefs" not in a.content() and a.is_empty()
    b = apply_edit(a, PREF)
    assert b.hash() != a.hash() and not b.is_empty() and b.content()["model_prefs"] == {"verifier": "gemma-4-31b"}


def test_the_preference_never_bypasses_the_allowlist_or_the_hard_filters(tmp_path):
    cheap, pricey = entry("cheap", price=(1, 1)), entry("pricey", price=(2, 2), ctx=1000)
    r = router([cheap, pricey], tmp_path, recipe_prefs={"worker": "pricey"})
    assert r.route(CallSpec(role="worker", step=1))[1]["why"] == "recipe preference"
    name, dec = r.route(CallSpec(role="worker", step=1, prompt_tokens=5000, max_output=100))  # context filter
    assert name == "cheap" and "context" in dec["filtered"]["pricey"]
    r = router([cheap, pricey], tmp_path, allowed=["cheap"], recipe_prefs={"worker": "pricey"})
    name, dec = r.route(CallSpec(role="worker", step=1))                                     # allowlist
    assert name == "cheap" and dec["why"] != "recipe preference"
    r = router([pricey], tmp_path, allowed=["cheap"], recipe_prefs={"worker": "pricey"})
    with pytest.raises(NoModelAvailable):                                                    # no fallback around it
        r.route(CallSpec(role="worker", step=1))


def test_a_verifier_preference_for_the_same_family_is_logged_as_such(tmp_path):
    g, q = entry("gemma", family="gemma"), entry("qwen", family="qwen", price=(3, 3))
    r = router([g, q], tmp_path, recipe_prefs={"verifier": "gemma"})
    r.step_family[1] = "gemma"
    name, dec = r.route(CallSpec(role="verifier", step=2, checks=(1,)))
    assert name == "gemma" and dec["verifier_same_family"] == "recipe preference"


def test_the_role_list_in_models_yaml_matches_the_router():
    import yaml
    from pathlib import Path
    from amoeba.llm.router import ROLES
    roles = yaml.safe_load(Path("amoeba/config/models.yaml").read_text())["routing"]["roles"]
    assert tuple(roles) == ROLES
