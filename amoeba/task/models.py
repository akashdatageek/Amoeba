"""Data records passed between the three boxes."""
from __future__ import annotations

import json
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    prompt: str
    family: str = "freeform"
    ground_truth: str | None = None  # toy tasks only
    tags: list[str] = Field(default_factory=list)
    expected: dict = Field(default_factory=dict)   # eval only, e.g. {"derived": [["10 TB", "10,000 GB"]]} (D24)


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
    blocked_steps: list[dict] = Field(default_factory=list)          # steps a helper answered BLOCKED: X (D21)
    requested_capabilities: list[CapabilityRequest] = Field(default_factory=list)   # unknown tools chosen at run time


class Answer(BaseModel):
    text: str | None
    error: str | None = None


class CapabilityRequest(BaseModel):
    """A tool or skill the team asked for that the registry does not have (D19). Recorded, never acted on."""

    model_config = ConfigDict(extra="ignore")

    name: str
    kind: Literal["tool", "skill"] = "tool"
    for_role: str = ""
    what_it_does: str = ""
    input: str = ""
    output: str = ""
    example_input: str = ""
    example_output: str = ""
    # planner = listed under "## Capability Requests"; unregistered_tool = a role's tools named it and the resolver
    # found no such tool; runtime_unknown_tool = a helper chose it as an action during the run
    source: Literal["planner", "unregistered_tool", "runtime_unknown_tool"] = "planner"
    # D29: the canonical name from amoeba/capabilities/aliases.yaml; `name` keeps what the model wrote
    canonical: str = ""
    mapped: bool = False

    @model_validator(mode="after")
    def _canonical(self):
        if not self.canonical:
            from amoeba.capabilities import normalise
            self.canonical, self.mapped = normalise(self.name)
        return self

    @field_validator("name", "for_role", "what_it_does", "input", "output", "example_input", "example_output",
                     mode="before")
    @classmethod
    def _as_text(cls, v):
        if v is None:
            return ""
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, v):
        return "skill" if str(v or "").strip().lower() == "skill" else "tool"


class DraftedRole(BaseModel):
    """One JSON blob from the planner (AutoAgents keys: name, description, tools, suggestions, prompt)."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    tools: list[str] = Field(default_factory=list)
    suggestions: str = ""
    prompt: str = ""
    missing_tools: list[str] = Field(default_factory=list)   # named by the planner, not registered (D19)
    is_summariser: bool = False   # the role that writes the final answer (D20); never inferred from "has no tools"
    # D24 role record (empty for d19 drafts): what the role must know, receive, produce and how it is judged
    seniority: str = ""
    goal: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[Any] = Field(default_factory=list)          # {"artifact", "format"} objects or plain strings
    success_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    covers: list[str] = Field(default_factory=list)            # requirement ids, e.g. ["R1", "R3"]

    @field_validator("tools", mode="before")
    @classmethod
    def _tools_as_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(t) for t in v]

    @field_validator("description", "suggestions", "prompt", "seniority", "goal", mode="before")
    @classmethod
    def _text(cls, v):
        return "" if v is None else str(v)

    @field_validator("responsibilities", "skills", "inputs", "success_criteria", "constraints", "covers",
                     mode="before")
    @classmethod
    def _str_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        return [x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in v]

    @field_validator("outputs", mode="before")
    @classmethod
    def _outputs(cls, v):
        if v is None:
            return []
        return [v] if isinstance(v, (str, dict)) else list(v)


class DraftPlanStep(BaseModel):
    index: int
    agent_names: list[str]
    text: str  # the raw "[Role A, Role B]: STEP TEXT" line
    # D24 step detail, from the indented lines under the first line (empty for d19 drafts)
    title: str = ""
    covers: list[str] = Field(default_factory=list)
    depends_on: list[int] = Field(default_factory=list)       # step numbers as written (1-based)
    do: str = ""
    output: str = ""
    done_when: str = ""


class DraftRound(BaseModel):
    """One drafting round, as it happened: the Planner's reply (raw and parsed) and both observers' replies."""

    index: int                                                    # 1-based
    planner_raw: str = ""
    roles: list[dict] = Field(default_factory=list)               # role blobs as parsed from this reply (before checks)
    plan: list[dict] = Field(default_factory=list)                # [{"agents": [...], "text": "..."}] as written
    capability_requests: list[CapabilityRequest] = Field(default_factory=list)   # this reply's own section (D19)
    agent_observer_raw: str = ""
    agent_observer: str = ""                                      # its Suggestions section
    plan_observer_raw: str = ""
    plan_observer: str = ""
    consensus: bool = False                                       # both approved this round (D2; D25 / D24 rules)
    gate_failed: list[str] = Field(default_factory=list)          # D28 --quality-gate: hard checks this round failed
    agent_verdict: str | None = None                              # D24: APPROVE | REVISE | OTHER; None for d19
    plan_verdict: str | None = None
    agent_suggestions_n: int = 0                                  # numbered suggestions in each observer's reply
    plan_suggestions_n: int = 0


class Draft(BaseModel):
    created_roles: list[DraftedRole]
    plan: list[DraftPlanStep]
    rounds_used: int
    consensus: bool
    role_feedback: str = ""
    plan_feedback: str = ""
    raw_draft: str = ""
    capability_requests: list[CapabilityRequest] = Field(default_factory=list)
    rounds: list[DraftRound] = Field(default_factory=list)     # every round, in order; the last one is raw_draft
    prompts: str = "d19"                                           # which drafting prompts ran: d19 | d24 (D24)
    requirements: dict[str, str] = Field(default_factory=dict)     # D24: {"R1": "...", ...} in order
    givens: list[str] = Field(default_factory=list)                # D24: givens, derived numbers, assumptions
    risks: list[str] = Field(default_factory=list)                 # D24: risks and decision points
    quality: dict = Field(default_factory=dict)                    # D24 draft_quality checks (recorded, not enforced)
    gate_hits: int = 0                                             # D28: rounds the --quality-gate sent back
    requests_proposed: int = 0                 # distinct capabilities asked for in round 1
    requests_dropped_by_observers: int = 0     # of those, how many the final draft no longer asks for


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
    blocked_steps: list[dict] = Field(default_factory=list)
    requested_capabilities: list[CapabilityRequest] = Field(default_factory=list)
    requests_proposed: int = 0
    requests_dropped_by_observers: int = 0
    draft_quality: dict = Field(default_factory=dict)   # D24 checks on the draft (recorded, not enforced)
    unmapped_capabilities: list[str] = Field(default_factory=list)   # D29: names aliases.yaml does not know yet
