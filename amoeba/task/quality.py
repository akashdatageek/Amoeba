"""Deterministic checks on a finished draft (D24, spec/BOX2_PROMPT_UPGRADE_D24.md §4.4).

LLM proposes, code disposes, but here code only *measures*: every check is recorded in Draft.quality, result.json
and the trace, and none rejects a draft (yet). A check that needs D24 fields a d19 draft does not have reports
ok=None ("n/a") rather than failing.
"""
from __future__ import annotations

import re

from amoeba.task.models import Draft
from amoeba.task.parsers import parse_json_objects, parse_sections

ROLE_FIELDS = ("goal", "skills", "outputs", "success_criteria", "prompt")
# D28: the checks --quality-gate enforces (a failure sends the draft back for another round)
HARD_CHECKS = ("requirements_covered", "independent_verification", "summariser")
VERIFY_WORDS = re.compile(r"\b(verif\w*|check\w*|cross-check\w*|review\w*|validat\w*|audit\w*|reconcil\w*|"
                          r"sanity|double-check\w*|peer review)\b", re.I)


def _role_blobs(raw: str) -> list[dict]:
    sec = parse_sections(raw or "", all_fences=True)
    return parse_json_objects(sec.get("Created Roles List", "")) + parse_json_objects(sec.get("Selected Roles List", ""))


def draft_quality(d: Draft) -> dict:
    checks: dict[str, dict] = {}
    req = list(d.requirements)
    steps = d.plan
    number = {s.index + 1: s for s in steps}                      # step numbers as the planner wrote them

    # 1. every requirement is covered by at least one step and one role
    if req:
        by_steps = {r for s in steps for r in s.covers}
        by_roles = {r for x in d.created_roles for r in x.covers}
        miss_s, miss_r = [r for r in req if r not in by_steps], [r for r in req if r not in by_roles]
        checks["requirements_covered"] = {"ok": not miss_s and not miss_r, "requirements": len(req),
                                          "uncovered_by_steps": miss_s, "uncovered_by_roles": miss_r}
    else:
        checks["requirements_covered"] = {"ok": None, "detail": "no requirement ids (d19 draft or none written)"}

    # 2. every depends_on points to an earlier, existing step (so there is no cycle)
    if any(s.depends_on for s in steps) or any(s.covers for s in steps):
        bad = [{"step": s.index + 1, "depends_on": dep} for s in steps for dep in s.depends_on
               if dep not in number or dep >= s.index + 1]
        checks["dependencies_valid"] = {"ok": not bad, "bad": bad}
    else:
        checks["dependencies_valid"] = {"ok": None, "detail": "no depends_on lines"}

    # 3. every role has goal, skills, outputs, success_criteria and a prompt
    thin = {x.name: [f for f in ROLE_FIELDS if not getattr(x, f)] for x in d.created_roles}
    thin = {k: v for k, v in thin.items() if v}
    n = len(d.created_roles)
    checks["roles_fully_defined"] = {"ok": not thin, "defined": n - len(thin), "roles": n, "thin": thin}

    # 4. exactly one summariser declared by the planner; it has no tools and owns only the last step
    blobs = d.rounds[-1].roles if d.rounds else _role_blobs(d.raw_draft)   # the gate scores a round before it is logged
    declared = sum(bool(b.get("is_summariser")) for b in blobs)
    summ = next((x for x in d.created_roles if x.is_summariser), None)
    owns = [s.index + 1 for s in steps if summ and summ.name in s.agent_names]
    last = steps[-1].index + 1 if steps else None
    # d19 never asks the planner to declare a summariser, so there it is judged on tools and ownership only (D28)
    declared_ok = declared == 1 if d.prompts == "d24" else True
    checks["summariser"] = {"ok": declared_ok and summ is not None and not summ.tools and not summ.missing_tools
                            and owns == [last],
                            "declared_by_planner": declared, "name": summ.name if summ else None,
                            "tools": (summ.tools + summ.missing_tools) if summ else [], "owns_steps": owns}

    # 5. every tool the draft names is installed or requested by the planner itself
    key = lambda n: "".join(ch for ch in n.lower() if ch.isalnum())   # 'web_search' == 'Web search'
    asked = {key(q.name) for q in d.capability_requests if q.source == "planner"}
    unasked = sorted({t for x in d.created_roles for t in x.missing_tools if key(t) not in asked})
    checks["tools_accounted"] = {"ok": not unasked, "missing_not_requested_by_planner": unasked}

    # 6. a verification step: it re-covers requirements an earlier step covered, done by a role not in that step
    if any(s.covers for s in steps):
        verify = [s.index + 1 for s in steps for e in steps if e.index < s.index
                  and set(s.covers) & set(e.covers) and not set(s.agent_names) & set(e.agent_names)]
        checks["verification_step"] = {"ok": bool(verify), "steps": sorted(set(verify))}
    else:
        checks["verification_step"] = {"ok": None, "detail": "no covers lines"}

    # 7. D28 independent verification: a step that verifies (checks, reviews, validates, reconciles ...) numbers,
    # sources or test results, depends on the steps that produced them, and shares no role with those producers
    summ_name = summ.name if summ else None
    candidates = [s for s in steps if s.depends_on and VERIFY_WORDS.search(f"{s.text}\n{s.do}\n{s.done_when}")
                  and s.agent_names != [summ_name]]
    if any(s.depends_on for s in steps):
        found = []
        for s in candidates:
            producers = {n for dep in s.depends_on if dep in number for n in number[dep].agent_names}
            found.append({"step": s.index + 1, "verifiers": s.agent_names, "producers": sorted(producers),
                          "independent": bool(producers) and not set(s.agent_names) & producers})
        checks["independent_verification"] = {"ok": any(f["independent"] for f in found), "candidates": found}
    else:
        checks["independent_verification"] = {"ok": None, "detail": "no depends_on lines"}

    oks = [c["ok"] for c in checks.values()]
    return {"checks": checks, "passed": oks.count(True), "failed": oks.count(False), "na": oks.count(None),
            "failed_checks": [k for k, c in checks.items() if c["ok"] is False],
            "hard_failed": [k for k in HARD_CHECKS if checks.get(k, {}).get("ok") is False]}


def gate_suggestions(q: dict) -> str:
    """D28: what the quality gate tells the planner, one numbered line per failed hard check."""
    c, lines = q["checks"], []
    if "requirements_covered" in q["hard_failed"]:
        rc = c["requirements_covered"]
        lines.append(f"Requirements not covered by any step: {', '.join(rc['uncovered_by_steps']) or 'none'}; "
                     f"by any role: {', '.join(rc['uncovered_by_roles']) or 'none'}. Cover every requirement id.")
    if "independent_verification" in q["hard_failed"]:
        lines.append("No step verifies numbers, sources or test results by a role that did not produce them. Add a "
                     "verification step (depends_on the producing steps) done by a different role.")
    if "summariser" in q["hard_failed"]:
        sm = c["summariser"]
        lines.append(f"Summariser problem: exactly one role must have \"is_summariser\": true, no tools, and own only "
                     f"the last step (declared: {sm['declared_by_planner']}, tools: {sm['tools'] or 'none'}, "
                     f"owns steps: {sm['owns_steps']}).")
    return "\n".join(f"{i}. {x}" for i, x in enumerate(lines, 1))
