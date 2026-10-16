"""D141 — protocol v2's reply models: one pydantic model per call kind, and plain code that turns each typed reply
into the text the legacy reader already parses.

No model has a thought, reasoning or chain-of-thought field: Claude refuses to write out its reasoning
(`reasoning_extraction`, D134), and nothing downstream reads it. Each has an optional `rationale` of at most two
sentences, kept in the trace only. Under `--protocol v2` every call site asks for its model through `llm/ask.py`
(`ask`), and the typed reply is rendered by `to_legacy` into the sections or JSON the call site parsed before, so the
code after the call is the same in both protocols (the way D136 renders a typed Final_Output into markers).
"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from amoeba.adapt.proposer import FixReply
from amoeba.interp.step_protocol import FinalOutput, ResolverOutput

StepFinal = FinalOutput          # Final_Output (D136)
ResolveOut = ResolverOutput      # the dispute resolver (D136)
FixOut = FixReply                # the fix proposer (D117 D): its params differ per op, so it goes as json_prompt


def two_sentences(v: str | None) -> str | None:
    """A rationale is at most two sentences (and 400 characters)."""
    if not v:
        return None
    parts = re.split(r"(?<=[.!?])\s+", str(v).strip())
    return " ".join(parts[:2])[:400]


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rationale: str | None = Field(default=None, description="optional, at most two sentences")

    _two = field_validator("rationale")(lambda cls, v: two_sentences(v))


# ---- Box 1 ------------------------------------------------------------------------------------------------------
class Reading(BaseModel):
    reading: str
    why: str = Field(description="one line")
    confidence: float = Field(description="0 to 1; one entity's readings add up to at most 1")


class Entity(BaseModel):
    entity: str = Field(description="the words as written in the task")
    readings: list[Reading]


# box: interpret
class ReadingOut(_Out):
    entities: list[Entity] = Field(description="empty when nothing in the task is in doubt")


# box: interpret
class FamilyOut(_Out):
    family: str = Field(description="a family name from the list, or new")
    why: str


class SearchQuery(BaseModel):
    query: str
    reason: str


# box: interpret
class PlanSearchOut(_Out):
    need_search: bool
    why: str
    queries: list[SearchQuery]


# ---- Box 2 ------------------------------------------------------------------------------------------------------
class RequirementOut(BaseModel):
    id: str = Field(description="R1, R2, ...")
    text: str


class QuestionOut(BaseModel):
    question: str
    assumption: str


class OutputSpec(BaseModel):
    artifact: str
    format: str


class RoleOut(BaseModel):
    name: str
    seniority: str
    description: str
    goal: str
    responsibilities: list[str]
    skills: list[str]
    tools: list[str]
    inputs: list[str]
    outputs: list[OutputSpec]
    success_criteria: list[str]
    constraints: list[str]
    covers: list[str]
    is_summariser: bool
    prompt: str = Field(description="the full working prompt for this specialist")


class RequestOut(BaseModel):
    name: str
    kind: Literal["tool", "skill"]
    for_role: str
    what_it_does: str
    input: str
    output: str
    example_input: str
    example_output: str


class CheckOut(BaseModel):
    """D142: one typed step check from the fixed vocabulary (task/contract.py VOCAB)."""
    name: Literal["file_exists", "docx_pages_max", "docx_words_between", "docx_has_table", "xlsx_rows_min",
                  "xlsx_columns", "xlsx_has_formulas", "csv_rows_min", "csv_columns", "image_exists",
                  "output_has_table", "output_has_list", "output_mentions", "cites_every_figure", "figures_dated",
                  "verdict_present", "not_sent_fallback"]
    params: dict = Field(default_factory=dict, description="the check's parameters, e.g. {\"n\": 3}")
    covers: list[str] = Field(description="the requirement ids this check proves")


class StepOut(BaseModel):
    number: int
    roles: list[str]
    title: str
    kind: Literal["work", "verify"]
    covers: list[str]
    depends_on: list[int]
    do: str
    output: str = Field(description="the artifact, starting with format markers: table:, list:, code:, memo:")
    done_when: str
    checks: list[CheckOut] = Field(default_factory=list, description="D142: what plain code checks when the step ends")


class ReadingRevisionOut(BaseModel):
    """D143: the planner's proposal to change Box 1's reading of one entity (accepted only by code's rules)."""
    entity: str
    from_reading: str
    to_reading: str
    reason: str = Field(description="one sentence")
    evidence: list[str] = Field(description='plan search source ids such as "P2", or "task text"')


# box: planner
class PlanOut(_Out):
    requirements: list[RequirementOut]
    givens: list[str]
    open_questions: list[QuestionOut]
    roles: list[RoleOut]
    capability_requests: list[RequestOut]
    plan: list[StepOut]
    risks: list[str]
    reading_revision: ReadingRevisionOut | None = Field(default=None, description="D143: only when the evidence shows "
                                                                                  "the working reading cannot hold")


class IssueOut(BaseModel):
    severity: Literal["blocking", "minor"]
    step: int | None = Field(default=None, description="the step number, when the issue is about one step")
    requirement: str | None = Field(default=None, description="the requirement id, when it is about one")
    problem: str
    fix: str


# box: planner
class ReviewOut(_Out):
    """Both Box 2 observers (team and plan)."""
    verdict: Literal["APPROVE", "REVISE"]
    issues: list[IssueOut]


# ---- Box 3 ------------------------------------------------------------------------------------------------------
# box: plan_step
class CritiqueOut(_Out):
    verdict: Literal["AGREE", "REVISE"]
    issues: list[str]


# box: action_obs
class ReplanOut(_Out):
    decision: Literal["CONTINUE", "REVISE_REMAINING", "ADD_STEP", "REASSIGN_STEP", "DROP_STEP", "ADD_ROLE"]
    reason: str
    steps: str = Field(description="as the decision asks, in the Execution Plan format; empty when none")
    role: RoleOut | None = Field(default=None, description="for ADD_ROLE only")
    unmet: str = Field(description="for DROP_STEP; empty when none")
    capability_requests: list[RequestOut]


# box: toolbox
class PoolPickOut(_Out):
    choice: str = Field(description="exactly one candidate id from the list, or NONE")


# box: toolmaker
class ToolWriterOut(_Out):
    name: str = Field(description="a short snake_case name")
    description: str = Field(description="one line: what the tool does")
    input: str = Field(description="the JSON fields run() reads")
    code: str = Field(description="the whole Python module: run(args) and self_test()")


# the call kinds and their models
SCHEMAS: dict[str, type[BaseModel]] = {
    "reading": ReadingOut, "family": FamilyOut, "plan_search": PlanSearchOut, "plan": PlanOut,
    "review": ReviewOut, "step_final": StepFinal, "resolve": ResolveOut, "replan": ReplanOut,
    "critique": CritiqueOut, "pool_pick": PoolPickOut, "fix": FixOut, "tool_writer": ToolWriterOut,
}


# ---- typed reply → the legacy reader's text ----------------------------------------------------------------------
# box: planner
def to_legacy(kind: str, out: BaseModel) -> str:
    """Plain code: a typed reply as the text the legacy parser of that call site reads (sections or JSON)."""
    d = out.model_dump(mode="json")
    if kind == "reading":
        return "## Entities\n```json\n" + json.dumps(d["entities"], ensure_ascii=False) + "\n```"
    if kind in ("family", "plan_search", "fix"):
        return json.dumps({k: v for k, v in d.items() if k != "rationale"}, ensure_ascii=False)
    if kind == "tool_writer":
        head = {k: d[k] for k in ("name", "description", "input")}
        return json.dumps(head, ensure_ascii=False) + "\n```python\n" + d["code"].rstrip() + "\n```"
    if kind == "pool_pick":
        return d["choice"].strip()
    if kind == "critique":
        issues = "\n".join(f"{i}. {x}" for i, x in enumerate(d["issues"], 1)) or "None"
        return f"## Verdict\n{d['verdict']}\n\n## Issues\n{issues}"
    if kind == "review":
        return review_text(out)
    if kind == "replan":
        role = json.dumps(d["role"], ensure_ascii=False) if d.get("role") else "None"
        reqs = "\n".join(json.dumps(r, ensure_ascii=False) for r in d["capability_requests"]) or "None"
        return (f"## Decision\n{d['decision']}\n\n## Reason\n{d['reason']}\n\n## Steps\n{d['steps'] or 'None'}\n\n"
                f"## Role\n{role}\n\n## Unmet\n{d['unmet'] or 'None'}\n\n## Capability Requests\n{reqs}")
    if kind == "plan":
        return plan_markdown(out)
    raise ValueError(f"no legacy text for kind {kind!r}")


# box: planner
def review_text(out: "ReviewOut", only_blocking: bool = False) -> str:
    """An observer's typed review as the d24 sections (Suggestions, Verdict). With only_blocking, minor issues are
    left out (D143: only blocking issues go back to the planner)."""
    issues = [i for i in out.issues if i.severity == "blocking" or not only_blocking]
    lines = []
    for n, i in enumerate(issues, 1):
        where = ", ".join(x for x in (f"step {i.step}" if i.step else "", i.requirement or "") if x)
        lines.append(f"{n}. [{i.severity}]{' ' + where + ':' if where else ''} {i.problem} — fix: {i.fix}")
    return f"## Suggestions\n{chr(10).join(lines) or 'No Suggestions'}\n\n## Verdict\n{out.verdict}"


# box: planner
def plan_markdown(p: "PlanOut") -> str:
    """The planner's typed plan as the d24 reply sections, so the d24 parsers and the quality checks read it."""
    roles = ",\n".join(json.dumps(r.model_dump(mode="json"), ensure_ascii=False) for r in p.roles)
    reqs = ",\n".join(json.dumps(r.model_dump(mode="json"), ensure_ascii=False) for r in p.capability_requests)
    steps = []
    for s in sorted(p.plan, key=lambda x: x.number):
        steps.append(f"{s.number}. [{', '.join(s.roles)}]: {s.title}\n   kind: {s.kind}\n"
                     f"   covers: {', '.join(s.covers) or 'none'}\n"
                     f"   depends_on: {', '.join(map(str, s.depends_on)) or 'none'}\n   do: {s.do}\n"
                     f"   output: {s.output}\n   done_when: {s.done_when}" +
                     (f"\n   checks: {json.dumps([c.model_dump(mode='json') for c in s.checks], ensure_ascii=False)}"
                      if s.checks else ""))
    oq = "\n".join(f"- question: {q.question} | assumption: {q.assumption}" for q in p.open_questions) or "None"
    return ("## Requirements:\n" + ("\n".join(f"{r.id}: {r.text}" for r in p.requirements) or "None") +
            "\n\n## Givens and Assumptions:\n" + ("\n".join(f"- {g}" for g in p.givens) or "None") +
            f"\n\n## Open Questions:\n{oq}" +
            "\n\n## Selected Roles List:\n```\n[]\n```" +
            f"\n\n## Created Roles List:\n```\n{roles}\n```" +
            f"\n\n## Capability Requests:\n```\n{reqs or 'None'}\n```" +
            "\n\n## Execution Plan:\n" + "\n".join(steps) +
            "\n\n## Risks and Decisions:\n" + ("\n".join(f"- {r}" for r in p.risks) or "None") +
            "\n\n## RoleFeedback\nNone\n\n## PlanFeedback\nNone")
