"""Toy tasks with known answers — the same ones every time for a given seed. Three families in Phase 1."""
from __future__ import annotations

import random
import re

from amoeba.task.models import Task
from amoeba.tools.registry import calc

FAMILIES = ("arith", "reverse", "vowels")
WORDS = ("adaptive", "amoeba", "topology", "interpreter", "envelope", "reviewer", "planner",
         "observer", "sentinel", "consensus", "programming", "deterministic", "trace", "schema")


# box: toy_source
def _make(rng: random.Random, family: str, i: int, seed: int) -> Task:
    tid = f"toy-{seed}-{i:03d}"
    if family == "arith":
        a, b, c = rng.randint(2, 40), rng.randint(2, 40), rng.randint(1, 99)
        expr = f"{a} * {b} + {c}"
        return Task(id=tid, prompt=f"Compute {expr}. Reply with just the number.", family=family,
                    ground_truth=calc(expr), tags=["toy"])
    word = rng.choice(WORDS)
    if family == "reverse":
        return Task(id=tid, prompt=f"Reverse the string '{word}' then uppercase it. Reply with just the result.",
                    family=family, ground_truth=word[::-1].upper(), tags=["toy"])
    return Task(id=tid, prompt=f"How many vowels are in the word '{word}'? Reply with just the number.",
                family="vowels", ground_truth=str(sum(ch in "aeiou" for ch in word)), tags=["toy"])


# box: ov_task, toy_source
class ToyTaskSource:
    def __init__(self, seed: int = 0, n: int = 20):
        self.seed, self.n = seed, n

    def tasks(self) -> list[Task]:
        rng = random.Random(self.seed)
        return [_make(rng, FAMILIES[i % len(FAMILIES)], i, self.seed) for i in range(self.n)]

    def __iter__(self):
        return iter(self.tasks())

    def __len__(self) -> int:
        return self.n


def solve_toy(prompt: str) -> str | None:
    """Deterministic oracle for the three families (used by the toy mock model); None for anything else."""
    m = re.search(r"Compute (.+?)\. Reply", prompt)
    if m:
        return calc(m.group(1))
    m = re.search(r"Reverse the string '(.+?)' then uppercase it", prompt)
    if m:
        return m.group(1)[::-1].upper()
    m = re.search(r"How many vowels are in the word '(.+?)'", prompt)
    if m:
        return str(sum(ch in "aeiou" for ch in m.group(1)))
    return None
