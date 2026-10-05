"""D109 — the verifier's blind result against the worker's figures, by plain code.

A verify step first works out its own result without the outputs it checks (D90). Here plain code pairs the figures
of that blind result with the figures of the checked outputs by their labels (the words before the number on its
line, e.g. "BEV purchase price"), and compares the values with the rubric's tolerance (5% relative, or equal at the
coarser precision written). A labelled figure of the blind result that the outputs state only with different values
is a disagreement. Any disagreement makes the verify step `disputed`: the producers get one rework turn with both
values shown; if they still disagree after it, the step is partial and both values go into the answer's Limitations.
A PASS verdict never overrides a recorded disagreement. A figure the outputs do not state at all is not a
disagreement (it stays in D90's `own_only`).
"""
from __future__ import annotations

import re

from amoeba.interp.provenance import IDS, LIST_MARKER, NUM, TAG

TOLERANCE = 0.05            # the rubric's default relative tolerance (RubricNumber.tolerance)
MAX_DISPUTES = 10
STOP = {"the", "a", "an", "of", "for", "in", "on", "at", "to", "is", "are", "was", "were", "be", "per", "and", "or",
        "with", "by", "from", "its", "this", "that", "as", "about", "approx", "approximately", "around", "roughly",
        "estimated", "estimate", "est", "usd", "us", "dollars", "dollar", "it", "we", "our", "my", "which", "than",
        "each", "will", "would", "be", "has", "have", "value", "figure", "number", "amount", "result", "results",
        "s", "vs", "x", "e", "g", "i", "kwh", "mi", "mile", "miles", "year", "years", "yr", "month", "months",
        "should", "give", "gives", "given", "say", "says", "come", "comes", "equal", "equals", "get", "gets", "got",
        "find", "finds", "found", "show", "shows", "comes", "out", "about", "new", "own", "step", "steps"}


def _kind(body: str, m: re.Match) -> str:
    tok = m.group(0)
    if tok.endswith("%") or body[m.end():m.end() + 2].strip().startswith(("%", "percent")):
        return "%"
    return "$" if tok[:1] in "$€£" else "n"


# box: step_check
def labelled_figures(text: str) -> list[dict]:
    """Each figure of a text with the label before it on its line: list markers, [S#] tags, step labels, bare years
    and small counts (≤ 10) left out; a figure with no label word is left out too."""
    out = []
    for line in (text or "").splitlines():
        body = IDS.sub(" ", TAG.sub(" ", LIST_MARKER.sub("", line)))
        body = re.sub(r"[*_`|#]", " ", body)
        prev = 0
        for m in NUM.finditer(body):
            tok = m.group(0)
            bare = tok.strip("$€£%").replace(",", "")
            try:
                v = float(bare)
            except ValueError:
                continue
            plain = tok == bare and "." not in bare
            seg, prev = body[prev:m.start()], m.end()
            if plain and (1900 <= v <= 2100 or v <= 10):
                continue
            seg = re.split(r"[;(]|\.\s", seg)[-1]                     # the label starts after the last clause break
            words = [w for w in re.findall(r"[a-z][a-z0-9'-]*", seg.lower()) if w not in STOP]
            if not words:
                continue
            out.append({"label": words[-5:], "tok": tok, "value": v, "digits": len(bare.partition(".")[2]),
                        "kind": _kind(body, m), "line": line.strip()[:200]})
    return out


def _same_label(a: list[str], b: list[str]) -> int:
    """How well two labels match: at least two shared words, or the shorter one ends the longer one ("count" and
    "should give count"); 0 = not the same figure."""
    shared = len(set(a) & set(b))
    short, long_ = sorted((a, b), key=len)
    return shared if shared >= 2 or (short and long_[-len(short):] == short) else 0


def agree(a: float, da: int, b: float, db: int, tolerance: float = TOLERANCE) -> bool:
    d = min(da, db)
    return abs(round(a, d) - round(b, d)) < 1e-9 or abs(a - b) <= tolerance * max(abs(a), abs(b))


# box: step_check
def disputed_figures(own: str, outputs: dict[int, str], tolerance: float = TOLERANCE) -> list[dict]:
    """The labelled figures of the verifier's blind result that the checked outputs state under the same label only
    with a different value (beyond the tolerance): {label, verifier, worker, step, verifier_line, worker_line}."""
    theirs = [(d, f) for d, text in sorted(outputs.items()) for f in labelled_figures(text)]
    out, seen = [], set()
    for f in labelled_figures(own):
        cands = [(s, d, g) for d, g in theirs if g["kind"] == f["kind"] and (s := _same_label(f["label"], g["label"]))]
        if not cands or any(agree(f["value"], f["digits"], g["value"], g["digits"], tolerance) for _, _, g in cands):
            continue
        s, d, g = max(cands, key=lambda c: c[0])
        key = (" ".join(f["label"]), g["tok"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"label": " ".join(min(f["label"], g["label"], key=len)), "verifier": f["tok"], "worker": g["tok"], "step": d,
                    "verifier_line": f["line"], "worker_line": g["line"]})
    return out[:MAX_DISPUTES]


# box: step_check
def dispute_text(disputes: list[dict]) -> str:
    """The disagreements as rework issues: both values, where each comes from."""
    return "\n".join(f"- DISPUTED {x['label']}: step {x['step']} says {x['worker']} (\"{x['worker_line']}\"); the "
                     f"verifier's own result, worked out without your output, says {x['verifier']} "
                     f"(\"{x['verifier_line']}\"). Recheck it with its source or a calculation, then either correct "
                     f"it or show why your value is right." for x in disputes)
