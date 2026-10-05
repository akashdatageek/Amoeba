"""D110 — every web-sourced figure in the final answer carries its source's date.

A figure is web-sourced when its line cites a search or fetched-page source ([S#] of the web tools). It carries a date
when its line states one (a year, a month and year, a quarter, an ISO date, "as of …", a fiscal year), or when every
source it cites has a dated entry in the answer's sources list ("[S3] … (published 2025)"). The answer step gets one
refine turn for the undated ones; those still undated are listed in the Limitations section by plain code.
"""
from __future__ import annotations

import re

from amoeba.interp.provenance import IDS, LIST_MARKER, NUM, TAG

MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATE = re.compile(rf"\b(?:19|20)\d{{2}}\b|\b{MONTHS}\s+\d{{1,2}},?\s+\d{{4}}|\b{MONTHS}\s+\d{{4}}|\bq[1-4]\s*(?:19|20)\d{{2}}"
                  r"|\b\d{4}-\d{2}-\d{2}\b|\bas of\b|\b(?:fy|cy)\s?'?\d{2,4}\b", re.I)
CITE = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")
SECTION = re.compile(r"^\s*#+\s*(sources|references|citations|bibliography)\b", re.I)
LIMITS = re.compile(r"^\s*#+\s*limitations\b", re.I)


def _figures(line: str) -> list[str]:
    body = IDS.sub(" ", TAG.sub(" ", LIST_MARKER.sub("", line)))
    out = []
    for m in NUM.finditer(body):
        tok = m.group(0)
        bare = tok.strip("$€£%").replace(",", "")
        if tok == bare and re.fullmatch(r"(?:19|20)\d{2}", bare):
            continue                                   # a year is a date, not a figure
        out.append(tok)
    return out


# box: step_check
def undated_figures(text: str, web_ids: set[str]) -> list[dict]:
    """The web-sourced figures of an answer without a date: {figure, sources, line}."""
    dated_sources, body, section = set(), [], None
    for line in (text or "").splitlines():
        if SECTION.match(line):
            section = "sources"
            continue
        if LIMITS.match(line):
            section = "limits"
            continue
        if re.match(r"^\s*#+\s", line):
            section = None
        if section == "sources":
            m = re.match(r"^\s*(?:[-*]\s*)?\[?(S\d+)\]?", line)
            if m and DATE.search(line):
                dated_sources.add(m.group(1))
        elif section is None:
            body.append(line)
    out = []
    for line in body:
        ids = [i.strip() for m in CITE.finditer(line) for i in m.group(1).split(",")]
        web = [i for i in ids if i in web_ids]
        figs = _figures(line)
        if not web or not figs or DATE.search(TAG.sub(" ", line)):
            continue
        if all(i in dated_sources for i in web):
            continue
        out.append({"figure": figs[0], "sources": web, "line": line.strip()[:200]})
    return out


# box: step_check
def dated_finding(undated: list[dict]) -> str:
    return ("these figures come from web sources but carry no date: " + "; ".join(
        f"{u['figure']} [{', '.join(u['sources'])}]" for u in undated[:10]) + ". Write each source's date (its "
        "publication date, or the period its data covers) next to the figure or in the source's entry under Sources; "
        "if a source gives no date, say so.")
