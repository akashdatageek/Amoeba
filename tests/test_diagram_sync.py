"""The diagram must stay in sync with the code (CLAUDE.md "The diagram").

(a) parse every data-card in diagram/amoeba_phase1.html; (b) every Files: path that points into amoeba/ must exist;
(c) every module under amoeba/ must be named in at least one card; (d) fail with the full list of what is missing
on either side.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIAGRAM = ROOT / "diagram" / "amoeba_phase1.html"
PACKAGE = ROOT / "amoeba"
SUBPACKAGES = tuple(p.name + "/" for p in PACKAGE.iterdir() if p.is_dir() and not p.name.startswith("__"))


def cards() -> list[dict[str, str]]:
    """Every data-card as {field: text}; the attribute is HTML-escaped twice (entity inside an attribute)."""
    src = DIAGRAM.read_text(encoding="utf-8")
    out = []
    for raw in re.findall(r'data-card="(.*?)"', src, re.S):
        body = html.unescape(html.unescape(raw))
        out.append({dt: re.sub(r"<[^>]+>", "", dd).strip()
                    for dt, dd in re.findall(r"<dt>(.*?)</dt><dd[^>]*>(.*?)</dd>", body, re.S)})
    return out


def files_field(card: dict[str, str]) -> str:
    """The part of Files: before any source citation (← original file), arrow (→ output) or dash (— note)."""
    return re.split(r"←|→|—", card.get("Files", ""))[0]


def package_paths(text: str) -> set[str]:
    """Paths in a Files: field that point into amoeba/, as paths relative to amoeba/. Bare *.txt names are prompts."""
    paths = set()
    for tok in re.findall(r"[\w./*-]+\.(?:py|txt)", text):
        if tok.startswith(SUBPACKAGES):
            paths.add(tok)
        elif "/" not in tok and tok.endswith(".txt"):
            paths.add(f"config/prompts/{tok}")
    return paths


def test_cards_parse():
    cs = cards()
    assert len(cs) >= 20
    assert all("Description" in c and "Files" in c for c in cs), [c for c in cs if "Files" not in c]


def test_every_card_file_exists_and_every_module_is_named():
    named: set[str] = set()
    missing_files: list[str] = []
    for c in cards():
        for rel in package_paths(files_field(c)):
            named.add(rel)
            if not list(PACKAGE.glob(rel)):
                missing_files.append(f"{rel}  (card: {c.get('Description', '')[:50]!r})")
    modules = sorted(str(p.relative_to(PACKAGE)) for p in PACKAGE.rglob("*.py") if p.name != "__init__.py")
    unnamed = [m for m in modules if not any(Path(m).match(n) or m == n for n in named)]
    problems = []
    if missing_files:
        problems.append("Files: paths in the diagram that do not exist in amoeba/:\n  " + "\n  ".join(missing_files))
    if unnamed:
        problems.append("modules under amoeba/ that no card names in Files: (add them to the box's data-card):\n  "
                        + "\n  ".join(unnamed))
    assert not problems, "\n\n".join(problems)
