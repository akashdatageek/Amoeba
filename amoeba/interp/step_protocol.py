"""D136 — step protocol v2: a helper's turn in native tool-calling mode with nothing the model must write as text
sections.

The legacy step protocol (verbatim AutoAgents, D31) asks the model to write `## Thought / ## CurrentStep / ## Action /
## ActionInput`. Claude refuses a prompt that asks for written-out reasoning (`reasoning_extraction`, D134), and
answers a text tool protocol with an empty content_filter reply (D132). In v2 (`--protocol v2`, only with native tool
calling):

- the step prompts are `plan_step_v2.txt`, `plan_resolve_v2.txt`, `plan_verify_own_v2.txt` (ours, DEVIATION D136);
  the notes plain code adds to a prompt are translated by `v2_text`. No prompt names Action, ActionInput, a "Final
  Output" section, "## Thought" or any ## heading the model must write (`banned_words`, checked by a test);
- each tool takes typed arguments (`TYPED`; a pool tool its MCP input schema; anything else one `input` string). Plain
  code checks the arguments (`check_args`): a bad call is not run, and its result names the schema and gives an
  example;
- the step ends with `Final_Output` and typed fields (`FinalOutput`; the resolver: `ResolverOutput`). Plain code
  renders them into the same text markers the legacy parsers read (`final_text`, `resolver_text`), so the stuck watch
  (Box 4), the verify-step reader and settle() work unchanged. A reply with text and no call is still read as the
  step output, markers included (the fallback).
LLM proposes (the call and its fields), plain code disposes (checks, runs, records).
"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

FINAL = "Final Output"          # the tool's real name in the plan runner (FINAL_OUTPUT); its function name is Final_Output
PRINT = "Print"
FIND_TOOL = "find_tool"


# box: plan_step
class FinalOutput(BaseModel):
    """The typed end of a step (v2). status is the helper's own word; plain code still decides the step's status
    from its checks."""
    status: Literal["done", "partial", "blocked"]
    output: str = Field(description="the whole step output, in the form the step's output line asks for; only this "
                                    "text is passed on to later steps")
    blocked: list[str] = Field(default_factory=list, description="one item per capability you lacked: "
                                                                 "'<capability> — <what could not be done>'")
    missing_data: list[str] = Field(default_factory=list, description="one item per fact or figure you could not "
                                                                      "find: '<what> — <where you looked>'")
    missing_input: list[str] = Field(default_factory=list, description="one item per input a step you depend on "
                                                                       "did not deliver: '<what> — <which step>'")
    not_needed: list[str] = Field(default_factory=list, description="one item per tool you were given and did not "
                                                                    "need: '<name> — <why>'")
    verdict: Literal["PASS", "FAIL"] | None = Field(default=None, description="verify steps only: PASS or FAIL")
    issues: list[str] = Field(default_factory=list, description="verify steps only: one issue per item (which step, "
                                                                "what is wrong, how to fix it)")


# box: plan_step
class ResolverFigure(BaseModel):
    n: int = Field(description="the figure's number in the list of disputes")
    value: str = Field(description="the value the evidence supports, a number with its unit")
    evidence: str = Field(description="a short quote copied exactly from the source text with its [S#], or the "
                                      "command you ran and the line of its output that gives the value")
    verdict: Literal["WORKER", "CHECK", "NEITHER", "UNRESOLVED"]


# box: plan_step
class ResolverOutput(BaseModel):
    figures: list[ResolverFigure]


# tool → ({argument: description}, example, how plain code turns the arguments into the tool's input string)
TYPED: dict[str, tuple[dict[str, str], dict, object]] = {
    "web_search": ({"query": "the search words: one entity, one period, one data series"},
                   {"query": "EIA weekly retail diesel price Midwest"}, lambda a: a["query"]),
    "fetch_url": ({"url": "a url, or an [S#] from web_search"}, {"url": "https://www.eia.gov/petroleum/gasdiesel/"},
                  lambda a: a["url"]),
    "calc": ({"expr": "an arithmetic expression"}, {"expr": "(3.85 - 1.25) / 6.2"}, lambda a: a["expr"]),
    "local:Bash": ({"command": "a shell command; it runs from the workspace folder"},
                   {"command": "python3 make_chart.py"}, lambda a: a["command"]),
    "local:Read": ({"path": "a file path inside the workspace"}, {"path": "diesel_prices.csv"},
                   lambda a: json.dumps({"file_path": a["path"]})),
    "local:Write": ({"path": "a file path inside the workspace", "content": "the whole file content"},
                    {"path": "series_note.md", "content": "# Series\n..."},
                    lambda a: json.dumps({"file_path": a["path"], "content": a["content"]})),
    FIND_TOOL: ({"need": "a capability you need and do not hold, in plain words"},
                {"need": "convert a docx file to pdf"}, lambda a: a["need"]),
    PRINT: ({"note": "a note for your teammates in this step"}, {"note": "series chosen: EMD_EPD2D_PTE_R20_DPG"},
            lambda a: a["note"]),
}
EMPTY_OK = {("local:Write", "content")}        # an empty file is a real request


# box: plan_step
def tool_schema(tool: str, mcp_schema: dict | None = None, final_kind: str | None = None) -> dict:
    """The JSON schema of a tool's arguments in v2: the typed table, a pool tool's MCP input schema, the typed end
    of the step, else one `input` string."""
    if tool == FINAL:
        from amoeba.llm.anthropic_client import claude_schema
        return claude_schema(ResolverOutput if final_kind == "resolve" else FinalOutput)
    if tool in TYPED:
        props = TYPED[tool][0]
        return {"type": "object", "properties": {k: {"type": "string", "description": d} for k, d in props.items()},
                "required": list(props), "additionalProperties": False}
    if mcp_schema and (mcp_schema.get("properties") or {}):
        return mcp_schema
    return {"type": "object", "properties": {"input": {"type": "string"}}, "required": ["input"],
            "additionalProperties": False}


# box: plan_step
def example(tool: str, schema: dict) -> dict:
    if tool in TYPED:
        return TYPED[tool][1]
    if tool == FINAL:
        return {"status": "done", "output": "<the whole step output>", "blocked": [], "missing_data": []}
    props = schema.get("properties") or {}
    return {k: f"<{(v or {}).get('type', 'value')}>" for k, v in props.items() if k in (schema.get("required") or props)}


TYPES = {"string": str, "number": (int, float), "integer": int, "boolean": bool, "object": dict, "array": list}


# box: plan_step
def check_args(tool: str, args, schema: dict, final_kind: str | None = None) -> str | None:
    """Plain code's check of one call's arguments: None when they fit the schema, else what is wrong. The typed end
    of the step is validated by its pydantic model."""
    if not isinstance(args, dict):
        return "arguments that are not a JSON object"
    if tool == FINAL:
        try:
            (ResolverOutput if final_kind == "resolve" else FinalOutput).model_validate(args)
        except ValidationError as e:
            return "fields that do not fit: " + "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}"
                                                          for x in e.errors()[:4])
        return None
    props, required = schema.get("properties") or {}, schema.get("required") or []
    missing = [k for k in required if k not in args or (args[k] in ("", None) and (tool, k) not in EMPTY_OK)]
    if missing:
        return f"no {', '.join(missing)}"
    if schema.get("additionalProperties") is False:
        extra = [k for k in args if k not in props]
        if extra:
            return f"unknown argument(s) {', '.join(extra)}"
    wrong = [k for k, v in args.items() if k in props and (props[k] or {}).get("type") in TYPES
             and not isinstance(v, TYPES[props[k]["type"]])]
    if wrong:
        return "the wrong type for " + ", ".join(f"{k} (wants {props[k]['type']})" for k in wrong)
    return None


# box: plan_step
def bad_call_text(tool: str, problem: str, schema: dict) -> str:
    """The tool result of a call whose arguments do not fit: what it takes and an example (worded like D131's
    repeated-error hint). The tool is not run."""
    props = schema.get("properties") or {}
    takes = ", ".join(f"{k} ({(v or {}).get('type', 'value')}{', required' if k in (schema.get('required') or []) else ''})"
                      for k, v in props.items()) or "no arguments"
    return (f"error: {tool} was called with {problem}; it was not run. {tool} takes: {takes}. For example: "
            f"{json.dumps(example(tool, schema), ensure_ascii=False)}. Change the input, or use another tool you have.")


# box: plan_step
def typed_input(tool: str, args: dict, schema: dict) -> str:
    """The input string the tool's runner takes, from checked arguments."""
    if tool in TYPED:
        return TYPED[tool][2](args)
    if set(args) == {"input"}:
        v = args["input"]
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return json.dumps(args, ensure_ascii=False)


# box: plan_step
def final_text(args: dict) -> str:
    """The typed end of a step as the text the legacy readers parse: Verdict first, the output, one BLOCKED / NOT
    NEEDED / MISSING DATA / MISSING INPUT line per item, the Issues last."""
    fo = FinalOutput.model_validate(args)
    lines = [f"Verdict: {fo.verdict}"] if fo.verdict else []
    lines.append(fo.output.strip())
    lines += [f"BLOCKED: {x.strip()}" for x in fo.blocked if x.strip()]
    lines += [f"NOT NEEDED: {x.strip()}" for x in fo.not_needed if x.strip()]
    lines += [f"MISSING DATA: {x.strip()}" for x in fo.missing_data if x.strip()]
    lines += [f"MISSING INPUT: {x.strip()}" for x in fo.missing_input if x.strip()]
    if fo.verdict:
        lines.append("Issues:" + ("" if fo.issues else " none"))
        lines += [f"{i}. {x.strip()}" for i, x in enumerate(fo.issues, 1)]
    return "\n".join(x for x in lines if x)


# box: plan_step
def typed_verdict(args: dict) -> tuple[str | None, str]:
    """(verdict, issues) of a typed end of a verify step, as parse_verdict_block returns them."""
    fo = FinalOutput.model_validate(args)
    return fo.verdict, "\n".join(f"{i}. {x.strip()}" for i, x in enumerate(fo.issues, 1)) if fo.issues else \
        ("none" if fo.verdict else "")


# box: plan_step
def resolver_text(args: dict) -> str:
    """The resolver's typed figures as the blocks parse_resolution reads (settle() unchanged)."""
    ro = ResolverOutput.model_validate(args)
    return "\n\n".join(f"Figure {f.n}\nValue: {f.value}\nEvidence: {f.evidence}\nVerdict: {f.verdict}"
                       for f in ro.figures)


# ---- the prompt words v2 must not use -------------------------------------------------------------------------------
# A heading the model must write shows up as a protocol heading, a quoted heading or a # Format section; the ## headings
# of the data a prompt shows (an input step's output, a disputed figure) are not instructions and are not banned.
BANNED = [(r"\bActionInput\b", "ActionInput"), (r"\bAction\b", "Action"), (r"Final Output", "a 'Final Output' section"),
          (r"#+\s*Thought\b", "## Thought"), (r"\bCurrentStep\b", "CurrentStep"),
          (r"[\"'“]\s*##", "a quoted ## heading to write"), (r"(?m)^#+\s*Format\s*$", "a # Format section"),
          (r"(?i)must use exactly these sections", "a list of sections to write")]


# box: plan_step
def banned_words(text: str) -> list[str]:
    """What a native-mode (v2) prompt still says of the text protocol (empty when clean)."""
    return [name for pattern, name in BANNED if re.search(pattern, text or "")]


# the notes plain code adds to a step prompt, worded for v2 (exact legacy text → v2 text; regexes after)
V2_REPLACEMENTS = [
    ('Your Final Output MUST start with a line "Verdict: PASS" or "Verdict: FAIL", then a line "Issues:" and one '
     'numbered\nissue per line (which step, what is wrong, how to fix it). Answer FAIL if any issue would change a '
     'number or a\nconclusion; PASS otherwise (then write "Issues: none").',
     "Set Final_Output's verdict to PASS or FAIL and list each issue in its issues (which step, what is wrong, how to "
     "fix it).\nAnswer FAIL if any issue would change a number or a conclusion; PASS otherwise (issues empty)."),
    ("No more tool calls: choose Final Output and write your conclusion", "No more tool calls: call Final_Output with "
                                                                         "your conclusion"),
    ('put a line "MISSING INPUT: <what> — <which step should have given it>" in your Final Output.',
     "add \"<what> — <which step should have given it>\" to Final_Output's missing_input."),
    ('either use it (call the tool) or put a line "BLOCKED: <name> — <what could not be done without it>" or "NOT '
     'NEEDED: <name> — <why this step does not need it>" in your Final Output.',
     "either use it (call the tool) or add \"<name> — <what could not be done without it>\" to Final_Output's blocked "
     "or \"<name> — <why this step does not need it>\" to its not_needed."),
    ('Write "NOT NEEDED: {cap} — worked around: <how>"', "Add \"{cap} — worked around: <how>\" to Final_Output's "
                                                         "not_needed"),
    ("writing BLOCKED for", "listing as blocked"),
    ('end with a section "## Limitations" that lists them', "end with a markdown section headed Limitations that "
                                                            "lists them"),
    ('When the answer is complete, choose "Final Output" and put the whole final answer in ActionInput.',
     "When the answer is complete, call Final_Output with the whole final answer as its output."),
]
V2_PATTERNS = [
    (r"Call it with Action (\S+) and ActionInput", r"Call the tool \1 with the input"),
    (r"\bActionInput\s*:", "Input:"),
    (r"answer BLOCKED: ([^\n]+)", r"list \1 in Final_Output's blocked"),
    (r"\bas Final Output\b", "with Final_Output"),
    (r"\bin your Final Output\b", "in Final_Output's fields"),
    (r"\bchoose (?:the )?\"?Final Output\"?", "call Final_Output"),
    (r"\bFinal Output\b", "Final_Output"),
]


# box: plan_step
def v2_text(text: str) -> str:
    """A rendered step prompt with the legacy notes worded for v2 (plain text replacements; the v2 templates
    themselves need none)."""
    for old, new in V2_REPLACEMENTS:
        text = text.replace(old, new)
    for pattern, new in V2_PATTERNS:
        text = re.sub(pattern, new, text)
    return text


HOW_TO_ACT = "\n# How to act\n"     # the v2 templates' last section; plain code's notes go right above it
# for a step prompt without a v2 file (the summariser's plan_summarise.txt): its # Format section is replaced by this
HOW_TO_ACT_TEXT = ("# How to act\nCall one tool per turn through tool calling, with the arguments its definition names; "
                   "its result comes back to you next turn. When the output is complete, call Final_Output: status "
                   "(done, partial or blocked) and output (the whole output).")
UNREADABLE_NOTE_V2 = ("error: your last reply could not be read ({why}). Call one of your tools, or Final_Output with "
                      "the step's output.")
PROVIDER_BLOCKED_NOTE_V2 = ("error: the model service returned no reply for your last turn. Continue the step from where "
                            "it stands: call one of your tools, or Final_Output with the step's output.")
