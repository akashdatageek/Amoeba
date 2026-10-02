"""D80 — Box 0, the task stream (Phase 2 spec §2).

`tasks/stream_<name>.jsonl`: one task per line, the Phase 1 Task fields plus `split` (practice | heldout), `phase`
(pre | post the family's shift) and `order` (the position in the stream; practice tasks only).
`tasks/stream_<name>.shifts.yaml`: the shifts — a `feedback` shift (the post-phase rubrics carry new item(s) that the
prompts never mention) or a `remove_tool` shift (code takes a tool out of the family's runs, `--disable-tools`).

Held-out tasks are never run as stream tasks and never reach the practice loop or any prompt: `Stream.practice()` is
the only way the loop gets tasks, and `heldout()` is for Box 7 only. The only rubric information the loop ever sees
is the feedback channel: the names of the rubric items a practice run failed (`feedback`).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from amoeba.task.models import Task

TASKS_DIR = Path(__file__).resolve().parents[2] / "tasks"


# box: stream
class HeldOutLeak(RuntimeError):
    """A held-out task (or its text) was about to reach the practice loop or a prompt."""


# box: stream
class StreamTask(Task):
    split: Literal["practice", "heldout"]
    phase: Literal["pre", "post"]
    order: int | None = None

    @model_validator(mode="after")
    def _order(self):
        if self.split == "practice" and self.order is None:
            raise ValueError(f"{self.id}: a practice task needs an order")
        if self.split == "heldout" and self.order is not None:
            raise ValueError(f"{self.id}: a held-out task has no order")
        if self.rubric is None:
            raise ValueError(f"{self.id}: a stream task is scored by its D30 rubric")
        return self

    def as_task(self) -> Task:
        """The plain Phase 1 Task Boxes 1–3 run (split, phase and order stay with the stream)."""
        return Task(**self.model_dump(include=set(Task.model_fields)))


# box: stream
class Shift(BaseModel):
    after: int                                   # takes effect from practice order after + 1
    family: str
    kind: Literal["feedback", "remove_tool"]
    items: list[str] = Field(default_factory=list)     # feedback: the new rubric item names
    tool: str | None = None                            # remove_tool: e.g. "local:Bash"

    @model_validator(mode="after")
    def _shape(self):
        if self.kind == "feedback" and not self.items:
            raise ValueError("a feedback shift names its rubric item(s)")
        if self.kind == "remove_tool" and not self.tool:
            raise ValueError("a remove_tool shift names its tool")
        return self


# box: stream
def item_names(task: Task) -> list[str]:
    r = task.rubric
    if r is None:
        return []
    return [x.name for x in [*r.required_deliverables, *r.expected_numbers, *r.constraints_to_respect, *r.must_not]]


# box: stream
class Stream(BaseModel):
    name: str
    tasks: list[StreamTask]
    shifts: list[Shift] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self):
        ids = [t.id for t in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("stream task ids must be unique")
        orders = [t.order for t in self.tasks if t.split == "practice"]
        if len(orders) != len(set(orders)):
            raise ValueError("practice orders must be unique")
        for s in self.shifts:
            fam = [t for t in self.tasks if t.family == s.family]
            for t in fam:
                if t.split == "practice":
                    want = "post" if t.order > s.after else "pre"
                    if t.phase != want:
                        raise ValueError(f"{t.id}: order {t.order} is {want} the shift after {s.after}")
                if s.kind != "feedback":
                    continue
                names = {n.lower() for n in item_names(t)}
                for item in s.items:
                    if (item.lower() in names) != (t.phase == "post"):
                        raise ValueError(f"{t.id}: the item {item!r} belongs to the post-phase rubrics only")
                    if item.lower() in t.prompt.lower():
                        raise ValueError(f"{t.id}: the prompt mentions the feedback item {item!r}")
        return self

    # ---- what the practice loop may see -----------------------------------------------------------------------
    def practice(self, family: str | None = None) -> list[StreamTask]:
        """The practice tasks in stream order — the only tasks the loop runs. Never a held-out one."""
        out = sorted((t for t in self.tasks if t.split == "practice" and family in (None, t.family)),
                     key=lambda t: t.order)
        for t in out:
            assert_practice(t)
        return out

    def shifts_due(self, task: StreamTask) -> list[Shift]:
        """The shifts in effect for a practice task (its family, order past `after`)."""
        assert_practice(task)
        return [s for s in self.shifts if s.family == task.family and task.order > s.after]

    def disabled_tools(self, task: StreamTask) -> list[str]:
        return [s.tool for s in self.shifts_due(task) if s.kind == "remove_tool"]

    # ---- Box 7 only -------------------------------------------------------------------------------------------
    def heldout(self, family: str, phase: str | None = None) -> list[StreamTask]:
        """The family's held-out tasks (post first, then pre) — for the Experimenter only."""
        xs = [t for t in self.tasks if t.split == "heldout" and t.family == family and phase in (None, t.phase)]
        return sorted(xs, key=lambda t: (t.phase != "post", t.id))

    def families(self) -> list[str]:
        return sorted({t.family for t in self.tasks})


# box: stream
def assert_practice(task) -> None:
    if getattr(task, "split", "practice") == "heldout":
        raise HeldOutLeak(f"held-out task {task.id} reached the practice loop")


# box: stream
def stream_paths(name_or_path: str | Path) -> tuple[Path, Path]:
    p = Path(name_or_path)
    if p.suffix == ".jsonl":
        return p, p.with_name(p.stem + ".shifts.yaml")
    return TASKS_DIR / f"stream_{name_or_path}.jsonl", TASKS_DIR / f"stream_{name_or_path}.shifts.yaml"


# box: stream
def load_stream(name_or_path: str | Path) -> Stream:
    tasks_file, shifts_file = stream_paths(name_or_path)
    tasks = [StreamTask.model_validate_json(l) for l in tasks_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    shifts = (yaml.safe_load(shifts_file.read_text(encoding="utf-8")) or {}).get("shifts", []) \
        if shifts_file.exists() else []
    name = tasks_file.stem.removeprefix("stream_")
    return Stream(name=name, tasks=tasks, shifts=[Shift.model_validate(s) for s in shifts])


# box: stream
def feedback(rubric_result: dict | None) -> list[str]:
    """The feedback channel (§2.2): the NAMES of the rubric items a practice run failed — nothing else (no
    patterns, no expected numbers, no evidence)."""
    return [i["name"] for i in (rubric_result or {}).get("items", []) if not i["pass"]]


# box: stream
def feedback_record(task: StreamTask, result) -> dict:
    """What the loop keeps from one practice run's scoring."""
    assert_practice(task)
    graded = result.rubric if hasattr(result, "rubric") else result.get("rubric")
    return {"task_id": task.id, "order": task.order, "family": task.family, "failed_items": feedback(graded)}


# ---- leakage screen (§7, re-checked by the Gate §9.2.1) ------------------------------------------------------------
# box: stream
def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:[.,][0-9]+)*", (text or "").lower())


# box: stream
def leaks(text: str, heldout: list[StreamTask], ngram: int = 8) -> list[str]:
    """Why `text` (an edit's text) leaks held-out content: an 8-word sequence from a held-out prompt, a held-out
    expected number, or a held-out task id. Empty when clean."""
    out = []
    low = (text or "").lower()
    words = _words(text)
    grams = {" ".join(words[i:i + ngram]) for i in range(len(words) - ngram + 1)}
    for t in heldout:
        if t.id.lower() in low:
            out.append(f"held-out task id {t.id}")
        pw = _words(t.prompt)
        hit = next((" ".join(pw[i:i + ngram]) for i in range(len(pw) - ngram + 1)
                    if " ".join(pw[i:i + ngram]) in grams), None)
        if hit:
            out.append(f"8-word sequence from {t.id}: {hit!r}")
        for x in (t.rubric.expected_numbers if t.rubric else []):
            v = f"{x.value:.12g}"
            if len(v.replace(".", "")) >= 3 and re.search(rf"(?<![\d.]){re.escape(v)}(?![\d])",
                                                          low.replace(",", "")):
                out.append(f"held-out expected number {v} ({t.id})")
    return out


# box: stream
def dump_task_line(t: StreamTask) -> str:
    return json.dumps(t.model_dump(mode="json", exclude_none=True), ensure_ascii=False)
