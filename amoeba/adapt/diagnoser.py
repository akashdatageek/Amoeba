"""D86 — Box 5, the Diagnoser, tier 0 (Phase 2 spec §6). Plain code: Phase 1 already records why each step failed, so
the Diagnoser counts the records of the alarm's window instead of guessing.

Over the window's run folders it counts: D61 causes per step (with the step's kind, its roles and their tools);
blocked capabilities, contract findings (missing, unused), unverified checks, claimed files missing; honesty signals
(hallucinated citations, mislabelled citations, cited figures left out of the answer); failed rubric item names (the
feedback channel). The cause is the one that rose most from the reference runs to the window (the alarm is a change;
a cause that was always there does not explain it), then the most frequent, then the table order. The allowed edits
come from the cause → edit table in amoeba/config/adapt.yaml. `--diagnoser none` (diagnose_none) hands the Architect
the alarm only, with every edit allowed — the untargeted baseline.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from amoeba.adapt.monitor import Alarm, PracticeRecord
from amoeba.adapt.recipe import EDIT_OPS, adapt_config
from amoeba.adapt.stream import Stream, assert_practice


# box: diagnoser
class Diagnosis(BaseModel):
    family: str
    symptom: str
    cause: Literal["capability", "checks", "max_turns", "unused_tool", "claimed_file_missing", "feedback", "honesty",
                   "alarm_only"]
    where: dict = Field(default_factory=dict)          # a Selector-shaped hint
    evidence: list[str] = Field(default_factory=list)  # short quotes: step file + field + value, at most 8
    counts: dict[str, int] = Field(default_factory=dict)
    allowed_edits: list[str] = Field(default_factory=list)
    examples: list[dict] = Field(default_factory=list) # practice examples for the Architect (practice tasks only)
    alarm: dict = Field(default_factory=dict)
    shares: dict[str, dict] = Field(default_factory=dict)   # cause -> {"window": share, "reference": share}


def _load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _steps(run_dir: Path) -> list[dict]:
    return [s for f in sorted((run_dir / "artifacts").glob("step_*.json")) if (s := _load(f))]


def _plan(run_dir: Path) -> dict:
    return _load(run_dir / "plan.json")


# box: diagnoser
def run_signals(run_dir: str | Path, failed_items: list[str]) -> dict:
    """What one run shows, by cause: {cause: [evidence lines]} and the raw counts."""
    d = Path(run_dir)
    r = _load(d / "result.json")
    plan = _plan(d)
    by_step = {s.get("index", i) + 1: s for i, s in enumerate(plan.get("plan") or [])}
    tools = {x.get("name"): x.get("tools", []) for x in plan.get("created_roles") or []}
    out: dict[str, list[str]] = {}
    counts: Counter = Counter()
    for s in _steps(d):
        n = s.get("step")
        f = f"{d.name}/artifacts/step_{n}.json"
        for c in s.get("causes") or []:
            out.setdefault(c, []).append(f"{f} causes {c} (kind {(by_step.get(n) or {}).get('kind') or 'work'}, "
                                         f"roles {s.get('roles')})")
            counts[f"cause:{c}"] += 1
        for k in ("blocked_canonical", "contract_missing", "unused", "claimed_files_missing"):
            for v in s.get(k) or []:
                counts[k] += 1
                cause = {"blocked_canonical": "capability", "contract_missing": "capability", "unused": "unused_tool",
                         "claimed_files_missing": "claimed_file_missing"}[k]
                out.setdefault(cause, []).append(f"{f} {k} {v}")
        if s.get("unverified_check"):
            counts["unverified_check"] += 1
            out.setdefault("honesty", []).append(f"{f} unverified_check true")
        for m in s.get("mislabelled_citations") or []:
            counts["mislabelled_citations"] += 1
            out.setdefault("honesty", []).append(f"{f} mislabelled_citations {m.get('source')} {m.get('claim')}")
    hall = int(((r.get("provenance") or {}).get("total") or {}).get("hallucinated_citations") or 0)
    if hall:
        counts["hallucinated_citations"] += hall
        out.setdefault("honesty", []).append(f"{d.name}/result.json provenance.total.hallucinated_citations {hall}")
    for v in (r.get("summary_check") or {}).get("cited_figures_left_out") or []:
        counts["cited_figures_left_out"] += 1
        out.setdefault("honesty", []).append(f"{d.name}/result.json summary_check.cited_figures_left_out {v}")
    for item in failed_items:
        counts[f"feedback:{item}"] += 1
        out.setdefault("feedback", []).append(f"{d.name}/result.json rubric failed item {item!r}")
    return {"by_cause": out, "counts": counts, "tools": tools, "steps_by_n": by_step}


def _allowed(cause: str) -> list[str]:
    return list(adapt_config()["diagnoser"]["allowed_edits"].get(cause, []))


# box: diagnoser
def diagnose(alarm: Alarm, records: list[PracticeRecord], stream: Stream) -> Diagnosis:
    """Box 5: count the window's run records, name the cause that rose most, and say which edits may answer it."""
    c = adapt_config()["diagnoser"]
    by_order = {r.order: r for r in records}
    window = [by_order[o] for o in alarm.window_orders if o in by_order]
    ref = [by_order[o] for o in alarm.reference_orders if o in by_order]
    sig_w = [run_signals(r.run_dir, r.failed_items) for r in window]
    sig_r = [run_signals(r.run_dir, r.failed_items) for r in ref]

    def share(sigs, cause):
        return sum(bool(s["by_cause"].get(cause)) for s in sigs) / len(sigs) if sigs else 0.0
    order = list(c["causes"])
    shares = {k: {"window": round(share(sig_w, k), 3), "reference": round(share(sig_r, k), 3)} for k in order}
    present = [k for k in order if shares[k]["window"] > 0]
    if not present:
        cause = "feedback" if any(r.failed_items for r in window) else order[0]
    else:
        cause = sorted(present, key=lambda k: (-(shares[k]["window"] - shares[k]["reference"]),
                                               -shares[k]["window"], order.index(k)))[0]
    counts: Counter = Counter()
    for s in sig_w:
        counts += s["counts"]
    evidence = [e for s in sig_w for e in s["by_cause"].get(cause, [])][: int(c["max_evidence"])]
    items = Counter(i for r in window for i in r.failed_items)
    if cause == "feedback" and items:
        name, n = items.most_common(1)[0]
        symptom = f"feedback: {name} missing in {n}/{len(window)} runs"
        where = {"last_work_step": True}
    else:
        n = sum(bool(s["by_cause"].get(cause)) for s in sig_w)
        symptom = f"{cause} in {n}/{len(window)} runs (reference {shares[cause]['reference']:.0%})"
        where = _where(cause, sig_w)
    return Diagnosis(family=alarm.family, symptom=symptom, cause=cause, where=where, evidence=evidence,
                     counts=dict(sorted(counts.items())), allowed_edits=_allowed(cause),
                     examples=examples(window, sig_w, cause, stream, int(c["examples"])),
                     alarm=alarm.model_dump(), shares=shares)


def _where(cause: str, sigs: list[dict]) -> dict:
    """A Selector-shaped hint: the step kind where the cause shows most, and a tool its roles hold."""
    kinds: Counter = Counter()
    tools: Counter = Counter()
    for s in sigs:
        for line in s["by_cause"].get(cause, []):
            if "(kind " in line:
                kinds[line.split("(kind ")[1].split(",")[0]] += 1
        for t in s["tools"].values():
            tools.update(t)
    out = {}
    if kinds:
        out["step_kind"] = kinds.most_common(1)[0][0]
    if tools:
        out["roles_with_tool"] = tools.most_common(1)[0][0]
    return out


def examples(window: list[PracticeRecord], sigs: list[dict], cause: str, stream: Stream, k: int) -> list[dict]:
    """Up to k practice examples: the task prompt, the failing (else the answer) step's do / output / done_when, and
    the evidence lines. Held-out tasks never appear here."""
    tasks = {t.id: t for t in stream.practice()}
    out = []
    pairs = sorted(zip(window, sigs), key=lambda rs: not rs[1]["by_cause"].get(cause))   # runs showing the cause first
    for r, s in pairs:
        if len(out) >= k or r.task_id not in tasks:
            continue
        assert_practice(tasks[r.task_id])
        steps = s["steps_by_n"]
        bad = [int(line.split("step_")[1].split(".json")[0]) for line in s["by_cause"].get(cause, [])
               if "/artifacts/step_" in line]
        n = bad[0] if bad else (max(steps) if steps else None)
        st = steps.get(n, {}) if n else {}
        out.append({"task": tasks[r.task_id].prompt, "step": n, "do": st.get("do", ""), "output": st.get("output", ""),
                    "done_when": st.get("done_when", ""), "evidence": s["by_cause"].get(cause, [])[:3],
                    "score": r.score})
    return out


# box: diagnoser
def diagnose_none(alarm: Alarm) -> Diagnosis:
    """--diagnoser none: the alarm only, every edit allowed (the untargeted baseline of the ablation)."""
    return Diagnosis(family=alarm.family, cause="alarm_only", allowed_edits=list(EDIT_OPS), alarm=alarm.model_dump(),
                     symptom=f"{alarm.kind} alarm at order {alarm.at_order}: {alarm.before:.2f} -> {alarm.after:.2f}")
