"""Draft → TeamConfig (spec §5.3). Plain code: durable ids, edges, entry/exit, validation."""
from __future__ import annotations

from itertools import pairwise
from uuid import uuid4

from amoeba.config.prompts import GROUP_PREFIX
from amoeba.config.schema import AgentSpec, Edge, PlanStep, PromptRef, TeamConfig
from amoeba.config.validate import validate
from amoeba.safety.envelope import Envelope
from amoeba.task.draft import DraftError
from amoeba.task.models import Draft, Task


# box: ov_plan, instantiate
def instantiate(draft: Draft, topology: str, task: Task, envelope: Envelope) -> TeamConfig:
    agents: dict[str, AgentSpec] = {}
    by_name: dict[str, str] = {}
    for r in draft.created_roles:
        aid = str(uuid4())
        by_name[r.name] = aid
        agents[aid] = AgentSpec(
            agent_id=aid, name=r.name, role="worker", model=envelope.default_model,
            # GROUP_PREFIX is the system message (group.py:23, role.py:17); the drafted role prompt goes into the
            # USER message as {role} (custom_action.py:148), as in the original
            prompt=PromptRef(system=GROUP_PREFIX, user="seed:autoagents_custom_action", format="sections"),
            tools=list(r.tools), suggestions=r.suggestions, role_prompt=r.prompt,
            missing_tools=list(r.missing_tools), is_summariser=r.is_summariser,
            goal=r.goal, skills=list(r.skills), outputs=list(r.outputs), success_criteria=list(r.success_criteria),
            constraints=list(r.constraints),
            description=r.description or r.prompt,   # AgentVerse ${role_description}: description, else prompt
        )
    common = dict(team_id=str(uuid4()), name=f"team-{topology}-{task.id[:8]}",
                  meta={"task_id": task.id, "draft_rounds": draft.rounds_used, "consensus": draft.consensus})

    if topology == "flat":
        plan = [PlanStep(index=s.index, agent_ids=[by_name[n] for n in s.agent_names], text=s.text, kind=s.kind, covers=s.covers,
                         depends_on=s.depends_on, do=s.do, output=s.output, done_when=s.done_when)   # D24 detail
                for s in draft.plan]
        edges = [Edge(src=a, dst=b, type="sequential")
                 for s1, s2 in pairwise(plan) for a in s1.agent_ids for b in s2.agent_ids]
        cfg = TeamConfig(**common, topology="flat", agents=agents, edges=edges,
                         entry=list(plan[0].agent_ids), exit=plan[-1].agent_ids[-1], plan=plan)
    elif topology == "boss_reviewers":   # AgentVerse vertical-solver-first
        solver_id = next(by_name[r.name] for r in draft.created_roles if r.is_summariser)   # D20 flag, not "no tools"
        agents[solver_id].role = "solver"
        agents[solver_id].max_history = 5
        agents[solver_id].prompt = PromptRef(system="seed:agentverse_solver_prepend",
                                             user="seed:agentverse_solver_append_generic", format="history+append")
        critics = [a for a in agents if a != solver_id]
        for c in critics:
            agents[c].role = "critic"
            agents[c].max_history = 3
            agents[c].prompt = PromptRef(system="seed:agentverse_critic_prepend",
                                         user="seed:agentverse_critic_append", format="history+append")
        edges = [Edge(src=solver_id, dst=c, type="review") for c in critics] + \
                [Edge(src=c, dst=solver_id, type="revise", condition="critic_disagrees") for c in critics]
        cfg = TeamConfig(**common, topology="boss_reviewers", agents=agents, edges=edges,
                         entry=[solver_id], exit=solver_id, max_inner_turns=3)
    elif topology == "plan":   # D31: the plan runner over depends_on (amoeba/interp/plan_runner.py)
        from amoeba.interp.plan_runner import PLAN_MAX_TOKENS, number, relink
        plan = [PlanStep(index=s.index, agent_ids=[by_name[n] for n in s.agent_names], text=s.text, kind=s.kind, covers=s.covers,
                         depends_on=s.depends_on, do=s.do, output=s.output, done_when=s.done_when)
                for s in draft.plan]
        written = {i + 1: list(w.get("depends_on") or []) for i, w in enumerate(draft.rounds[-1].plan)} \
            if draft.rounds else {}
        plan, relinked = relink(plan, written)
        for a in agents.values():
            a.max_tokens = PLAN_MAX_TOKENS
        steps = {number(s): s for s in plan}
        edges = list({(a, b): Edge(src=a, dst=b, type="sequential") for s in plan for d in s.depends_on
                      if d in steps for a in steps[d].agent_ids for b in s.agent_ids if a != b}.values())
        roots = [s for s in plan if not any(d in steps for d in s.depends_on)] or plan[:1]
        last = plan[-1]
        exit_id = next((a for a in last.agent_ids if agents[a].is_summariser), last.agent_ids[-1])
        cfg = TeamConfig(**common, topology="plan", agents=agents, edges=edges,
                         entry=list(dict.fromkeys(a for s in roots for a in s.agent_ids)), exit=exit_id, plan=plan,
                         requirements=dict(draft.requirements))   # D35: the summariser's deliverable list
        cfg.meta["dependency_relinked"] = relinked
        # D32: who asked for what, so Box 3 can hand a role the tools that now exist for its request
        cfg.meta["capability_requests"] = [{"name": q.name, "for_role": q.for_role, "canonical": q.canonical}
                                           for q in draft.capability_requests]
    else:
        raise ValueError(f"unknown topology {topology!r}")

    errs = validate(cfg, envelope)
    if errs:
        raise DraftError("invalid team: " + "; ".join(errs))
    return cfg
