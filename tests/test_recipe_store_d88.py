"""D88 — Box 9, the recipe store: versions, index with history, experience log; only a Gate accept writes a version;
revert goes back to the parent; run_task reads --recipes and falls back to --recipes-from; warm start copies a store.
Offline, plain code."""
import json

import pytest

from amoeba.adapt.recipe import Edit, apply_edit, seed_recipe
from amoeba.memory.recipes import RecipeStore, load_family_recipe
from scripts.run_task import parse_args

ACCEPT = {"event": "decision", "decision": "accept", "observed_delta": 0.27, "reasons": [], "gate_version": "v2"}
RULE = Edit(op="add_planner_rule", params={"text": "End with an Assumptions section."})


def test_commit_record_and_revert(tmp_path):
    st = RecipeStore(tmp_path / "recipes")
    assert st.current("calc") is None and st.current_or_seed("calc").version == 1
    v2 = apply_edit(st.ensure_seed("calc"), RULE, hypothesis_id="h1")
    with pytest.raises(PermissionError):
        st.commit(v2, {**ACCEPT, "decision": "reject"})
    with pytest.raises(PermissionError):
        st.commit(v2, {**ACCEPT, "post_hoc": True})                # a post-hoc row never changes the store
    st.commit(v2, ACCEPT)
    st.record({"cause": "feedback"}, {"family": "calc", "hypothesis_id": "h1", "edit": RULE.model_dump(),
                                      "predicted_delta": 0.2}, ACCEPT)
    idx = json.loads((tmp_path / "recipes" / "index.json").read_text())
    assert idx["calc"]["current"] == 2 and [h["version"] for h in idx["calc"]["history"]] == [1, 2]
    assert idx["calc"]["history"][1]["hypothesis_id"] == "h1" and (tmp_path / "recipes" / "calc" / "v2.yaml").exists()
    assert st.experience("calc")[0]["observed_delta"] == 0.27
    with pytest.raises(ValueError):                                   # v3 must be built on the current version
        st.commit(apply_edit(seed_recipe("calc"), RULE), ACCEPT)
    back = st.revert("calc", "rollback watch: practice mean 0.5 < 0.6 - 0.05")
    assert back.version == 1 and st.current("calc").version == 1
    assert json.loads((tmp_path / "recipes" / "index.json").read_text())["calc"]["history"][1]["reverted_at"]


def test_run_task_reads_recipes_then_recipes_from(tmp_path):
    a, b = RecipeStore(tmp_path / "a"), RecipeStore(tmp_path / "b")
    b.commit(apply_edit(b.ensure_seed("calc"), RULE), ACCEPT)
    assert load_family_recipe("calc", tmp_path / "a", tmp_path / "b").version == 2      # warm start fallback
    a.ensure_seed("calc")
    assert load_family_recipe("calc", tmp_path / "a", tmp_path / "b").version == 1      # the stream's own store wins
    assert load_family_recipe("code", tmp_path / "a", tmp_path / "b") is None
    assert parse_args(["x", "--topology", "plan", "--recipes-from", "b"]).recipes_from == "b"
    with pytest.raises(SystemExit):
        parse_args(["x", "--topology", "flat", "--recipes-from", "b"])
    w = RecipeStore.warm_start(tmp_path / "w", tmp_path / "b")
    assert w.current("calc").version == 2 and not (tmp_path / "w" / "experience.jsonl").exists()
