"""YAML persistence and a content hash for TeamConfig."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel

from amoeba.config.schema import TeamConfig


def to_dict(cfg: BaseModel) -> dict:
    return cfg.model_dump(mode="json")


def dump_yaml(cfg: TeamConfig, path: str | Path) -> None:
    Path(path).write_text(yaml.safe_dump(to_dict(cfg), sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_yaml(path: str | Path) -> TeamConfig:
    return TeamConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def config_hash(cfg: TeamConfig | dict) -> str:
    """sha256 of the canonical JSON form — stable under key reordering."""
    d = to_dict(cfg) if isinstance(cfg, BaseModel) else cfg
    canonical = json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
