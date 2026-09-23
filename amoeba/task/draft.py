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
from amoeba.task.parsers import MissingSections, parse_json_objects, parse_plan, parse_role_blobs

PLANNER_SECTIONS = ["Selected Roles List", "Created Roles List", "Execution Plan", "RoleFeedback", "PlanFeedback"]
REQUESTS_SECTION = "Capability Requests"   # D19: optional — never required, so a missing one costs no repair call
MAX_ROUNDS = 3  # manager.py:27 num_steps = 3
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
        if str(d.get("name", "")).strip():
            out.append(CapabilityRequest(**{**d, "name": str(d["name"]).strip(), "source": "planner"}))
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


def section_requests(sec: dict[str, str], envelope: Envelope) -> list[CapabilityRequest]:
    """The requests one planner reply makes: its Capability Requests part plus unregistered tools in its role blobs.
    Works on copies; used to see which round-1 requests survive to the final draft."""
    roles, seen = [], set()
    for b in parse_role_blobs(sec.get("Created Roles List", "")) + parse_role_blobs(sec.get("Selected Roles List", "")):
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


def _sections(llm: TracedLLM, name: str, user: str, keys: list[str], seed: int,
              log: list[DraftRound]) -> tuple[str, dict[str, str]]:
    try:
        return llm.chat_sections(MANAGER_PREFIX, user, keys, seed, agent_name=name)  # action.py:60 system = prefix
    except MissingSections as e:
        raise DraftError(f"{name}: {e}", log) from e


def draft_team(task: Task, llm: LLMClient, envelope: Envelope, trace: TraceWriter, seed: int = 0) -> Draft:
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
            raw, sec = _sections(tl, "planner", render(   # D19 variants: may request missing capabilities
                PROMPT.autoagents_create_roles_d19, context=ctx, existing_roles="[]", tools=tools, history=history,
                suggestions=suggestions, format_example=PROMPT.autoagents_create_roles_format_d19),
                PLANNER_SECTIONS, seed, log)
            rec.planner_raw = raw
            rec.roles = parse_role_blobs(sec["Created Roles List"]) + parse_role_blobs(sec["Selected Roles List"])
            rec.plan = [{"agents": names, "text": text} for names, text in parse_plan(sec["Execution Plan"])]
            rec.capability_requests = parse_capability_requests(sec.get(REQUESTS_SECTION, ""))
            requests_text = sec.get(REQUESTS_SECTION, "").strip() or "None"
            if rounds == 0:
                first_requests = section_requests(sec, envelope)   # what the observers are shown first
            last = (raw, sec)
            history = raw   # original: str(instruct_content) pydantic repr (manager.py:33). DEVIATION D1: raw text

            # state 1 — Agent Observer (CheckRoles). Always runs: the guard at manager.py:34 is dead code.
            hist_roles = f"## Role Suggestions\n{sugg_roles}\n\n## Feedback\n{sec['RoleFeedback']}"   # manager.py:36
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
            rec.plan_observer_raw, s = _sections(tl, "plan_observer", render(
                PROMPT.autoagents_check_plans_d19, capability_requests=requests_text, context=task.prompt,   # D19
                roles=sec["Selected Roles List"] + sec["Created Roles List"],   # check_plans.py:72-75
                plan=sec["Execution Plan"], history=hist_plan, tools=tools,
                format_example=PROMPT.autoagents_check_plans_format), ["Suggestions"], seed, log)
            sp = rec.plan_observer = s["Suggestions"]
            sugg_plan += sp                           # manager.py:43
            suggestions = f"## Role Suggestions\n{sr}\n\n## Plan Suggestions\n{sp}"   # manager.py:45
            if NO_SUGGESTIONS in sr and NO_SUGGESTIONS in sp:
                consensus = rec.consensus = True
            # original tests the CUMULATIVE strings (manager.py:47): one early "No Suggestions" sticks forever.
            # DEVIATION D2: current-round test (stricter, saner).
            rounds += 1

    # publish: the LAST draft is used whether or not consensus was reached (manager.py:52-59)
    raw, sec = last
    blobs = parse_role_blobs(sec["Created Roles List"]) + parse_role_blobs(sec["Selected Roles List"])
    steps = parse_plan(sec["Execution Plan"])

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
    for i, (bracket, text) in enumerate(steps):
        who = [n for n in names if n in bracket]      # exact bracket match, roster order
        if not who:                                   # then the AutoAgents substring rule (group.py:61-64)
            head = text.split(":")[0]
            who = [n for n in names if n.replace("_", " ") in head]
        if who:                                       # original: empty match → UnboundLocalError (group.py:104)
            plan.append(DraftPlanStep(index=i, agent_names=who, text=text))
    if not plan:
        raise DraftError("empty plan", log)
    pick_summariser(roles, plan)                      # D20 (was: "the first role without tools")
    if not 2 <= len(roles) <= envelope.max_agents:
        raise DraftError(f"roster size {len(roles)} outside 2..{envelope.max_agents}", log)
    proposed, dropped = request_survival(first_requests, requests)
    for q in requests:
        trace.event("capability_request", {"capability.name": q.name, "capability.kind": q.kind,
                                           "capability.for_role": q.for_role, "capability.source": q.source})
    return Draft(created_roles=roles, plan=plan, rounds_used=rounds, consensus=consensus,
                 role_feedback=sugg_roles, plan_feedback=sugg_plan, raw_draft=raw, capability_requests=requests, rounds=log,
                 requests_proposed=proposed, requests_dropped_by_observers=dropped)
