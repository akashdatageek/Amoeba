"""Deterministic checks on a finished draft (D24, spec/BOX2_PROMPT_UPGRADE_D24.md §4.4).

LLM proposes, code disposes, but here code only *measures*: every check is recorded in Draft.quality, result.json
and the trace, and none rejects a draft (yet). A check that needs D24 fields a d19 draft does not have reports
ok=None ("n/a") rather than failing.
"""
from __future__ import annotations

import re

from amoeba.capabilities import normalise, snake
from amoeba.interp.provenance import claim_numbers, numbers_in
from amoeba.task.models import Draft
from amoeba.task.parsers import parse_json_objects, parse_sections

ROLE_FIELDS = ("goal", "skills", "outputs", "success_criteria", "prompt")
# D28: the checks --quality-gate enforces (a failure sends the draft back for another round)
HARD_CHECKS = ("requirements_covered", "independent_verification", "summariser", "task_coverage")
VERIFY_WORDS = re.compile(r"\b(verif\w*|check\w*|cross-check\w*|review\w*|validat\w*|audit\w*|reconcil\w*|"
                          r"sanity|double-check\w*|peer review)\b", re.I)


def _role_blobs(raw: str) -> list[dict]:
    sec = parse_sections(raw or "", all_fences=True)
    return parse_json_objects(sec.get("Created Roles List", "")) + parse_json_objects(sec.get("Selected Roles List", ""))


# D52: deliverable-like verbs of the task text, each with the word forms that count as the same verb
DELIVERABLE_VERBS = {
    "deliver": r"deliver(?:s|ed|ing)?", "estimate": r"estimat(?:e|es|ed|ing|ion|ions)",
    "assess": r"assess(?:es|ed|ing|ment|ments)?", "prototype": r"prototyp(?:e|es|ed|ing)",
    "test": r"test(?:s|ed|ing)?", "gather": r"gather(?:s|ed|ing)?", "build": r"(?:build(?:s|ing)?|built)",
    "plan": r"plan(?:s|ned|ning)?",
}
_VERB = re.compile(r"\b(" + "|".join(DELIVERABLE_VERBS.values()) + r")\b", re.I)
_OBJECT_END = re.compile(r"[.;:!?,\n(]|\b(?:and|then|or|but|so)\b", re.I)
STOP = set("a an the of to in on at by as for with from into over per and or is are be it its this that these "
           "those each both all any our your their we you they them which what how".split())
OBJECT_WORDS = 6


def _verb_key(word: str) -> str:
    return next(k for k, rx in DELIVERABLE_VERBS.items() if re.fullmatch(rx, word, re.I))


def _content(text: str) -> set[str]:
    words = (w.lower().rstrip("s") for w in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text))
    return {w for w in words if w not in STOP}


def deliverable_phrases(task_text: str) -> list[tuple[str, str, str]]:
    """(verb key, phrase, object) for every deliverable-like verb in the task: the verb and up to six words after
    it, cut at punctuation or a joining word ("prototype and test the schema" gives "prototype" and "test the
    schema")."""
    out = []
    for m in _VERB.finditer(task_text or ""):
        rest = task_text[m.end():]
        cut = _OBJECT_END.search(rest)
        obj = " ".join((rest[:cut.start()] if cut else rest).split()[:OBJECT_WORDS])
        out.append((_verb_key(m.group(1)), f"{m.group(1)} {obj}".strip(), obj))
    return out


def task_coverage(task_text: str, requirements: dict[str, str], givens: list[str]) -> dict:
    """D52: is the task carried into the Planner's Requirements and Givens? Every number the task states must
    appear in a requirement or a given; every deliverable-like phrase must map to a requirement — one that uses
    the same verb (any form: "test" is not "estimate") and, when the phrase names an object, shares a word of it."""
    carried = numbers_in("\n".join([*requirements.values(), *givens]))
    numbers = sorted(claim_numbers(task_text), key=lambda n: (len(n), n))
    phrases, missing = [], []
    for key, phrase, obj in deliverable_phrases(task_text):
        if phrase in phrases:
            continue
        phrases.append(phrase)
        words = _content(obj)
        if not any(re.search(r"\b" + DELIVERABLE_VERBS[key] + r"\b", r, re.I) and (not words or words & _content(r))
                   for r in requirements.values()):
            missing.append(phrase)
    miss_n = [n for n in numbers if n not in carried]
    return {"ok": not miss_n and not missing, "numbers": numbers, "missing_numbers": miss_n,
            "phrases": phrases, "missing_phrases": missing}


def draft_quality(d: Draft, task_text: str = "") -> dict:
    """task_text: the task as Box 2 saw it; without it (or without requirement ids) task_coverage is n/a."""
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
    key = lambda n: snake(normalise(n)[0])   # 'web_search' == 'Web search' == 'Web Research' (D29)
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
    declared = any(s.kind for s in steps)          # D37: the planner's kind: verify wins; keywords only as fallback
    candidates = [s for s in steps if s.depends_on and s.agent_names != [summ_name]
                  and (s.kind == "verify" if declared else VERIFY_WORDS.search(f"{s.text}\n{s.do}\n{s.done_when}"))]
    if any(s.depends_on for s in steps):
        found = []
        for s in candidates:
            producers = {n for dep in s.depends_on if dep in number for n in number[dep].agent_names}
            found.append({"step": s.index + 1, "verifiers": s.agent_names, "producers": sorted(producers),
                          "independent": bool(producers) and not set(s.agent_names) & producers})
        checks["independent_verification"] = {"ok": any(f["independent"] for f in found), "candidates": found}
    else:
        checks["independent_verification"] = {"ok": None, "detail": "no depends_on lines"}

    # 8. D52 task intake: every number and deliverable-like phrase of the task reaches a requirement or given
    if req and task_text:
        checks["task_coverage"] = task_coverage(task_text, d.requirements, d.givens)
    else:
        checks["task_coverage"] = {"ok": None, "detail": "no requirement ids (d19 draft or none written)"
                                   if not req else "no task text given"}

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
    if "task_coverage" in q["hard_failed"]:
        tc = c["task_coverage"]
        if tc["missing_numbers"]:
            lines.append(f"Numbers in the task that no requirement or given carries: {', '.join(tc['missing_numbers'])}. "
                         f"Add each to Givens and Assumptions (or to the requirement that uses it).")
        if tc["missing_phrases"]:
            lines.append("Task phrases no requirement keeps (same verb, same object): "
                         + "; ".join(f'"{x}"' for x in tc["missing_phrases"])
                         + ". Add a requirement for each, keeping the task's own verb.")
    return "\n".join(f"{i}. {x}" for i, x in enumerate(lines, 1))
