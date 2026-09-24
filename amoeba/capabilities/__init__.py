"""Capability names (D29): map what models call a tool or skill onto one canonical name, from aliases.yaml."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

ALIASES_FILE = Path(__file__).with_name("aliases.yaml")


def snake(name: str) -> str:
    """Lowercase snake_case key: 'Web Search', 'web_search' and 'Web-Search' all give 'web_search'."""
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


@lru_cache(maxsize=1)
def _table() -> dict[str, str]:
    data = yaml.safe_load(ALIASES_FILE.read_text(encoding="utf-8")) or {}
    table: dict[str, str] = {}
    for canonical, aliases in data.items():
        for alias in [canonical, *(aliases or [])]:
            table[snake(alias)] = canonical
    return table


def normalise(name: str) -> tuple[str, bool]:
    """(canonical name, mapped?). An unknown name is kept as written (not snake-cased) and reported as unmapped."""
    canonical = _table().get(snake(name))
    return (canonical, True) if canonical else ((name or "").strip(), False)
