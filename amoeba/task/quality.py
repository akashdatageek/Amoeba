"""Deterministic checks on a finished draft (D24, spec/BOX2_PROMPT_UPGRADE_D24.md §4.4).

LLM proposes, code disposes, but here code only *measures*: every check is recorded in Draft.quality, result.json
and the trace, and none rejects a draft (yet). A check that needs D24 fields a d19 draft does not have reports
ok=None ("n/a") rather than failing.
"""
from __future__ import annotations

from amoeba.task.models import Draft

ROLE_FIELDS = ("goal", "skills", "outputs", "success_criteria", "prompt")


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
    declared = sum(bool(b.get("is_summariser")) for b in (d.rounds[-1].roles if d.rounds else []))
    summ = next((x for x in d.created_roles if x.is_summariser), None)
    owns = [s.index + 1 for s in steps if summ and summ.name in s.agent_names]
    last = steps[-1].index + 1 if steps else None
    checks["summariser"] = {"ok": declared == 1 and summ is not None and not summ.tools and not summ.missing_tools
                            and owns == [last],
                            "declared_by_planner": declared, "name": summ.name if summ else None,
                            "tools": (summ.tools + summ.missing_tools) if summ else [], "owns_steps": owns}

    # 5. every tool the draft names is installed or requested by the planner itself
    asked = {q.name.lower() for q in d.capability_requests if q.source == "planner"}
    unasked = sorted({t for x in d.created_roles for t in x.missing_tools if t.lower() not in asked})
    checks["tools_accounted"] = {"ok": not unasked, "missing_not_requested_by_planner": unasked}

    # 6. a verification step: it re-covers requirements an earlier step covered, done by a role not in that step
    if any(s.covers for s in steps):
        verify = [s.index + 1 for s in steps for e in steps if e.index < s.index
                  and set(s.covers) & set(e.covers) and not set(s.agent_names) & set(e.agent_names)]
        checks["verification_step"] = {"ok": bool(verify), "steps": sorted(set(verify))}
    else:
        checks["verification_step"] = {"ok": None, "detail": "no covers lines"}

    oks = [c["ok"] for c in checks.values()]
    return {"checks": checks, "passed": oks.count(True), "failed": oks.count(False), "na": oks.count(None),
            "failed_checks": [k for k, c in checks.items() if c["ok"] is False]}
