"""D56 — match a capability request to pool entries by keyword overlap (plain code, 0 tokens, no embeddings)."""
from __future__ import annotations

import re

import yaml

from amoeba.capabilities import ALIASES_FILE, snake

STOP = set("""a an and any are as at be by can for from given has have in into is it its of on or per that the their
this to via what when which with without who will your you our one each all more most other such than then them
these those use used uses using get gets return returns returned input output inputs outputs text tool tools skill
skills server servers mcp model models agent agents helper helpers ability able provide provides provided support
supports based data new run runs task tasks work works do does make makes need needs named name""".split())


# box: toolbox
def words(text: str) -> set[str]:
    """Lower-case content words of 3+ characters; a plural 's' is dropped so 'prices' meets 'price'."""
    out = set()
    for w in re.findall(r"[a-z0-9]+", (text or "").lower().replace("_", " ")):
        if len(w) < 3 or w in STOP or w.isdigit():
            continue
        out.add(w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w)
    return out


# box: toolbox
def aliases_of(canonical: str) -> list[str]:
    """The alias list of a standard name (amoeba/capabilities/aliases.yaml); [] when it has none."""
    data = yaml.safe_load(ALIASES_FILE.read_text(encoding="utf-8")) or {}
    for name, aliases in data.items():
        if snake(name) == snake(canonical):
            return list(aliases or [])
    return []


# box: toolbox
def request_words(q) -> set[str]:
    """What a request says it needs: its standard name and aliases, raw name, what it does, input and output."""
    return words(" ".join([q.canonical, *aliases_of(q.canonical), q.name, q.what_it_does, q.input, q.output]))


# box: toolbox
def rank(q, entries: list[dict], top: int = 5) -> list[tuple[int, dict]]:
    """The best `top` entries as (score, entry), best first; only scores above zero. Tools and skills compete alike
    (D58): the request's kind is the planner's guess, so an xlsx 'tool' may be met by an xlsx skill. A word counts
    once for appearing in the entry's description and once more for appearing in its name or title."""
    want = request_words(q)
    scored = []
    for e in entries:
        name = words(f"{e.get('name', '')} {e.get('title', '')}".replace("/", " ").replace(".", " "))
        score = len(want & words(e.get("description", ""))) + len(want & name)
        if score > 0:
            scored.append((score, e))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return scored[:top]
