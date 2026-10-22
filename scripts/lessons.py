"""D163 — the user's review of the lesson library (data/lessons/ by default; adapt.yaml `lessons.library`).

    python -m scripts.lessons list                 # every entry: status, counts, tasks, whether it has a lesson
    python -m scripts.lessons show <id>            # the cue, the lesson, the counts per niche and the evidence
    python -m scripts.lessons approve <id>         # later tasks may be shown it (--lessons on, D164)
    python -m scripts.lessons reject <id>          # never shown

Box 4 counts every verdict and saves new entries "unreviewed"; nothing unreviewed or rejected is ever shown to a task.
One library serves every task: an entry is (cause, op, scope), and the niche of each count is only recorded.
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
        rows = sorted(lib.entries(), key=lambda e: -e["counts"]["helped"])
        if not rows:
            print(f"no lessons in {lib.root}")
        for e in rows:
            c = e["counts"]
            print(f"{e['id']:<48} {e['status']:<16} helped {c['helped']:>3} hurt {c['hurt']:>3} "
                  f"none {c['no_effect']:>3} conf {c['confounded']:>3} · {len(e['task_ids'])} task(s) · "
                  f"{'lesson' if e.get('lesson') else 'no lesson yet'}")
        return 0
    e = lib.get(a.id)
    if e is None:
        print(f"no lesson {a.id!r} in {lib.root}", file=sys.stderr)
        return 1
    if a.cmd == "show":
        print(json.dumps(e, indent=2, ensure_ascii=False))
        print("\n# ---- EXPERIENCE.md ----\n" + (lib.root / a.id / "EXPERIENCE.md").read_text(encoding="utf-8"))
        return 0
    e = lib.set_status(a.id, "approved" if a.cmd == "approve" else "rejected")
    print(f"{e['id']}: {e['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
