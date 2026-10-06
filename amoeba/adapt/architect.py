"""The single-edit proposal format and its checks (kept from D87 by D117).

D117 removed the offline learning loop and the Architect that served it. What is kept is the contract every proposed
change has to meet: the reply is ONE strict JSON object with one typed edit, a short rationale and a signed predicted
change; plain code parses it strictly, checks that the edit is allowed for the cause, that the edited recipe passes
V1-V6 (amoeba/adapt/recipe.py validate_recipe), and that it does not repeat an edit already tried. D117's in-task fix
proposer (Stage D) reuses this format and these checks.
"""
from __future__ import annotations

import json
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

from amoeba.adapt.recipe import Edit, Recipe, apply_edit, validate_recipe

SHAPES = {"add_planner_rule": '{"text": "<lesson, at most 300 characters>"}',
          "remove_planner_rule": '{"id": "L<n>"}',
          "add_verify_step": '{"select": SELECTOR}',
          "tighten_done_when": '{"select": SELECTOR, "clause": "<one sentence>"}',
          "grant_tool": '{"select": SELECTOR, "tool": "<tool name>"}',
          "revoke_tool": '{"select": SELECTOR, "tool": "<tool name>"}',
          "add_role_rule": '{"select": SELECTOR, "text": "<one rule for the role card>"}',
          "set_run_option": '{"name": "<option>", "value": <value>}',
          "prefer_model": '{"role": "<interpreter|planner|worker|verifier|summariser|...>", "model": "<registry name>"}'}
SELECTOR = ('SELECTOR = {"kind": "work"|"verify"|"any", "roles_with_tool": "<tool>"|null, "last_work_step": true|false, '
            '"all_roles": true|false} (fields you leave out take their defaults: any, null, false, false)')


# box: arch_check
class ArchitectReply(BaseModel):
    """The reply, parsed strictly: exactly these keys."""

    model_config = ConfigDict(extra="forbid")
    edit: Edit
    rationale: str = Field(max_length=400)
    predicted_delta: float
    metric: str = "score"
    hypothesis_id: str | None = None          # ignored: code names the hypothesis
    family: str | None = None
    diagnosis_ref: str | None = None

    @field_validator("predicted_delta")
    @classmethod
    def _range(cls, v):
        if not -1 <= v <= 1:
            raise ValueError("predicted_delta must be between -1 and 1")
        return v


# box: arch_check
def _allowed_ok(edit: Edit, allowed: list[str]) -> bool:
    """An allowed entry is an op, or "set_run_option:<name>" for one run option only."""
    if edit.op in allowed:
        return True
    return edit.op == "set_run_option" and f"set_run_option:{edit.params.get('name')}" in allowed


# box: arch_check
def allowed_text(allowed: list[str]) -> str:
    lines = []
    for a in allowed:
        op, _, only = a.partition(":")
        shape = SHAPES[op] if not only else f'{{"name": "{only}", "value": <value>}}'
        lines.append(f"- {op}: params {shape}")
    if any(SHAPES[a.partition(':')[0]].count("SELECTOR") for a in allowed):
        lines.append(SELECTOR)
    return "\n".join(lines)


# box: arch_check
def failed_text(failed: list[dict]) -> str:
    if not failed:
        return "None yet."
    return "\n".join(f"- {json.dumps(r['edit'], ensure_ascii=False)}: observed {r.get('observed_delta')}, "
                     f"reasons {r.get('reasons')}" for r in failed)


# box: arch_check
def parse_reply(text: str) -> ArchitectReply:
    """The first JSON object in the reply (a <thought> block or a code fence around it is allowed)."""
    t = re.sub(r"<thought>.*?</thought>", "", text or "", flags=re.S)
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        raise ValueError("no JSON object in the reply")
    return ArchitectReply.model_validate(json.loads(m.group(0)))


# box: arch_check, ov_adapt
def check(reply: ArchitectReply, allowed: list[str], recipe: Recipe, failed: list[dict], envelope=None,
          sample_draft=None) -> list[str]:
    """Plain code's checks of one proposal; empty when it may be applied. `allowed`: the edits the cause allows
    (amoeba/config/adapt.yaml diagnoser.allowed_edits); `failed`: the edits already tried, as {"edit": {...}}."""
    problems = []
    e = reply.edit
    if not _allowed_ok(e, allowed):
        problems.append(f"edit {e.op!r} is not allowed here; allowed: {allowed}")
    try:
        new = apply_edit(recipe, e)
        problems += [f"{v.rule}: {v.detail}" for v in validate_recipe(new, envelope, sample_draft)]
    except ValueError as x:
        problems.append(str(x))
    keys = {Edit.model_validate(r["edit"]).key() for r in failed if r.get("edit")}
    if e.key() in keys:
        problems.append("this edit was already tried")
    return problems
