"""Deterministic parsers — regexes copied from the source code (spec §5.1). Departures are marked DEVIATION."""
from __future__ import annotations

import json
import re


class ParseError(ValueError):
    pass


class MissingSections(ParseError):
    def __init__(self, missing: list[str], found: list[str]):
        super().__init__(f"missing sections {missing}; found {found}")
        self.missing, self.found = missing, found


def parse_sections(text: str, all_fences: bool = False) -> dict[str, str]:
    """AutoAgents OutputParser.parse_blocks + parse_code (system/utils/common.py:31-59).
    all_fences: DEVIATION D26 — join every fenced block of a section, in order, instead of keeping only the first
    (a model that puts each role in its own ```json block otherwise loses roles 2..n)."""
    out: dict[str, str] = {}
    for block in text.split("##"):                                  # common.py:33
        if not block.strip() or re.fullmatch(r"\s*-{3,}\s*", block):
            continue   # DEVIATION D23: a bare '---' fence (copied from the FORMAT_EXAMPLE) is not a section
        if "\n" in block:
            title, body = block.split("\n", 1)                      # common.py:43
        else:
            title, body = block, ""   # DEVIATION: a title-only block raises ValueError in the original
        if title.endswith(":"):                                     # common.py:45-46 (checked before .strip())
            title = title[:-1]
        body = re.sub(r"(?:\n\s*-{3,}\s*)+$", "", body.strip())   # DEVIATION D23: drop a closing '---' fence
        if all_fences:
            blocks = re.findall(r"```.*?\s+(.*?)```", body, re.DOTALL)   # D26: every fenced block, tags dropped
            if blocks:
                body = "\n".join(blocks)
        else:
            m = re.search(r"```.*?\s+(.*?)```", body, re.DOTALL)    # common.py:53 — first fenced block, tag dropped
            if m:
                body = m.group(1)
        out[title.strip()] = body
    return out


def require(sections: dict[str, str], keys: list[str]) -> dict[str, str]:
    """Missing key → MissingSections; the caller makes one LLM repair call (action.py:69-75) then gives up."""
    missing = [k for k in keys if k not in sections]
    if missing:
        raise MissingSections(missing, list(sections))
    return sections


def parse_role_blobs(text: str) -> list[dict]:
    """environment._parser_roles (environment.py:60-73)."""
    roles: list[dict] = []
    for blob in re.findall(r"{[\s\S]*?}", text):                    # environment.py:62 — non-greedy; nested {} truncates
        try:
            d = json.loads(blob.strip())                            # environment.py:65 — uncaught in the original
        except json.JSONDecodeError:
            continue  # DEVIATION: skip bad blobs (FORMAT_EXAMPLE's trailing comma would crash the original)
        if isinstance(d, dict) and d:                               # environment.py:66-67
            roles.append(d)
    return roles
# DEVIATION: we run it on sections["Created Roles List"] (+ "Selected Roles List"); the original scans the whole
# planner output, so blobs from "Thought" get included too.


def parse_plan(text: str) -> list[tuple[list[str], str]]:
    """environment._parser_plan (environment.py:75-84) + our bracket parser."""
    steps = [v.split("\n")[0] for v in re.split(r"\n\d+\. ", "\n" + text)[1:]]   # environment.py:78
    # original: re.findall(r'## Execution Plan([\s\S]*?)##', raw)[0] then steps.insert(0, '') sentinel (:77, :83)
    # DEVIATION: we take the parsed section (no trailing-## dependence) and drop the '' sentinel
    out: list[tuple[list[str], str]] = []
    for s in steps:
        m = re.match(r"\s*\[(.*?)\]\s*:\s*(.*)", s)                  # DEVIATION: explicit "[A, B]: text" parser
        names = [n.strip() for n in m.group(1).split(",")] if m else []
        out.append((names, s))
    return out
# The original never parses the bracket: at run time it matches roster names by SUBSTRING, case-sensitive,
# against the text before the first ':' (group.py:61-64), so "Analyst" matches "[Data Analyst]". draft_team
# resolves names exactly, then falls back to the substring rule if exact fails.


def parse_json_objects(text: str) -> list[dict]:
    """Every top-level JSON object in `text`, found by brace balance (strings respected), so a request whose
    example is itself an object survives. Ours, not AutoAgents': role blobs keep the original regex."""
    out: list[dict] = []
    depth, start, in_str, esc = 0, -1, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"' and depth > 0:
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                try:
                    d = json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    d = None   # skip, as with role blobs
                if isinstance(d, dict) and d:
                    out.append(d)
    return out


STEP_FIELDS = ("kind", "covers", "depends_on", "do", "output", "done_when")


def parse_plan_d24(text: str) -> list[tuple[list[str], str, dict]]:
    """D24 plan: like parse_plan (same step split, same '[A, B]: title' first line, so name matching is unchanged)
    but the indented 'covers / depends_on / do / output / done_when' lines under each step are kept.
    Returns (names, first line, fields); a field's continuation lines are joined to it."""
    out: list[tuple[list[str], str, dict]] = []
    for block in re.split(r"\n\d+\. ", "\n" + text)[1:]:
        first, *rest = block.split("\n")
        m = re.match(r"\s*\[(.*?)\]\s*:\s*(.*)", first)
        names = [n.strip() for n in m.group(1).split(",")] if m else []
        fields: dict = {"title": (m.group(2) if m else first).strip()}
        key = None
        for line in rest:
            f = re.match(r"^\s*[-*]?\s*(kind|covers|depends_on|do|output|done_when)\s*:\s*(.*)$", line, re.I)
            if f:
                key = f.group(1).lower()
                fields[key] = f.group(2).strip()
            elif key and line.strip():
                fields[key] += "\n" + line.strip()
        fields["covers"] = re.findall(r"R\d+", fields.get("covers", ""))
        kind = fields.get("kind", "").strip().lower()                      # D37: work | verify; "" = not written
        fields["kind"] = "verify" if kind.startswith("verif") else "work" if kind.startswith("work") else ""
        dep = fields.get("depends_on", "")
        fields["depends_on"] = [] if re.match(r"\s*(none|-|n/a)?\s*$", dep, re.I) else [int(x) for x in re.findall(r"\d+", dep)]
        out.append((names, first, fields))
    return out


def parse_requirements(text: str) -> dict[str, str]:
    """D24 '## Requirements': lines 'R1: ...' (a leading '-' and ':', '.', ')' or '-' after the id are accepted)."""
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        m = re.match(r"^\s*[-*]?\s*\**(R\d+)\**\s*[:.)\-–]\s*(.+)$", line)
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(2).strip()
    return out


def parse_bullets(text: str) -> list[str]:
    """D24 givens / risks: one item per non-empty line, leading '- ' removed; 'None' and '...' dropped."""
    items = [re.sub(r"^\s*[-*]\s*", "", line).strip() for line in (text or "").splitlines()]
    return [x for x in items if x and x.lower() not in ("none", "none.", "...")]


def parse_verdict(sections: dict[str, str]) -> str | None:
    """D24 '## Verdict': "APPROVE" or "REVISE" when that is the whole answer (markdown emphasis and a final full stop
    are ignored); "OTHER" for anything else; None when the section is missing."""
    if "Verdict" not in sections:
        return None
    word = re.sub(r"[*_`]", "", sections["Verdict"]).strip().rstrip(".").strip()
    return word if word in ("APPROVE", "REVISE") else "OTHER"


CRITIC_DEFAULT = "I think it is not correct. Please think carefully and improve it."


def parse_critic(text: str) -> tuple[bool, str]:
    """AgentVerse 'critic' parser = CommonParser3 (output_parser/output_parser.py:541-561) → (is_agree, criticism)."""
    text = re.sub(r"\n+", "\n", text.strip())                       # :544
    first = text.split("\n")[0]                                     # :545
    if not first.startswith("Action:"):                             # :546-547
        raise ParseError(text)
    if first.strip(". ") == "Action: Agree":                        # :548-549 exact, case-sensitive
        return True, ""
    if first.strip(". ") == "Action: Disagree":                     # :550
        m = re.findall(r"Action Input: ([\S\n ]+)", text)           # :551 — to end of text
        return False, (m[0].strip() if m else CRITIC_DEFAULT)      # :552-557
    raise ParseError(text)                                          # :560-561


def repair_prompt(user: str, raw: str, keys: list[str], error: str) -> str:
    """The one repair round AutoAgents makes when a required section is missing (action.py:69-75)."""
    wanted = "\n".join(f"## {k}" for k in keys)
    return (f"{user}\n\n# Error\nYour previous answer could not be parsed: {error}.\n"
            f"Rewrite the FULL answer so that it contains every one of these sections, each written as "
            f"'## <SECTION_NAME>' on its own line:\n{wanted}\n\n# Previous answer\n{raw}")
