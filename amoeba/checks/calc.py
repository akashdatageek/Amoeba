"""D102 — the `calc` domain check: every figure in the final answer must be reproducible by calc from the stated
inputs — it is a number the task states, or a result of a calc (or local-tool) call made in this run, equal at the
precision it is written with (a figure an earlier step only wrote down does not count). Small counting numbers (0–10), years (1900–2100) and step/section
numbers are not figures. Only the answer step is checked; other steps pass."""
from __future__ import annotations

import re

from amoeba.interp.provenance import computed_values, equals_computed

FIGURE = re.compile(r"(?<![\w.])-?\$?\d[\d,]*(?:\.\d+)?%?(?![\w])")


# box: niche
def figures(text: str) -> list[str]:
    out = []
    for m in FIGURE.finditer(text or ""):
        tok = m.group(0)
        num = tok.replace("$", "").replace(",", "").rstrip("%")
        try:
            v = float(num)
        except ValueError:
            continue
        bare = tok.isdigit()                          # no $, comma, % or decimals: maybe a year or a count
        if (bare and 0 <= v <= 10) or (bare and len(tok) == 4 and 1900 <= v <= 2100):
            continue
        out.append(num)
    return out


# box: niche
def check(output: str, evidence: dict) -> tuple[bool, str]:
    if not evidence.get("answer_step"):
        return True, "not the answer step"
    stated = computed_values([evidence.get("task", "")])     # the task's own figures; an earlier step's are not inputs
    computed = computed_values(evidence.get("computed") or [])
    loose = [f for f in figures(output) if not equals_computed(f, stated + computed)]
    if loose:
        return False, ("figures not reproducible by calc from the stated inputs: " + ", ".join(dict.fromkeys(loose))[:300]
                       + " — compute each with calc from the task's numbers, or drop it")
    return True, "every figure is a stated input or a calc result"
