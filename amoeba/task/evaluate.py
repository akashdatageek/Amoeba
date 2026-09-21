"""Deterministic scoring for toy tasks. No AI judge in Phase 1 (that is Phase 2, as a signal only)."""
from __future__ import annotations

import re


def normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower()).rstrip(".").strip()


def score(answer: str | None, ground_truth: str | None) -> float | None:
    """1.0 / 0.0 after trimming spaces and case; None when there is no known answer."""
    if ground_truth is None or answer is None:
        return None
    return 1.0 if normalise(answer) == normalise(ground_truth) else 0.0
