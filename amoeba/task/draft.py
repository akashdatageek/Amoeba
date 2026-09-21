"""BOX 2 — Plan a new team: the AutoAgents drafting trio (spec §5.2), then deterministic post-checks.

Source: AutoAgents roles/manager.py Manager._act (loop), environment.py publish_message/_parser_roles/_parser_plan
(parsing), actions/{create_roles,check_roles,check_plans}.py (prompts), actions/action/action.py _aask_v1.
"""
from __future__ import annotations

from amoeba.config.prompts import MANAGER_PREFIX, PROMPT, render
from amoeba.interp.trace import TracedLLM, TraceWriter
from amoeba.llm.client import LLMClient
from amoeba.safety.envelope import Envelope
from amoeba.task.models import Draft, DraftedRole, DraftPlanStep, Task
from amoeba.task.parsers import MissingSections, parse_plan, parse_role_blobs

PLANNER_SECTIONS = ["Selected Roles List", "Created Roles List", "Execution Plan", "RoleFeedback", "PlanFeedback"]
MAX_ROUNDS = 3  # manager.py:27 num_steps = 3
NO_SUGGESTIONS = "No Suggestions"


class DraftError(RuntimeError):
    pass


def language_expert() -> DraftedRole:
    """The summariser plain code guarantees (the original only asks for it in the prompt)."""
    return DraftedRole(name="Language Expert",
                       description="A language expert with no tools who summarizes the final results.",
                       tools=[], suggestions="State the established result exactly; add nothing.",
                       prompt=PROMPT.language_expert)


def _sections(llm: TracedLLM, name: str, user: str, keys: list[str], seed: int) -> tuple[str, dict[str, str]]:
    try:
        return llm.chat_sections(MANAGER_PREFIX, user, keys, seed, agent_name=name)  # action.py:60 system = prefix
    except MissingSections as e:
        raise DraftError(f"{name}: {e}") from e


def draft_team(task: Task, llm: LLMClient, envelope: Envelope, trace: TraceWriter, seed: int = 0) -> Draft:
    tl = TracedLLM(llm, trace)
    tools = envelope.tool_catalog_string()
    ctx = f"[Question/Task: {task.prompt}]"          # manager.py:32 str(important_memory) — keep the bracketed form
    history = ""                                      # manager.py:26 roles_plan
    sugg_roles, sugg_plan = "", ""                    # manager.py:26 — cumulative strings
    suggestions = ""                                  # manager.py:27 — what the planner sees: LATEST round only
    consensus, rounds, last = False, 0, None
    with trace.span("invoke_agent", {"gen_ai.agent.name": "planner"}):
        while not consensus and rounds < MAX_ROUNDS:  # manager.py:27,30
            # state 0 — Planner (CreateRoles)
            raw, sec = _sections(tl, "planner", render(
                PROMPT.autoagents_create_roles, context=ctx, existing_roles="[]", tools=tools, history=history,
                suggestions=suggestions, format_example=PROMPT.autoagents_create_roles_format), PLANNER_SECTIONS, seed)
            last = (raw, sec)
            history = raw   # original: str(instruct_content) pydantic repr (manager.py:33). DEVIATION D1: raw text

            # state 1 — Agent Observer (CheckRoles). Always runs: the guard at manager.py:34 is dead code.
            hist_roles = f"## Role Suggestions\n{sugg_roles}\n\n## Feedback\n{sec['RoleFeedback']}"   # manager.py:36
            _, s = _sections(tl, "agent_observer", render(
                PROMPT.autoagents_check_roles,
                question=task.prompt,   # original: regex on the planner's raw text (check_roles.py:95); DEVIATION D4
                existing_roles="[]", selected_roles=sec["Selected Roles List"], created_roles=sec["Created Roles List"],
                history=hist_roles, tools=tools,   # original TOOLS='None' for observers (check_roles.py:86); DEVIATION D4
                format_example=PROMPT.autoagents_check_roles_format), ["Suggestions"], seed)
            sr = s["Suggestions"]
            sugg_roles += sr                          # manager.py:38

            # state 2 — Plan Observer (CheckPlans)
            hist_plan = f"## Plan Suggestions\n{sugg_plan}\n\n## Feedback\n{sec['PlanFeedback']}"
            # original passes sugg_roles here (manager.py:41) — a bug; fixed (DEVIATION D3)
            _, s = _sections(tl, "plan_observer", render(
                PROMPT.autoagents_check_plans, context=task.prompt,
                roles=sec["Selected Roles List"] + sec["Created Roles List"],   # check_plans.py:72-75
                plan=sec["Execution Plan"], history=hist_plan, tools=tools,
                format_example=PROMPT.autoagents_check_plans_format), ["Suggestions"], seed)
            sp = s["Suggestions"]
            sugg_plan += sp                           # manager.py:43
            suggestions = f"## Role Suggestions\n{sr}\n\n## Plan Suggestions\n{sp}"   # manager.py:45
            if NO_SUGGESTIONS in sr and NO_SUGGESTIONS in sp:
                consensus = True
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
        r.tools = [t for t in r.tools if t in envelope.allowed_tool_names]
        roles.append(r)
    if not any(not r.tools for r in roles):
        roles.append(language_expert())               # summariser guaranteed by code
    if not 2 <= len(roles) <= envelope.max_agents:
        raise DraftError(f"roster size {len(roles)} outside 2..{envelope.max_agents}")
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
        raise DraftError("empty plan")
    return Draft(created_roles=roles, plan=plan, rounds_used=rounds, consensus=consensus,
                 role_feedback=sugg_roles, plan_feedback=sugg_plan, raw_draft=raw)
