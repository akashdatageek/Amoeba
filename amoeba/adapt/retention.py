"""D100 — recipe expiry, replay and pruning (plain code; no model call).

Retention replay: every N practice tasks of a family (adapt.yaml `retention.every`, default 12; `--retention-every 0`
turns it off) the family's pre-shift gate tasks (held-out phase `pre`) are replayed with the current recipe and with
the seed recipe (v1), same seeds, through the arm-A cache. If the current recipe scores lower than the seed by more
than the family's calibration noise, the loop raises an alarm of cause `retention` at once instead of waiting for a
new shift; it then goes through Diagnoser → Architect → Experimenter → Gate like any alarm. Only scores reach the
Diagnoser: held-out tasks never reach a prompt.

Pruning: at the end of a stream (`--prune end`, the default; `off`) and on demand (`scripts/prune_recipe.py`), each
line of the current recipe (rule, transform, run option, model preference) is removed one at a time and the recipe
without it is replayed against the recipe with it on the gate set. If removing it does not lower the score beyond
noise and lowers cost (USD when both arms have prices, else tokens), the line goes: the Gate's prune decision is a
ledger row (`prune: true`) and the store commits it like any accept. Prune rows count toward no hypothesis quota.
"""
from __future__ import annotations

from pathlib import Path
from statistics import mean

from amoeba.adapt.evidence import experiment_refs
from amoeba.adapt.experimenter import _arm_a, replay
from amoeba.adapt.gate import decide_prune
from amoeba.adapt.monitor import Alarm
from amoeba.adapt.recipe import Recipe, adapt_config


# box: retention
def retention_cfg() -> dict:
    return {"every": 12, "prune": "end", **(adapt_config().get("retention") or {})}


# box: retention
def retention_due(records, family: str, every: int) -> int | None:
    """The family's practice count when a retention replay is due now (every N-th practice task), else None."""
    if not every:
        return None
    n = sum(1 for r in records if r.family == family)
    return n if n and n % every == 0 else None


# box: retention
def _mean_score(got: dict) -> float:
    return round(mean(r.score or 0.0 for r in got.values()), 4) if got else 0.0


# box: retention
def retention_check(stream, family: str, store, runner, root: str | Path, repeats: int, noise: float,
                    count: int) -> dict:
    """One retention replay: the current recipe against the seed (v1) on the pre-shift gate tasks."""
    tasks = stream.heldout(family, "pre")
    cur = store.current_or_seed(family)
    row = {"family": family, "count": count, "recipe_version": cur.version, "reference_version": 1,
           "n_tasks": len(tasks), "repeats": repeats, "noise": noise}
    if not tasks:
        return {**row, "skipped": "no pre-shift gate tasks", "alarm": False}
    if cur.version == 1 or cur.hash() == store.get(family, 1).hash():
        return {**row, "skipped": "the seed recipe is current", "alarm": False}
    now, _ = _arm_a(stream, cur, Path(root), tasks, repeats, runner)
    ref, _ = _arm_a(stream, store.get(family, 1), Path(root), tasks, repeats, runner)
    m_now, m_ref = _mean_score(now), _mean_score(ref)
    drop = round(m_ref - m_now, 4)
    return {**row, "reference_mean": m_ref, "mean": m_now, "drop": drop, "alarm": drop > noise}


# box: retention
def retention_alarm(row: dict, order: int) -> Alarm:
    return Alarm(family=row["family"], kind="retention", window=[], before=row["reference_mean"], after=row["mean"],
                 at_order=order, signals=["retention"], inputs={k: v for k, v in row.items() if k != "alarm"})


# box: retention
def remove_line(recipe: Recipe, key: str, hypothesis_id: str | None = None) -> Recipe:
    """Pure: the recipe without one line (by its provenance key), version + 1."""
    r = recipe.model_copy(deep=True)
    if key.startswith("L"):
        r.planner_rules = [x for x in r.planner_rules if x.id != key]
    elif key.startswith("T"):
        r.transforms = [x for x in r.transforms if x.id != key]
    elif key.startswith("run_options."):
        r.run_options.pop(key.split(".", 1)[1], None)
    elif key.startswith("model_prefs."):
        r.model_prefs.pop(key.split(".", 1)[1], None)
    else:
        raise ValueError(f"unknown recipe line {key!r}")
    if key not in recipe.line_keys():
        raise ValueError(f"no line {key} in {recipe.family} v{recipe.version}")
    r.provenance.pop(key, None)
    return r.model_copy(update={"version": recipe.version + 1, "parent_version": recipe.version,
                                "created_by": "prune", "hypothesis_id": hypothesis_id})


# box: retention
def prune_family(stream, family: str, store, ledger, runner, root: str | Path, repeats: int, noise: float,
                 ev=None, log=print, gate_version: str = "v3") -> list[dict]:
    """Each line of the family's current recipe, removed one at a time; a prune the Gate accepts is committed
    before the next line is tried. Resumable: a line already decided on this recipe version is not replayed."""
    root = Path(root)
    rows = []
    cur = store.current(family)
    if cur is None:
        return rows
    for key in list(cur.line_keys()):
        cur = store.current(family)
        if key not in cur.line_keys():
            continue
        hid = f"{stream.name}-{family}-prune-{key}-v{cur.version}"
        done = [r for r in ledger.rows(family, "decision") if r.get("hypothesis_id") == hid]
        if done:
            rows.append(done[-1])
            continue
        b = remove_line(cur, key, hypothesis_id=hid)
        same_draft = not (key.startswith("L") or key in ("model_prefs." + x for x in
                                                          ("interpreter", "planner", "agent_observer", "plan_observer")))
        res = replay(cur, b, hid, stream, runner, root, repeats, same_draft, {"op": "remove_line", "line": key})
        dec = decide_prune(res, noise)
        row = ledger.append({"event": "decision", "prune": True, "family": family, "hypothesis_id": hid,
                             "line": key, "line_provenance": cur.provenance.get(key), "recipe_from": cur.version,
                             "recipe_to": b.version, "recipe_A_hash": cur.hash(), "recipe_B_hash": b.hash(),
                             "noise": noise, "gate_version": gate_version, "experiment": f"experiments/{hid}/", **dec})
        if ev is not None:
            ev.append("prune", row, experiment_refs(root, root / "experiments" / hid), key=f"prune:{hid}")
        log(f"[prune] {family} {key}: {dec['decision']} {dec['reasons']}")
        if dec["decision"] == "accept":
            store.commit(b, row)
        rows.append(row)
    return rows
