"""D117: the adaptation settings (amoeba/config/adapt.yaml) and one helper the niche profile shares.

`adapt_config()` reads adapt.yaml once: `limits` (the proposer's text limits and denied wording, the ranges a code fix
may set a run option to), `diagnoser` (the stuck causes in tie order and the edits each allows), `adapt` (the fix
limits) and `evidence`. Nothing here is read by a model.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from amoeba.task.models import Draft

CONFIG = Path(__file__).resolve().parents[1] / "config" / "adapt.yaml"


# box: diag_edits
@lru_cache(maxsize=1)
def adapt_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


# box: niche
def answer_steps(d: Draft) -> set[int]:
    """Step numbers (1-based) of a draft's answer step(s): the summariser's steps, else the last step."""
    s = next((r.name for r in d.created_roles if r.is_summariser), None)
    owned = {x.index + 1 for x in d.plan if s and s in x.agent_names}
    return owned or ({d.plan[-1].index + 1} if d.plan else set())
