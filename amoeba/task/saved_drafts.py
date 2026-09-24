"""D45 — reuse saved Box 2 drafts instead of drafting again.

Two folder shapes are read:
- an eval_draft output folder: <dir>/drafts/<task_id>.<repeat>.json (one Draft per task and repeat);
- a run_task runs folder: <dir>/<run_id>/plan.json (or draft.json) with result.json naming the task, or one run
  folder itself.
A saved file whose draft failed (no created_roles) is skipped. The team (team.yaml) is not reused: it is built per
topology, so each topology builds its own team from the same Draft.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from amoeba.task.models import Draft


@dataclass
class SavedDraft:
    task_id: str
    draft: Draft
    source: str          # the eval_draft file stem ("<folder>/drafts/<task>.<rep>") or the run id


def _load(path: Path) -> Draft | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Draft.model_validate(data) if data.get("created_roles") else None


def load_saved_drafts(folder: str | Path) -> dict[str, list[SavedDraft]]:
    """task id -> its saved drafts, in repeat order (eval_draft) or run start order (run folders)."""
    root = Path(folder)
    out: dict[str, list[SavedDraft]] = {}
    if (root / "drafts").is_dir():                                   # eval_draft output
        files = [p for p in (root / "drafts").glob("*.json") if re.match(r".+\.\d+$", p.stem)]
        for p in sorted(files, key=lambda p: (p.stem.rsplit(".", 1)[0], int(p.stem.rsplit(".", 1)[1]))):
            task_id = p.stem.rsplit(".", 1)[0]
            d = _load(p)
            if d:
                out.setdefault(task_id, []).append(SavedDraft(task_id, d, f"{root.name}/drafts/{p.stem}"))
        return out
    runs = [root] if (root / "result.json").exists() else [p for p in root.iterdir() if (p / "result.json").exists()]
    runs.sort(key=lambda p: _started(p))
    for run in runs:
        f = run / "draft.json" if (run / "draft.json").exists() else run / "plan.json"
        if not f.exists():
            continue
        d = _load(f)
        if d:
            task_id = json.loads((run / "result.json").read_text(encoding="utf-8"))["task_id"]
            out.setdefault(task_id, []).append(SavedDraft(task_id, d, run.name))
    return out


def _started(run: Path) -> str:
    """The first trace line's timestamp (the run's start), else the folder name."""
    t = run / "trace.jsonl"
    if t.exists():
        with t.open(encoding="utf-8") as f:
            first = f.readline()
        if first.strip():
            return json.loads(first).get("ts", run.name)
    return run.name


def pick(saved: dict[str, list[SavedDraft]], task_id: str, k: int) -> SavedDraft | None:
    """The k-th saved draft for a task (0-based), or None when there are not that many."""
    xs = saved.get(task_id, [])
    return xs[k] if 0 <= k < len(xs) else None
