"""Phase 2 week-1 check (spec §8): one hand-written hypothesis through Box 7 (the Experimenter) — and, from D84, Box 8.

    python -m scripts.run_experiment --stream m1 --family calc --edit edit.yaml \\
        --llm openai --profile gemma-api --timezone America/Chicago --llm-cache runs/cache --env-file keys.env

edit.yaml:
    hypothesis_id: h1-assumptions-rule
    edit: {op: add_planner_rule, params: {text: "..."}}
    predicted_delta: 0.15
    rationale: "..."

Recipe A is the family's current recipe in --recipes (default eval/loop/<stream>/recipes), else the empty seed
recipe. Every flag this script does not know is passed to each run_task run unchanged (model, cache, time zone…),
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
from amoeba.adapt.recipe import Edit, adapt_config, load_recipe, seed_recipe
from amoeba.adapt.stream import load_stream

ROOT = Path(__file__).resolve().parents[1]


# box: experimenter
def load_env(files: list[str]) -> dict:
    e = dict(os.environ)
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
    p.add_argument("--env-file", action="append", default=[], help="KEY=VALUE files for the runs (never printed)")
    return p.parse_known_args(argv)


# box: experimenter
def main(argv=None) -> int:
    args, passthrough = parse(argv)
    cfg = adapt_config().get("experiment", {})
    root = Path(args.root or ROOT / "eval" / "loop" / args.stream)
    stream = load_stream(args.stream)
    recipe_A = load_recipe(args.recipes or root / "recipes", args.family) or seed_recipe(args.family)
    runner = SubprocessRunner([*experiment_flags(), *option_defaults(), *passthrough], env=load_env(args.env_file),
                              parallel=args.parallel or cfg.get("parallel", 8), scratch=root / "jobs")
    repeats = args.repeats or cfg.get("repeats", 3)
    if args.calibrate_only:
        res = calibrate(recipe_A, stream, runner, root, repeats)
        print(summary(res))
        return 0
    if not args.edit:
        print("give --edit or --calibrate-only")
        return 2
    h = yaml.safe_load(Path(args.edit).read_text(encoding="utf-8"))
    res = experiment(recipe_A, Edit.model_validate(h["edit"]), h["hypothesis_id"], stream, runner, root, repeats)
    print(summary(res))
    print(json.dumps({"experiment": str(root / "experiments" / h["hypothesis_id"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
