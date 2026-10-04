"""D100 — prune a family's recipe on demand: each line (rule, transform, run option, model preference) is removed one
at a time and replayed against the recipe with it on the gate set; a line whose removal loses nothing beyond noise
and lowers cost goes. Each prune is a Gate decision in the ledger (`prune: true`) and an events.jsonl row.

    python -m scripts.prune_recipe --stream m2 --family calc [--repeats 3] [--parallel 4] [--env-file gemma.env]
    (the loop does the same at the end of a stream unless --prune off)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from amoeba.adapt.evidence import EvidenceLog, make_shipper, run_finished, secret_values
from amoeba.adapt.experimenter import SubprocessRunner, experiment_flags
from amoeba.adapt.ledger import Ledger
from amoeba.adapt.recipe import adapt_config
from amoeba.adapt.retention import prune_family
from amoeba.adapt.stream import load_stream
from amoeba.memory.recipes import RecipeStore
from scripts.run_experiment import (cfg_gate_version, ensure_calibration, load_env, load_ship_state, option_defaults,
                                    ship)

ROOT = Path(__file__).resolve().parents[1]


# box: prune
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stream", required=True)
    p.add_argument("--family", action="append", default=[], help="default: every family of the stream")
    p.add_argument("--root", default=None, help="default eval/loop/<stream>")
    p.add_argument("--repeats", type=int, default=None)
    p.add_argument("--parallel", type=int, default=None)
    p.add_argument("--no-ship", action="store_true", help="D95: do not ship evidence to the evidence branch")
    p.add_argument("--env-file", action="append", default=[], help="KEY=VALUE files for the runs (never printed)")
    args, passthrough = p.parse_known_args(argv)
    cfg = adapt_config().get("experiment", {})
    root = Path(args.root or ROOT / "eval" / "loop" / args.stream)
    stream = load_stream(args.stream)
    env = load_env(args.env_file)
    runner = SubprocessRunner([*experiment_flags(), *option_defaults(), *passthrough], env=env,
                              parallel=args.parallel or cfg.get("parallel", 8), scratch=root / "jobs")
    repeats = args.repeats or cfg.get("repeats", 3)
    store, ledger, ev = RecipeStore(root / "recipes"), Ledger(root / "ledger.jsonl"), EvidenceLog(root)
    shipper = None
    if not args.no_ship:
        st = load_ship_state(root)
        shipper = make_shipper(root, stream.name, secret_values(env), st.get("unshipped"), st.get("ship_state"))
        runner.on_done = lambda rec: rec.run_dir and (run_finished(ev, root, Path(rec.run_dir), shipper),
                                                      ship(root, shipper))
    out = []
    for fam in args.family or stream.families():
        cal = ensure_calibration(stream, fam, runner, root, store.root, repeats)
        out += prune_family(stream, fam, store, ledger, runner, root, repeats, cal["noise"], ev,
                            lambda m: print(m, flush=True), cfg_gate_version())
    print(json.dumps([{k: r.get(k) for k in ("hypothesis_id", "line", "decision", "reasons")} for r in out], indent=2))
    if shipper is not None:
        ship(root, shipper, force=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
