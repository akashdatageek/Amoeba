"""Phase 2 week-1 check (spec §8): one hand-written hypothesis through Box 7 (the Experimenter) and Box 8 (the Gate).

    python -m scripts.run_experiment --stream m1 --family calc --edit edit.yaml \\
        --llm openai --profile gemma-api --timezone America/Chicago --llm-cache runs/cache --env-file keys.env

edit.yaml:
    hypothesis_id: h1-assumptions-rule
    edit: {op: add_planner_rule, params: {text: "..."}}
    predicted_delta: 0.15
    rationale: "..."

Recipe A is the family's current recipe in --recipes (default eval/loop/<stream>/recipes), else the empty seed
recipe. Without a calibration row for recipe A in eval/loop/<stream>/ledger.jsonl the noise floor is calibrated
first (A vs A′ on the held-out post slice). The ledger gets a hypothesis row and a decision row with the reasons;
an accepted recipe B becomes the family's current version in the store. Every flag this script does not know is passed to each run_task run unchanged (model, cache, time zone…),
after the experiment flags of amoeba/config/adapt.yaml. Keys come from --env-file files and are never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from amoeba.adapt.experimenter import SubprocessRunner, calibrate, experiment, experiment_flags
from amoeba.adapt.gate import Hypothesis, decide, decision_row, noise_floor, noise_floor_tasks, task_spread
from amoeba.adapt.ledger import Ledger
from amoeba.adapt.recipe import adapt_config, apply_edit, load_recipe, seed_recipe, write_store
from amoeba.adapt.stream import Stream, load_stream
from amoeba.memory.recipes import RecipeStore
from amoeba.safety.envelope import Envelope
from amoeba.task.models import Draft
from amoeba.tools.registry import default_registry

ROOT = Path(__file__).resolve().parents[1]


OVERRIDES = ("AMOEBA_BASE_URL", "AMOEBA_MODEL", "AMOEBA_API_KEY")   # would override --profile (as in the bench drivers)


# box: experimenter
def load_env(files: list[str]) -> dict:
    """The runs' environment: this one without the AMOEBA_* model overrides, plus the KEY=VALUE files."""
    e = {k: v for k, v in os.environ.items() if k not in OVERRIDES}
    for f in files or []:
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            line = line.strip().removeprefix("export ").strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                e[k.strip()] = v.strip().strip('"').strip("'")
    return e


# box: experimenter
def option_defaults() -> list[str]:
    d = adapt_config().get("experiment", {}).get("option_defaults") or {}
    return ["--option-defaults", ",".join(f"{k}={v}" for k, v in d.items())] if d else []


# box: experimenter
def summary(res) -> str:
    def mean(xs):
        return sum(xs) / len(xs) if xs else float("nan")
    post, pre = res.post(), res.pre()
    return (f"{res.hypothesis_id} [{res.mode}] post n={len(post)} mean A={mean([p.score_A for p in post]):.3f} "
            f"B={mean([p.score_B for p in post]):.3f} d={mean([p.d for p in post]):+.3f}; pre n={len(pre)} "
            f"d={mean([p.d for p in pre]):+.3f}; tokens A={mean([p.tokens_A for p in post]):.0f} "
            f"B={mean([p.tokens_B for p in post]):.0f}; arm-A cache hits {res.arm_a_cache_hits}; runs {res.runs}")


# box: experimenter
def _rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


# box: experimenter
def sample_draft(res) -> Draft | None:
    """V5's sample draft: Box 2's draft of the first arm-A run."""
    for p in res.post():
        for f in ("draft.json", "plan.json"):
            path = Path(p.run_A) / f if p.run_A else None
            if path and path.exists():
                try:
                    return Draft.model_validate_json(path.read_text(encoding="utf-8"))
                except ValueError:
                    pass
    return None


# box: experimenter
def cfg_gate_version() -> str:
    return adapt_config()["gate"].get("version", "v2")


# box: gate
def ensure_calibration(stream: Stream, family: str, runner, root: Path, store: Path, repeats: int) -> dict:
    """§9.1: the calibration row of the family's current recipe, run (A vs A′) when the ledger has none."""
    ledger = Ledger(root / "ledger.jsonl")
    recipe_A = load_recipe(store, family) or seed_recipe(family)
    key = stream.slice_key(family, "post")
    v3 = cfg_gate_version() == "v3"
    row = ledger.calibration(family, recipe_A.hash(), key, v3_only=v3)
    if row is not None:
        return row
    cal = calibrate(recipe_A, stream, runner, root, repeats)
    post = cal.post()
    spread = task_spread(cal) if v3 else {}          # D91: per-task noise across seeds, not only pair equality
    extra = {"n_tasks": len(spread), "task_spread": spread,
             "mean_task_spread": round(sum(e["spread"] for e in spread.values()) / len(spread), 4) if spread else None,
             "pairs_equal": sum(abs(p.d) < 1e-9 for p in post)} if v3 else {}
    return ledger.append({"event": "calibration", "family": family, "recipe_from": recipe_A.version,
                          "recipe_hash": recipe_A.hash(), "noise": noise_floor_tasks(cal) if v3 else noise_floor(cal),
                          "n": len(post), **extra,
                          "d_AA_mean": round(sum(p.d for p in post) / len(post), 4) if post else None,
                          "score_A_mean": round(sum(p.score_A for p in post) / len(post), 4) if post else None,
                          "score_A2_mean": round(sum(p.score_B for p in post) / len(post), 4) if post else None,
                          "tokens_A_mean": round(sum(p.tokens_A for p in post) / len(post)) if post else None,
                          "tokens_A2_mean": round(sum(p.tokens_B for p in post) / len(post)) if post else None,
                          "runs": f"experiments/{cal.hypothesis_id}/", "gate_version": cfg_gate_version(),
                          **({"slice": key} if key else {})})


# box: gate
def hand_check(stream: Stream, h: Hypothesis, runner, root: Path, store: Path | None = None,
               repeats: int = 3, check: bool = False) -> dict:
    """One hand-written hypothesis through Box 7 and Box 8: calibration if needed, the experiment, the decision.
    Returns the ledger's decision row; on accept recipe B becomes the family's current version in `store`.
    check (D91): the single pre-registered check — decided under v3 at gate.v3.check_alpha, rows marked
    "check": true, outside the loop's quota, and the recipe store is never changed."""
    root = Path(root)
    store = Path(store or root / "recipes")
    ledger = Ledger(root / "ledger.jsonl")
    cal = ensure_calibration(stream, h.family, runner, root, store, repeats)
    recipe_A = load_recipe(store, h.family) or seed_recipe(h.family)
    recipe_B = apply_edit(recipe_A, h.edit, created_by="human", hypothesis_id=h.hypothesis_id)
    done = [r for r in ledger.rows(h.family, "decision") if r.get("hypothesis_id") == h.hypothesis_id]
    if done:                                       # decided already: the ledger row stands, nothing is re-run
        return done[-1]
    if not [r for r in ledger.rows(h.family, "hypothesis") if r.get("hypothesis_id") == h.hypothesis_id]:
        ledger.append({"event": "hypothesis", "family": h.family, "hypothesis_id": h.hypothesis_id,
                       "recipe_from": recipe_A.version, "edit": h.edit.model_dump(),
                       "predicted_delta": h.predicted_delta, "rationale": h.rationale, "created_by": "human",
                       **({"check": True} if check else {})})
    # (resumed after a crash: the hypothesis row is already there and finished runs are reused, D73)
    res = experiment(recipe_A, h.edit, h.hypothesis_id, stream, runner, root, repeats)
    print(summary(res), flush=True)
    tools = default_registry()
    g = adapt_config()["gate"]
    v3 = cfg_gate_version() == "v3"
    if check and not v3:
        raise SystemExit("--check is a Gate v3 pre-registered check (D91)")
    quota = None if check or not v3 else ledger.hypotheses_used(h.family) + 1
    dec = decide(recipe_A, recipe_B, h, res, cal["noise"], ledger.tried_since_accept(h.family) + 1,
                 stream.heldout(h.family, everything=True), Envelope.from_registry(tools), sample_draft(res),
                 hypothesis_index=quota, alpha=float(g["v3"]["check_alpha"]) if check else None)
    row = ledger.append({**decision_row(h, recipe_A, recipe_B, dec, f"experiments/{h.hypothesis_id}/"),
                         **({"check": True} if check else {})})
    if check:                                      # D91: a person's test; the store and the experience log stay out
        return row
    mem = RecipeStore(store)
    mem.record(None, h.model_dump(mode="json"), row)
    if dec.decision == "accept":                   # Box 9 (D88): only the Gate's accept writes a version
        mem.commit(recipe_B, row)
    return row


# box: gate
def redecide(stream: Stream, hypothesis_id: str, root: Path, store: Path | None = None, version: str = "v2") -> dict:
    """D84b: decide a hypothesis again under `version` from its saved pairs — no new runs. The original rows are not
    touched; the new decision row is marked post_hoc and does not change the recipe store."""
    from amoeba.adapt.experimenter import Pair, ReplayResult, honesty_parts
    root = Path(root)
    ledger = Ledger(root / "ledger.jsonl")
    hyp = [r for r in ledger.rows(event="hypothesis") if r.get("hypothesis_id") == hypothesis_id][-1]
    orig = [r for r in ledger.rows(event="decision") if r.get("hypothesis_id") == hypothesis_id and not r.get("post_hoc")][-1]
    exp = root / "experiments" / hypothesis_id
    meta = json.loads((exp / "experiment.json").read_text(encoding="utf-8"))
    pairs = []
    for line in (exp / "pairs.jsonl").read_text(encoding="utf-8").splitlines():
        p = Pair.model_validate_json(line)
        upd = {}
        for arm in ("A", "B"):
            run = Path(getattr(p, f"run_{arm}"))
            run = run if run.is_absolute() else ROOT / run
            if not getattr(p, f"flags_{arm}") and (run / "result.json").exists():
                upd[f"flags_{arm}"] = honesty_parts(run)
        pairs.append(p.model_copy(update=upd))
    res = ReplayResult.model_validate({**meta, "pairs": [x.model_dump() for x in pairs]})
    h = Hypothesis.model_validate({"hypothesis_id": hypothesis_id, "family": hyp["family"], "edit": hyp["edit"],
                                   "predicted_delta": hyp["predicted_delta"], "rationale": hyp.get("rationale", "")})
    recipe_A = (load_recipe(store, h.family) if store else None)
    recipe_A = recipe_A if recipe_A is not None and recipe_A.version == orig["recipe_from"] else seed_recipe(h.family)
    recipe_B = apply_edit(recipe_A, h.edit, created_by="human", hypothesis_id=h.hypothesis_id)
    cal = ledger.calibration(h.family, res.recipe_A_hash, None)          # the Stage A slice had no slices file
    dec = decide(recipe_A, recipe_B, h, res, cal["noise"] if cal else orig["noise"], orig["N"],
                 stream.heldout(h.family, everything=True), Envelope.from_registry(default_registry()),
                 sample_draft(res), version=version)
    return ledger.append(decision_row(h, recipe_A, recipe_B, dec, orig["runs"], post_hoc=True))


# box: experimenter
def parse(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stream", required=True)
    p.add_argument("--family", required=True)
    p.add_argument("--edit", default=None, help="the hypothesis (YAML); omit with --calibrate-only")
    p.add_argument("--root", default=None, help="default eval/loop/<stream>")
    p.add_argument("--recipes", default=None, help="the recipe store recipe A comes from (default <root>/recipes)")
    p.add_argument("--repeats", type=int, default=None)
    p.add_argument("--parallel", type=int, default=None)
    p.add_argument("--calibrate-only", action="store_true", help="run the noise-floor calibration (A vs A') only")
    p.add_argument("--redecide", default=None, metavar="HYPOTHESIS_ID",
                   help="D84b: decide a hypothesis again from its saved pairs (no runs); the row is marked post_hoc")
    p.add_argument("--gate-version", default="v2", choices=["v1", "v2", "v3"], help="with --redecide")
    p.add_argument("--check", action="store_true",
                   help="D91: the single pre-registered check (Gate v3 at gate.v3.check_alpha, rows marked check, "
                        "outside the loop's quota, recipe store unchanged)")
    p.add_argument("--env-file", action="append", default=[], help="KEY=VALUE files for the runs (never printed)")
    return p.parse_known_args(argv)


# box: experimenter
def main(argv=None) -> int:
    args, passthrough = parse(argv)
    cfg = adapt_config().get("experiment", {})
    root = Path(args.root or ROOT / "eval" / "loop" / args.stream)
    stream = load_stream(args.stream)
    runner = SubprocessRunner([*experiment_flags(), *option_defaults(), *passthrough], env=load_env(args.env_file),
                              parallel=args.parallel or cfg.get("parallel", 8), scratch=root / "jobs")
    repeats = args.repeats or cfg.get("repeats", 3)
    store = Path(args.recipes or root / "recipes")
    if args.redecide:
        print(json.dumps(redecide(stream, args.redecide, root, store, args.gate_version), indent=2))
        return 0
    if args.calibrate_only:
        print(json.dumps(ensure_calibration(stream, args.family, runner, root, store, repeats)))
        return 0
    if not args.edit:
        print("give --edit or --calibrate-only")
        return 2
    h = Hypothesis.model_validate({"family": args.family, **yaml.safe_load(Path(args.edit).read_text(encoding="utf-8"))})
    row = hand_check(stream, h, runner, root, store, repeats, check=args.check)
    print(json.dumps(row, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
