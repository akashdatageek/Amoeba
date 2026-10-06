"""D117 Stage C — code fixes for a stuck step (no AI), cheapest first.

For one diagnosis (amoeba/adapt/stuck.py) `candidates` lists the code fixes in the order they are tried; the plan
runner (PlanRunner.fix_stuck) applies the first one that is allowed for the cause, within its range, not tried before
in this task and within the limits, re-runs only the stuck step and re-checks it:

  missing_input   a. the upstream step is done and its output holds the data → add_dependency (add it to depends_on,
                     or, when it is already a dependency, pass its output in full with a pointer to the item)
                  b. the upstream output lacks the data → rerun_upstream: that step once more, the missing item added
                     to its done_when, then the stuck step (the only exception to "never redo a completed step")
  tool_error      rung 1: more turns
  checks          rung 1: more retry turns, then a larger input when an input was shortened
  max_turns       rung 1: more turns
  capability      rung 2: attach the missing tool or skill from the pool shortlist (pool or local tools must be on;
                  otherwise the rung is skipped with "capability fix unavailable: pool off")

A cause with no code fix (claimed_file_missing, …) is left to Stage D. Limits come from `adapt` in adapt.yaml.
"""
from __future__ import annotations

import json
import re

from amoeba.adapt.recipe import adapt_config

GENERIC = {"step", "steps", "data", "input", "inputs", "output", "outputs", "missing", "file", "files", "raw",
           "provided", "previous", "earlier", "upstream", "results", "result", "the", "and", "from", "of", "for"}
POOL_OFF = "capability fix unavailable: pool off"
LIMIT_DEFAULTS = {"max_fixes_per_step": 3, "max_fixes_per_task": 8, "max_tokens_per_task": 200000,
                  "max_usd_per_task": 1.0, "more_turns": 3, "more_retry_turns": 1, "input_factor": 2,
                  "stop_when_exhausted": True, "max_added_helpers": 2}


# box: fixes
def limits(config: dict | None = None) -> dict:
    """The adaptation limits (adapt.yaml `adapt`), with defaults for what is not set."""
    return {**LIMIT_DEFAULTS, **((config or adapt_config()).get("adapt") or {})}


# box: fixes
def fix_key(fix: dict) -> str:
    """What makes two fixes the same (a failed fix is never repeated): its kind, the step it changes and its values."""
    return json.dumps([fix["kind"], fix.get("target"), fix.get("params", {})], sort_keys=True)


# box: fixes
def _specific(item: str) -> set[str]:
    label = (item or "").partition(" — ")[0]
    return {w for w in re.findall(r"[a-z][a-z0-9]+", label.lower().replace("_", " ")) if w not in GENERIC
            and not w.isdigit()}


# box: fixes
def holds(item: str, text: str) -> bool:
    """Whether an upstream output holds a missing item: most (60%) of the item's own words are in it; an item with
    no words of its own ("Step 1 Data") is held by any non-empty output."""
    words = _specific(item)
    if not (text or "").strip():
        return False
    if not words:
        return True
    have = {w for w in re.findall(r"[a-z][a-z0-9]+", text.lower().replace("_", " "))}
    return len(words & have) / len(words) >= 0.6


# box: fixes
def _option(kind: str, name: str, now: int, new: int, ranges: dict, n: int) -> dict | None:
    r = ranges.get(name) or {}
    new = min(new, int(r.get("max", new)))
    if new <= now:
        return None
    return {"kind": kind, "rung": 1, "target": n, "params": {name: new}, "was": {name: now}}


# box: fixes
def candidates(d: dict, n: int, ctx: dict, config: dict | None = None) -> tuple[list[dict], list[str]]:
    """The code fixes for one diagnosis, cheapest first, and the notes of rungs skipped. ctx: {"deps": the step's
    dependencies, "steps": {number: {"status", "text"}} of the steps run, "opts": the step's current max_turns,
    check_retry_turns and max_input_chars, "capped": inputs shortened for this step, "stock": pool or local tools on,
    "upstream_rerun": steps already re-run once, "attached": pool ids a grant already gave this step}. Each fix: {kind, rung, target, params, ...}."""
    cfg = config or adapt_config()
    lim, ranges = limits(cfg), (cfg.get("recipe") or {}).get("run_options") or {}
    opts, out, notes = ctx.get("opts") or {}, [], []
    cause = d.get("cause")
    if cause == "missing_input":
        steps, deps = ctx.get("steps") or {}, set(ctx.get("deps") or [])
        for u in d.get("upstream") or []:
            up = steps.get(u) or {}
            items = [x for x in d.get("missing") or []]
            held = [x for x in items if up.get("status") == "done" and holds(x, up.get("text", ""))]
            if held:                                                       # case a: it is there, not passed
                mode = "passed_in_full" if u in deps else "added"
                out.append({"kind": "add_dependency", "rung": "input", "target": n, "params": {"from": u, "mode": mode},
                            "items": held})
            lacking = [x for x in items if x not in held]
            if lacking and u not in (ctx.get("upstream_rerun") or set()):  # case b: the upstream lacks it
                out.append({"kind": "rerun_upstream", "rung": "input", "target": u, "params": {"then": n,
                            "add_done_when": "; ".join(x.partition(" — ")[0] for x in lacking)[:300]},
                            "items": lacking})
        if not d.get("upstream"):
            notes.append("missing input with no upstream step named or matched")
    elif cause in ("tool_error", "max_turns"):
        f = _option("set_run_option:max_turns", "max_turns", int(opts.get("max_turns", 0)),
                    int(opts.get("max_turns", 0)) + int(lim["more_turns"]), ranges, n)
        out += [f] if f else []
        if not f:
            notes.append("more turns: already at the maximum")
    elif cause == "checks":
        f = _option("set_run_option:check_retry_turns", "check_retry_turns", int(opts.get("check_retry_turns", 0)),
                    int(opts.get("check_retry_turns", 0)) + int(lim["more_retry_turns"]), ranges, n)
        out += [f] if f else []
        if ctx.get("capped"):
            g = _option("set_run_option:max_input_chars", "max_input_chars", int(opts.get("max_input_chars", 0)),
                        int(opts.get("max_input_chars", 0)) * int(lim["input_factor"]), ranges, n)
            out += [g] if g else []
    elif cause == "capability":
        if not ctx.get("stock"):
            notes.append(POOL_OFF)
        else:
            out.append({"kind": "grant_tool", "rung": 2, "target": n,
                        "params": {"items": sorted(x.partition(" — ")[0].strip() for x in d.get("lacked") or []),
                                   "exclude": sorted(ctx.get("attached") or [])}})
    else:
        notes.append(f"no code fix for the cause {cause}")
    allowed = set(d.get("allowed_edits") or [])
    kept = [f for f in out if f["kind"] in allowed]
    notes += [f"{f['kind']}: not allowed for {cause} (adapt.yaml)" for f in out if f["kind"] not in allowed]
    return kept, notes
