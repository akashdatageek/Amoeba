"""D95 — check an evidence log: the whole hash chain of eval/loop/<stream>/events.jsonl and every run-folder manifest
its rows name. Prints the first break (line, kind, detail) and exits 1 on one; exits 0 when everything holds.

    python -m scripts.verify_evidence --stream m2          # or --root <folder holding events.jsonl>, or --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from amoeba.adapt.evidence import verify

ROOT = Path(__file__).resolve().parents[1]


# box: evidence
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--stream")
    g.add_argument("--root")
    g.add_argument("--all", action="store_true", help="every eval/loop/*/events.jsonl")
    args = p.parse_args(argv)
    roots = sorted(f.parent for f in (ROOT / "eval" / "loop").glob("*/events.jsonl")) if args.all else \
        [Path(args.root) if args.root else ROOT / "eval" / "loop" / args.stream]
    bad = 0
    for r in roots:
        res = verify(r)
        print(json.dumps({"root": str(r), **res}))
        bad += not res["ok"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
