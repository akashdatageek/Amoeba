"""D88 — Box 9, Memory: the recipe store (Phase 2 spec §10). Plain code.

    <store>/<family>/v<N>.yaml   a full Recipe
    <store>/index.json           {family: {"current": N, "history": [{version, parent, hypothesis_id, accepted_at,
                                                                     reverted_at?}]}}
    <store>/experience.jsonl     one line per decided hypothesis: diagnosis, edit, predicted / observed delta, decision

`run_task --recipes DIR` reads the current version of the task's family (read-only); `--recipes-from DIR` is a second,
read-only store used when the first has no recipe for the family (a warm start from another stream's store). Only the
Gate writes: `commit` takes the Gate's accept row, `revert` the rollback watch's decision, `record` every decided
hypothesis. With the D77 user context (amoeba/memory/context.py), Memory has two read-only parts at run time: who is
asking, and the best recipe for this kind of task.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from amoeba.adapt.recipe import Recipe, seed_recipe


# box: memory
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# box: memory, ov_m9
class RecipeStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    # ---- read (anyone) ------------------------------------------------------------------------------------------
    def index(self) -> dict:
        p = self.root / "index.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def get(self, family: str, version: int) -> Recipe:
        return Recipe.model_validate(yaml.safe_load((self.root / family / f"v{version}.yaml").read_text(encoding="utf-8")))

    def current(self, family: str) -> Recipe | None:
        cur = (self.index().get(family) or {}).get("current")
        return self.get(family, cur) if cur is not None else None

    def current_or_seed(self, family: str) -> Recipe:
        return self.current(family) or seed_recipe(family)

    def experience(self, family: str | None = None) -> list[dict]:
        p = self.root / "experience.jsonl"
        rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []
        return [r for r in rows if family in (None, r.get("family"))]

    # ---- write (the Gate only) ----------------------------------------------------------------------------------
    def _write(self, recipe: Recipe) -> None:
        (self.root / recipe.family).mkdir(parents=True, exist_ok=True)
        (self.root / recipe.family / f"v{recipe.version}.yaml").write_text(
            yaml.safe_dump(recipe.model_dump(mode="json"), sort_keys=False, allow_unicode=True), encoding="utf-8")

    def _save_index(self, index: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")

    def ensure_seed(self, family: str) -> Recipe:
        """The family's v1 (empty) recipe, written once so the store names every version it has used."""
        index = self.index()
        if family not in index:
            seed = seed_recipe(family)
            self._write(seed)
            index[family] = {"current": 1, "history": [{"version": 1, "parent": None, "hypothesis_id": None,
                                                        "accepted_at": _now()}]}
            self._save_index(index)
        return self.current(family)

    def commit(self, recipe: Recipe, decision: dict) -> Recipe:
        """The Gate's accept: recipe becomes the family's current version."""
        if decision.get("event") != "decision" or decision.get("decision") != "accept" or decision.get("post_hoc"):
            raise PermissionError("only a Gate accept (not post hoc) may write a recipe version")
        self.ensure_seed(recipe.family)
        index = self.index()
        if recipe.parent_version != index[recipe.family]["current"]:
            raise ValueError(f"recipe v{recipe.version} is not built on the current v{index[recipe.family]['current']}")
        recipe = stamp_provenance(recipe, decision)
        self._write(recipe)
        index[recipe.family]["current"] = recipe.version
        index[recipe.family]["history"].append({"version": recipe.version, "parent": recipe.parent_version,
                                                "hypothesis_id": recipe.hypothesis_id, "accepted_at": _now()})
        self._save_index(index)
        return recipe

    def revert(self, family: str, reason: str) -> Recipe:
        """The rollback watch (§9.3): back to the parent of the current version."""
        index = self.index()
        cur = index[family]["current"]
        entry = next(h for h in reversed(index[family]["history"]) if h["version"] == cur)
        if entry["parent"] is None:
            raise ValueError("the seed recipe has no parent")
        entry["reverted_at"], entry["reverted_because"] = _now(), reason
        index[family]["current"] = entry["parent"]
        self._save_index(index)
        return self.get(family, entry["parent"])

    def record(self, diagnosis: dict | None, hypothesis: dict, decision: dict) -> None:
        """One line per decided hypothesis (accepted or not): the Architect's experience."""
        row = {"ts": _now(), "family": hypothesis.get("family"), "hypothesis_id": hypothesis.get("hypothesis_id"),
               "diagnosis": diagnosis, "edit": hypothesis.get("edit"), "predicted_delta": hypothesis.get("predicted_delta"),
               "observed_delta": decision.get("observed_delta"), "decision": decision.get("decision"),
               "reasons": decision.get("reasons"), "gate_version": decision.get("gate_version")}
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.root / "experience.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    @classmethod
    def warm_start(cls, dst: str | Path, src: str | Path) -> "RecipeStore":
        """A new stream's store starting from another stream's (--recipes-from): the recipes and index are copied;
        the experience log is not (it belongs to the other stream)."""
        dst, src = Path(dst), Path(src)
        if not (dst / "index.json").exists() and (src / "index.json").exists():
            shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("experience.jsonl"))
        return cls(dst)


# box: memory
def stamp_provenance(recipe: Recipe, decision: dict) -> Recipe:
    """D99: the accepting Gate row on the lines this hypothesis added; a line from before D99 is marked so."""
    r = recipe.model_copy(deep=True)
    row = f"ledger.jsonl decision {decision.get('hypothesis_id')} {decision.get('ts', '')}".strip()
    for k in r.line_keys():
        p = r.provenance.setdefault(k, {"hypothesis_id": None, "created_by": None, "date": None, "gate_row": None,
                                        "note": "added before D99 provenance"})
        if p.get("gate_row") is None and p.get("hypothesis_id") and p["hypothesis_id"] == decision.get("hypothesis_id"):
            p["gate_row"] = row
            p["gate_version"] = decision.get("gate_version")
    return r


# box: memory
def load_family_recipe(family: str, store: str | Path | None, fallback: str | Path | None = None) -> Recipe | None:
    """run_task: the family's current recipe from --recipes, else from --recipes-from; None = a Phase 1 run."""
    for root in (store, fallback):
        if root:
            r = RecipeStore(root).current(family)
            if r is not None:
                return r
    return None
