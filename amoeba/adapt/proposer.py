"""D117 Stage D — the fix proposer's reply format and the checks plain code makes on it.

The fix proposer is a small agent called only when the code fixes for a stuck step are used up or not allowed
(amoeba/adapt/fixes.py). It returns exactly one JSON edit with a short reason:

  add_role_rule     {"role", "text"}: one rule on the card of a role of the stuck step
  add_helper_role   {"role": <role card, the Box 2 Planner's schema>, "lead": bool}: a new helper joins the stuck step
  grant_tool        {"role", "tool"}: a tool available in this run, to a role of the stuck step
  split_step        {"steps": [2-3 sub-steps {"roles", "text", "do", "output", "done_when"}]}: the stuck step becomes
                    a chain of sub-steps; the steps that waited for it wait for the last one
  replan_remaining  {"plan": "<steps in the Planner's Execution Plan format>"}: replacement steps for the part not
                    done yet (the stuck step and the steps not run)
  work_around       {"capability", "method", "done_when", "limitation"}: finish without the missing capability by
                    another method or a narrower done_when, stated in the final answer under Limitations
                    (capability only)

`parse_fix` reads the reply strictly; `fix_problems` makes the checks that need no live plan: the edit is allowed for
the cause, its texts pass V3 (sizes) and V4 (no wording that skips checks), its tools pass V1 (available in this run,
no outside action, not paid), work_around is for capability only, and it is not a repeat. The plan runner adds the
checks on the live plan (roles, team size, done steps, the step graph: V5) and applies the edit
(PlanRunner.propose_fix). V2 (run options) and V6 (model preferences) have no edit here.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from amoeba.adapt.recipe import adapt_config
from amoeba.task.models import DraftedRole

D_OPS = ("add_role_rule", "add_helper_role", "grant_tool", "split_step", "replan_remaining", "work_around")
SHAPES = {"add_role_rule": '{"role": "<a role of the stuck step>", "text": "<one rule, at most 300 characters>"}',
          "add_helper_role": '{"role": {"name": "...", "description": "...", "goal": "...", "responsibilities": '
                             '["..."], "skills": ["..."], "tools": ["<available tools only>"], "outputs": '
                             '[{"artifact": "...", "format": "..."}], "success_criteria": ["..."], "constraints": [], '
                             '"prompt": "You are ..."}, "lead": true|false (true: the new helper writes the step)}',
          "grant_tool": '{"role": "<a role of the stuck step>", "tool": "<an available tool>"}',
          "split_step": '{"steps": [{"roles": ["<role>"], "text": "<what this sub-step does>", "do": "...", '
                        '"output": "...", "done_when": "..."}, ... 2 or 3 sub-steps, in order]}',
          "replan_remaining": '{"plan": "<the replacement steps, in the Planner\'s Execution Plan format: '
                              '\\"N. [Role]: title\\" lines with covers / depends_on / do / output / done_when; '
                              'number a rewritten step with its own number and new steps from ${next}>"}',
          "work_around": '{"capability": "<the missing capability>", "method": "<the other method>", '
                         '"done_when": "<the narrower done_when, or empty to keep it>", '
                         '"limitation": "<one sentence for the final answer\'s Limitations>"}'}
MAX_CARD_CHARS = 1500     # a new helper's prompt / description
MAX_STEP_CHARS = 600      # a sub-step's text or do


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoleRuleP(_P):
    role: str
    text: str


class HelperP(_P):
    role: dict
    lead: bool = False


class GrantP(_P):
    role: str
    tool: str


class SubStep(_P):
    roles: list[str] = Field(min_length=1)
    text: str
    do: str = ""
    output: str = ""
    done_when: str = ""


class SplitP(_P):
    steps: list[SubStep] = Field(min_length=2, max_length=3)


class ReplanP(_P):
    plan: str


class WorkAroundP(_P):
    capability: str
    method: str
    done_when: str = ""
    limitation: str


PARAMS = {"add_role_rule": RoleRuleP, "add_helper_role": HelperP, "grant_tool": GrantP, "split_step": SplitP,
          "replan_remaining": ReplanP, "work_around": WorkAroundP}


# box: proposer
class FixEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["add_role_rule", "add_helper_role", "grant_tool", "split_step", "replan_remaining", "work_around"]
    params: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _params(self):
        self.params = PARAMS[self.op].model_validate(self.params).model_dump()
        if self.op == "add_helper_role":
            DraftedRole.model_validate(self.params["role"])
        return self

    def key(self) -> str:
        """The op and its parameters with texts normalised: the same edit proposed twice has the same key."""
        def norm(v: Any):
            if isinstance(v, str):
                return " ".join(v.lower().split())
            if isinstance(v, dict):
                return {k: norm(x) for k, x in sorted(v.items())}
            if isinstance(v, list):
                return [norm(x) for x in v]
            return v
        return "proposer:" + hashlib.sha256(json.dumps({"op": self.op, "params": norm(self.params)},
                                                       sort_keys=True).encode()).hexdigest()[:16]

    def texts(self) -> list[tuple[str, str, int]]:
        """(where, text, size limit) of every text the edit puts in front of the team."""
        lim = int(adapt_config()["recipe"]["max_text_chars"])
        p = self.params
        if self.op == "add_role_rule":
            return [("rule", p["text"], lim)]
        if self.op == "add_helper_role":
            r = p["role"]
            out = [("role prompt", str(r.get("prompt") or ""), MAX_CARD_CHARS),
                   ("role description", str(r.get("description") or ""), MAX_CARD_CHARS),
                   ("role goal", str(r.get("goal") or ""), lim)]
            return out + [(f"role {k}", str(x), lim) for k in ("responsibilities", "success_criteria", "constraints")
                          for x in r.get(k) or []]
        if self.op == "split_step":
            return [(f"sub-step {i} {k}", s[k], MAX_STEP_CHARS if k in ("text", "do") else lim)
                    for i, s in enumerate(p["steps"], 1) for k in ("text", "do", "output", "done_when")]
        if self.op == "replan_remaining":
            return [("plan", p["plan"], 8000)]
        if self.op == "work_around":
            return [("method", p["method"], lim), ("done_when", p["done_when"], lim), ("limitation", p["limitation"], lim)]
        return []


# box: proposer
class FixReply(BaseModel):
    """The reply, parsed strictly: exactly these keys."""
    model_config = ConfigDict(extra="forbid")
    edit: FixEdit
    reason: str = Field(max_length=300)


# box: proposer
def parse_fix(text: str) -> FixReply:
    """The first JSON object of the reply (a code fence around it is allowed)."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("no JSON object in the reply")
    return FixReply.model_validate(json.loads(m.group(0)))


# box: proposer
def allowed_text(allowed: list[str], next_step: int) -> str:
    return "\n".join(f"- {op}: params {SHAPES[op].replace('${next}', str(next_step))}" for op in allowed
                     if op in SHAPES) or "None."


# box: proposer
def fix_problems(reply: FixReply, cause: str, allowed: list[str], tools: dict[str, str], tried: set[str],
                 roles_of_step: list[str]) -> list[str]:
    """The checks that need no live plan. tools: name → description of the tools available in this run; tried: the
    keys of the fixes already tried in this task; roles_of_step: the stuck step's role names."""
    from amoeba.pool.stock import side_effect
    cfg = adapt_config()["recipe"]
    e, p, out = reply.edit, reply.edit.params, []
    if e.op not in allowed:
        out.append(f"edit {e.op!r} is not allowed for the cause {cause}; allowed: {[a for a in allowed if a in D_OPS]}")
    if e.op == "work_around" and cause != "capability":
        out.append("work_around is allowed for a missing capability only")
    for where, text, lim in e.texts():
        if len(text) > lim:
            out.append(f"V3: {where}: {len(text)} characters > {lim}")
        hits = [w for w in cfg["denylist"] if w in text.lower()]
        if hits:
            out.append(f"V4: {where}: denied wording {hits}")
    if e.op in ("add_role_rule", "grant_tool") and p["role"] not in roles_of_step:
        out.append(f"role {p['role']!r} is not a role of the stuck step ({', '.join(roles_of_step)})")
    if e.op == "add_role_rule" and not p["text"].strip():
        out.append("V3: rule: empty text")
    wanted = [p["tool"]] if e.op == "grant_tool" else list(DraftedRole.model_validate(p["role"]).tools) \
        if e.op == "add_helper_role" else []
    for t in wanted:
        if t not in tools:
            out.append(f"V1: tool {t!r} is not available in this run")
        elif side_effect(t, tools.get(t, "")):
            out.append(f"V1: tool {t!r} acts outside the run")
        elif "x402" in t.lower() or "paid" in t.lower():
            out.append(f"V1: tool {t!r} is a paid endpoint")
    if e.key() in tried:
        out.append("this edit was already tried in this task")
    return out
