"""D109 (amended) — the disagreement resolver.

A verify step first works out its own result without the outputs it checks (D90). Plain code pairs the figures of
that blind result with the figures of the checked outputs by their labels (the words before the number on its line,
e.g. "BEV purchase price") and compares the values with the rubric's tolerance (5% relative, or equal at the coarser
precision written). A labelled figure the outputs state only with a different value is a disagreement.

Every disagreement goes to the resolver: one separate, fresh call (plan_resolve.txt) whose only job is to settle each
disputed figure against the source text the team was shown, a fresh fetch, a calculation, or a re-run in the sandbox.
For each figure it writes a value, its evidence (a quote copied from the source, or a command and its output) and a
verdict. Plain code disposes: a quote must be in the source text and state the value, or the value must be in the
resolver's own tool output; otherwise the figure is unresolved. The value plain code accepts replaces the wrong one in
the producer's output; an unresolved figure keeps the step from PASS, makes it partial and goes into Limitations.
Every dispute and every resolution is logged. A figure the outputs do not state at all is not a disagreement (it stays
in D90's `own_only`).
"""
from __future__ import annotations

import re

from amoeba.interp.citecheck import norm
from amoeba.interp.provenance import IDS, LIST_MARKER, NUM, TAG, computed_values

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


def _value(tok: str | None) -> tuple[float, int] | None:
    m = NUM.search(tok or "")
    if not m:
        return None
    bare = m.group(0).strip("$€£%").replace(",", "")
    try:
        return float(bare), len(bare.partition(".")[2])
    except ValueError:
        return None


# box: step_check
def parse_resolution(text: str) -> dict[int, dict]:
    """The resolver's blocks: figure number -> {value, evidence, verdict} (missing fields are empty)."""
    out = {}
    for m in re.finditer(r"(?ims)^\s*#*\s*figure\s+(\d+)\b(.*?)(?=^\s*#*\s*figure\s+\d+\b|\Z)", text or ""):
        body = m.group(2)
        field = lambda name: (re.search(rf"(?im)^\s*{name}\s*:\s*(.+)$", body) or [None, ""])[1].strip()
        out[int(m.group(1))] = {"value": field("value"), "evidence": field("evidence"),
                                "verdict": field("verdict").upper().split()[0] if field("verdict") else ""}
    return out


# box: step_check
def settle(text: str, disputes: list[dict], sources: dict[str, str], tool_results: list[str]) -> list[dict]:
    """Plain code's verdict on each disputed figure from the resolver's reply: worker (its value stands), verifier
    (the check's value), corrected (a third value) or unresolved — only with evidence code can find."""
    blocks, ran = parse_resolution(text), computed_values(tool_results)
    out = []
    for i, d in enumerate(disputes, 1):
        r = blocks.get(i, {"value": "", "evidence": "", "verdict": ""})
        got = _value(r["value"])
        kind = None
        if got is not None:
            v, dv = got
            for q in re.findall(r"[\"“]([^\"”]{4,400})[\"”]", r["evidence"]):
                inside = [t for t in sources.values() if norm(q).strip(" .,;:") in norm(t)]
                if inside and any(agree(v, dv, x, dx) for x, dx in filter(None, map(_value, NUM.findall(q)))):
                    kind = "source"
                    break
            if kind is None and any(agree(v, dv, x, 6) for x in ran):
                kind = "command"
        verdict = "unresolved"
        if kind is not None:
            wv, cv = _value(d["worker"]), _value(d["verifier"])
            verdict = "worker" if wv and agree(v, dv, *wv) else "verifier" if cv and agree(v, dv, *cv) else "corrected"
        out.append({**{k: d[k] for k in ("label", "worker", "verifier", "step")},
                    "value": r["value"][:60] if kind else None, "evidence": r["evidence"][:400],
                    "evidence_kind": kind, "verdict": verdict, "verdict_model": r["verdict"] or None})
    return out


# box: step_check
def disputes_text(disputes: list[dict], sources: dict[str, str]) -> str:
    """What the resolver is shown: each disputed figure, both lines, and the source text behind them."""
    blocks = []
    for i, x in enumerate(disputes, 1):
        ids = sorted(set(re.findall(r"S\d+", x["worker_line"] + " " + x["verifier_line"])), key=lambda s: int(s[1:]))
        src = "\n".join(f"[{s}] {sources[s][:1500].strip()}" for s in ids if sources.get(s)) or \
            "(no source text was cited for it: fetch it again, recompute it or re-run it)"
        blocks.append(f"## Figure {i}: {x['label']}\nThe worker (step {x['step']}) wrote: {x['worker_line']}\n"
                      f"The independent check wrote: {x['verifier_line']}\nSource text the team was shown:\n{src}")
    return "\n\n".join(blocks)


# box: step_check
def replace_figure(text: str, line: str, old: str, new: str) -> tuple[str, bool]:
    """The producer's output with `old` replaced by `new` on the line that starts like `line` (one place only)."""
    key = line.strip()[:60]
    out, done = [], False
    for ln in (text or "").split("\n"):
        if not done and key and ln.strip().startswith(key) and old in ln:
            ln, done = ln.replace(old, new, 1), True
        out.append(ln)
    return "\n".join(out), done
