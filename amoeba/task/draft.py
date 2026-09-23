"""BOX 2 — Plan a new team: the AutoAgents drafting trio (spec §5.2), then deterministic post-checks.

Source: AutoAgents roles/manager.py Manager._act (loop), environment.py publish_message/_parser_roles/_parser_plan
(parsing), actions/{create_roles,check_roles,check_plans}.py (prompts), actions/action/action.py _aask_v1.
"""
from __future__ import annotations

from amoeba.config.prompts import MANAGER_PREFIX, PROMPT, render
from amoeba.interp.trace import TracedLLM, TraceWriter
from amoeba.llm.client import LLMClient
from amoeba.safety.envelope import Envelope
from amoeba.task.models import CapabilityRequest, Draft, DraftedRole, DraftPlanStep, DraftRound, Task
from amoeba.task.quality import draft_quality
import re

from amoeba.task.parsers import (MissingSections, parse_bullets, parse_json_objects, parse_plan, parse_plan_d24,
                                 parse_requirements, parse_sections, parse_verdict)

PLANNER_SECTIONS = ["Selected Roles List", "Created Roles List", "Execution Plan", "RoleFeedback", "PlanFeedback"]
# DEVIATION D24 (spec/BOX2_PROMPT_UPGRADE_D24.md): our prompts, one system message per role, more sections
D19, D24 = "d19", "d24"
DRAFT_PROMPTS = (D19, D24)
D24_PLANNER_SECTIONS = ["Requirements", "Givens and Assumptions", "Selected Roles List", "Created Roles List",
                        "Execution Plan", "Risks and Decisions", "RoleFeedback", "PlanFeedback"]
REQUESTS_SECTION = "Capability Requests"   # D19: optional — never required, so a missing one costs no repair call
MAX_ROUNDS = 3  # manager.py:27 num_steps = 3
PLANNER_MAX_TOKENS = 8192     # D24: a detailed draft does not fit the client default (2048); a cut-off one fails
OBSERVER_MAX_TOKENS = 2048    # to parse, and the trace flags any reply that stops at its limit
NO_SUGGESTIONS = "No Suggestions"


class DraftError(RuntimeError):
    """Drafting failed. `rounds` holds every round up to the failure, so a failed draft is still on record."""

    def __init__(self, message: str, rounds: list[DraftRound] | None = None):
        super().__init__(message)
        self.rounds = rounds if rounds is not None else []


def parse_capability_requests(text: str) -> list[CapabilityRequest]:
    """The planner's "## Capability Requests" section (D19). 'None', prose or bad JSON yield nothing."""
    out: list[CapabilityRequest] = []
    for d in parse_json_objects(text or ""):
        # the D19 keys; a blob that names its capability "request"/"tool"/"capability" and gives a "reason" (as
        # models write when not shown the keys) is kept too rather than dropped
        name = next((str(d[k]).strip() for k in ("name", "request", "tool", "capability") if str(d.get(k, "")).strip()), "")
        if name:
            extra = {"what_it_does": d["reason"]} if "reason" in d and "what_it_does" not in d else {}
            out.append(CapabilityRequest(**{**d, **extra, "name": name, "source": "planner"}))
    return out


def resolve_tools(roles: list[DraftedRole], envelope: Envelope,
                  requests: list[CapabilityRequest]) -> list[CapabilityRequest]:
    """Keep each role's registered tools; a name the registry lacks becomes a recorded request and the role's
    `missing_tools`, never a silent drop (D19). Returns `requests` plus the new ones, one per (name, role)."""
    out = list(requests)
    seen = {(r.name, r.for_role) for r in out}
    for role in roles:
        kept, missing = [], []
        for t in role.tools:
            (kept if t in envelope.allowed_tool_names else missing).append(t)
        role.tools, role.missing_tools = kept, missing
        for t in missing:
            if (t, role.name) not in seen and (t, "") not in seen:
                out.append(CapabilityRequest(name=t, kind="tool", for_role=role.name, source="unregistered_tool",
                                             what_it_does="named in the role's tools; no such tool is registered"))
                seen.add((t, role.name))
    return out


def role_blobs(sec: dict[str, str]) -> list[dict]:
    """Role JSON blobs of one planner reply, Created then Selected. DEVIATION D22: brace-balanced parsing
    (parse_json_objects) instead of AutoAgents' non-greedy regex (environment.py:62, kept as parse_role_blobs for T3),
    which cut a blob short at the first '}' inside a role prompt ('{expression}') or a nested object."""
    return parse_json_objects(sec.get("Created Roles List", "")) + parse_json_objects(sec.get("Selected Roles List", ""))


def section_requests(sec: dict[str, str], envelope: Envelope) -> list[CapabilityRequest]:
    """The requests one planner reply makes: its Capability Requests part plus unregistered tools in its role blobs.
    Works on copies; used to see which round-1 requests survive to the final draft."""
    roles, seen = [], set()
    for b in role_blobs(sec):
        name = str(b.get("name", "")).strip()
        if name and name not in seen:
            seen.add(name)
            roles.append(DraftedRole(**b))
    return resolve_tools(roles, envelope, parse_capability_requests(sec.get(REQUESTS_SECTION, "")))


def request_survival(first: list[CapabilityRequest], final: list[CapabilityRequest]) -> tuple[int, int]:
    """(requests_proposed, requests_dropped_by_observers): distinct capability names asked for in round 1, and how
    many of them the final draft no longer asks for. Matched by name, case-insensitive (roles may be renamed)."""
    proposed = {q.name.lower() for q in first}
    return len(proposed), len(proposed - {q.name.lower() for q in final})


def pick_summariser(roles: list[DraftedRole], plan: list[DraftPlanStep]) -> DraftedRole:
    """D20: the role that writes the final answer — the first one the planner marks "is_summariser": true, else
    the last role named by the plan's last step (the flat runner's exit). Having no tools says nothing about it;
    the plan is never empty here, so a summariser always exists (replaces the code-appended Language Expert)."""
    flagged = [r for r in roles if r.is_summariser]
    last = plan[-1].agent_names[-1]
    chosen = flagged[0] if flagged else next(r for r in roles if r.name == last)
    for r in roles:
        r.is_summariser = r is chosen
    return chosen


def requirements_text(sec: dict[str, str]) -> str:
    """D24: what the observers are shown as the planner's requirements and givens."""
    return (f"## Requirements\n{sec.get('Requirements', '')}\n\n"
            f"## Givens and Assumptions\n{sec.get('Givens and Assumptions', '')}")


_NUMBERED = re.compile(r"^\s*(?:[-*]\s*)?\**\d+[.)]\**\s+(?!\**No Suggestions)\S", re.M)


def n_suggestions(text: str) -> int:
    """Numbered suggestion lines in an observer's Suggestions ('1. No Suggestions' is not one)."""
    return len(_NUMBERED.findall(text or ""))


def approves(suggestions: str) -> bool:
    """d19 approval. The original tests the substring "No Suggestions" (manager.py:47). DEVIATION D25: a reply that
    also lists a numbered suggestion is not an approval — real replies list four fixes and then add
    "No Suggestions." (the db-choice transcript, attempt 1 round 2)."""
    return NO_SUGGESTIONS in suggestions and n_suggestions(suggestions) == 0


def _observer_sections(llm: TracedLLM, name: str, user: str, seed: int, log: list[DraftRound],
                       system: str) -> tuple[str, dict[str, str]]:
    """D24 observers must write '## Verdict'. A missing one costs the usual single repair call; if the repaired
    reply still has none, its sections are used and the missing verdict counts as REVISE."""
    try:
        return llm.chat_sections(system, user, ["Suggestions", "Verdict"], seed, agent_name=name,
                                 max_tokens=OBSERVER_MAX_TOKENS)
    except MissingSections as e:
        if e.missing == ["Verdict"] and getattr(e, "raw", None) is not None:
            return e.raw, parse_sections(e.raw)
        raise DraftError(f"{name}: {e}", log) from e


def _sections(llm: TracedLLM, name: str, user: str, keys: list[str], seed: int,
              log: list[DraftRound], system: str = MANAGER_PREFIX) -> tuple[str, dict[str, str]]:
    try:
        return llm.chat_sections(system, user, keys, seed, agent_name=name,   # action.py:60 system = prefix (d19)
                                 max_tokens=PLANNER_MAX_TOKENS if name == "planner" else OBSERVER_MAX_TOKENS)
    except MissingSections as e:
        raise DraftError(f"{name}: {e}", log) from e


def draft_team(task: Task, llm: LLMClient, envelope: Envelope, trace: TraceWriter, seed: int = 0,
               prompts: str = D19) -> Draft:
    if prompts not in DRAFT_PROMPTS:
        raise ValueError(f"unknown draft prompts {prompts!r}; expected one of {DRAFT_PROMPTS}")
    d24 = prompts == D24
    tl = TracedLLM(llm, trace)
    tools = envelope.tool_catalog_string()
    ctx = f"[Question/Task: {task.prompt}]"          # manager.py:32 str(important_memory) — keep the bracketed form
    history = ""                                      # manager.py:26 roles_plan
    sugg_roles, sugg_plan = "", ""                    # manager.py:26 — cumulative strings
    suggestions = ""                                  # manager.py:27 — what the planner sees: LATEST round only
    consensus, rounds, last = False, 0, None
    first_requests: list[CapabilityRequest] = []
    log: list[DraftRound] = []                        # ours: the full record of every round (Draft.rounds)
    with trace.span("invoke_agent", {"gen_ai.agent.name": "planner"}):
        while not consensus and rounds < MAX_ROUNDS:  # manager.py:27,30
            log.append(rec := DraftRound(index=rounds + 1))
            # state 0 — Planner (CreateRoles)
            if d24:   # D24: plan the ideal first, full role records, detailed steps, requirements and givens
                raw, sec = _sections(tl, "planner", render(
                    PROMPT.d24_create_team, context=task.prompt, existing_roles="[]", tools=tools, history=history,
                    suggestions=suggestions, max_agents=str(envelope.max_agents),
                    format_example=PROMPT.d24_create_team_format),
                    D24_PLANNER_SECTIONS, seed, log, system=PROMPT.d24_planner_system.strip())
            else:
                raw, sec = _sections(tl, "planner", render(   # D19 variants: may request missing capabilities
                    PROMPT.autoagents_create_roles_d19, context=ctx, existing_roles="[]", tools=tools, history=history,
                    suggestions=suggestions, format_example=PROMPT.autoagents_create_roles_format_d19),
                    PLANNER_SECTIONS, seed, log)
            rec.planner_raw = raw
            rec.roles = role_blobs(sec)
            rec.plan = ([{"agents": names, "text": text, **fields}
                         for names, text, fields in parse_plan_d24(sec["Execution Plan"])] if d24 else
                        [{"agents": names, "text": text} for names, text in parse_plan(sec["Execution Plan"])])
            rec.capability_requests = parse_capability_requests(sec.get(REQUESTS_SECTION, ""))
            requests_text = sec.get(REQUESTS_SECTION, "").strip() or "None"
            if rounds == 0:
                first_requests = section_requests(sec, envelope)   # what the observers are shown first
            last = (raw, sec)
            history = raw   # original: str(instruct_content) pydantic repr (manager.py:33). DEVIATION D1: raw text

            # state 1 — Agent Observer (CheckRoles). Always runs: the guard at manager.py:34 is dead code.
            hist_roles = f"## Role Suggestions\n{sugg_roles}\n\n## Feedback\n{sec['RoleFeedback']}"   # manager.py:36
            if d24:
                rec.agent_observer_raw, s = _observer_sections(tl, "agent_observer", render(
                    PROMPT.d24_review_team, question=task.prompt, requirements=requirements_text(sec),
                    created_roles=sec["Created Roles List"], selected_roles=sec["Selected Roles List"],
                    capability_requests=requests_text, tools=tools, history=hist_roles,
                    max_agents=str(envelope.max_agents)),
                    seed, log, system=PROMPT.d24_agent_observer_system.strip())
                rec.agent_verdict = parse_verdict(s) or "REVISE"
            else:
                rec.agent_observer_raw, s = _sections(tl, "agent_observer", render(
                    PROMPT.autoagents_check_roles_d19, capability_requests=requests_text,   # D19
                    question=task.prompt,   # original: regex on the planner's raw text (check_roles.py:95); DEVIATION D4
                    existing_roles="[]", selected_roles=sec["Selected Roles List"], created_roles=sec["Created Roles List"],
                    history=hist_roles, tools=tools,   # original TOOLS='None' for observers (check_roles.py:86); DEVIATION D4
                    format_example=PROMPT.autoagents_check_roles_format), ["Suggestions"], seed, log)
            sr = rec.agent_observer = s["Suggestions"]
            sugg_roles += sr                          # manager.py:38

            # state 2 — Plan Observer (CheckPlans)
            hist_plan = f"## Plan Suggestions\n{sugg_plan}\n\n## Feedback\n{sec['PlanFeedback']}"
            # original passes sugg_roles here (manager.py:41) — a bug; fixed (DEVIATION D3)
            if d24:
                rec.plan_observer_raw, s = _observer_sections(tl, "plan_observer", render(
                    PROMPT.d24_review_plan, context=task.prompt, requirements=requirements_text(sec),
                    roles=sec["Selected Roles List"] + sec["Created Roles List"], plan=sec["Execution Plan"],
                    risks=sec["Risks and Decisions"], capability_requests=requests_text, history=hist_plan),
                    seed, log, system=PROMPT.d24_plan_observer_system.strip())
                rec.plan_verdict = parse_verdict(s) or "REVISE"
            else:
                rec.plan_observer_raw, s = _sections(tl, "plan_observer", render(
                    PROMPT.autoagents_check_plans_d19, capability_requests=requests_text, context=task.prompt,   # D19
                    roles=sec["Selected Roles List"] + sec["Created Roles List"],   # check_plans.py:72-75
                    plan=sec["Execution Plan"], history=hist_plan, tools=tools,
                    format_example=PROMPT.autoagents_check_plans_format), ["Suggestions"], seed, log)
            sp = rec.plan_observer = s["Suggestions"]
            sugg_plan += sp                           # manager.py:43
            suggestions = f"## Role Suggestions\n{sr}\n\n## Plan Suggestions\n{sp}"   # manager.py:45
            rec.agent_suggestions_n, rec.plan_suggestions_n = n_suggestions(sr), n_suggestions(sp)
            if (rec.agent_verdict == rec.plan_verdict == "APPROVE") if d24 else (approves(sr) and approves(sp)):
                consensus = rec.consensus = True   # D24: both verdicts exactly APPROVE; d19: D2 + D25
            # original tests the CUMULATIVE strings (manager.py:47): one early "No Suggestions" sticks forever.
            # DEVIATION D2: current-round test (stricter, saner).
            rounds += 1

    # publish: the LAST draft is used whether or not consensus was reached (manager.py:52-59)
    raw, sec = last
    blobs = role_blobs(sec)                           # D22
    steps = parse_plan_d24(sec["Execution Plan"]) if d24 else \
        [(names, text, {}) for names, text in parse_plan(sec["Execution Plan"])]   # D24 keeps the step detail

    # DEVIATION D5 — deterministic post-checks; none exist in AutoAgents (all are prompt-only there):
    roles: list[DraftedRole] = []
    for b in blobs:
        if not str(b.get("name", "")).strip():
            continue   # a blob without a name cannot be addressed by a plan step
        r = DraftedRole(**b)
        if any(x.name == r.name for x in roles):
            continue   # duplicate names would collide in the roster; keep the first
        roles.append(r)
    # D19: unregistered tool names are recorded as capability requests, not dropped silently
    requests = resolve_tools(roles, envelope, parse_capability_requests(sec.get(REQUESTS_SECTION, "")))
    names = [r.name for r in roles]
    plan: list[DraftPlanStep] = []
    for i, (bracket, text, fields) in enumerate(steps):
        who = [n for n in names if n in bracket]      # exact bracket match, roster order
        if not who:                                   # then the AutoAgents substring rule (group.py:61-64)
            head = text.split(":")[0]
            who = [n for n in names if n.replace("_", " ") in head]
        if who:                                       # original: empty match → UnboundLocalError (group.py:104)
            plan.append(DraftPlanStep(index=i, agent_names=who, text=text, **fields))
    if not plan:
        raise DraftError("empty plan", log)
    pick_summariser(roles, plan)                      # D20 (was: "the first role without tools")
    if not 2 <= len(roles) <= envelope.max_agents:
        raise DraftError(f"roster size {len(roles)} outside 2..{envelope.max_agents}", log)
    proposed, dropped = request_survival(first_requests, requests)
    for q in requests:
        trace.event("capability_request", {"capability.name": q.name, "capability.kind": q.kind,
                                           "capability.for_role": q.for_role, "capability.source": q.source})
    d = Draft(created_roles=roles, plan=plan, rounds_used=rounds, consensus=consensus,
                 role_feedback=sugg_roles, plan_feedback=sugg_plan, raw_draft=raw, capability_requests=requests, rounds=log,
                 requests_proposed=proposed, requests_dropped_by_observers=dropped, prompts=prompts,
                 requirements=parse_requirements(sec.get("Requirements", "")) if d24 else {},
                 givens=parse_bullets(sec.get("Givens and Assumptions", "")) if d24 else [],
                 risks=parse_bullets(sec.get("Risks and Decisions", "")) if d24 else [])
    d.quality = draft_quality(d)                      # D24: measured, never used to reject (yet)
    trace.event("draft_quality", {"amoeba.quality.passed": d.quality["passed"],
                                  "amoeba.quality.failed": d.quality["failed"],
                                  "amoeba.quality.failed_checks": ",".join(d.quality["failed_checks"]) or None})
    return d
