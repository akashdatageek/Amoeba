"""D33 — provenance: every number a step writes must be traceable, and plain code counts which ones are not.

A plan step is told to tag every number, price, date, law or benchmark figure with [S#] (a tool result) or
[unverified] (model knowledge). After the step, this module classifies each number in its output, line by line:

- cited       the line carries an [S#] tag that exists (the step's own sources or those of its inputs)
- unverified  the line carries [unverified]
- given       the number is in the task text
- derived     the step computed it: it is a calc result, or it follows "=" in a shown calculation
- inherited   it already appears in one of the step's input artifacts (checked when that step ran)
- untagged    none of the above: a figure with no source and no admission that it has none

An [S#] tag whose id the step could not have seen is a hallucinated citation. Nothing here rejects a step; the
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


def _derived(line: str, tok: str) -> bool:
    """The number is the result of a calculation shown on the line: '... = 10,000 GB' or '≈ 10 TB'."""
    return bool(re.search(r"[=≈]\s*~?\s*" + re.escape(tok), line))


def check_provenance(text: str, allowed_ids: set[str], task_text: str = "", inputs_text: str = "",
                     tool_results: list[str] | None = None) -> dict:
    given, inherited = numbers_in(task_text), numbers_in(inputs_text)
    computed = set().union(*(numbers_in(r) for r in (tool_results or []))) if tool_results else set()
    counts = {"cited": 0, "unverified": 0, "given": 0, "derived": 0, "inherited": 0, "untagged": 0}
    untagged, hallucinated = [], []
    for line in (text or "").splitlines():
        tags = [m.group(0) for m in TAG.finditer(line)]
        ids = [i.strip().upper() for t in tags if t.lower() != "[unverified]" for i in t.strip("[]").split(",")]
        bad = [i for i in ids if i not in allowed_ids]
        hallucinated += bad
        good = [i for i in ids if i in allowed_ids]
        for tok in _line_numbers(line):
            n = _norm(tok)
            if good:
                counts["cited"] += 1
            elif "[unverified]" in line.lower():
                counts["unverified"] += 1
            elif n in given:
                counts["given"] += 1
            elif n in computed or _derived(line, tok):
                counts["derived"] += 1
            elif n in inherited:
                counts["inherited"] += 1
            else:
                counts["untagged"] += 1
                untagged.append(tok)
    return {**counts, "numbers": sum(counts.values()), "hallucinated_citations": sorted(set(hallucinated)),
            "untagged_examples": untagged[:20]}


def total(per_step: list[dict]) -> dict:
    """The run's provenance: the per-step counts summed; hallucinated citations listed with their step."""
    keys = ("cited", "unverified", "given", "derived", "inherited", "untagged", "numbers")
    out = {k: sum(p.get(k, 0) for p in per_step) for k in keys}
    out["hallucinated_citations"] = sum(len(p.get("hallucinated_citations", [])) for p in per_step)
    return out
