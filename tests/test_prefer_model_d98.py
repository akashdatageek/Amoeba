"""D98 — `prefer_model {role, model}` as a recipe edit (built, OFF by default; mock models, no network): it sets the
router's choice (3c) for one role, never bypasses the allowlist or the hard filters, is allowed only for the causes
max_turns / checks / capability (never feedback), is refused by V6 while --allow-model-edits is off, and the Gate
judges it on gain and USD like any edit. Recipes without a preference keep their hash."""
import pytest

from amoeba.adapt.diagnoser import _allowed, diagnose_none
from amoeba.adapt.experimenter import Pair, ReplayResult
from amoeba.adapt.gate import decide
from amoeba.adapt.monitor import Alarm
from amoeba.adapt.recipe import Edit, adapt_config, apply_edit, seed_recipe, validate_recipe
from amoeba.llm.router import CallSpec, NoModelAvailable
from tests.test_gate_d84 import ENV, hyp
from tests.test_router_d97 import entry, router

PREF = Edit(op="prefer_model", params={"role": "verifier", "model": "gemma-4-31b"})


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("AMOEBA_ALLOW_MODEL_EDITS", "1")


def test_off_by_default_and_the_flag_turns_it_on(monkeypatch):
    monkeypatch.delenv("AMOEBA_ALLOW_MODEL_EDITS", raising=False)
    assert adapt_config()["recipe"]["allow_model_edits"] is False
    r = apply_edit(seed_recipe("calc"), PREF)
    assert r.model_prefs == {"verifier": "gemma-4-31b"}
    assert [v.rule for v in validate_recipe(r, ENV)] == ["V6"]
    monkeypatch.setenv("AMOEBA_ALLOW_MODEL_EDITS", "1")
    assert validate_recipe(r, ENV) == []


def test_unknown_roles_and_models_are_refused(on):
    r = apply_edit(seed_recipe("calc"), Edit(op="prefer_model", params={"role": "boss", "model": "gpt-x"}))
    details = " ".join(v.detail for v in validate_recipe(r, ENV))
    assert "unknown role 'boss'" in details and "'gpt-x' is not in the model registry" in details


def test_allowed_for_max_turns_checks_capability_never_feedback(monkeypatch, on):
    for cause in ("max_turns", "checks", "capability"):
        assert "prefer_model" in _allowed(cause), cause
    for cause in ("feedback", "unused_tool", "claimed_file_missing", "honesty"):
        assert "prefer_model" not in _allowed(cause), cause
    alarm = Alarm(family="calc", kind="score", window=["r1"], at_order=5, before=0.8, after=0.5)
    assert "prefer_model" in diagnose_none(alarm).allowed_edits
    monkeypatch.delenv("AMOEBA_ALLOW_MODEL_EDITS")
    assert all("prefer_model" not in _allowed(c) for c in ("max_turns", "checks", "capability"))
    assert "prefer_model" not in diagnose_none(alarm).allowed_edits


def test_the_recipe_hash_is_unchanged_without_a_preference():
    a = seed_recipe("calc")
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


def test_the_gate_judges_it_on_gain_and_usd(on):
    def res(usd_a, usd_b):
        pairs = [Pair(task_id=f"t{i}", phase="post", k=0, seed=0, score_A=0.5, score_B=0.9, tokens_A=1000,
                      tokens_B=1000, honesty_A=0, honesty_B=0, usd_A=usd_a, usd_B=usd_b) for i in range(15)]
        return ReplayResult(hypothesis_id="h", family="calc", recipe_from=1, recipe_to=2, recipe_A_hash="a",
                            mode="own_draft", pairs=pairs)
    a, h = seed_recipe("calc"), hyp(edit=PREF)
    d = decide(a, apply_edit(a, PREF), h, res(0.01, 0.05), 0.0, 1, [], ENV, version="v3", hypothesis_index=1)
    assert d.cost_basis == "usd" and d.decision == "reject" and any("4 cost not justified: USD" in x for x in d.reasons)
    d = decide(a, apply_edit(a, PREF), h, res(0.01, 0.011), 0.0, 1, [], ENV, version="v3", hypothesis_index=1)
    assert d.cost_basis == "usd" and d.decision == "accept", d.reasons


def test_the_gate_refuses_it_while_model_edits_are_off(monkeypatch):
    monkeypatch.delenv("AMOEBA_ALLOW_MODEL_EDITS", raising=False)
    from tests.test_gate_d84 import result
    a = seed_recipe("calc")
    d = decide(a, apply_edit(a, PREF), hyp(edit=PREF), result(), 0.0, 1, [], ENV, version="v3", hypothesis_index=1)
    assert d.decision == "reject" and any("V6" in x for x in d.reasons)


def test_the_role_list_in_models_yaml_matches_the_router():
    import yaml
    from pathlib import Path
    from amoeba.llm.router import ROLES
    roles = yaml.safe_load(Path("amoeba/config/models.yaml").read_text())["routing"]["roles"]
    assert tuple(roles) == ROLES
