"""The envelope: tool allowlists per role and the roster cap. No cost fields in Phase 1 (spec §2 "Cost")."""
from __future__ import annotations

from pydantic import BaseModel, Field

ROLES = ("planner", "observer", "solver", "critic", "worker")


class Envelope(BaseModel):
    allowed_tools: dict[str, list[str]] = Field(default_factory=dict)  # per role
    max_agents: int = 5
    default_model: str = "mock"
    tool_descriptions: dict[str, str] = Field(default_factory=dict)

    @property
    def allowed_tool_names(self) -> list[str]:
        return sorted({t for ts in self.allowed_tools.values() for t in ts})

    def tool_catalog_string(self) -> str:
        """AutoAgents create_roles.py:109 shape: 'tool: NAME, description: TEXT', one entry per tool."""
        names = self.allowed_tool_names
        if not names:
            return "None"
        return "; ".join(f"tool: {n}, description: {self.tool_descriptions.get(n, '')}" for n in names)

    @classmethod
    def from_registry(cls, registry, model: str = "mock", max_agents: int = 5) -> "Envelope":
        return cls(allowed_tools={r: list(registry.names()) for r in ROLES}, max_agents=max_agents,
                   default_model=model, tool_descriptions=registry.descriptions())
