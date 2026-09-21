"""Data records passed between the three boxes."""
from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    prompt: str
    family: str = "freeform"
    ground_truth: str | None = None  # toy tasks only
    tags: list[str] = Field(default_factory=list)


class Message(BaseModel):
    """One line of an episode's history (Who&When shape)."""

    name: str
    role: str
    content: str


class AgentResult(BaseModel):
    agent_id: str
    body: str
    success: bool = True
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class Episode(BaseModel):
    episode_id: str
    team_id: str
    team_version: int = 1
    task_id: str
    seed: int = 0
    answer: str | None = None
    error: str | None = None
    history: list[Message] = Field(default_factory=list)
    outputs: dict[str, list[AgentResult]] = Field(default_factory=dict)  # per agent_id, in order
    total_tokens: int = 0
    n_llm_calls: int = 0
    latency_ms: int = 0


class Answer(BaseModel):
    text: str | None
    error: str | None = None


class DraftedRole(BaseModel):
    """One JSON blob from the planner (AutoAgents keys: name, description, tools, suggestions, prompt)."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    tools: list[str] = Field(default_factory=list)
    suggestions: str = ""
    prompt: str = ""

    @field_validator("tools", mode="before")
    @classmethod
    def _tools_as_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(t) for t in v]

    @field_validator("description", "suggestions", "prompt", mode="before")
    @classmethod
    def _text(cls, v):
        return "" if v is None else str(v)


class DraftPlanStep(BaseModel):
    index: int
    agent_names: list[str]
    text: str  # the raw "[Role A, Role B]: STEP TEXT" line


class Draft(BaseModel):
    created_roles: list[DraftedRole]
    plan: list[DraftPlanStep]
    rounds_used: int
    consensus: bool
    role_feedback: str = ""
    plan_feedback: str = ""
    raw_draft: str = ""


class RunResult(BaseModel):
    run_id: str
    task_id: str
    team_id: str
    topology: str
    answer: str | None
    error: str | None
    score: float | None
    total_tokens: int
    latency_ms: int
    n_llm_calls: int
    draft_rounds: int
    consensus: bool
