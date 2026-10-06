"""D117 Stage B — the stuck watch and its diagnosis (plain code only, no fixes yet).

After each Box 3 step attempt, plain code looks for five stuck signals in what the step recorded (its step_<n>.json
meta, its tool calls, the files it made, and the attempt before it when the step was redone):

  repeated_error       the same tool error twice in a row (same tool, same error text once digits are masked)
  checks_after_retry   checks still failing at the end of the step (after its retry turn when it got one), unless the
                       helpers ran out of turns (then the checks fail for that reason: max_turns)
  max_turns            the helpers ran out of turns before a Final Output
  capability_unfilled  a capability or skill the step needed was requested and not filled (BLOCKED, not declared,
                       or an unfilled request for one of the step's roles)
  no_file_change       the step owes a file (claimed but missing, a file type in its output line with none made, or
                       a failed spreadsheet check) and its files did not change between two attempts

A step is STUCK when it did not end `done` and at least one signal holds; a step that recovered by itself is not
stuck. The diagnosis picks one cause, in the order of `diagnoser.causes` in amoeba/config/adapt.yaml, and the edits
that cause allows (`diagnoser.allowed_edits`). The same functions read live steps (the plan runner) and stored run
folders (scripts/stuck_report.py), so the counts of old runs and the live watch agree.
"""
from __future__ import annotations

import re

from amoeba.adapt.recipe import adapt_config

SIGNAL_CAUSE = {"missing_input": "missing_input", "capability_unfilled": "capability", "repeated_error": "tool_error",
                "max_turns": "max_turns", "checks_after_retry": "checks", "no_file_change": "claimed_file_missing"}
# D117 Stage C: a lacked item is a missing input (data an earlier step should have given) unless it names a tool
TOOL_WORDS = re.compile(r"tool|\bapi\b|_api|reader|interpreter|executor|calculator|\bcalc|access|generator|analy[sz]er|"
                        r"\bengine\b|_engine|service|search|network|browser|capability|skill|\blocal\b|local:|script|"
                        r"command|python|\bpdf\b|docx|xlsx|excel|spreadsheet|\bword\b|email|route|\bcode\b|\.py\b|bash|"
                        r"sandbox|fetch|curl", re.I)
INPUT_WORDS = re.compile(r"\bsteps?\s*#?\d|\bprevious steps?\b|\bearlier steps?\b|\bupstream\b|\binputs?\b|"
                         r"\boutputs?\b|\bdeliverables?\b|\bdata\b|\bfiles?\b", re.I)
STEP_REF = re.compile(r"\bsteps?\s*#?(\d+)(?:\s*(?:,|&|and)\s*(?:step\s*)?(\d+))?", re.I)
STOP = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "by", "from", "as", "per", "each", "all",
        "its", "their", "this", "that", "list", "one", "two", "three"}
FILE_KINDS = r"\b(xlsx|xlsm|csv|tsv|docx|pptx|pdf|png|jpg|svg|json)\b|\.(?:xlsx|csv|docx|pptx|pdf|png|json)\b"
MAX_EVIDENCE = 8


# box: stuck
def norm_error(text: str) -> str:
    """An error as compared for "the same error twice": its first 160 characters, lower case, digits masked,
    whitespace squeezed (so line numbers and sizes do not make two identical errors look different)."""
    t = re.sub(r"\s+", " ", (text or "")).strip().lower()
    return re.sub(r"\d+", "#", t)[:160]


# box: stuck
def repeated_errors(calls: list[dict]) -> list[str]:
    """Evidence lines for each run of two failed calls in a row with the same tool and the same error."""
    out, prev = [], None
    for i, c in enumerate(calls or []):
        key = (c.get("tool"), norm_error(c.get("result", ""))) if not c.get("ok", True) else None
        if key is not None and key == prev:
            out.append(f"{c.get('agent', '?')}: {c.get('tool')} failed twice in a row with the same error: "
                       f"{(c.get('result') or '')[:160]}")
        prev = key
    return list(dict.fromkeys(out))


# box: stuck
def file_sig(files: list[dict] | None) -> tuple:
    return tuple(sorted((f.get("path", ""), f.get("size")) for f in files or []))


# box: stuck
def owes_file(meta: dict) -> list[str]:
    """Why the step owes a file it does not have: claimed but missing, a file type in its output line and none made,
    or a failed spreadsheet-formula check."""
    why = [f"claimed but not in the workspace: {', '.join(meta['claimed_files_missing'])}"] \
        if meta.get("claimed_files_missing") else []
    if re.search(FILE_KINDS, meta.get("output_spec") or "", re.I) and not meta.get("files_made"):
        why.append(f"the output line asks for a file ({(meta.get('output_spec') or '')[:80]}) and none was made")
    why += [f"check {c['name']} failed: {c.get('detail', '')[:120]}" for c in meta.get("checks") or []
            if not c.get("pass") and "xlsx" in c.get("name", "")]
    return why


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9]+", (text or "").lower().replace("_", " ")) if w not in STOP}


# box: stuck
def classify_lacked(item: str, n: int | None, plan: dict | None, deps: list[int] | None = None) -> dict:
    """One lacked item: {"item", "kind": "missing_input" | "capability", "upstream": [step numbers]}. The label is the
    text before " — ". A tool word in the label → capability. A step, input, output, data or file named in the label,
    a step named in the explanation, another step's role, or most of an earlier step's planned output → missing input;
    the upstream steps are the ones named, else the role's, else the best match among the dependencies."""
    label, _, why = (item or "").partition(" — ")
    plan, deps = plan or {}, list(deps or [])
    earlier = [k for k in sorted(plan) if n is None or k < n or k in deps]
    out = {"item": item, "kind": "capability", "upstream": []}
    if TOOL_WORDS.search(label) and not (INPUT_WORDS.search(label) and STEP_REF.search(why)):
        return out
    named = sorted({int(g) for m in STEP_REF.finditer(label + " " + why) for g in m.groups() if g} & set(earlier))
    mine = set(plan.get(n, {}).get("roles") or []) if n is not None else set()
    by_role = [k for k in earlier if set(plan[k].get("roles") or []) - mine
               and any(r.lower() in label.lower() for r in set(plan[k].get("roles") or []) - mine)]
    lw = _words(label)
    overlap = {k: len(lw & _words(plan[k].get("output") or "")) / max(len(lw), 1) for k in earlier}
    best = [k for k in sorted(overlap, key=lambda k: -overlap[k]) if overlap[k] >= 0.5][:1]
    if named or by_role or best or INPUT_WORDS.search(label) or STEP_REF.search(why):
        out["kind"] = "missing_input"
        out["upstream"] = named or by_role or best or \
            ([k for k in sorted(overlap, key=lambda k: -overlap[k]) if k in deps and overlap[k] > 0][:1] or deps)
    return out


# box: stuck
def step_signals(meta: dict, previous: dict | None = None, unfilled: list[dict] | None = None,
                 files_unchanged: bool | None = None, plan: dict | None = None) -> list[dict]:
    """The stuck signals of one step attempt. `previous`: the meta of the attempt before (a reworked or re-run step);
    `unfilled`: capability requests with status unfilled ({name, for_role}); `files_unchanged`: the live watch's own
    comparison of the step's files across its refine turn (None: not known); `plan`: step number → {"output",
    "roles", "status"} of the run's steps, to tell a missing input from a missing capability (D117 Stage C)."""
    sig = []
    rep = repeated_errors(meta.get("tool_calls") or [])
    if rep:
        sig.append({"signal": "repeated_error", "evidence": rep})
    failed = [c for c in meta.get("checks") or [] if not c.get("pass")]
    reason = meta.get("status_reason") or ""
    out_of_turns = "max_turns" in (meta.get("causes") or []) or reason.startswith("max_turns") or "; max_turns" in reason
    if failed and not out_of_turns:          # checks that fail because nothing was finished are max_turns (D117 C)
        how = "after the retry turn" if meta.get("retried") or meta.get("refine") else "and no retry turn was possible"
        sig.append({"signal": "checks_after_retry",
                    "evidence": [f"check {c['name']} still fails {how}: {c.get('detail', '')[:140]}" for c in failed]})
    if out_of_turns:
        sig.append({"signal": "max_turns", "evidence": [f"turns used: {meta.get('turns')}; no Final Output from "
                                                        f"every helper ({reason[:120]})"]})
    lacked = list(dict.fromkeys([*(meta.get("blocked") or []), *(meta.get("contract_missing") or [])]))
    kinds = [classify_lacked(x, meta.get("step"), plan, meta.get("depends_on")) for x in lacked]
    inputs = [k for k in kinds if k["kind"] == "missing_input"]
    inputs += [{"item": x, "kind": "missing_input", "upstream": list(meta.get("depends_on") or [])}
               for x in meta.get("missing_inputs") or [] if x not in {k["item"] for k in inputs}]   # D63 marks
    if inputs:
        sig.append({"signal": "missing_input", "upstream": sorted({u for k in inputs for u in k["upstream"]}),
                    "items": [k["item"] for k in inputs],
                    "evidence": [f"missing input: {k['item'][:140]}"
                                 + (f" (from step {', '.join(map(str, k['upstream']))})" if k["upstream"] else "")
                                 for k in inputs]})
    lacked = [k["item"] for k in kinds if k["kind"] == "capability"]
    roles = set(meta.get("roles") or [])
    asked = [q for q in unfilled or [] if q.get("for_role") in roles]
    if lacked or asked:
        ev = [f"lacked: {', '.join(lacked)}"] if lacked else []
        ev += [f"requested {q.get('kind') or 'capability'} {q.get('name')} for {q.get('for_role')}: unfilled"
               + (f" ({q.get('reason')})" if q.get("reason") else "") for q in asked]
        sig.append({"signal": "capability_unfilled", "evidence": ev,
                    "items": lacked + [q.get("name") for q in asked], "requests": asked})
    why = owes_file(meta)
    if why:
        unchanged = files_unchanged if files_unchanged is not None else (
            previous is not None and file_sig(previous.get("files_made")) == file_sig(meta.get("files_made")))
        if unchanged:
            sig.append({"signal": "no_file_change",
                        "evidence": why + ["the step's files did not change between its attempts"]})
    for s in sig:
        s["cause"] = SIGNAL_CAUSE[s["signal"]]
        s["evidence"] = s["evidence"][:MAX_EVIDENCE]
    return sig


# box: stuck
def is_stuck(meta: dict, signals: list[dict]) -> bool:
    """Stuck: the step did not end done and at least one signal holds (a step that recovered is not stuck)."""
    return bool(signals) and meta.get("status") != "done"


# box: stuck
def diagnose(signals: list[dict], config: dict | None = None) -> dict:
    """One cause for a stuck step: the first cause in `diagnoser.causes` that a signal names; its allowed edits
    from `diagnoser.allowed_edits`; the evidence lines of every signal (at most MAX_EVIDENCE)."""
    d = (config or adapt_config()).get("diagnoser") or {}
    order = list(d.get("causes") or [])
    named = [s["cause"] for s in signals]
    cause = next((c for c in order if c in named), named[0] if named else None)
    evidence = [e for s in signals for e in s["evidence"]][:int(d.get("max_evidence", MAX_EVIDENCE))]
    allowed = list((d.get("allowed_edits") or {}).get(cause, [])) if cause else []
    if not adapt_config().get("recipe", {}).get("allow_model_edits"):
        allowed = [a for a in allowed if a != "prefer_model"]
    out = {"cause": cause, "signals": [s["signal"] for s in signals], "allowed_edits": allowed, "evidence": evidence}
    for s in signals:
        if s["signal"] == "missing_input":
            out["upstream"], out["missing"] = s["upstream"], s["items"]
        if s["signal"] == "capability_unfilled":
            out["lacked"] = s.get("items", [])
    return out
