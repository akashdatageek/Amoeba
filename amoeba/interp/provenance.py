"""D33 — provenance: every number a step writes must be traceable, and plain code counts which ones are not.

A plan step is told to tag every number, price, date, law or benchmark figure with [S#] (a tool result) or
[unverified] (model knowledge). After the step, this module classifies each number in its output, line by line:

- cited       the line carries an [S#] tag that exists (the step's own sources or those of its inputs)
- unverified  the line carries [unverified]
- given       the number is in the task text
- derived     the step computed it: it is a calc result, or it follows "=" in a shown calculation. D66: a number
              equal (to its shown precision) to a calc or local-tool result of the same step is derived even when
              the helper tagged it [unverified]; plain code removes that tag (strip_unverified)
- inherited   it already appears in one of the step's input artifacts (checked when that step ran)
- untagged    none of the above: a figure with no source and no admission that it has none

An [S#] tag whose id the step could not have seen is a hallucinated citation. D66: a number given in the task that
carries only a web source tag ([S#] of a search or fetched page that does not contain it) stays "given" and is
flagged (given_with_web_tag). Nothing here rejects a step; the
counts go into the step's artifact metadata, the trace and result.json.
"""
from __future__ import annotations

import re

TAG = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]|\[unverified\]", re.I)
NUM = re.compile(r"(?<![\w.])[$€£]?\d(?:[\d,]*\d)?(?:\.\d+)?%?")   # "$1.45M" -> $1.45, "10TB" -> 10
LIST_MARKER = re.compile(r"^\s*(?:[-*]\s*)?\d+[.)]\s")
IDS = re.compile(r"\b(?:S|R|Q|P|p|v|V|step|Step|phase|Phase|week|Week|day|Day|month|Month|wave|Wave)\s?\d+\b")


def _norm(n: str) -> str:
    return n.strip("$€£%").replace(",", "")


def numbers_in(text: str) -> set[str]:
    return {_norm(m.group(0)) for m in NUM.finditer(text or "")}


def _line_numbers(line: str) -> list[str]:
    body = LIST_MARKER.sub("", line)
    body = TAG.sub(" ", body)
    body = IDS.sub(" ", body)          # S3, R2, p95, "step 4", "Phase 1" are labels, not facts
    return [m.group(0) for m in NUM.finditer(body)]


# box: provenance
def claim_numbers(text: str) -> set[str]:
    """The numbers a text states as figures: list markers, [S#] tags and labels (step 3, R2, p95) left out."""
    return {_norm(t) for line in (text or "").splitlines() for t in _line_numbers(line)}


def _derived(line: str, tok: str) -> bool:
    """The number is the result of a calculation shown on the line: '... = 10,000 GB' or '≈ 10 TB'."""
    return bool(re.search(r"[=≈]\s*~?\s*" + re.escape(tok), line))


def _float(tok: str) -> float | None:
    try:
        return float(_norm(tok))
    except ValueError:
        return None


# box: provenance
def computed_values(results: list[str] | None) -> list[float]:
    """D66: every number in the calc and local-tool results of a step, as floats."""
    out = []
    for r in results or []:
        out += [v for v in (_float(m.group(0)) for m in NUM.finditer(r or "")) if v is not None]
    return out


def equals_computed(tok: str, values: list[float]) -> bool:
    """D66: the stated number is one of the computed values, rounded to the precision it is written with."""
    x = _float(tok)
    if x is None or not values:
        return False
    dec = len(_norm(tok).split(".")[1]) if "." in _norm(tok) else 0
    return any(abs(round(v, dec) - x) < 1e-9 or abs(v - x) < 1e-9 for v in values)


# box: provenance
def strip_unverified(text: str, values: list[float]) -> tuple[str, int]:
    """D66: remove an [unverified] tag that stands right after a number equal to a calc or local-tool result of the
    same step (the number is derived, not model knowledge). Returns the text and how many tags were removed."""
    if not values:
        return text, 0
    n = 0

    def fix(m: re.Match) -> str:
        nonlocal n
        if equals_computed(m.group(1), values):
            n += 1
            return m.group(1) + (m.group(2) if m.group(2).strip() else "")
        return m.group(0)
    out = re.sub(r"([$€£]?\d(?:[\d,]*\d)?(?:\.\d+)?%?)(\s*(?:[A-Za-z/]{1,6}\.?)?)\s*\[unverified\]", fix, text or "",
                 flags=re.I)
    return out, n


# box: provenance
def check_provenance(text: str, allowed_ids: set[str], task_text: str = "", inputs_text: str = "",
                     tool_results: list[str] | None = None, computed_results: list[str] | None = None,
                     web_ids: set[str] | None = None) -> dict:
    """computed_results: D66 — the step's calc and local-tool results (a number equal to one is derived, whatever
    its tag); web_ids: the ids of search / fetched-page sources (a task number cited only to one is flagged)."""
    given, inherited = numbers_in(task_text), numbers_in(inputs_text)
    computed = set().union(*(numbers_in(r) for r in (tool_results or []))) if tool_results else set()
    exact = computed_values(computed_results)
    web_ids = web_ids or set()
    counts = {"cited": 0, "unverified": 0, "given": 0, "derived": 0, "inherited": 0, "untagged": 0}
    untagged, hallucinated, figures, given_web = [], [], [], []
    for line in (text or "").splitlines():
        tags = [m.group(0) for m in TAG.finditer(line)]
        ids = [i.strip().upper() for t in tags if t.lower() != "[unverified]" for i in t.strip("[]").split(",")]
        bad = [i for i in ids if i not in allowed_ids]
        hallucinated += bad
        good = [i for i in ids if i in allowed_ids]
        for tok in _line_numbers(line):
            n = _norm(tok)
            if good and n in given and n not in computed and set(good) <= web_ids:
                st = "given"                                   # D66: a task number with a web tag it did not earn
                given_web.append(tok)
            elif good:
                st = "cited"
            elif equals_computed(tok, exact):
                st = "derived"                                 # D66: a calc / local result, whatever its tag
            elif "[unverified]" in line.lower():
                st = "unverified"
            elif n in given:
                st = "given"
            elif n in computed or _derived(line, tok):
                st = "derived"
            elif n in inherited:
                st = "inherited"
            else:
                st = "untagged"
                untagged.append(tok)
            counts[st] += 1
            figures.append({"n": n, "as": tok, "status": st, "sources": good})
    return {**counts, "numbers": sum(counts.values()), "hallucinated_citations": sorted(set(hallucinated)),
            "untagged_examples": untagged[:20], "figures": figures,   # D43: figures feed the run's ledger
            "given_with_web_tag": sorted(set(given_web))}


# box: provenance
def total(per_step: list[dict]) -> dict:
    """The run's provenance: the per-step counts summed; hallucinated citations listed with their step."""
    keys = ("cited", "unverified", "given", "derived", "inherited", "untagged", "numbers")
    out = {k: sum(p.get(k, 0) for p in per_step) for k in keys}
    out["hallucinated_citations"] = sum(len(p.get("hallucinated_citations", [])) for p in per_step)
    return out
