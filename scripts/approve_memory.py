"""D99 — the user's approval of a user-memory proposal: the only way a line enters `standards:` of the user context
file. The loop writes proposals to eval/loop/<stream>/memory_proposals.jsonl; nothing else writes user memory.

    python -m scripts.approve_memory --stream m2 --list
    python -m scripts.approve_memory --stream m2 --id P1 --context user.yaml [--text "Answers end with ..."]

The approval (text, time, proposal id) is added to the context file and logged in the stream's events.jsonl.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from amoeba.adapt.evidence import EvidenceLog
from amoeba.memory.context import approve_standard, read_proposals

ROOT = Path(__file__).resolve().parents[1]


# box: memory
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stream")
    p.add_argument("--root", help="the folder holding memory_proposals.jsonl (default eval/loop/<stream>)")
    p.add_argument("--list", action="store_true", help="print the proposals")
    p.add_argument("--id", help="the proposal to approve (P1, P2, ...)")
    p.add_argument("--context", help="the user context file (YAML) that receives the standard")
    p.add_argument("--text", help="your wording of the standard (default: the proposal's)")
    args = p.parse_args(argv)
    if not (args.stream or args.root):
        p.error("give --stream or --root")
    root = Path(args.root) if args.root else ROOT / "eval" / "loop" / args.stream
    props = read_proposals(root)
    if args.list or not args.id:
        for row in props:
            print(json.dumps(row, ensure_ascii=False))
        return 0
    prop = next((r for r in props if r["id"] == args.id), None)
    if prop is None:
        p.error(f"no proposal {args.id} in {root / 'memory_proposals.jsonl'}")
    if not args.context:
        p.error("give --context <user.yaml>")
    entry = approve_standard(args.context, prop, args.text, EvidenceLog(root))
    print(json.dumps(entry, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
