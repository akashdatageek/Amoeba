"""D163 — the user's review of the lesson library (data/lessons/ by default; adapt.yaml `lessons.library`).

    python -m scripts.lessons list                 # every family (all verdicts) and its lessons (their own uses)
    python -m scripts.lessons show <id>            # a family or a lesson: counts per niche and the evidence
    python -m scripts.lessons approve <lesson id>  # later tasks may be shown it (--lessons on, D164)
    python -m scripts.lessons reject <lesson id>   # never shown

Box 4 counts every verdict in its family and saves each written lesson as its own "unreviewed" entry (D167); nothing
unreviewed or rejected is ever shown to a task. One library serves every task: a family is (cause, op, scope), and the
niche of each count is only recorded.
"""
from __future__ import annotations

import argparse
import json
import sys

from amoeba.adapt.lessons import LessonLibrary


# box: lessons
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.lessons", description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", help="the library folder (default: adapt.yaml lessons.library)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for c in ("show", "approve", "reject"):
        sub.add_parser(c).add_argument("id")
    a = ap.parse_args(argv)
    lib = LessonLibrary(a.root)
    if a.cmd == "list":
        fams = sorted(lib.entries(), key=lambda e: -e["counts"]["helped"])
        if not fams:
            print(f"no lessons in {lib.root}")
        for f in fams:                                   # D167: the family (every verdict), then its own lessons
            c = f["counts"]
            print(f"{f['id']:<48} family           helped {c['helped']:>3} hurt {c['hurt']:>3} "
                  f"none {c['no_effect']:>3} conf {c['confounded']:>3} · {len(f['task_ids'])} task(s)")
            for e in sorted(lib.lessons(f["id"]), key=lambda e: e["id"]):
                c = e["counts"]
                print(f"  {e['id']:<46} {e['status']:<16} helped {c['helped']:>3} hurt {c['hurt']:>3} "
                      f"none {c['no_effect']:>3} conf {c['confounded']:>3} · {len(e['task_ids'])} task(s) · "
                      f"{e['lesson'][:70]}")
        return 0
    e = lib.get(a.id)
    if e is None:
        print(f"no lesson {a.id!r} in {lib.root}", file=sys.stderr)
        return 1
    if a.cmd == "show":
        print(json.dumps(e, indent=2, ensure_ascii=False))
        print("\n# ---- EXPERIENCE.md ----\n" + (lib.root / a.id / "EXPERIENCE.md").read_text(encoding="utf-8"))
        return 0
    if lib.lesson(a.id) is None:
        print(f"{a.id!r} is a family; approve or reject one of its lessons (python -m scripts.lessons list)",
              file=sys.stderr)
        return 1
    e = lib.set_status(a.id, "approved" if a.cmd == "approve" else "rejected")
    print(f"{e['id']}: {e['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
