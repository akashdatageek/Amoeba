"""Team configuration schema (spec §4). Names match the full BUILD_SPEC so later phases add fields, not renames."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["planner", "observer", "solver", "critic", "worker"]


class Contract(BaseModel):
    inputs: dict[str, str] = Field(default_factory=lambda: {"prior": "text"})
    outputs: dict[str, str] = Field(default_factory=lambda: {"result": "text"})
    effects: list[str] = Field(default_factory=list)


class Limits(BaseModel):
    """Loop caps only — not cost."""
    # Renamed from the full spec's Budget; Phase 3 adds token/usd fields here (no renames).

    max_turns: int = 5  # inner LLM turns per step (AutoAgents group.py:75 num_steps = 5)


class PromptRef(BaseModel):
    system: str  # literal or "seed:<stem>"
    user: str
    format: Literal["sections", "history+append"] = "sections"
    # "sections": AutoAgents — one user prompt, output parsed into "## Section" blocks
    # "history+append": AgentVerse — system=prepend, then chat-history messages, then user=append


class AgentSpec(BaseModel):
    agent_id: str  # str(uuid4()); durable
    name: str
    role: Role
    model: str
    prompt: PromptRef
    tools: list[str] = Field(default_factory=list)
    contract: Contract = Field(default_factory=Contract)
    limits: Limits = Field(default_factory=Limits)
    suggestions: str = ""  # AutoAgents role field
    description: str = ""  # AutoAgents role field (observers only) / AgentVerse role_description
    role_prompt: str = ""  # AutoAgents drafted `prompt` field; rendered into {role} of the USER message (custom_action.py:148)
    max_history: int = 5  # AgentVerse: solver 5, critic 3 (solver.py:23, critic.py:22)
    missing_tools: list[str] = Field(default_factory=list)   # tools the draft named that are not registered (D19)
    is_summariser: bool = False   # writes the team's final answer; boss_reviewers makes it the solver (D20)
    created_by: Literal["human", "drafter"] = "drafter"
    temperature: float = 0.2
    max_tokens: int = 2048


class Edge(BaseModel):
    src: str
    dst: str
    type: Literal["sequential", "review", "revise"]
    schema_id: str = "text"
    condition: str | None = None  # "critic_disagrees" only


class PlanStep(BaseModel):
    index: int
    agent_ids: list[str]
    text: str  # the raw "[Role A, Role B]: STEP TEXT" line


class TeamConfig(BaseModel):
    team_id: str
    version: int = 1
    parent_version: int | None = None
    name: str
    topology: Literal["flat", "boss_reviewers"]
    agents: dict[str, AgentSpec]
    edges: list[Edge]
    entry: list[str]
    exit: str
    plan: list[PlanStep] = Field(default_factory=list)  # flat only
    max_inner_turns: int = 3  # boss_reviewers only (vertical_solver_first.py:24)
    meta: dict = Field(default_factory=dict)
