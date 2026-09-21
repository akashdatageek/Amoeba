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


def parse_sections(text: str) -> dict[str, str]:
    """AutoAgents OutputParser.parse_blocks + parse_code (system/utils/common.py:31-59)."""
    out: dict[str, str] = {}
    for block in text.split("##"):                                  # common.py:33
        if not block.strip():
            continue
        if "\n" in block:
            title, body = block.split("\n", 1)                      # common.py:43
        else:
            title, body = block, ""   # DEVIATION: a title-only block raises ValueError in the original
        if title.endswith(":"):                                     # common.py:45-46 (checked before .strip())
            title = title[:-1]
        body = body.strip()
        m = re.search(r"```.*?\s+(.*?)```", body, re.DOTALL)        # common.py:53 — first fenced block, tag dropped
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
