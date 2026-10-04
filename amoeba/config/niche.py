"""D102 — niche profiles: one file per environment, `profiles/<niche>.yaml`, chosen with --niche (default `general`).

A profile says, for one environment: which tools are allowed and the local-tool sandbox limits (D96), which models
are allowed and the verifier-independence setting (feeding the D97 router), the domain's rules and vocabulary, what
"done" means (default done_when clauses on the answer step), which domain checks run after each step
(amoeba/checks/<name>.py), and safety limits (USD, tokens and calls per run; outside actions).

Prompts stay generic: the profile only fills one "Environment" section of Box 1's interpretation prompt and Box 2's
Planner and Observer prompts. Enforcement is code: Box 3 refuses a tool outside the profile even if a plan or a
replan asks for it (and logs the refusal), and the router refuses a model outside it. `general` is today's behaviour
exactly: every tool, every model, no Environment section, no domain check, no extra limit.
"""
from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

PROFILES = Path(__file__).resolve().parents[2] / "profiles"
DEFAULT = "general"
ENV_HEAD = ("\n\n# Environment ({name})\nAssess this environment first: which tools you have, what is limited, what "
            "counts as done; plan only with what is allowed.\n")


# box: niche
class Safety(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_usd_per_run: float | None = None
    max_tokens_per_run: int | None = None
    max_calls_per_run: int | None = None
    outside_actions: bool | None = None          # False: a tool with an outside-action word is refused


# box: niche
class NicheProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str = ""
    tools: dict = Field(default_factory=dict)    # {allowed: [names or patterns] | "all", sandbox: {timeout_s, cpu, ...}}
    models: dict = Field(default_factory=dict)   # {allowed: [registry names] | "all", verifier_independence: ...}
    domain: dict = Field(default_factory=dict)   # {rules: [...], vocabulary: {term: meaning}}
    done_when: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    safety: Safety = Field(default_factory=Safety)

    @property
    def allowed_tools(self) -> list[str] | None:
        a = self.tools.get("allowed", "all")
        return None if a in (None, "all") else list(a)

    @property
    def allowed_models(self) -> list[str] | None:
        a = self.models.get("allowed", "all")
        return None if a in (None, "all") else list(a)

    @property
    def sandbox(self) -> dict:
        return dict(self.tools.get("sandbox") or {})

    def is_neutral(self) -> bool:
        """Nothing to say and nothing to enforce (the `general` profile): the run is exactly today's."""
        return (self.allowed_tools is None and self.allowed_models is None and not self.sandbox
                and not self.models.get("verifier_independence") and not self.domain.get("rules")
                and not self.domain.get("vocabulary") and not self.done_when and not self.checks
                and self.safety == Safety())


# box: niche
def load_profile(name: str | None = None, root: str | Path = PROFILES) -> NicheProfile:
    name = name or DEFAULT
    path = Path(root) / f"{name}.yaml"
    if not path.exists():
        known = sorted(p.stem for p in Path(root).glob("*.yaml"))
        raise ValueError(f"no niche profile {name!r} (profiles/: {', '.join(known)})")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    prof = NicheProfile.model_validate({"name": name, **data})
    from amoeba.checks import CHECKS
    unknown = [c for c in prof.checks if c not in CHECKS]
    if unknown:
        raise ValueError(f"profiles/{name}.yaml names unknown domain checks {unknown} (amoeba/checks/: {sorted(CHECKS)})")
    return prof


# box: niche
def tool_allowed(name: str, prof: NicheProfile, description: str = "") -> tuple[bool, str]:
    """Plain code: may Box 3 run this tool in this environment? (allowed, reason when not)."""
    allowed = prof.allowed_tools
    if allowed is not None and not any(fnmatch(name, pat) for pat in allowed):
        return False, f"not in the {prof.name} profile's tools"
    if prof.safety.outside_actions is False:
        from amoeba.pool.stock import side_effect
        hit = side_effect(name, description)
        if hit:
            return False, f"outside action ({hit!r}) and the {prof.name} profile allows none"
    return True, ""


# box: niche
def environment_text(prof: NicheProfile, tools: list[str] | None = None) -> str:
    """The one Environment section for Box 1 and Box 2 ("" for a neutral profile: prompts unchanged)."""
    if prof.is_neutral():
        return ""
    lines = []
    shown = [t for t in (tools or []) if tool_allowed(t, prof)[0]] if tools is not None else prof.allowed_tools
    if shown is not None:
        lines.append("- Tools you may use: " + (", ".join(sorted(shown)) or "none"))
    lim = []
    sb = prof.sandbox
    if sb.get("timeout_s"):
        lim.append(f"a local command stops after {sb['timeout_s']} s")
    if sb.get("cpu") or sb.get("memory"):
        lim.append(f"the local sandbox has {sb.get('cpu', '1')} CPU and {sb.get('memory', '1Gi')} memory")
    s = prof.safety
    if s.max_usd_per_run is not None:
        lim.append(f"at most ${s.max_usd_per_run:g} of model use per run")
    if s.max_calls_per_run is not None:
        lim.append(f"at most {s.max_calls_per_run} model calls per run")
    if s.outside_actions is False:
        lim.append("no outside actions (nothing is sent, bought, booked or changed outside this run)")
    if lim:
        lines.append("- Limits: " + "; ".join(lim))
    if prof.done_when:
        lines.append("- Done means: " + " ".join(prof.done_when))
    for r in prof.domain.get("rules") or []:
        lines.append(f"- Rule: {r}")
    for term, meaning in (prof.domain.get("vocabulary") or {}).items():
        lines.append(f"- Term: {term} = {meaning}")
    return ENV_HEAD.format(name=prof.name) + "\n".join(lines) + "\n"


# box: niche
def add_done_clauses(draft, prof: NicheProfile):
    """The profile's default done_when clauses, added by code to the answer step(s) of the final draft."""
    if not prof.done_when:
        return draft, []
    from amoeba.adapt.recipe import _answer_steps
    steps = _answer_steps(draft)
    plan = []
    for s in draft.plan:
        if s.index + 1 in steps:
            extra = " ".join(c for c in prof.done_when if c not in s.done_when)
            s = s.model_copy(update={"done_when": f"{s.done_when} {extra}".strip()})
        plan.append(s)
    return draft.model_copy(update={"plan": plan}), sorted(steps)
