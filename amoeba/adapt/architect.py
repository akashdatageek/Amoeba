"""D87 — Box 6, the Architect (Phase 2 spec §7): the only box of the loop that calls a model.

It reads the diagnosis, the current recipe (YAML), the allowed edits with their parameter shapes, the family's failed
hypotheses (edit + observed result, from the ledger) and up to two practice examples, and proposes ONE typed edit with
a rationale and a signed predicted_delta, as strict JSON. Plain code then checks the reply: it parses (pydantic,
strict), the edit is allowed by the diagnosis and its parameters validate, the new recipe validates (V1–V5), it is not
a repeat of a failed hypothesis (same op and normalised parameters), it passes the leakage screen against every
held-out task (8-word sequences, expected numbers, ids), and -1 ≤ predicted_delta ≤ 1. A failed check gets one retry
with the error shown; then the Architect gives up (`no_hypothesis`). At most 3 hypotheses per alarm; after that the
alarm is `unresolved` and goes to eval/loop/<stream>/human_queue.jsonl.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from amoeba.adapt.diagnoser import Diagnosis
from amoeba.adapt.gate import Hypothesis
from amoeba.adapt.recipe import PARAMS, Edit, Recipe, apply_edit, validate_recipe
from amoeba.adapt.stream import leaks
from amoeba.config.prompts import PROMPT, render
from amoeba.interp.trace import TracedLLM

MAX_TOKENS = 4096
MAX_PER_ALARM = 3

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


# box: architect
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


# box: arch_prompt
def allowed_text(allowed: list[str]) -> str:
    lines = []
    for a in allowed:
        op, _, only = a.partition(":")
        shape = SHAPES[op] if not only else f'{{"name": "{only}", "value": <value>}}'
        lines.append(f"- {op}: params {shape}")
    if any(SHAPES[a.partition(':')[0]].count("SELECTOR") for a in allowed):
        lines.append(SELECTOR)
    return "\n".join(lines)


# box: arch_prompt
def failed_text(failed: list[dict]) -> str:
    if not failed:
        return "None yet."
    return "\n".join(f"- {json.dumps(r['edit'], ensure_ascii=False)}: observed {r.get('observed_delta')}, "
                     f"reasons {r.get('reasons')}" for r in failed)


# box: arch_prompt
def examples_text(examples: list[dict]) -> str:
    out = []
    for i, e in enumerate(examples, 1):
        out.append(f"Example {i} (score {e.get('score')}):\nTask: {e['task']}\nStep {e.get('step')}: do: {e.get('do')}\n"
                   f"output: {e.get('output')}\ndone when: {e.get('done_when')}\nEvidence: "
                   + "; ".join(e.get("evidence") or []))
    return "\n\n".join(out) or "None."


# box: arch_prompt
def diagnosis_text(d: Diagnosis) -> str:
    keep = {k: v for k, v in d.model_dump().items() if k in ("symptom", "cause", "where", "evidence", "counts")}
    if d.supporting:                  # D93: the model's own claims, shown apart; they did not choose the cause
        keep["supporting (declared by the team's model, not checked by code)"] = d.supporting
    return yaml.safe_dump(keep, sort_keys=False, allow_unicode=True).strip()


# box: arch_prompt
def build_prompt(d: Diagnosis, recipe: Recipe, failed: list[dict]) -> str:
    return render(PROMPT.architect, diagnosis=diagnosis_text(d),
                  recipe=yaml.safe_dump(recipe.model_dump(mode="json"), sort_keys=False, allow_unicode=True).strip(),
                  allowed_edits=allowed_text(d.allowed_edits), failed=failed_text(failed),
                  examples=examples_text(d.examples))


# box: architect
def parse_reply(text: str) -> ArchitectReply:
    """The first JSON object in the reply (a <thought> block or a code fence around it is allowed)."""
    t = re.sub(r"<thought>.*?</thought>", "", text or "", flags=re.S)
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        raise ValueError("no JSON object in the reply")
    return ArchitectReply.model_validate(json.loads(m.group(0)))


# box: arch_check
def check(reply: ArchitectReply, d: Diagnosis, recipe: Recipe, failed: list[dict], heldout: list,
          envelope=None, sample_draft=None) -> list[str]:
    """Plain code's checks of one proposal; empty when it may go to the Experimenter."""
    problems = []
    e = reply.edit
    if not _allowed_ok(e, d.allowed_edits):
        problems.append(f"edit {e.op!r} is not allowed for cause {d.cause!r}; allowed: {d.allowed_edits}")
    try:
        new = apply_edit(recipe, e)
        problems += [f"{v.rule}: {v.detail}" for v in validate_recipe(new, envelope, sample_draft)]
    except ValueError as x:
        problems.append(str(x))
    keys = {Edit.model_validate(r["edit"]).key() for r in failed if r.get("edit")}
    if e.key() in keys:
        problems.append("this edit was already tried and rejected for this kind of task")
    problems += [f"leakage: {x}" for t in e.texts() for x in leaks(t, heldout)]
    return problems


# box: architect, ov_m6
def propose(d: Diagnosis, recipe: Recipe, failed: list[dict], heldout: list, llm, trace, hypothesis_id: str,
            seed: int = 0, envelope=None, sample_draft=None) -> tuple[Hypothesis | None, dict]:
    """One hypothesis, or None after one retry. Returns (hypothesis, record of the attempt(s))."""
    tl = TracedLLM(llm, trace)
    prompt = build_prompt(d, recipe, failed)
    messages = [{"role": "user", "content": prompt}]
    record = {"hypothesis_id": hypothesis_id, "prompt": prompt, "attempts": []}     # D95: kept in full
    for attempt in (1, 2):
        raw = tl.chat_messages(messages, seed=seed, max_tokens=MAX_TOKENS, agent_name="architect",
                               role="planner").content
        try:
            reply = parse_reply(raw)
            problems = check(reply, d, recipe, failed, heldout, envelope, sample_draft)
        except (ValueError, ValidationError, json.JSONDecodeError) as x:
            reply, problems = None, [f"the reply is not valid: {str(x)[:500]}"]
        record["attempts"].append({"attempt": attempt, "reply": raw, "problems": problems})   # D95: no truncation
        trace.event("architect_proposal", {"amoeba.box": "architect", "amoeba.attempt": attempt,
                                           "amoeba.problems": problems, "amoeba.hypothesis_id": hypothesis_id})
        if reply is not None and not problems:
            h = Hypothesis(hypothesis_id=hypothesis_id, family=d.family, edit=reply.edit, rationale=reply.rationale,
                           predicted_delta=reply.predicted_delta, diagnosis_ref=d.symptom)
            record["hypothesis"] = h.model_dump()
            return h, record
        messages = messages + [{"role": "assistant", "content": raw},
                               {"role": "user", "content": "Your reply was refused by the checks:\n- "
                                + "\n- ".join(problems) + "\nReply again with one JSON object that passes them."}]
    record["no_hypothesis"] = True
    return None, record


# box: arch_queue
def log_unresolved(root: str | Path, alarm: dict, diagnosis: Diagnosis, tried: list[str]) -> dict:
    """After MAX_PER_ALARM hypotheses (or none), the alarm waits for a person: eval/loop/<stream>/human_queue.jsonl."""
    row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": "unresolved",
           "family": diagnosis.family, "alarm": alarm, "diagnosis": diagnosis.model_dump(exclude={"examples"}),
           "hypotheses_tried": tried}
    p = Path(root) / "human_queue.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row
