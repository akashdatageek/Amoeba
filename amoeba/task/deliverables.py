"""D105 — a run whose required deliverables are missing ends `no_deliverable`, not "no error".

After a plan run, plain code checks what the team owes: an answer with content, and every file the plan promised.
A promised file is one a step's `output` or a Box 2 requirement names (`income.csv`) or asks for by kind ("a CSV
file", "an Excel workbook", "a PNG chart", "a Word memo"). A named file counts as made when the workspace holds a file
of that name, or else one of the same kind; a kind counts when the workspace holds a file of that kind. Files are
checked only with local tools on (without them no file can be made). The answer has content when, without headings,
BLOCKED lines and the plain-code Limitations section, it keeps at least MIN_ANSWER_CHARS characters.
"""
from __future__ import annotations

import re
from pathlib import Path

MIN_ANSWER_CHARS = 80
KINDS = {"csv": {"csv", "tsv"}, "xlsx": {"xlsx", "xlsm", "xls", "ods"}, "png": {"png", "jpg", "jpeg", "svg"},
         "docx": {"docx", "doc", "odt"}, "pdf": {"pdf"}, "pptx": {"pptx", "odp"}, "json": {"json"},
         "html": {"html", "htm"}}
EXT_KIND = {e: k for k, exts in KINDS.items() for e in exts}
FILE = re.compile(r"(?<![\w/.-])([\w][\w.-]*\.(" + "|".join(sorted(EXT_KIND, key=len, reverse=True)) + r"))\b", re.I)
WORDS = {"csv": r"\bcsv\b", "xlsx": r"\b(?:xlsx|excel|spreadsheet|workbook)\b",
         "png": r"\b(?:png|jpe?g|svg)\b|\b(?:chart|graph|plot) (?:image|file|picture)\b",
         "docx": r"\b(?:docx|word (?:document|file|memo))\b", "pdf": r"\bpdf (?:file|report|document)\b",
         "pptx": r"\b(?:pptx|powerpoint|slide deck)\b"}


# box: runresult
def promised_files(texts: dict[str, str]) -> list[dict]:
    """Every file the plan promised: {name or None, kind, where} from the step outputs and requirements."""
    out, seen = [], set()
    for where, text in texts.items():
        for m in FILE.finditer(text or ""):
            key = ("name", m.group(1).lower())
            if key not in seen:
                seen.add(key)
                out.append({"name": m.group(1), "kind": EXT_KIND[m.group(2).lower()], "where": where})
        named = {f["kind"] for f in out if f["where"] == where and f["name"]}
        for kind, pat in WORDS.items():
            if kind not in named and re.search(pat, text or "", re.I) and ("kind", kind) not in seen:
                seen.add(("kind", kind))
                out.append({"name": None, "kind": kind, "where": where})
    return out


# box: runresult
def answer_content(answer: str | None) -> int:
    """Characters of real content in the answer: headings, BLOCKED lines and the Limitations section left out."""
    text = re.split(r"^\s*#+\s*limitations\b", answer or "", flags=re.I | re.M)[0]
    keep = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")
            and "BLOCKED" not in ln]
    return len(re.sub(r"\s+", " ", " ".join(keep)).strip())


# box: runresult
def check_deliverables(answer: str | None, plan_texts: dict[str, str], files_created: list[dict] | None) -> dict:
    """{answer_chars, answer_ok, promised, missing, checked_files, ok}."""
    chars = answer_content(answer)
    promised = promised_files(plan_texts) if files_created is not None else []
    made = [Path(f.get("path", "")).name for f in files_created or []]
    made_kinds = {EXT_KIND.get(Path(n).suffix.lower().lstrip(".")) for n in made}
    missing = []
    for p in promised:
        if p["name"] and p["name"].lower() in {n.lower() for n in made}:
            continue
        if p["kind"] in made_kinds:
            continue
        missing.append(p["name"] or f"a {p['kind']} file")
    ok = chars >= MIN_ANSWER_CHARS and not missing
    return {"answer_chars": chars, "answer_ok": chars >= MIN_ANSWER_CHARS, "promised": promised, "missing": missing,
            "checked_files": files_created is not None, "files_made": made, "ok": ok}


# box: runresult
def no_deliverable_error(check: dict) -> str | None:
    if check["ok"]:
        return None
    what = (["no answer content"] if not check["answer_ok"] else []) + \
        ([f"promised but not made: {', '.join(check['missing'])}"] if check["missing"] else [])
    return "no_deliverable: " + "; ".join(what)
