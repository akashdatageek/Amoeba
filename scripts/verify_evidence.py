"""D95 — check an evidence log: the whole hash chain of eval/loop/<stream>/events.jsonl and every run-folder manifest
its rows name. Prints the first break (line, kind, detail) and exits 1 on one; exits 0 when everything holds.

    python -m scripts.verify_evidence --stream m2          # or --root <folder holding events.jsonl>, or --all
    python -m scripts.verify_evidence --branch evidence [--stream m2]   # GitHub's copy: commit chain heads + head copy
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from amoeba.adapt.evidence import verify, verify_branch

ROOT = Path(__file__).resolve().parents[1]


# box: evidence
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stream")
    p.add_argument("--root")
    p.add_argument("--all", action="store_true", help="every eval/loop/*/events.jsonl")
    p.add_argument("--branch", default=None, help="verify this evidence branch (origin/<branch>) instead of the local copy")
    p.add_argument("--no-fetch", action="store_true", help="with --branch: do not fetch first")
    args = p.parse_args(argv)
    if args.branch:
        res = verify_branch(ROOT, args.branch, args.stream, fetch=not args.no_fetch)
        print(json.dumps({"branch": args.branch, **res}))
        return 0 if res["ok"] else 1
    if not (args.stream or args.root or args.all):
        p.error("give --stream, --root, --all or --branch")
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
