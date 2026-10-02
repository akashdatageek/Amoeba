"""D81 — the team recipe, the edit menu and validation (Phase 2 spec §3).

A recipe is data, one per task family. Code applies it at three fixed points that already exist in Phase 1 (D82):
the planner rules go into the Box 2 prompts ("Lessons for this kind of task"), the transforms are applied by code to
the final Draft before Box 3 builds the team, and the run options overlay the plan runner's settings. The seed recipe
of every family is empty, and an empty recipe changes nothing (a Draft comes back byte-identical).

One edit per hypothesis; each is a pure function Recipe -> Recipe (a new version whose parent is the old one).
`validate_recipe` (V1–V5) is plain code; nothing here calls a model.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from amoeba.task.models import Draft, DraftedRole, DraftPlanStep

CONFIG = Path(__file__).resolve().parents[1] / "config" / "adapt.yaml"
TRANSFORM_OPS = ("add_verify_step", "tighten_done_when", "grant_tool", "revoke_tool", "add_role_rule")
EDIT_OPS = ("add_planner_rule", "remove_planner_rule", *TRANSFORM_OPS, "set_run_option")


# box: recipe
@lru_cache(maxsize=1)
def adapt_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


# box: recipe
class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str                                # "L1", "L2", ...
    text: str                              # ≤ 300 characters, task-neutral (V3; the Gate's leakage screen)


# box: recipe
class Selector(BaseModel):
    """Which steps or roles a transform acts on — matched by code against DraftPlanStep / DraftedRole fields only.
    Steps: kind (an unset kind counts as work; the answer step is never selected), last_work_step, roles_with_tool
    (steps whose roles hold the tool). Roles: all_roles (every role but the summariser), roles_with_tool, or the
    roles of the selected steps."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["work", "verify", "any"] = "any"
    roles_with_tool: str | None = None
    last_work_step: bool = False
    all_roles: bool = False


# box: recipe
class Transform(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str                                # "T1", ...
    op: Literal["add_verify_step", "tighten_done_when", "grant_tool", "revoke_tool", "add_role_rule"]
    select: Selector = Field(default_factory=Selector)
    params: dict = Field(default_factory=dict)     # op-specific: clause | tool | text


# box: recipe
class Recipe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family: str
    version: int = 1
    parent_version: int | None = None
    planner_rules: list[Rule] = Field(default_factory=list)
    transforms: list[Transform] = Field(default_factory=list)
    run_options: dict[str, Any] = Field(default_factory=dict)
    created_by: Literal["seed", "human", "architect"] = "seed"
    hypothesis_id: str | None = None

    def is_empty(self) -> bool:
        return not (self.planner_rules or self.transforms or self.run_options)

    def content(self) -> dict:
        """What the recipe does (not its version or history): the key of the arm-A cache (D83)."""
        return {"rules": [r.text for r in self.planner_rules],
                "transforms": [t.model_dump(exclude={"id"}) for t in self.transforms],
                "run_options": dict(sorted(self.run_options.items()))}

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.content(), sort_keys=True).encode()).hexdigest()[:12]


# box: recipe
def seed_recipe(family: str) -> Recipe:
    return Recipe(family=family)


# ---- the edit menu (§3.2) ------------------------------------------------------------------------------------------
class _P(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AddRule(_P):
    text: str


class RemoveRule(_P):
    id: str


class SelectOnly(_P):
    select: Selector = Field(default_factory=Selector)


class Tighten(_P):
    select: Selector = Field(default_factory=Selector)
    clause: str


class ToolEdit(_P):
    select: Selector = Field(default_factory=Selector)
    tool: str


class RoleRule(_P):
    select: Selector = Field(default_factory=Selector)
    text: str


class SetOption(_P):
    name: str
    value: Any


PARAMS: dict[str, type[_P]] = {"add_planner_rule": AddRule, "remove_planner_rule": RemoveRule,
                               "add_verify_step": SelectOnly, "tighten_done_when": Tighten, "grant_tool": ToolEdit,
                               "revoke_tool": ToolEdit, "add_role_rule": RoleRule, "set_run_option": SetOption}


# box: recipe
class Edit(BaseModel):
    """One typed edit (§3.2) with its parameters, validated per op (unknown keys are refused)."""

    model_config = ConfigDict(extra="forbid")
    op: Literal["add_planner_rule", "remove_planner_rule", "add_verify_step", "tighten_done_when", "grant_tool",
                "revoke_tool", "add_role_rule", "set_run_option"]
    params: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _params(self):
        self.params = PARAMS[self.op].model_validate(self.params).model_dump(exclude_defaults=False)
        return self

    def key(self) -> str:
        """The op and its normalised parameters, hashed: the same edit proposed twice has the same key (D87)."""
        norm = json.loads(json.dumps(self.params, sort_keys=True))
        for k in ("text", "clause"):
            if isinstance(norm.get(k), str):
                norm[k] = " ".join(norm[k].lower().split())
        return hashlib.sha256(json.dumps({"op": self.op, "params": norm}, sort_keys=True).encode()).hexdigest()[:16]

    def texts(self) -> list[str]:
        return [str(self.params[k]) for k in ("text", "clause") if self.params.get(k)]


def _next_id(prefix: str, ids: list[str]) -> str:
    nums = [int(i[len(prefix):]) for i in ids if i.startswith(prefix) and i[len(prefix):].isdigit()]
    return f"{prefix}{max(nums, default=0) + 1}"


# box: recipe
def apply_edit(recipe: Recipe, edit: Edit, created_by: str = "architect", hypothesis_id: str | None = None) -> Recipe:
    """Pure: a new recipe (version + 1, parent = this version) with the edit applied. The input is not changed."""
    r = recipe.model_copy(deep=True)
    p = edit.params
    if edit.op == "add_planner_rule":
        r.planner_rules.append(Rule(id=_next_id("L", [x.id for x in r.planner_rules]), text=p["text"]))
    elif edit.op == "remove_planner_rule":
        if p["id"] not in [x.id for x in r.planner_rules]:
            raise ValueError(f"no planner rule {p['id']} in {recipe.family} v{recipe.version}")
        r.planner_rules = [x for x in r.planner_rules if x.id != p["id"]]
    elif edit.op == "set_run_option":
        r.run_options[p["name"]] = p["value"]
    else:
        extra = {k: v for k, v in p.items() if k != "select"}
        r.transforms.append(Transform(id=_next_id("T", [x.id for x in r.transforms]), op=edit.op,
                                      select=Selector.model_validate(p["select"]), params=extra))
    return r.model_copy(update={"version": recipe.version + 1, "parent_version": recipe.version,
                                "created_by": created_by, "hypothesis_id": hypothesis_id})


# ---- transforms on a Draft (used by D82 between Box 2 and Box 3, and by V5) ---------------------------------------
def _summariser(d: Draft) -> str | None:
    return next((r.name for r in d.created_roles if r.is_summariser), None)


def _answer_steps(d: Draft) -> set[int]:
    """Step numbers (1-based) of the answer step(s): the summariser's steps, else the last step."""
    s = _summariser(d)
    owned = {x.index + 1 for x in d.plan if s and s in x.agent_names}
    return owned or ({d.plan[-1].index + 1} if d.plan else set())


def _tools_of(d: Draft) -> dict[str, list[str]]:
    return {r.name: list(r.tools) for r in d.created_roles}


def select_steps(d: Draft, sel: Selector) -> list[int]:
    """Step numbers (1-based) the selector matches; the answer step is never selected."""
    answer = _answer_steps(d)
    tools = _tools_of(d)
    out = []
    for s in d.plan:
        n = s.index + 1
        if n in answer:
            continue
        kind = s.kind or "work"
        if sel.kind != "any" and kind != sel.kind:
            continue
        if sel.roles_with_tool and not any(sel.roles_with_tool in tools.get(a, []) for a in s.agent_names):
            continue
        out.append(n)
    if sel.last_work_step:
        work = [n for n in out if (d.plan[n - 1].kind or "work") == "work"]
        out = work[-1:]
    return out


def select_roles(d: Draft, sel: Selector) -> list[str]:
    """Role names the selector matches; the summariser (who writes the answer and holds no tools) never is."""
    summ = _summariser(d)
    names = [r.name for r in d.created_roles if r.name != summ]
    if sel.all_roles:
        return names
    if sel.roles_with_tool and sel.kind == "any" and not sel.last_work_step:
        return [r.name for r in d.created_roles if r.name != summ and sel.roles_with_tool in r.tools]
    steps = select_steps(d, sel)
    picked = {a for n in steps for a in d.plan[n - 1].agent_names}
    return [n for n in names if n in picked]


def _renumber(plan: list[DraftPlanStep], at: int) -> list[DraftPlanStep]:
    """Make room for a new step number `at` (1-based): later steps move up one, and so do references to them."""
    out = []
    for s in plan:
        deps = [d + 1 if d >= at else d for d in s.depends_on]
        out.append(s.model_copy(update={"index": s.index + 1 if s.index + 1 >= at else s.index, "depends_on": deps}))
    return out


def _checker(d: Draft, avoid: list[str]) -> tuple[Draft, str]:
    """The team's checker role: one that already owns a verify step, else one whose name says it checks; else a
    new one (adapt.yaml checker_role), unless the team is full, then a role not in the step it checks."""
    summ = _summariser(d)
    owners = [a for s in d.plan if (s.kind or "") == "verify" for a in s.agent_names if a != summ]
    if owners:
        return d, owners[0]
    named = [r.name for r in d.created_roles if r.name != summ and
             any(w in (r.name + " " + r.description).lower() for w in ("check", "verif", "review", "qa", "audit"))]
    if named:
        return d, named[0]
    cfg = adapt_config()["recipe"]["checker_role"]
    name = cfg["name"]
    if len(d.created_roles) < 5 and name not in [r.name for r in d.created_roles]:
        role = DraftedRole(
            name=name, description="Re-checks the figures and claims of the step it follows.", tools=list(cfg["tools"]),
            goal="Confirm or correct every figure and claim of the step it checks, with the check shown.",
            skills=["re-computing figures", "checking claims against their sources"],
            outputs=[{"artifact": "check report", "format": "PASS or FAIL per claim, with the re-check shown"}],
            success_criteria=["every figure re-computed or traced to its source"],
            prompt="You re-check another helper's step: re-compute every figure with calc and confirm every claim; "
                   "report PASS or FAIL per item with what you did.")
        return d.model_copy(update={"created_roles": [*d.created_roles, role]}), name
    others = [r.name for r in d.created_roles if r.name != summ and r.name not in avoid]
    return d, (others or [r.name for r in d.created_roles if r.name != summ])[0]


def _t_add_verify_step(d: Draft, t: Transform) -> tuple[Draft, dict]:
    targets = select_steps(d, t.select)
    added, roles_before = [], {r.name for r in d.created_roles}
    for orig in sorted(targets, reverse=True):          # from the end, so earlier numbers stay put
        n = orig
        producer = d.plan[n - 1]
        d, checker = _checker(d, producer.agent_names)
        at = n + 1
        plan = _renumber(d.plan, at)
        new = DraftPlanStep(
            index=at - 1, agent_names=[checker], kind="verify", covers=list(producer.covers), depends_on=[n],
            title=f"Check step {n}", text=f"[{checker}]: Check the output of step {n}",
            do=f"Re-check every figure and claim in step {n}'s output: re-compute the figures, confirm each claim "
               f"against its source, and correct what is wrong.",
            output=f"PASS or FAIL for each figure and claim of step {n}, with the re-check shown and any correction.",
            done_when=f"Every figure and claim of step {n} is marked PASS or FAIL with the check that was done.")
        plan.insert(at - 1, new)
        for s in plan:                                   # the answer step reads the check too
            if s.index + 1 in _answer_steps(d.model_copy(update={"plan": plan})) and at not in s.depends_on:
                s.depends_on.append(at)
        d = d.model_copy(update={"plan": plan})
        added.append(at)
    return d, {"steps": sorted(added), "roles": sorted({r.name for r in d.created_roles} - roles_before),
               "after_steps": sorted(targets)}


def _t_tighten(d: Draft, t: Transform) -> tuple[Draft, dict]:
    steps = select_steps(d, t.select)
    clause = t.params["clause"].strip()
    plan = [s.model_copy(update={"done_when": (s.done_when.rstrip(" .") + ". " if s.done_when.strip() else "") + clause})
            if s.index + 1 in steps else s for s in d.plan]
    return d.model_copy(update={"plan": plan}), {"steps": steps}


def _t_tools(d: Draft, t: Transform) -> tuple[Draft, dict]:
    roles, tool = select_roles(d, t.select), t.params["tool"]
    changed, out = [], []
    for r in d.created_roles:
        if r.name in roles:
            if t.op == "grant_tool" and tool not in r.tools:
                r = r.model_copy(update={"tools": [*r.tools, tool]})
                changed.append(r.name)
            elif t.op == "revoke_tool" and tool in r.tools:
                r = r.model_copy(update={"tools": [x for x in r.tools if x != tool]})
                changed.append(r.name)
        out.append(r)
    return d.model_copy(update={"created_roles": out}), {"roles": changed}


def _t_role_rule(d: Draft, t: Transform) -> tuple[Draft, dict]:
    roles, text = select_roles(d, t.select), t.params["text"].strip()
    out = [r.model_copy(update={"constraints": [*r.constraints, text]}) if r.name in roles else r
           for r in d.created_roles]
    return d.model_copy(update={"created_roles": out}), {"roles": roles}


OPS = {"add_verify_step": _t_add_verify_step, "tighten_done_when": _t_tighten, "grant_tool": _t_tools,
       "revoke_tool": _t_tools, "add_role_rule": _t_role_rule}


# box: recipe
def apply_transforms(draft: Draft, recipe: Recipe | None) -> tuple[Draft, list[dict]]:
    """The recipe's transforms, in order, on a copy of the final Draft; returns it and what each one changed
    ({id, op, steps?, roles?}). With no transforms the Draft itself comes back unchanged (byte-identical)."""
    if recipe is None or not recipe.transforms:
        return draft, []
    d, log = draft.model_copy(deep=True), []
    for t in recipe.transforms:
        d, changed = OPS[t.op](d, t)
        log.append({"id": t.id, "op": t.op, **changed})
    return d, log


# ---- validation (§3.3) ---------------------------------------------------------------------------------------------
# box: recipe
class Violation(BaseModel):
    rule: Literal["V1", "V2", "V3", "V4", "V5"]
    detail: str


def _texts(recipe: Recipe) -> list[tuple[str, str]]:
    out = [(f"rule {r.id}", r.text) for r in recipe.planner_rules]
    out += [(f"transform {t.id}", str(t.params[k])) for t in recipe.transforms for k in ("clause", "text")
            if k in t.params]
    return out


def plan_problems(d: Draft) -> list[str]:
    """The Phase 1 plan checks V5 re-runs after the transforms: depends_on names existing steps, no cycle, every
    role a step names exists, step numbers are 1..n in order."""
    out = []
    numbers = [s.index + 1 for s in d.plan]
    if numbers != list(range(1, len(d.plan) + 1)):
        out.append(f"step numbers are not 1..{len(d.plan)}: {numbers}")
    known, roles = set(numbers), {r.name for r in d.created_roles}
    deps = {s.index + 1: list(s.depends_on) for s in d.plan}
    for n, ds in deps.items():
        bad = [x for x in ds if x not in known]
        if bad:
            out.append(f"step {n} depends on unknown step(s) {bad}")
    done: set[int] = set()
    while len(done) < len(deps):
        ready = [n for n in deps if n not in done and all(x in done or x not in known for x in deps[n])]
        if not ready:
            out.append(f"cycle among steps {sorted(set(deps) - done)}")
            break
        done.update(ready)
    for s in d.plan:
        missing = [a for a in s.agent_names if a not in roles]
        if missing:
            out.append(f"step {s.index + 1} names unknown role(s) {missing}")
    return out


# box: recipe
def validate_recipe(recipe: Recipe, envelope=None, sample_draft: Draft | None = None) -> list[Violation]:
    """V1–V5, plain code. envelope: the Phase 1 Envelope (its allowlist is the registry's tools); sample_draft: a
    draft to apply the transforms to for V5 (skipped without one)."""
    from amoeba.pool.stock import side_effect
    cfg = adapt_config()["recipe"]
    out: list[Violation] = []
    # V1: tools
    allowed = set(getattr(envelope, "allowed_tool_names", None) or []) | set(cfg["grantable_extra"])
    for t in recipe.transforms:
        if t.op in ("grant_tool", "revoke_tool") or t.select.roles_with_tool:
            for tool in filter(None, [t.params.get("tool"), t.select.roles_with_tool]):
                if envelope is not None and tool not in allowed:
                    out.append(Violation(rule="V1", detail=f"{t.id}: tool {tool!r} is not in the registry or allowlist"))
                desc = (getattr(envelope, "tool_descriptions", {}) or {}).get(tool, "")
                hit = side_effect(tool, desc) if t.op == "grant_tool" else None
                if hit:
                    out.append(Violation(rule="V1", detail=f"{t.id}: tool {tool!r} acts outside ({hit!r})"))
                if t.op == "grant_tool" and ("x402" in tool.lower() or "paid" in tool.lower()):
                    out.append(Violation(rule="V1", detail=f"{t.id}: tool {tool!r} is a paid endpoint"))
    # V2: run options
    for name, value in recipe.run_options.items():
        spec = cfg["run_options"].get(name)
        if spec is None:
            out.append(Violation(rule="V2", detail=f"run option {name!r} is not whitelisted"))
        elif "values" in spec and value not in spec["values"]:
            out.append(Violation(rule="V2", detail=f"run option {name}={value!r} not in {spec['values']}"))
        elif "min" in spec and not (isinstance(value, int) and not isinstance(value, bool)
                                    and spec["min"] <= value <= spec["max"]):
            out.append(Violation(rule="V2", detail=f"run option {name}={value!r} not in {spec['min']}–{spec['max']}"))
    # V3: sizes
    if len(recipe.planner_rules) > cfg["max_rules"]:
        out.append(Violation(rule="V3", detail=f"{len(recipe.planner_rules)} rules > {cfg['max_rules']}"))
    if len(recipe.transforms) > cfg["max_transforms"]:
        out.append(Violation(rule="V3", detail=f"{len(recipe.transforms)} transforms > {cfg['max_transforms']}"))
    for where, text in _texts(recipe):
        if len(text) > cfg["max_text_chars"]:
            out.append(Violation(rule="V3", detail=f"{where}: {len(text)} characters > {cfg['max_text_chars']}"))
        if not text.strip():
            out.append(Violation(rule="V3", detail=f"{where}: empty text"))
    # V4: no telling the team to skip checks, citations, the sandbox or the contract
    for where, text in _texts(recipe):
        low = text.lower()
        hits = [w for w in cfg["denylist"] if w in low]
        if hits:
            out.append(Violation(rule="V4", detail=f"{where}: denied wording {hits} (review by hand)"))
    # V5: the step graph still passes the plan checks after the transforms
    if sample_draft is not None and recipe.transforms:
        try:
            d, _ = apply_transforms(sample_draft, recipe)
            out += [Violation(rule="V5", detail=p) for p in plan_problems(d)]
            if len(d.created_roles) > getattr(envelope, "max_agents", 5):
                out.append(Violation(rule="V5", detail=f"{len(d.created_roles)} roles > {envelope.max_agents}"))
        except (ValidationError, ValueError, KeyError, IndexError) as e:
            out.append(Violation(rule="V5", detail=f"the transforms fail on the sample draft: {e}"[:300]))
    return out


# ---- the hook in Boxes 2 and 3 (D82) -------------------------------------------------------------------------------
LESSONS_HEAD = "\n\n# Lessons for this kind of task (from earlier tasks of the same kind)\n"
LESSONS_TAIL = {"planner": "Follow each lesson in the plan, or say in Risks and Decisions why it does not apply.",
                "agent_observer": "Check that the roles let the team follow each lesson.",
                "plan_observer": "Check item: every lesson is followed by the plan, or the plan says why not; report "
                                 "each lesson that is neither as a problem."}


# box: recipe
def lessons_text(recipe: Recipe | None) -> dict[str, str]:
    """The d24 prompts' {lessons} slot for the Planner and both Observers; empty strings (prompts unchanged) when
    the recipe has no planner rules."""
    if recipe is None or not recipe.planner_rules:
        return {}
    body = "\n".join(f"- {r.id}: {r.text}" for r in recipe.planner_rules)
    return {who: f"{LESSONS_HEAD}{body}\n{tail}" for who, tail in LESSONS_TAIL.items()}


# box: recipe
def load_recipe(store: str | Path, family: str) -> Recipe | None:
    """The current recipe of a family from a recipe store (§10: <store>/index.json {family: {"current": N}} and
    <store>/<family>/v<N>.yaml); None when the store has none for the family (the run is then a Phase 1 run)."""
    root = Path(store)
    index = root / "index.json"
    if not index.exists():
        return None
    cur = (json.loads(index.read_text(encoding="utf-8")).get(family) or {}).get("current")
    if cur is None:
        return None
    return Recipe.model_validate(yaml.safe_load((root / family / f"v{cur}.yaml").read_text(encoding="utf-8")))


# box: recipe
def write_store(store: str | Path, recipes: list[Recipe]) -> Path:
    """A minimal store holding these recipes, each its family's current version (the Experimenter's per-arm stores;
    the Gate's committed store with history is D88)."""
    root = Path(store)
    index = json.loads((root / "index.json").read_text(encoding="utf-8")) if (root / "index.json").exists() else {}
    for r in recipes:
        (root / r.family).mkdir(parents=True, exist_ok=True)
        (root / r.family / f"v{r.version}.yaml").write_text(
            yaml.safe_dump(r.model_dump(mode="json"), sort_keys=False, allow_unicode=True), encoding="utf-8")
        entry = index.setdefault(r.family, {"current": r.version, "history": []})
        entry["current"] = r.version
        if r.version not in [h["version"] for h in entry["history"]]:
            entry["history"].append({"version": r.version, "parent": r.parent_version,
                                     "hypothesis_id": r.hypothesis_id})
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return root


PLAN_OPTION_NAMES = {"replan": "--replan", "self_refine": "--self-refine", "collab": "--collab",
                     "check_retry_turns": "--check-retry-turns"}
LIMIT_OPTION_NAMES = {"max_turns": "--max-turns"}


# box: recipe
def overlay_run_options(plan_options, recipe: Recipe | None, explicit: set[str] | frozenset = frozenset()):
    """Box 3: the recipe's run options over the CLI's PlanOptions and Limits values. A CLI flag wins only when it
    was set explicitly (ablations). Returns (plan_options, max_turns or None, applied, overridden_by_cli)."""
    from dataclasses import replace
    if recipe is None or not recipe.run_options:
        return plan_options, None, {}, []
    applied, overridden, changes, max_turns = {}, [], {}, None
    for name, value in recipe.run_options.items():
        flag = PLAN_OPTION_NAMES.get(name) or LIMIT_OPTION_NAMES.get(name)
        if flag in explicit:
            overridden.append(name)
            continue
        if name in PLAN_OPTION_NAMES:
            changes[name] = value
        elif name in LIMIT_OPTION_NAMES:
            max_turns = int(value)
        applied[name] = value
    if changes and plan_options is not None:
        plan_options = replace(plan_options, **changes)
    return plan_options, max_turns, applied, overridden
