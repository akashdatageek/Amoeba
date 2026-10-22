"""D54 — named model profiles (amoeba/config/models.yaml) and per-role routing.

A profile names an endpoint, a model and how to call it (merge_system, reasoning_effort, max_tokens), and may give
each role group its own model and reply limit. `RoleRouter` holds one client per distinct model; `TracedLLM` asks it
for the client and limit of the call's role group, so every box keeps talking to one LLMClient. The mock client is
not routed: tests and --llm mock never read this file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml

from amoeba.llm.client import ChatResponse, LLMClient, Messages, opts_kw, tools_kw

MODELS = Path(__file__).resolve().parents[1] / "config" / "models.yaml"
ROLE_GROUPS = ("planner", "observers", "workers", "reviewers", "summariser", "pool")   # pool: D56's picker
PROFILE_KEYS = {"base_url", "model", "api_key_env", "merge_system", "reasoning_effort", "max_tokens", "roles",
                "temperature", "provider", "verifier"}
DEFAULT_TEMPERATURE = 0.2
ROLE_KEYS = {"model", "max_tokens"}
BOX2_GROUPS = {"planner": "planner", "agent_observer": "observers", "plan_observer": "observers",
               "interpreter": "planner",   # D77: the task interpretation step
               "architect": "planner",     # D87's Architect (removed by D117); kept so old traces still map
               "fix_proposer": "planner",  # D117 Stage D: the fix proposer uses the planner's model
               "tool_writer": "planner"}   # D125: the tool writer too


@dataclass
class Profile:
    name: str
    base_url: str
    model: str
    api_key_env: str | None = None
    merge_system: bool = False
    reasoning_effort: str | None = None
    max_tokens: int | None = None
    roles: dict[str, dict] = field(default_factory=dict)   # group -> {model?, max_tokens?}
    temperature: float | None = DEFAULT_TEMPERATURE        # None: not sent (`temperature: omit`)
    provider: str | None = None    # D134: `anthropic` → the Messages-API client; else the OpenAI-compatible client
    verifier: str | None = None    # D146: another profile whose model runs the verify steps and the plan observer


def load_profiles(path: str | Path = MODELS) -> tuple[str, dict[str, Profile]]:
    """(default profile name, name -> Profile). An unknown key or role group is an error, not ignored."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    out: dict[str, Profile] = {}
    for name, p in (data.get("profiles") or {}).items():
        bad = set(p) - PROFILE_KEYS
        if bad:
            raise ValueError(f"profile {name}: unknown key(s) {sorted(bad)}; allowed: {sorted(PROFILE_KEYS)}")
        for group, r in (p.get("roles") or {}).items():
            if group not in ROLE_GROUPS:
                raise ValueError(f"profile {name}: unknown role group {group!r}; allowed: {list(ROLE_GROUPS)}")
            if set(r) - ROLE_KEYS:
                raise ValueError(f"profile {name}, role {group}: unknown key(s) {sorted(set(r) - ROLE_KEYS)}")
        out[name] = Profile(name=name, **{**p, "roles": dict(p.get("roles") or {}),
                                          "temperature": temperature_setting(p, f"profile {name}")})
    default = data.get("default")
    if default not in out:
        raise ValueError(f"default profile {default!r} is not defined in {path}")
    return default, out


def temperature_setting(entry: dict, where: str) -> float | None:
    """A profile's or registry entry's `temperature`: absent → 0.2 (the client default, unchanged for every existing
    entry); a number → that number; `omit` → None (the field is not sent)."""
    if "temperature" not in entry:
        return DEFAULT_TEMPERATURE
    t = entry["temperature"]
    if t == "omit":
        return None
    if isinstance(t, bool) or not isinstance(t, (int, float)):
        raise ValueError(f"{where}: temperature must be a number or omit, not {t!r}")
    return float(t)


def get_profile(name: str | None = None, path: str | Path = MODELS) -> Profile:
    default, profiles = load_profiles(path)
    name = name or default
    if name not in profiles:
        raise ValueError(f"unknown profile {name!r}; defined in {path}: {', '.join(profiles)}")
    return profiles[name]


def role_group(agent_name: str | None = None, *, is_summariser: bool = False, role: str | None = None,
               reviewing: bool = False) -> str:
    """Which role group a call belongs to: the Box 2 caller's name, else the Box 3 helper's part in the run."""
    if agent_name in BOX2_GROUPS:
        return BOX2_GROUPS[agent_name]
    if reviewing or role == "critic":
        return "reviewers"
    return "summariser" if is_summariser else "workers"


# box: client
class RoleRouter(LLMClient):
    """The profile's clients: `route(group)` gives the client and reply limit (None = the call's own) of a role
    group. Called directly, it is the profile's default client."""

    def __init__(self, profile: str, default: LLMClient, by_group: dict[str, LLMClient] | None = None,
                 max_tokens: dict[str, int] | None = None):
        self.profile, self.default = profile, default
        self.model = default.model
        self.by_group, self.max_tokens = by_group or {}, max_tokens or {}
        self.by_agent: dict[str, LLMClient] = {}     # D146: a caller by name (the plan observer → the verifier)
        self.verifier: str | None = None

    def route(self, group: str | None, agent: str | None = None) -> tuple[LLMClient, int | None]:
        if agent in self.by_agent:
            return self.by_agent[agent], self.max_tokens.get(group)
        return self.by_group.get(group, self.default), self.max_tokens.get(group)

    def chat_messages(self, messages: Messages, seed: int = 0, max_tokens: int | None = None,
                      tools: list | None = None, **opts) -> ChatResponse:
        return self.default.chat_messages(messages, seed, max_tokens=max_tokens, **tools_kw(tools), **opts_kw(opts))

    @property
    def models(self) -> dict[str, str]:
        """The model of every role group (for result.json)."""
        out = {g: self.route(g)[0].model for g in ROLE_GROUPS}
        out.update({f"agent:{a}": c.model for a, c in self.by_agent.items()})       # D146
        return out


# box: client
def attach_verifier(router: RoleRouter, profile: Profile, make_for: Callable[[Profile], LLMClient | None]) -> str:
    """D146: when the profile names a `verifier` profile, its model runs the verify steps (the reviewers group) and
    the plan observer. make_for(verifier profile) builds its client, or returns None when its key is not set (the
    run then keeps one model and says so). Returns what happened, for the trace."""
    if not profile.verifier:
        return "none"
    vp = get_profile(profile.verifier)
    client = make_for(vp)
    if client is None:
        return f"{vp.name}: key {vp.api_key_env} not set; verify steps use {router.model}"
    router.by_group["reviewers"] = client
    router.by_agent["plan_observer"] = client
    router.verifier = vp.name
    return f"{vp.name}: verify steps and the plan observer use {vp.model}"


# box: client
def build_router(profile: Profile, make: Callable[[str], LLMClient], model: str | None = None,
                 keep_max_tokens: set[str] | None = None) -> RoleRouter:
    """make(model) builds one client (with the profile's endpoint and options); one client per distinct model.
    model: an override of the profile's default model (--model / AMOEBA_MODEL). keep_max_tokens: the role groups
    whose profile max_tokens stays (a group set on the command line is left out)."""
    clients: dict[str, LLMClient] = {}

    def client(m: str) -> LLMClient:
        if m not in clients:
            clients[m] = make(m)
        return clients[m]

    default = client(model or profile.model)
    by_group = {g: client(r["model"]) for g, r in profile.roles.items() if r.get("model")}
    if "pool" not in by_group and "workers" in by_group:   # D56: the pool picker defaults to the helpers' model
        by_group["pool"] = by_group["workers"]
    caps = {g: int(r["max_tokens"]) for g, r in profile.roles.items() if r.get("max_tokens")
            and (keep_max_tokens is None or g in keep_max_tokens)}
    return RoleRouter(profile.name, default, by_group, caps)
