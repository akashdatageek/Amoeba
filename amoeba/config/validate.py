"""Static validation of a TeamConfig against the envelope (spec §4.1). Returns a list of errors; empty = valid."""
from __future__ import annotations

import uuid

from amoeba.config.schema import TeamConfig
from amoeba.safety.envelope import Envelope


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, TypeError):
        return False


def validate(cfg: TeamConfig, envelope: Envelope) -> list[str]:
    errs: list[str] = []
    ids = set(cfg.agents)

    # V7  agent_ids unique, UUID-shaped
    seen: set[str] = set()
    for key, a in cfg.agents.items():
        if a.agent_id != key:
            errs.append(f"V7 agents[{key!r}].agent_id is {a.agent_id!r}")
        if a.agent_id in seen:
            errs.append(f"V7 duplicate agent_id {a.agent_id!r}")
        seen.add(a.agent_id)
        if not _is_uuid(a.agent_id):
            errs.append(f"V7 agent_id {a.agent_id!r} is not a UUID")

    # V1  edges reference existing agent_ids; exit exists; entry non-empty
    for e in cfg.edges:
        for end in (e.src, e.dst):
            if end not in ids:
                errs.append(f"V1 edge {e.src}->{e.dst} references unknown agent {end!r}")
    if cfg.exit not in ids:
        errs.append(f"V1 exit {cfg.exit!r} is not an agent")
    if not cfg.entry:
        errs.append("V1 entry is empty")
    for a in cfg.entry:
        if a not in ids:
            errs.append(f"V1 entry {a!r} is not an agent")

    # V3  edge.schema_id ∈ src.contract.outputs.values() and ∈ dst.contract.inputs.values()
    for e in cfg.edges:
        if e.src in ids and e.schema_id not in cfg.agents[e.src].contract.outputs.values():
            errs.append(f"V3 edge {e.src}->{e.dst}: {e.schema_id!r} not an output of src")
        if e.dst in ids and e.schema_id not in cfg.agents[e.dst].contract.inputs.values():
            errs.append(f"V3 edge {e.src}->{e.dst}: {e.schema_id!r} not an input of dst")

    # V5  agent.tools ⊆ envelope.allowed_tools[agent.role]
    for a in cfg.agents.values():
        extra = set(a.tools) - set(envelope.allowed_tools.get(a.role, []))
        if extra:
            errs.append(f"V5 agent {a.name!r} ({a.role}) uses tools outside the allowlist: {sorted(extra)}")

    # V6  2 ≤ len(agents) ≤ envelope.max_agents
    if not 2 <= len(cfg.agents) <= envelope.max_agents:
        errs.append(f"V6 team has {len(cfg.agents)} agents; need 2..{envelope.max_agents}")

    # V8  topology-specific shape
    if cfg.topology == "plan":   # D31: the depends_on graph must have no unknown step and no cycle
        from amoeba.interp.plan_runner import PlanGraphError, waves
        if not cfg.plan:
            errs.append("V8 plan: plan is empty")
        for s in cfg.plan:
            if not s.agent_ids or any(a not in ids for a in s.agent_ids):
                errs.append(f"V8 plan: step {s.index + 1} names no or an unknown agent")
        try:
            if cfg.plan:
                waves(cfg.plan)
        except PlanGraphError as e:
            errs.append(f"V8 plan: {e}")
    elif cfg.topology == "flat":
        if not cfg.plan:
            errs.append("V8 flat: plan is empty")
        for s in cfg.plan:
            if not s.agent_ids:
                errs.append(f"V8 flat: step {s.index} names no agent")
            for a in s.agent_ids:
                if a not in ids:
                    errs.append(f"V8 flat: step {s.index} names unknown agent {a!r}")
    else:
        n_solver = sum(a.role == "solver" for a in cfg.agents.values())
        n_critic = sum(a.role == "critic" for a in cfg.agents.values())
        if n_solver != 1:
            errs.append(f"V8 boss_reviewers: need exactly one solver, found {n_solver}")
        if n_critic < 1:
            errs.append("V8 boss_reviewers: need at least one critic")
    return errs
