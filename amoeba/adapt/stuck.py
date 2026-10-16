"""D117 Stage B — the stuck watch and its diagnosis (plain code only, no fixes yet).

After each Box 3 step attempt, plain code looks for six stuck signals in what the step recorded (its step_<n>.json
meta, its tool calls, the files it made, and the attempt before it when the step was redone):

  repeated_error       the same tool error twice in a row (same tool, same error text once digits are masked)
  checks_after_retry   checks still failing at the end of the step (after its retry turn when it got one), unless the
                       helpers ran out of turns (then the checks fail for that reason: max_turns)
  max_turns            the helpers ran out of turns before a Final Output
  capability_unfilled  a capability or skill the step needed was requested and not filled (BLOCKED, not declared,
                       or an unfilled request for one of the step's roles)
  missing_data         D127: a fact or figure the step had to find itself was not found (a MISSING DATA line, or a
                       lacked item that names no tool and no earlier step): a research gap, not a missing tool
  provider_blocked     D128: the model service blocked a helper's replies (finish reason content_filter, even after
                       one plain retry) and the step did not finish; no edit of the team can fix that
  unreadable_reply     D123: a helper's reply could not be read (a required section missing even after the unglue and
                       the repair call) and the step did not finish: the turns went to replies plain code could not use
  no_file_change       the step owes a file (claimed but missing, a file type in its output line with none made, or
                       a failed spreadsheet check) and its files did not change between two attempts

A step is STUCK when it did not end `done` and at least one signal holds; a step that recovered by itself is not
stuck. The diagnosis picks one cause, in the order of `diagnoser.causes` in amoeba/config/adapt.yaml, and the edits
that cause allows (`diagnoser.allowed_edits`). The same functions read live steps (the plan runner) and stored run
folders (scripts/stuck_report.py), so the counts of old runs and the live watch agree.
"""
from __future__ import annotations

import re

from amoeba.adapt.config import adapt_config

SIGNAL_CAUSE = {"missing_input": "missing_input", "capability_unfilled": "capability", "repeated_error": "tool_error",
                "max_turns": "max_turns", "checks_after_retry": "checks", "no_file_change": "claimed_file_missing",
                "unreadable_reply": "format", "missing_data": "missing_data",
                "provider_blocked": "provider_blocked"}
# D117 Stage C: a lacked item is a missing input (data an earlier step should have given) unless it names a tool
TOOL_WORDS = re.compile(r"tool|\bapi\b|_api|reader|interpreter|executor|calculator|\bcalc|access|generator|analy[sz]er|"
                        r"\bengine\b|_engine|service|search|network|browser|capability|skill|\blocal\b|local:|script|"
                        r"command|python|\bpdf\b|docx|xlsx|excel|spreadsheet|\bword\b|email|route|\bcode\b|\.py\b|bash|"
                        r"sandbox|fetch|curl", re.I)
# D127: a lacked item whose last word names content (a value, a text, a figure) is data, even when a tool word comes
# before it ("email body", "API key value"); a tool word at the end keeps it a capability ("pricing API")
DATA_HEAD = re.compile(r"\b(body|text|content|contents|draft|value|values|figure|figures|number|numbers|estimate|"
                       r"estimates|rate|rates|price|prices|cost|costs|income|amount|amounts|total|totals|series|"
                       r"statistic|statistics|stats|details|information|info|record|records|address|addresses|"
                       r"date|dates|count|counts|share|shares|level|levels|index values|history|list|table)\s*$", re.I)
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


# box: stuck
def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9]+", (text or "").lower().replace("_", " ")) if w not in STOP}


# box: stuck
def out_of_turns_item(item: str) -> bool:
    """D128: a lacked label that names the helper's own turns or time (adapt.yaml diagnoser.out_of_turns_phrases):
    the step ran out of turns; it is neither a tool nor data."""
    label = " ".join((item or "").partition(" — ")[0].lower().replace("-", " ").split())
    phrases = (adapt_config().get("diagnoser") or {}).get("out_of_turns_phrases") or []
    return any(p in label for p in phrases)


# box: stuck
def is_tool_name(label: str) -> bool:
    """D127: whether a lacked label names a tool or capability: a tool word, or a standard capability name
    (aliases.yaml), and no content word at its end ("email body" is data)."""
    from amoeba.capabilities import normalise
    label = (label or "").strip()
    if DATA_HEAD.search(label.replace("_", " ")):
        return False
    return bool(TOOL_WORDS.search(label)) or normalise(label)[1]


# box: stuck
def classify_lacked(item: str, n: int | None, plan: dict | None, deps: list[int] | None = None) -> dict:
    """One lacked item: {"item", "kind": "missing_input" | "capability" | "missing_data", "upstream": [step numbers]}.
    The label is the text before " — ". A tool name (is_tool_name) → capability. A step, input, output, data or file
    named in the label, a step named in the explanation, another step's role, or most of an earlier step's planned
    output → missing input; the upstream steps are the ones named, else the role's, else the best match among the
    dependencies. D127: anything else is missing data the step had to find itself (it was a capability before)."""
    label, _, why = (item or "").partition(" — ")
    plan, deps = plan or {}, list(deps or [])
    earlier = [k for k in sorted(plan) if n is None or k < n or k in deps]
    out = {"item": item, "kind": "capability", "upstream": []}
    if is_tool_name(label) and not (INPUT_WORDS.search(label) and STEP_REF.search(why)):
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
        if not out["upstream"]:                       # nothing earlier could have given it: the step's own research
            out["kind"] = "missing_data"
        return out
    out["kind"] = "missing_data"
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
    turns = meta.get("unreadable_turns") or []
    blocked = [b for b in turns if b.get("blocked")]
    bad = [b for b in turns if not b.get("blocked")]
    if blocked and not meta.get("finished", False):   # D128: the service refused the replies; not a format slip
        cats = [b.get("category") for b in blocked]
        why = f"refusal categories: {', '.join(sorted(set(cats)))}" if all(cats) else "content filter, no category given"
        sig.append({"signal": "provider_blocked", "categories": sorted({c for c in cats if c}),     # D134
                    "evidence": [f"{len(blocked)} of {meta.get('turns') or '?'} turns: the model service blocked the "
                                 f"reply ({why})"]
                    + [f"{b.get('agent', '?')}, turn {b.get('turn')}: blocked" for b in blocked][:4]})
    if bad and not meta.get("finished", False):    # D123: replies plain code could not read cost the step its end
        sig.append({"signal": "unreadable_reply",
                    "evidence": [f"{b.get('agent', '?')}, turn {b.get('turn')}: reply not readable — "
                                 f"{(b.get('why') or '')[:140]}" for b in bad]})
    lacked_all = list(dict.fromkeys([*(meta.get("blocked") or []), *(meta.get("contract_missing") or [])]))
    turns_out = [x for x in lacked_all if out_of_turns_item(x)]
    out_of_turns = out_of_turns or bool(turns_out)     # D128: a lacked line that is the helper's own turns
    if out_of_turns:
        sig.append({"signal": "max_turns", "evidence": [f"turns used: {meta.get('turns')}; no Final Output from "
                                                        f"every helper ({reason[:120]})"]})
    lacked = [x for x in lacked_all if x not in turns_out]
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
    data = [k["item"] for k in kinds if k["kind"] == "missing_data"]
    data += [x for x in meta.get("missing_data") or [] if x not in data]          # D127: MISSING DATA lines
    if data:
        sig.append({"signal": "missing_data", "items": data,
                    "evidence": [f"missing data: {x[:140]}" for x in data]})
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
def open_requests(requests: list | None, holds: dict[str, set] | None = None) -> list[dict]:
    """The capability requests that are really open: status unfilled, and not covered by a tool the run already has.
    "registered_tool" means the toolbox step found the tool in the run's registry (web_search and fetch_url, granted by
    D32), so the pool had nothing to add; it is not a missing capability. `holds` (the live watch): role name → the
    tools its helper holds now, so a request a later grant covered is not open either."""
    out = []
    for q in requests or []:
        if not isinstance(q, dict) or q.get("status") != "unfilled" or q.get("reason") == "registered_tool":
            continue
        have = (holds or {}).get(q.get("for_role")) or set()
        if (q.get("kind") or "tool") == "tool" and {q.get("name"), q.get("canonical")} & set(have):
            continue
        out.append(q)
    return out


# box: stuck
def waived_view(meta: dict, unfilled: list[dict], waived: set[str] | None, files: bool = True
                ) -> tuple[dict, list[dict]]:
    """D124: what the watch reads once a work-around for a capability was accepted (plain code applied the fix
    proposer's work_around): that capability no longer counts as lacked or requested, and a file type the capability
    names (docx_generator → docx) is no longer owed by the step's output line, its claimed files or its checks. The
    step's own status and reason are not changed; only the stuck signals stop firing for what was worked around.
    files=False (D125, a tool was made for the capability): the capability is no longer missing, but a file it makes
    is still owed."""
    names = {w.strip().lower() for w in waived or () if w and w.strip()}
    if not names:
        return meta, unfilled
    label = lambda x: (x or "").partition(" — ")[0].strip().lower()
    kinds = {k.lower() for w in names for k in re.findall(r"xlsx|xlsm|csv|tsv|docx|pptx|pdf|png|jpg|svg|json",
                                                            w.replace("_", " "))}
    view = {**meta, "blocked": [x for x in meta.get("blocked") or [] if label(x) not in names],
            "contract_missing": [x for x in meta.get("contract_missing") or [] if label(x) not in names]}
    if kinds and files:
        drop = re.compile(r"\.?\b(" + "|".join(sorted(kinds)) + r")\b", re.I)
        view["output_spec"] = drop.sub("", meta.get("output_spec") or "")
        view["claimed_files_missing"] = [f for f in meta.get("claimed_files_missing") or []
                                         if not drop.search(f)]
        view["checks"] = [c for c in meta.get("checks") or [] if not drop.search(c.get("name", ""))]
    keep = [q for q in unfilled or [] if not ({str(q.get("name") or "").lower(),
                                               str(q.get("canonical") or "").lower()} & names)]
    return view, keep


# box: stuck
def is_stuck(meta: dict, signals: list[dict]) -> bool:
    """Stuck: the step did not end done and at least one signal holds (a step that recovered is not stuck)."""
    return bool(signals) and meta.get("status") != "done"


# box: stuck, ov_adapt
def diagnose(signals: list[dict], config: dict | None = None) -> dict:
    """One cause for a stuck step: the first cause in `diagnoser.causes` that a signal names; its allowed edits
    from `diagnoser.allowed_edits`; the evidence lines of every signal (at most MAX_EVIDENCE)."""
    d = (config or adapt_config()).get("diagnoser") or {}
    order = list(d.get("causes") or [])
    named = [s["cause"] for s in signals]
    cause = next((c for c in order if c in named), named[0] if named else None)
    evidence = [e for s in signals for e in s["evidence"]][:int(d.get("max_evidence", MAX_EVIDENCE))]
    allowed = list((d.get("allowed_edits") or {}).get(cause, [])) if cause else []
    out = {"cause": cause, "signals": [s["signal"] for s in signals], "allowed_edits": allowed, "evidence": evidence,
           # D129: every cause a signal names, in the table's order (the first is `cause`); the code fixes of the
           # others are tried after the first cause's, before the fix proposer
           "causes": [c for c in order if c in named] + [c for c in dict.fromkeys(named) if c not in order]}
    for s in signals:
        if s["signal"] == "missing_input":
            out["upstream"], out["missing"] = s["upstream"], s["items"]
        if s["signal"] == "capability_unfilled":
            out["lacked"] = s.get("items", [])
        if s["signal"] == "missing_data":
            out["data"] = s["items"]
    return out
