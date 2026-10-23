"""D164 — what Box 2 and Box 4 are shown from the lesson library (D163). Retrieval is plain code, no embeddings, and
reads lessons, never families (D167: a lesson's counts are only its own uses):

- the lesson is approved;
- it helped more often than it hurt, over every niche;
- it never hurt in this run's niche;
- for Box 4, its cause is the stuck step's cause (Box 2 takes any cause).

Entries seen in this run's niche come first, then the most-helped; at most `lessons.max_entries` entries and
`lessons.max_section_chars` characters. A lesson is a hint, never a license: a Box 4 edit must still quote this run's
evidence, and every plain-code check still applies."""
from __future__ import annotations

from amoeba.adapt.lessons import LessonLibrary, lessons_config


# box: lessons_read
def retrieve(lib: LessonLibrary, niche: str, cause: str | None = None, max_entries: int | None = None) -> list[dict]:
    cfg = lessons_config()
    n = int(cfg["max_entries"] if max_entries is None else max_entries)
    ok = [e for e in lib.lessons() if e.get("status") == "approved" and (e.get("lesson") or "").strip()
          and e["counts"]["helped"] > e["counts"]["hurt"]
          and not (e.get("by_niche", {}).get(niche) or {}).get("hurt")
          and (cause is None or e["cause"] == cause)]
    here = lambda e: (e.get("by_niche", {}).get(niche) or {}).get("helped", 0) > 0
    ok.sort(key=lambda e: (not here(e), -e["counts"]["helped"], e["id"]))
    return ok[:n]


# box: lessons_read
def _lines(entries: list[dict], max_chars: int, cause: bool) -> list[str]:
    out, used = [], 0
    for e in entries:
        c = e["counts"]
        line = ("- " + (f"[{e['id']}] " if cause else "") + f"{e['op']} ({e['scope']}" +
                ("" if cause else f", for {e['cause']}") +
                f"), helped {c['helped']}, hurt {c['hurt']}: {e['lesson']}")
        if used + len(line) > max_chars:
            break
        out.append(line)
        used += len(line) + 1
    return out


# box: lessons_read
def box4_section(entries: list[dict], max_chars: int | None = None) -> str:
    """The proposers' section ("" with nothing to show, so the prompt is unchanged)."""
    lines = _lines(entries, int(max_chars or lessons_config()["max_section_chars"]), cause=True)
    if not lines:
        return ""
    return ("\n\n# What helped before for this cause\nFrom earlier tasks, counted by plain code. A hint only: your "
            "edit must still quote this run's evidence in `because`, and every check still applies. If your edit "
            "follows one of these lessons, add \"from_lesson\": \"<its id in brackets>\" to your reply (its op and "
            "scope must be yours); plain code counts the result for that lesson only then.\n"
            + "\n".join(lines))


# box: lessons_read
def box2_section(entries: list[dict], max_chars: int | None = None) -> str:
    """The Planner's and the observers' section, through the drafting prompts' {lessons} slot."""
    lines = _lines(entries, int(max_chars or lessons_config()["max_section_chars"]), cause=False)
    if not lines:
        return ""
    return ("\n\n# Lessons from earlier tasks\nWhat helped stuck steps of earlier tasks, counted by plain code. Use "
            "one when this task has the same kind of step; none is required.\n" + "\n".join(lines))
