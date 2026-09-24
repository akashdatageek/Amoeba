"""Deterministic scoring for toy tasks. No AI judge in Phase 1 (that is Phase 2, as a signal only)."""
from __future__ import annotations

import re


def normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower()).rstrip(".").strip()


def score(answer: str | None, ground_truth: str | None) -> float | None:
    """1.0 / 0.0 after trimming spaces and case; None when there is no known answer."""
    if ground_truth is None or answer is None:
        return None
    return 1.0 if normalise(answer) == normalise(ground_truth) else 0.0


# ---- D30: rubric scoring for tasks without a single right answer (deterministic; no LLM judge) -------------------
_BYTES = {"b": 1, "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12, "pb": 1e15,
          "kib": 2 ** 10, "mib": 2 ** 20, "gib": 2 ** 30, "tib": 2 ** 40, "pib": 2 ** 50}
_BINARY = {"kb": "kib", "mb": "mib", "gb": "gib", "tb": "tib", "pb": "pib"}   # a model may write TB and mean TiB
_SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6, "bn": 1e9, "b": 1e9, "billion": 1e9}
_CURRENCY = {"$": "usd", "usd": "usd", "us$": "usd", "€": "eur", "eur": "eur", "£": "gbp", "gbp": "gbp"}
_QTY = re.compile(
    r"(?P<cur>US\$|\$|€|£|USD|EUR|GBP)?\s?(?P<num>\d[\d,]*(?:\.\d+)?|\.\d+)\s?"
    r"(?P<unit>KiB|MiB|GiB|TiB|PiB|KB|MB|GB|TB|PB|million|billion|thousand|bn|mn|[kKMB](?![a-zA-Z])|USD|EUR|GBP)?",
    re.I)


def quantities(text: str) -> list[dict]:
    """Every number in `text` with what it measures: {"kind": "bytes"|"usd"|"eur"|"gbp"|"plain", "values": [...]}.
    Byte amounts carry both readings of a decimal unit (TB and TiB) so an answer computed in binary units is not
    marked wrong; money is scaled by million/billion/k/M/B."""
    out = []
    for m in _QTY.finditer(text or ""):
        try:
            n = float(m.group("num").replace(",", ""))
        except ValueError:
            continue
        unit, cur = (m.group("unit") or "").lower(), (m.group("cur") or "").lower()
        if unit in _BYTES:
            vals = [n * _BYTES[unit]] + ([n * _BYTES[_BINARY[unit]]] if unit in _BINARY else [])
            out.append({"kind": "bytes", "values": vals, "text": m.group(0).strip()})
            continue
        scale = _SCALE.get(unit, 1.0)
        kind = _CURRENCY.get(cur) or _CURRENCY.get(unit) or "plain"
        if kind == "plain" and unit in ("b",):   # a bare 'B' after a number without a currency is ambiguous
            scale = 1.0
        out.append({"kind": kind, "values": [n * scale], "text": m.group(0).strip()})
    return out


def number_found(text: str, value: float, unit: str, tolerance: float = 0.05) -> str | None:
    """The first quantity in `text` equal to value+unit within the relative tolerance (either reading of a byte
    unit), as written; None if there is none. Money may also be written without a currency sign."""
    u = unit.lower()
    if u in _BYTES:
        target, kinds = value * _BYTES[u], {"bytes"}
    else:
        target, kinds = value * _SCALE.get(u, 1.0), {_CURRENCY.get(u, u), "plain"}
    for q in quantities(text):
        if q["kind"] in kinds and any(abs(v - target) <= tolerance * abs(target) for v in q["values"]):
            return q["text"]
    return None


def _any(text: str, patterns: list[str]) -> str | None:
    for p in patterns:
        m = re.search(p, text or "", re.I)
        if m:
            return m.group(0)
    return None


def rubric_score(answer: str | None, rubric, judge=None) -> dict:
    """Per-item pass/fail and the overall fraction, by string/regex/number match only. `judge`, if given, is called
    as judge(answer, rubric) and its result is stored under "judge" as a separate signal that never changes the score
    (the hook for a later LLM judge)."""
    text = answer or ""
    items = []
    for d in rubric.required_deliverables:
        ev = _any(text, d.any_of)
        items.append({"kind": "deliverable", "name": d.name, "pass": ev is not None, "evidence": ev})
    for x in rubric.expected_numbers:
        ev = number_found(text, x.value, x.unit, x.tolerance)
        items.append({"kind": "number", "name": x.name, "pass": ev is not None, "evidence": ev,
                      "expected": f"{x.value:g} {x.unit} ±{x.tolerance:.0%}"})
    for c in rubric.constraints_to_respect:
        ev = _any(text, c.any_of)
        items.append({"kind": "constraint", "name": c.name, "pass": ev is not None, "evidence": ev})
    for mn in rubric.must_not:
        bad = []
        for m in re.finditer(mn.pattern, text, re.I):
            window = text[max(0, m.start() - mn.window): m.end() + mn.window]
            if not (mn.unless_nearby and re.search(mn.unless_nearby, window, re.I)):
                bad.append(m.group(0))
        items.append({"kind": "must_not", "name": mn.name, "pass": not bad, "evidence": bad[:5] or None})
    passed = sum(i["pass"] for i in items)
    return {"items": items, "passed": passed, "total": len(items),
            "score": round(passed / len(items), 3) if items else None,
            "judge": judge(answer, rubric) if judge else None}
