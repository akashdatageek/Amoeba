"""D105 + D110 (amended) — the final-answer requirement check.

After the summariser writes the answer, plain code checks the FINAL answer (not the steps' claims): each requirement
of Box 2's list (D24/D35) against the answer, each file the plan promised against the workspace, and (D110) that
every web-sourced figure carries its source's date. Missing items earn the answer step one refine turn; what is still
missing after it goes into Limitations, and the run ends `no_deliverable` when a core deliverable is missing (no
answer content, a promised file never made, or more than half of the requirements unmet). requirement_status in
result.json is this final-answer result.

A requirement is met when the answer contains at least half of its key terms (content words of four letters or more
and its numbers, matched by their first five letters) and no BLOCKED line of the answer is about it (two key terms or
more); a requirement that asks for a file is met only when the file exists.

D105 (first version) — a run whose required deliverables are missing ends `no_deliverable`, not "no error".

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


GENERIC = {"answer", "provide", "provides", "include", "includes", "including", "final", "must", "should", "each",
           "every", "with", "their", "which", "that", "this", "these", "those", "from", "into", "about", "using",
           "show", "shows", "list", "give", "state", "write", "report", "clear", "short", "brief", "summary",
           "section", "user", "task", "based", "where", "when", "what", "will", "have", "been", "also", "plus"}


# box: runresult
def requirement_terms(text: str) -> list[str]:
    """A requirement's key terms: content words of four letters or more (first five letters) and its numbers."""
    words = [w[:5] for w in re.findall(r"[a-z][a-z-]{3,}", (text or "").lower()) if w not in GENERIC]
    nums = re.findall(r"\b\d[\d,.]*\d\b|\b\d\b", text or "")
    return list(dict.fromkeys(words + [n.replace(",", "") for n in nums]))


def _has_term(term: str, answer_words: set[str], answer: str) -> bool:
    return term in answer_words if term[0].isalpha() else term in answer.replace(",", "")


# box: runresult
def requirement_check(rid: str, text: str, answer: str, files_made: list[str] | None) -> dict:
    """One requirement against the final answer (and the workspace, for a file it asks for)."""
    terms = requirement_terms(text)
    words = {w[:5] for w in re.findall(r"[a-z][a-z-]{3,}", (answer or "").lower())}
    have = [t for t in terms if _has_term(t, words, answer or "")]
    blocked = [ln.strip()[:160] for ln in (answer or "").splitlines() if "BLOCKED" in ln
               and sum(_has_term(t, {w[:5] for w in re.findall(r"[a-z][a-z-]{3,}", ln.lower())}, ln) for t in terms) >= 2]
    files = promised_files({rid: text}) if files_made is not None else []
    made_names = {n.lower() for n in files_made or []}
    made_kinds = {EXT_KIND.get(Path(n).suffix.lower().lstrip(".")) for n in files_made or []}
    missing_files = [f["name"] or f"a {f['kind']} file" for f in files
                     if not ((f["name"] and f["name"].lower() in made_names) or f["kind"] in made_kinds)]
    covered = (len(have) / len(terms)) if terms else 1.0
    status = "blocked" if blocked else "missing" if missing_files or covered < 0.5 else "met"
    return {"id": rid, "text": text, "status": status, "coverage": round(covered, 2),
            "terms_missing": [t for t in terms if t not in have][:10], "files_missing": missing_files,
            "blocked": blocked[:3]}


# box: runresult
def final_check(answer: str | None, requirements: dict[str, str], plan_texts: dict[str, str],
                files_made: list[str] | None, undated: list[dict] | None = None, check_requirements: bool = True) -> dict:
    """The final-answer requirement check: requirements, promised files, answer content and undated web figures;
    `core_missing` names what makes the run no_deliverable."""
    chars = answer_content(answer)
    reqs = {r: requirement_check(r, t, answer or "", files_made) for r, t in (requirements or {}).items()} \
        if check_requirements else {}
    files = check_deliverables(answer, plan_texts, [{"path": n} for n in files_made] if files_made is not None else None) \
        if check_requirements else {"missing": [], "promised": []}
    unmet = [r for r, x in reqs.items() if x["status"] != "met"]
    never_made = list(dict.fromkeys(files["missing"] + [f for x in reqs.values() for f in x["files_missing"]]))
    core = (["no answer content"] if check_requirements and chars < MIN_ANSWER_CHARS else []) + \
        ([f"promised but not made: {', '.join(never_made)}"] if never_made else []) + \
        ([f"requirements not met: {', '.join(unmet)}"] if reqs and len(unmet) * 2 > len(reqs) else [])
    return {"answer_chars": chars, "requirements": reqs, "unmet": unmet, "promised": files["promised"],
            "files_missing": files["missing"], "files_made": files_made, "checked_files": files_made is not None,
            "undated": undated or [], "core_missing": core, "ok": not core and not unmet and not (undated or [])}


# box: runresult
def final_findings(fc: dict) -> list[str]:
    """What the answer step's refine turn is told: each unmet requirement, missing file and undated figure."""
    out = []
    for r in fc["unmet"]:
        x = fc["requirements"][r]
        why = (f"it is marked BLOCKED ({x['blocked'][0]})" if x["status"] == "blocked" else
               f"the file is not in the workspace: {', '.join(x['files_missing'])}" if x["files_missing"] else
               f"the answer does not cover: {', '.join(x['terms_missing'][:6])}")
        out.append(f"requirement {r} ({x['text'][:160]}) is not met in the final answer — {why}. Cover it in the "
                   f"answer from the steps' work, or say plainly under Limitations why it could not be done.")
    if fc["files_missing"]:
        out.append(f"the plan promised these files and the workspace does not have them: {', '.join(fc['files_missing'])}. "
                   f"Make them if the work allows, or say under Limitations that they were not made.")
    if fc["undated"]:
        from amoeba.interp.dates import dated_finding
        out.append(dated_finding(fc["undated"]))
    return out


# box: runresult
def no_deliverable_of(fc: dict | None) -> str | None:
    return "no_deliverable: " + "; ".join(fc["core_missing"]) if fc and fc.get("core_missing") else None
