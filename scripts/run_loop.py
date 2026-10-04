"""D89 — run the adaptation loop over a task stream (Phase 2 spec §11). Resumable: run it again after a crash.

    python -m scripts.run_loop --stream m1 --parallel 4 --parallel-until 8 --env-file keys.env \\
        --llm openai --profile gemma-api --timezone America/Chicago --llm-cache runs/cache

Everything under eval/loop/<stream>/: practice/ (one run per practice task), practice.jsonl, armA/ and experiments/
(Box 7), ledger.jsonl (Box 8), recipes/ (Box 9), architect/ (each proposal with its trace), diagnoses/,
human_queue.jsonl, loop_state.json, summary.json, REPORT.md, and events.jsonl (D95: the hash-chained evidence log;
check it with scripts/verify_evidence.py). Every flag this script does not know is passed to each
run_task run and to the Architect's client. Keys come from --env-file files and are never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from amoeba.adapt.evidence import secret_values
from amoeba.adapt.experimenter import SubprocessRunner, experiment_flags
from amoeba.adapt.loop import run_loop
from amoeba.adapt.recipe import adapt_config
from amoeba.adapt.stream import load_stream
from amoeba.safety.envelope import Envelope
from amoeba.tools.registry import default_registry
from scripts.run_experiment import OVERRIDES, load_env, option_defaults

ROOT = Path(__file__).resolve().parents[1]


# box: loop
def architect_llm(passthrough: list[str], stream: str):
    """The Architect's client: the same model flags as the runs, its own cache namespace per hypothesis."""
    from scripts.run_task import build_llm, parse_args

    def make(hypothesis_id: str):
        args = parse_args(["architect", "--topology", "plan", *passthrough,
                           "--llm-cache-namespace", f"{stream}-architect-{hypothesis_id}"])
        return build_llm(args)
    return make


# box: loop
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stream", required=True)
    p.add_argument("--root", default=None, help="default eval/loop/<stream>")
    p.add_argument("--repeats", type=int, default=None)
    p.add_argument("--parallel", type=int, default=None, help="runs at once (Gemma's per-minute limit: 4)")
    p.add_argument("--parallel-until", type=int, default=0,
                   help="run practice orders up to this one as one batch (the recipe cannot change before an alarm)")
    p.add_argument("--diagnoser", choices=["tier0", "none"], default="tier0",
                   help="none: the Architect gets the alarm only, every edit allowed (the ablation)")
    p.add_argument("--recipes-from", default=None, help="D88: start the stream's recipe store from another one")
    p.add_argument("--env-file", action="append", default=[])
    p.add_argument("--allow-model-edits", action="store_true",
                   help="D98: let the Architect propose prefer_model edits (off: one real model)")
    p.add_argument("--no-ship", action="store_true", help="D95: do not ship evidence to the evidence branch")
    args, passthrough = p.parse_known_args(argv)
    if args.allow_model_edits:
        os.environ["AMOEBA_ALLOW_MODEL_EDITS"] = "1"
    env = load_env(args.env_file)
    for k in OVERRIDES:                                  # the Architect's client is built in this process
        os.environ.pop(k, None)
    for k, v in env.items():
        os.environ.setdefault(k, v)
    cfg = adapt_config().get("experiment", {})
    root = Path(args.root or ROOT / "eval" / "loop" / args.stream)
    if args.recipes_from:
        from amoeba.memory.recipes import RecipeStore
        RecipeStore.warm_start(root / "recipes", args.recipes_from)
    stream = load_stream(args.stream)
    runner = SubprocessRunner([*experiment_flags(), *option_defaults(), *passthrough], env=env,
                              parallel=args.parallel or cfg.get("parallel", 8), scratch=root / "jobs")
    summary = run_loop(stream, runner, root, architect_llm(passthrough, stream.name),
                       repeats=args.repeats or cfg.get("repeats", 3), parallel_until=args.parallel_until,
                       diagnoser=args.diagnoser, envelope=Envelope.from_registry(default_registry()),
                       log=lambda m: print(m, flush=True), secrets=secret_values(env),
                       shipper="none" if args.no_ship else "config")
    print(json.dumps({k: summary[k] for k in ("alarms", "unresolved", "reverts")}, indent=2)[:3000])
    print(json.dumps({"decisions": [(d["hypothesis_id"], d["decision"], d["reasons"]) for d in summary["decisions"]],
                      "recipes": summary["recipes"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
