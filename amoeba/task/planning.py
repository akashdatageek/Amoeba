"""D143 — planning v2 under code control: how much planning a task gets (tier), which round's draft is published
(the best, not the last), what changed between rounds, and whether the planner may revise Box 1's reading.

All of it is plain code: the planner proposes a reading revision; code accepts it only on Box 1's alternatives or a
fetched plan-search source, and only when the plan observer approved that round.
"""
from __future__ import annotations

import re

from amoeba.task.deliverables import promised_files
from amoeba.task.quality import OUTSIDE, deliverable_phrases

TIERS = ("light", "standard", "full")
# rounds and observers per tier (the round cap never exceeds the caller's max_rounds)
TIER_PLAN = {"light": {"rounds": 1, "agent_observer": False, "plan_observer": False},
             "standard": {"rounds": 2, "agent_observer": False, "plan_observer": True},
             "full": {"rounds": 3, "agent_observer": True, "plan_observer": True}}
WEB = re.compile(r"\b(current|currently|latest|today|recent|this (?:week|month|year)|news|price|prices|rates?|"
                 r"search|sources?|cite|citations?|online|website|web|20[2-3]\d)\b", re.I)


# box: planner
def tier_signals(task_text: str, interpretation: dict | None = None, web_needed: bool | None = None) -> dict:
    """What the tier is decided from: an estimate of the requirements (the task's deliverable phrases), whether web
    research is needed, the files to deliver, and any outside action."""
    files = promised_files({"task": task_text or ""})
    return {"requirements": max(len(deliverable_phrases(task_text or "")), 1),
            "web": bool(WEB.search(task_text or "")) if web_needed is None else bool(web_needed),
            "files": len(files), "outside": bool(OUTSIDE.search(task_text or ""))}


# box: planner
def resolve_tier(requested: str, protocol: str, task_text: str, interpretation: dict | None = None,
                 web_needed: bool | None = None) -> tuple[str, dict]:
    """The planning tier and its signals. An explicit tier wins; `auto` under legacy is `full` (today's behaviour);
    under v2: light (at most 3 requirements, no web, no files), full (7+ requirements, or web research and 2+
    files, or an outside action), standard otherwise."""
    sig = tier_signals(task_text, interpretation, web_needed)
    if requested in TIERS:
        return requested, {**sig, "how": "requested"}
    if protocol != "v2":
        return "full", {**sig, "how": "legacy auto"}
    if sig["requirements"] <= 3 and not sig["web"] and not sig["files"] and not sig["outside"]:
        tier = "light"
    elif sig["requirements"] >= 7 or (sig["web"] and sig["files"] >= 2) or sig["outside"]:
        tier = "full"
    else:
        tier = "standard"
    return tier, {**sig, "how": "auto"}


# box: planner
def draft_score(hard_failed: int, blocking: int, round_index: int) -> tuple:
    """Lower is better: fewer failed HARD checks, then fewer blocking review issues, then the later round."""
    return (hard_failed, blocking, -round_index)


# box: planner
def plan_diff(before, after) -> dict:
    """What changed between two PlanOut replies: requirements and steps added, removed or changed."""
    if before is None or after is None:
        return {}
    rb, ra = {r.id: r.text for r in before.requirements}, {r.id: r.text for r in after.requirements}
    sb = {s.number: s.model_dump(mode="json") for s in before.plan}
    sa = {s.number: s.model_dump(mode="json") for s in after.plan}
    return {"requirements_added": sorted(set(ra) - set(rb)), "requirements_removed": sorted(set(rb) - set(ra)),
            "requirements_changed": sorted(k for k in set(ra) & set(rb) if ra[k] != rb[k]),
            "steps_added": sorted(set(sa) - set(sb)), "steps_removed": sorted(set(sb) - set(sa)),
            "steps_changed": sorted(k for k in set(sa) & set(sb) if sa[k] != sb[k]),
            "roles_before": [r.name for r in before.roles], "roles_after": [r.name for r in after.roles]}


# ---- the reading revision ------------------------------------------------------------------------------------------
# box: interpret
def check_revision(rev: dict | None, interpretation: dict | None, plan_search_text: str = "",
                   observer_approved: bool | None = None) -> dict | None:
    """Whether the planner's proposed reading revision is accepted. (a) to_reading is one of Box 1's alternatives
    for the entity, or the evidence cites a plan-search source [P#] the planner was shown; and (b) the plan observer
    approved the plan that round (None: no observer ran). Returns the revision with accepted and why."""
    if not rev:
        return None
    rows = {w["entity"].lower(): w for w in (interpretation or {}).get("working", [])}
    w = rows.get(str(rev.get("entity", "")).strip().lower())
    if w is None:
        return {**rev, "accepted": False, "why": "the entity is not in Box 1's working interpretation"}
    if str(rev.get("from_reading", "")).strip().lower() != w["reading"].lower():
        return {**rev, "accepted": False, "why": f"from_reading is not the working reading ({w['reading']})"}
    to = str(rev.get("to_reading", "")).strip()
    alts = [a for a in w.get("alternatives") or [] if a.lower() == to.lower()]
    cited = [e for e in rev.get("evidence") or [] if re.fullmatch(r"\[?P\d+\]?", str(e).strip())
             and f"[{str(e).strip().strip('[]')}]" in (plan_search_text or "")]
    if not alts and not cited:
        return {**rev, "accepted": False, "why": "to_reading is not one of Box 1's alternatives and no fetched "
                                                 "plan-search source [P#] is cited"}
    if observer_approved is False:
        return {**rev, "accepted": False, "why": "the plan observer did not approve the plan in that round"}
    return {**rev, "to_reading": alts[0] if alts else to, "accepted": True,
            "why": "one of Box 1's alternatives" if alts else f"cites {', '.join(cited)}"}


# box: interpret
def apply_revision(interpretation: dict, rev: dict) -> dict:
    """The working interpretation with an accepted revision: the entity's reading becomes to_reading (settled
    "revised"), the old reading becomes an alternative, and the opening line states the change."""
    out = {**interpretation, "working": []}
    for w in interpretation.get("working", []):
        if w["entity"].lower() == str(rev["entity"]).lower():
            alts = [w["reading"]] + [a for a in w.get("alternatives") or [] if a.lower() != rev["to_reading"].lower()]
            w = {**w, "reading": rev["to_reading"], "settled": "revised", "alternatives": alts,
                 "revision": {k: rev.get(k) for k in ("from_reading", "to_reading", "reason", "evidence")}}
        out["working"].append(w)
    out["revised"] = rev
    return out
