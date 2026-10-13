"""D125 — the user's review of the tool library (data/tool_library/ by default; adapt.yaml `tool_writer.library`).

    python -m scripts.tool_library list
    python -m scripts.tool_library show <name>       # the manifest and the full code, to read before approving
    python -m scripts.tool_library approve <name>    # later tasks may use it (its self-test runs again first)
    python -m scripts.tool_library reject <name>     # never offered

Tools the tool writer made and a step used are saved "unreviewed"; nothing unreviewed or rejected is ever offered to
a task. Approving records the code's sha256 as reviewed, so a later edit of tool.py stops it being offered.
"""
from __future__ import annotations

import argparse
import json
import sys

from amoeba.adapt.toolmaker import ToolLibrary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.tool_library", description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", help="the library folder (default: adapt.yaml tool_writer.library)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for c in ("show", "approve", "reject"):
        sub.add_parser(c).add_argument("name")
    a = ap.parse_args(argv)
    lib = ToolLibrary(a.root)
    if a.cmd == "list":
        rows = lib.manifests()
        if not rows:
            print(f"no tools in {lib.root}")
        for m in rows:
            flag = "" if lib.intact(m) else "  (tool.py changed since it was saved or approved: not offered)"
            print(f"{m['name']:<28} {m.get('status', '?'):<11} {m.get('capability', ''):<24} {m.get('kind', ''):<5} "
                  f"task {m.get('task_id', '?')} · {m.get('saved_at', '')}{flag}")
        return 0
    m = lib.get(a.name)
    if m is None:
        print(f"no tool {a.name!r} in {lib.root}", file=sys.stderr)
        return 1
    if a.cmd == "show":
        print(json.dumps(m, indent=2, ensure_ascii=False))
        print("\n# ---- tool.py ----\n" + lib.text(a.name))
        return 0
    m = lib.set_status(a.name, "approved" if a.cmd == "approve" else "rejected")
    print(f"{m['name']}: {m['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
