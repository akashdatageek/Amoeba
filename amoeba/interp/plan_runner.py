"""BOX 3 — the `plan` topology (D31): carry out a d24 plan over its depends_on graph.

`run_flat` (AutoAgents) walks the steps in list order and hands every helper the whole history; this runner builds
a graph from `depends_on`, runs the steps in topological waves, and gives each step only the task, its own step
detail and the artifacts of the steps it depends on. Each step's result is an artifact (runs/<id>/artifacts/
step_<n>.md plus step_<n>.json metadata). Plain code owns the graph, the order, the turn cap and what each step sees.
"""
from __future__ import annotations

import json
import re
from uuid import uuid4
from dataclasses import asdict, dataclass
from pathlib import Path

from amoeba.capabilities import normalise
from amoeba.config.prompts import PROMPT, render
from amoeba.config.schema import AgentSpec, PlanStep, TeamConfig
from amoeba.interp.provenance import (check_provenance, claim_numbers, computed_values, numbers_in,
                                      strip_unverified)
from amoeba.interp.shorten import shorten
from amoeba.llm.profiles import role_group
from amoeba.pool.stock import pool_skill_notes, pool_tool_notes
from amoeba.localtools.claims import claimed_files
from amoeba.interp.runtime import BLOCKED, FINAL_OUTPUT, PRINT, UNAVAILABLE, _output_text
from amoeba.task.models import CapabilityRequest, DraftedRole, Episode, Task
from amoeba.task.parsers import MissingSections, parse_json_objects, parse_plan_d24, parse_sections
from amoeba.task.quality import VERIFY_WORDS
from amoeba.tools.web import WEB_TOOLS

PLAN_SECTIONS = ["CurrentStep", "Action", "ActionInput"]   # Thought is asked for but not required
PLAN_MAX_TOKENS = 8192                                     # per helper call (D27 room; flat keeps the client default)


@dataclass
class PlanOptions:
    """Settings of one plan run (run_task flags); every value is recorded in the `plan_graph` trace event."""

    rerun_stale: bool = False        # D39: re-run once the steps that used a step's output before it was reworked
    check_retry_turns: int = 2       # D42: turns a failed-check retry gets on top of the ones already used
    max_input_chars: int = 6000      # D44: characters of one input artifact a step is shown
    max_summary_input_chars: int = 30000   # D44: characters of all step outputs the summariser is shown
    # D50: off = only a failed format/input check earns a refine turn (the D42 retry); on-issues = also untagged
    # figures or citations of unseen sources; always = also a self-review turn when nothing was found. The CLI
    # default is on-issues; this library default keeps the earlier behaviour for callers that set nothing.
    self_refine: str = "off"
    # D51: how the roles of a multi-role step work together — concat: each writes and the outputs are joined (the
    # earlier behaviour, kept for the ablation); critique: the first role drafts, the others review, it revises.
    # The CLI default is critique; this library default keeps the earlier behaviour.
    collab: str = "concat"
    collab_rounds: int = 2           # D51: review rounds at most
    # D61: on = the step contract — before a step plain code lists what each helper must account for (capabilities
    # it asked for and lacks, tools and skills attached to it), after the step it checks the evidence (tool calls,
    # BLOCKED / NOT NEEDED lines, files, sources) and sets the outcome; also the verifier's evidence, the answer's
    # produced-work check and rework by cause. The CLI default is on; this library default keeps the earlier
    # behaviour for callers that set nothing.
    contract: str = "off"
    # D63: on = the Action Observer — after each wave plain code looks for a trigger (a step that lacked a
    # capability, a verify step still failing, a missing upstream input, a tool the plan did not know about); on one,
    # a single planner call proposes one typed decision for the steps that have not run, and plain code validates
    # it before anything changes. The CLI default is off.
    replan: str = "off"
    max_replans: int = 2             # D63: observer calls per run
    max_added_steps: int = 3         # D63: steps added per run, over all accepted decisions


class PlanGraphError(ValueError):
    """The plan's depends_on graph is unusable: an unknown step or a cycle. Raised before any LLM call."""


def number(step: PlanStep) -> int:
    """A step's number as the planner wrote it (depends_on uses these numbers)."""
    return step.index + 1


# box: plan_graph
def dependencies(plan: list[PlanStep]) -> dict[int, list[int]]:
    """step number -> the step numbers it depends on. A plan with no depends_on at all (a d19 draft) is a chain."""
    if not any(s.depends_on for s in plan):
        nums = [number(s) for s in plan]
        return {n: ([nums[i - 1]] if i else []) for i, n in enumerate(nums)}
    return {number(s): list(dict.fromkeys(s.depends_on)) for s in plan}


# box: plan_graph
def waves(plan: list[PlanStep]) -> list[list[int]]:
    """Topological waves: each wave holds the steps whose dependencies are all in earlier waves (Kahn's
    algorithm, steps in plan order within a wave). Unknown step numbers and cycles raise PlanGraphError."""
    deps = dependencies(plan)
    known = set(deps)
    for n, ds in deps.items():
        bad = [d for d in ds if d not in known]
        if bad:
            raise PlanGraphError(f"step {n} depends on unknown step(s) {bad}")
    done: set[int] = set()
    out: list[list[int]] = []
    while len(done) < len(deps):
        ready = [n for n in deps if n not in done and all(d in done for d in deps[n])]
        if not ready:
            raise PlanGraphError(f"cycle among steps {sorted(set(deps) - done)}")
        out.append(ready)
        done.update(ready)
    return out


# box: plan_graph
def relink(plan: list[PlanStep], written: dict[int, list[int]]) -> tuple[list[PlanStep], list[dict]]:
    """Box 2 drops a step that names no known role but keeps the others' numbers, so depends_on can point at a
    dropped step. Such a dependency is replaced by the dropped step's own dependencies (as the planner wrote
    them, recursively). A number the planner never wrote is left in place, so waves() rejects it."""
    kept = {number(s) for s in plan}
    events, out = [], []
    for s in plan:
        new: list[int] = []
        for d in s.depends_on:
            if d in kept or d not in written:
                new.append(d)
                continue
            seen, todo, repl = set(), [d], []
            while todo:
                x = todo.pop(0)
                if x in seen:
                    continue
                seen.add(x)
                if x in kept:
                    repl.append(x)
                elif x in written:
                    todo.extend(written[x])
            new.extend(repl)
            events.append({"amoeba.step": number(s), "amoeba.missing_step": d, "amoeba.replaced_by": repl})
        out.append(s.model_copy(update={"depends_on": list(dict.fromkeys(new))}))
    return out, events


# box: plan_step
def plan_card(agent: AgentSpec) -> str:
    """The role card a plan step's helper sees: the D24 role record, prompt last."""
    lines = [f"Name: {agent.name}",
             f"Goal: {agent.goal}" if agent.goal else "",
             f"Skills: {'; '.join(agent.skills)}" if agent.skills else "",
             f"Constraints: {'; '.join(agent.constraints)}" if agent.constraints else "",
             f"Outputs: {'; '.join(_output_text(o) for o in agent.outputs)}" if agent.outputs else "",
             f"Success criteria: {'; '.join(agent.success_criteria)}" if agent.success_criteria else "",
             f"Instructions: {agent.role_prompt}" if agent.role_prompt else "",
             f"Suggestions: {agent.suggestions}" if agent.suggestions else "",
             *pool_skill_notes(agent)]   # D56: skills from the pool, as data
    return "\n".join(x for x in lines if x)


# box: plan_step
def step_detail(step: PlanStep) -> str:
    extra = [f"{k}: {getattr(step, k)}" for k in ("do", "output", "done_when") if getattr(step, k)]
    return "\n".join([step.text, *extra])


# box: plan_step
def full_action_input(raw: str, parsed: str) -> str:
    """ActionInput is the last section, so it runs to the end of the reply. The AutoAgents parser splits on every
    '##', which cuts a markdown answer at its first '##'/'###' heading (the flat baseline loses its answers
    this way); the plan runner keeps the whole text."""
    head = raw.rfind("## ActionInput")
    if head < 0:
        return parsed
    rest = raw[head + len("## ActionInput"):].lstrip(":").strip()
    rest = re.sub(r"\n-{3,}\s*$", "", rest).strip()        # a closing '---' fence of the format example
    return rest if len(rest) >= len(parsed.strip()) else parsed


VERIFY_NOTE = """

You are VERIFYING the outputs of the steps you depend on: re-check their numbers, sources and test results.
Your Final Output MUST start with a line "Verdict: PASS" or "Verdict: FAIL", then a line "Issues:" and one numbered
issue per line (which step, what is wrong, how to fix it). Answer FAIL if any issue would change a number or a
conclusion; PASS otherwise (then write "Issues: none")."""
VERIFY_TOOLS_NOTE = """
Re-check with your tools, do not only read: re-run the code a step wrote or open the file it made (local tools), and
re-check at least one cited figure against its source (fetch_url or web_search) or recompute it (calc). Your inputs end
with the raw tool results the earlier steps used. Name in your output each re-check you ran and what it showed. A PASS
with no re-check counts as an unverified check."""
REWORK_NOTE = """

REWORK: verification step {by} found issues with this step's earlier output. Fix them and give the whole corrected
output as Final Output.
Issues found:
{issues}

Your earlier output:
{previous}"""
REVERIFY_NOTE = """

RE-CHECK: after your earlier FAIL, step(s) {steps} were reworked. Check their new outputs (in your inputs) against the
issues you raised and give a new verdict.
Your earlier issues:
{issues}"""
RETRY_NOTE = ("Plain code checked this step's output and it failed: {failed}. Fix that and give the whole step "
              "output again as Final Output.\n")


REVISION_NOTE = ("Your teammates reviewed your draft and asked for changes:\n{issues}\nRevise the draft to address "
                 "them and give the whole step output again as Final Output.\n")
REFINE_NOTE = ("Plain code checked this step's output and found:\n{findings}\nFix exactly these and give the whole step "
               "output again as Final Output.\n")
SELF_REVIEW_NOTE = ("Before this step is passed on, review your output against the step's done_when ({done_when}) and "
                    "your success criteria ({criteria}). Fix anything that falls short and give the whole step output "
                    "again as Final Output (the same output if nothing needs changing).\n")


def refine_findings(checks: list[dict], prov: dict) -> tuple[list[str], list[str]]:
    """D50: what plain code found in a step's output, as lines for the helper: failed checks, then provenance."""
    check_items = [c["detail"] for c in checks if not c["pass"]]
    prov_items = []
    if prov.get("untagged"):
        prov_items.append(f"{prov['untagged']} figure(s) carry no [S#] or [unverified] tag: "
                          f"{', '.join(prov.get('untagged_examples', [])[:10])}. Tag each: [S#] for a tool result you "
                          f"have, [unverified] for your own knowledge, or show the calculation.")
    if prov.get("given_with_web_tag"):                                              # D66
        prov_items.append(f"these numbers are given in the task, not found in a web source: "
                          f"{', '.join(prov['given_with_web_tag'][:10])}. Write them without a source tag.")
    if prov.get("hallucinated_citations"):
        prov_items.append(f"these citations name sources you never saw: {', '.join(prov['hallucinated_citations'])}. "
                          f"Cite only [S#] ids from your tool results or your inputs, or mark the figure [unverified].")
    return check_items, prov_items


def refine_counts(checks: list[dict], prov: dict, contract: int | None = None) -> dict:
    out = {"failed_checks": sum(not c["pass"] for c in checks), "untagged": prov.get("untagged", 0),
           "hallucinated": len(prov.get("hallucinated_citations", []))}
    return out if contract is None else {**out, "contract": contract}   # D61: when the step contract is on


CONTRACT_LINE = ("Plain code checks this step's contract: {items}. For each one, either use it (call the tool) or put "
                 "a line \"BLOCKED: <name> — <what could not be done without it>\" or \"NOT NEEDED: <name> — <why this "
                 "step does not need it>\" in your Final Output. Never fill in from memory what it would have given.")
LOCAL_TOOLS = "local tools"


# box: step_check
def tool_ok(result: str) -> bool:
    """D61: a tool call that returned something usable — not an error line, a refusal or an error result."""
    return not re.match(r"\s*(?:error\b|refused:|\[local:\w+ error\]|\[S\d+\][^\n]*returned an error)", result or "", re.I)


# box: step_check
def not_needed_marks(text: str) -> list[str]:
    """D61: the names in 'NOT NEEDED: <name> — why' lines: a helper's reason for not using what it was given."""
    names = []
    for m in re.finditer(r"NOT\s+NEEDED\s*[:：]\s*`?((?:(?:pool|local|skill):)?[A-Za-z][\w ./+-]{0,60}?)`?\s*"
                         r"(?:[—–:;,(\n]|-\s|$)", text or "", re.I):
        name = m.group(1).strip(" .-")
        if name and name.lower() not in (x.lower() for x in names):
            names.append(name)
    return names


# box: step_check
def strip_not_needed(text: str) -> str:
    """D61: NOT NEEDED lines are for plain code (kept in the step's metadata), not for later steps or the answer."""
    return re.sub(r"(?im)^[ \t>*-]*NOT\s+NEEDED\s*[:：].*(?:\n|$)", "", text or "").strip()


# box: step_check
def cap_key(name: str) -> str:
    """A capability or tool name compared by its canonical form, without a pool:/local:/skill: prefix."""
    bare = re.sub(r"^(?:pool|local|skill)\s*:\s*", "", (name or "").strip(), flags=re.I)
    return re.sub(r"[\s-]+", "_", normalise(bare)[0].lower())


# box: step_check
def names_match(a: str, b: str) -> bool:
    ka, kb = cap_key(a), cap_key(b)
    return bool(ka and kb) and (ka == kb or (min(len(ka), len(kb)) >= 4 and (ka in kb or kb in ka)))


class _Work:
    """The state of one step's turn loop, kept across a retry."""

    def __init__(self, max_turns: int):
        self.max_turns, self.turn, self.completed = max_turns, 0, ""
        self.done: dict[str, str] = {}          # agent_id -> its Final Output text
        self.blocked: dict[str, str] = {}       # agent_id -> the capability it answered BLOCKED on
        self.partial: dict[str, str] = {}       # agent_id -> what it wrote alongside BLOCKED
        self.contributions: list[dict] = []
        self.tool_results: list[str] = []       # what the step's tools returned (D33: their numbers count as derived)
        self.calls: list[dict] = []             # D61: every tool call of the step: who, which tool, ok or not
        self.last_message = ""                  # D44: the last helper message, passed on when no Final Output came


NUMERIC_WORDS = re.compile(r"\b(cost|costs|estimate|estimates|price|prices|pricing|number|numbers|figure|figures|"
                           r"metric|metrics|latency|revenue|size|sizing|storage|volume|tb|gb|usd|eur|percent|rate|rates|"
                           r"tariff|tariffs|benchmark|benchmarks|p95|throughput)\b|%|\$", re.I)


MARKERS = {"table": "format_table", "list": "format_list", "code": "format_code", "memo": "format_headings"}


# box: step_check
def output_markers(output: str) -> list[str]:
    """D42: the format markers the planner put in a step's `output` line (table:, list:, code:, memo:)."""
    return list(dict.fromkeys(m.lower() for m in re.findall(r"\b(table|list|code|memo)\s*:", output or "", re.I)))


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def shares_words(a: str, b: str, n: int = 8) -> bool:
    """D42: `a` and `b` share a run of n consecutive words (case and punctuation ignored)."""
    wa, wb = _words(a), _words(b)
    grams = {tuple(wb[i:i + n]) for i in range(len(wb) - n + 1)}
    return any(tuple(wa[i:i + n]) in grams for i in range(len(wa) - n + 1))


# box: step_check
def uses_inputs(body: str, deps: list[int], artifacts: dict) -> bool:
    """D42: a real match with an input — a figure it contains (not a single digit), one of its source ids, a
    dependency's step number or role name, or 8+ consecutive shared words. A whole output under 8 words that
    appears verbatim in an input (a copied value) also counts."""
    ids = set().union(*(set(artifacts[d]["meta"]["visible_source_ids"]) for d in deps))
    roles = {r for d in deps for r in artifacts[d]["meta"]["roles"]}
    dep_text = "\n".join(artifacts[d]["text"] for d in deps)
    figures = {x for x in numbers_in(dep_text) if len(x.replace(".", "")) > 1}
    short = body.strip()
    return (any(re.search(rf"\bstep\s*{d}\b", body, re.I) for d in deps) or any(f"[{i}]" in body for i in ids)
            or any(r and r in body for r in roles) or bool(numbers_in(body) & figures)
            or shares_words(body, dep_text)
            or (bool(short) and len(_words(short)) < 8 and short in dep_text))


# box: step_check
def step_checks(step: PlanStep, text: str, deps: list[int], artifacts: dict, verifier: bool = False) -> list[dict]:
    """D34: deterministic checks of a step's output. D42: the format checks come from the markers the planner
    wrote in `output` (table:, list:, code:, memo:); only when there are none are keywords in `output` /
    `done_when` used (check_source "keywords"). Only checks that apply are listed; each is {name, pass, detail}."""
    spec = f"{step.output}\n{step.done_when}".lower()
    body = text or ""
    out = [{"name": "output_present", "pass": bool(body.strip()), "detail": "the step output is empty"}]
    markers = output_markers(step.output)
    if markers:
        out += [_format_check(MARKERS[m], body) for m in markers]
    else:
        out += _keyword_checks(spec, body)
    if deps:
        out.append({"name": "inputs_referenced", "pass": uses_inputs(body, deps, artifacts),
                    "detail": "the output uses nothing from the steps it depends on (no figure, source id, step or "
                              "role name, or 8 words in a row from them)"})
    if verifier:
        out.append({"name": "verdict", "pass": parse_verdict_block(body)[0] is not None,
                    "detail": 'a verification step must start with "Verdict: PASS" or "Verdict: FAIL"'})
    for c in out:
        c["source"] = "markers" if markers else "keywords"
    return out


FORMAT_DETAIL = {"format_table": "the output line asks for a table; there is no markdown table (| a | b | with a "
                                 "|---| row)",
                 "format_list": "the output line asks for a list; there are fewer than 2 list items",
                 "format_code": "the output line asks for code; there is no code block or statement",
                 "format_headings": "the output line asks for a document; it has fewer than 2 headings"}


def _format_check(name: str, body: str) -> dict:
    ok = {"format_table": lambda: bool(re.search(r"^\s*\|.*\|\s*$", body, re.M))
          and bool(re.search(r"^\s*\|?\s*:?-{3,}", body, re.M)),
          "format_list": lambda: len(re.findall(r"^\s*(?:[-*]|\d+[.)])\s+\S", body, re.M)) >= 2,
          "format_code": lambda: "```" in body or bool(re.search(r"\b(SELECT|CREATE TABLE|def |INSERT INTO)\b", body)),
          "format_headings": lambda: len(re.findall(r"^\s*#{1,4}\s+\S|^\s*\*\*[^*]+\*\*\s*$", body, re.M)) >= 2}[name]()
    return {"name": name, "pass": ok, "detail": FORMAT_DETAIL[name]}


def _keyword_checks(spec: str, body: str) -> list[dict]:
    """The D34 rules, kept as the fallback for output lines without markers."""
    out = []
    if "table" in spec:
        out.append(_format_check("format_table", body))
    if re.search(r"\b(list|bullets?|checklist)\b", spec):
        out.append(_format_check("format_list", body))
    if re.search(r"\b(code|script|sql|query|queries|schema|ddl)\b", spec):
        out.append(_format_check("format_code", body))
    if re.search(r"\b(memo|report|runbook|plan|document)\b", spec):
        out.append(_format_check("format_headings", body))
    if NUMERIC_WORDS.search(spec):
        ok = bool(re.search(r"\d", re.sub(r"\[S\d+\]", "", body)))
        out.append({"name": "numbers_present", "pass": ok, "detail": "the output line asks for figures; the output "
                                                                      "has no number"})
    return out


# box: step_check
def blocked_marks(text: str) -> list[str]:
    """D36: the capabilities named in 'BLOCKED: <capability> — ...' lines of a step's output."""
    names = []
    for m in re.finditer(r"BLOCKED\s*[:：]\s*`?([A-Za-z][\w ./+-]{0,60}?)`?\s*(?:[—–:;,(\n]|-\s|$)", text or ""):
        name = m.group(1).strip(" .-")
        if name and name.lower() not in names and name.lower() not in ("none", "n/a"):
            names.append(name)
    return names


# box: step_check
def parse_verdict_block(text: str) -> tuple[str | None, str]:
    m = re.search(r"verdict\s*[:*]*\s*\**\s*(PASS|FAIL)", text or "", re.I)
    issues = re.split(r"issues\s*[:*]*", text or "", maxsplit=1, flags=re.I)
    return (m.group(1).upper() if m else None), (issues[1].strip() if len(issues) > 1 else "")


class PlanRunner:
    """Runs one TeamConfig with topology "plan" for an Interpreter (which owns the LLM, tools, trace and dispatch)."""

    def __init__(self, interp, cfg: TeamConfig, task: Task, ep: Episode, run_dir: Path | None = None,
                 options: PlanOptions | None = None):
        self.i, self.cfg, self.task, self.ep = interp, cfg, task, ep
        self.opt = options or PlanOptions()
        self.rerun_done: set[int] = set()        # D39: each stale step is re-run at most once
        self.dir = Path(run_dir) / "artifacts" if run_dir else None
        self.steps = {number(s): s for s in cfg.plan}
        self.artifacts: dict[int, dict] = {}     # step number -> {"text", "meta"}
        self.reworked: set[int] = set()          # D34: at most one rework per step
        self.ledger: dict[str, dict] = {}        # D43: figure -> its first status and the step that first wrote it
        self.inferred_logged: set[int] = set()   # D37: steps whose verifier status came from the keyword fallback
        self.agents = {k: a.model_copy(deep=True) for k, a in cfg.agents.items()}   # tools may be granted (D32)
        self.web = getattr(interp.tools, "web", None)
        self.pool = getattr(interp.tools, "pool", None)   # D56: pool tools; their [S#] share web's list when it exists
        self.local = getattr(interp.tools, "local", None)  # D59: local tools (--local-tools on)
        self.current_contract: dict[str, dict] = {}        # D61: the running step's contract, by helper name
        self.run_dir = Path(run_dir) if run_dir else None
        # D63: the Action Observer's state
        self.replans: list[dict] = []                     # every observer call: triggers, decision, verdict
        self.added_steps = 0
        self.roles_added = 0
        self.plan_version = 1
        self.triggered: set[tuple] = set()                # (kind, step or item) already shown to the observer
        self.unmet: dict[str, str] = {}                   # requirement id -> why a re-plan left it unmet
        self.max_num = max((number(s) for s in cfg.plan), default=0)

    # ---- D61: the step contract ---------------------------------------------------------------------------------
    # box: step_check
    def contract(self, agents: list[AgentSpec]) -> dict[str, dict]:
        """D61: before a step, what each of its helpers must account for — the capabilities it asked for that this
        run could not give it (its missing tools and its unfilled capability requests) and the items attached to it
        (each pool tool; the local tools and local skills as one item, used by any local call). A pool skill is
        text on the card and needs no call."""
        asked = self.cfg.meta.get("capability_requests", [])
        out = {}
        for a in agents:
            have = lambda q: q.get("status") == "filled" or any(
                x and x in a.tools for x in (q["name"], q.get("canonical"), normalise(q["name"])[0]))
            needs = list(dict.fromkeys([*a.missing_tools, *(q["name"] for q in asked
                                                             if q.get("for_role") == a.name and not have(q))]))
            items = [{"name": p["name"], "aliases": [p["name"], p.get("request", "")], "tools": [p["name"]]}
                     for p in a.pool if p["kind"] == "tool" and p.get("source") != "local"]
            local = [p for p in a.pool if p.get("source") == "local"]
            if local:
                skills = [p["name"] for p in local if p["kind"] == "skill"]
                tools = [p["name"] for p in local if p["kind"] == "tool"]
                label = (f"skill {', '.join(skills)}" if skills else LOCAL_TOOLS) + f" ({', '.join(tools)})"
                items.append({"name": label, "aliases": [LOCAL_TOOLS, *skills, *tools,
                                                         *(p.get("request", "") for p in local)], "tools": tools})
            out[a.name] = {"agent_id": a.agent_id, "needs": needs, "items": items}
        return out

    # box: step_check
    def contract_check(self, contract: dict[str, dict], w: "_Work", text: str) -> dict:
        """D61: after a step, the evidence against the contract. A capability the helper lacked is accounted for by
        a BLOCKED line (or a BLOCKED action) or a NOT NEEDED line; an attached item by a successful call, or by one
        of those lines. What is left is `missing` (it ran without it and did not say so) and `unused`."""
        blocked = [*blocked_marks(text), *w.blocked.values()]
        declared = not_needed_marks(text)
        said = lambda names, marks: any(names_match(x, m) for x in names if x for m in marks)
        missing, unused = [], []
        for who, c in contract.items():
            calls = [x for x in w.calls if x["agent_id"] == c["agent_id"]]
            for need in c["needs"]:
                if not said([need], blocked + declared):
                    missing.append({"agent": who, "name": need})
            for it in c["items"]:
                if any(x["ok"] and x["tool"] in it["tools"] for x in calls) or said(it["aliases"], blocked + declared):
                    continue
                unused.append({"agent": who, "name": it["name"], "tried": any(x["tool"] in it["tools"] for x in calls)})
        return {"missing": missing, "unused": unused, "not_needed": declared}

    # box: step_check
    @staticmethod
    def contract_findings(found: dict) -> list[str]:
        out = [f"{m['agent']} asked for {m['name']}, which this run could not provide, and the output neither says "
               f"what could not be done without it nor why it was not needed. If the step needed it, write "
               f"\"BLOCKED: {m['name']} — <what could not be done>\" and remove anything filled in from memory in its "
               f"place; if not, write \"NOT NEEDED: {m['name']} — <why>\"." for m in found["missing"]]
        out += [f"{u['agent']} was given {u['name']} for this step but "
                f"{'every call to it failed' if u['tried'] else 'never called it'}. Use it now, or write "
                f"\"BLOCKED: {u['name']} — <what could not be done>\" or \"NOT NEEDED: {u['name']} — <why>\"."
                for u in found["unused"]]
        return out

    # box: step_check
    def files_of(self, n: int | None = None) -> list[dict]:
        """D61: the files the team made in the workspace (of step n, or all), that still exist."""
        if self.local is None:
            return []
        return [v for p, v in sorted(self.local.files.items())
                if (n is None or v.get("step") == n) and self.local.has_file(p)]

    # box: plan_summary
    def answer_gaps(self, n: int, text: str) -> dict:
        """D61 (G5): work the team produced that the answer leaves out — files made, and figures a producer step
        cited from a source (two digits or more)."""
        have = numbers_in(text)
        files = [f for f in self.files_of() if Path(f["path"]).name not in (text or "")]
        figs = [{"figure": e["as"], "step": e["step"], "sources": e["sources"]} for k, e in self.ledger.items()
                if e["status"] == "cited" and e["step"] != n and len(k.replace(".", "")) > 1 and k not in have]
        return {"files": files, "figures": figs[:12]}

    # box: plan_summary
    @staticmethod
    def answer_findings(gaps: dict) -> list[str]:
        out = []
        if gaps["files"]:
            out.append("the team made these files but the answer does not name them: " + ", ".join(
                f"{f['path']} (step {f['step']})" for f in gaps["files"]) + ". Name each file the task asks for and "
                "say what is in it.")
        if gaps["figures"]:
            out.append("these figures were cited from a source by a step but are not in the answer: " + ", ".join(
                f"{g['figure']} [{', '.join(g['sources'])}] (step {g['step']})" for g in gaps["figures"]) + ". Put in "
                "each one the task needs, with its [S#]; leave out the rest.")
        return out

    # box: plan_summary
    @staticmethod
    def add_files_section(text: str, files: list[dict]) -> str:
        """D61: files still unnamed after the refine turn are listed by plain code, before the Limitations section."""
        if not files:
            return text
        block = "## Files made\n" + "\n".join(f"- {f['path']} ({f['size']:,} bytes, made in step {f['step']}; listed by "
                                               f"plain code)" for f in files) + "\n"
        m = re.search(r"^\s*#+\s*limitations\b", text or "", re.I | re.M)
        if m:
            return f"{text[:m.start()].rstrip()}\n\n{block}\n{text[m.start():].lstrip()}"
        return f"{(text or '').rstrip()}\n\n{block}"

    # box: step_check
    def evidence_text(self, d: int) -> str:
        """D61 (G4): what plain code recorded about a checked step, for its verifier."""
        m = self.artifacts[d]["meta"]
        p = m["provenance"]
        src = "; ".join(f"[{s['id']}] {s['title'][:80]} ({s['url'][:100]})" for s in m.get("sources", [])) or "none"
        calls = m.get("tool_calls", [])
        lines = [f"Evidence plain code recorded for step {d}:",
                 f"- sources it fetched: {src}",
                 f"- tool calls: {len(calls)}" + ("" if calls else " (none)"),
                 *(f"  - {c['agent']} → {c['tool']} ({'ok' if c['ok'] else 'failed'}): {c['input'][:120]!r} → "
                   f"{c['result'][:200]}" for c in calls[:8]),
                 f"- figures: {p['cited']} cited, {p['unverified']} unverified, {p['untagged']} untagged",
                 f"- files made: {', '.join(f['path'] for f in m.get('files_made', [])) or 'none'}"]
        if m.get("blocked") or m.get("unused"):
            lines.append(f"- lacked: {', '.join(m.get('blocked', [])) or 'nothing'}; given but unused: "
                         f"{', '.join(m.get('unused', [])) or 'nothing'}")
        return "\n".join(lines)

    # box: step_check
    def checkable(self, n: int) -> str:
        """D65: what the steps a verify step checks produced that a tool can re-check: code, files or cited
        figures ("" when none)."""
        what = []
        for d in self.upstream(n):
            m, text = self.artifacts[d]["meta"], self.artifacts[d]["text"]
            if "```" in text or any(c["tool"].startswith("local:") for c in m.get("tool_calls", [])):
                what.append(f"code of step {d}")
            if m.get("files_made"):
                what.append(f"files of step {d}")
            if m.get("provenance", {}).get("cited"):
                what.append(f"cited figures of step {d}")
        return ", ".join(dict.fromkeys(what))

    # box: step_check
    def upstream(self, n: int) -> list[int]:
        """D65: every step a step builds on, directly or through other steps, that has run (plan order)."""
        deps = dependencies(self.cfg.plan)
        seen, todo = set(), list(deps.get(n, []))
        while todo:
            d = todo.pop()
            if d not in seen:
                seen.add(d)
                todo.extend(deps.get(d, []))
        return [d for d in sorted(seen) if d in self.artifacts]

    # box: step_check
    def raw_results_text(self, n: int) -> str:
        """D65: the raw tool results every upstream step used (not only their text), for a verify step."""
        parts = []
        for d in self.upstream(n):
            for r in self.artifacts[d]["meta"].get("tool_results", []):
                parts.append(f"### Step {d} · {r['agent']} → {r['tool']} ({r['input'][:120]!r})\n{r['result']}")
        if not parts:
            return ""
        return "## Raw tool results of the steps you check (plain code copied them)\n" + "\n\n".join(parts)

    # box: step_check
    def verifier_tools(self, agents: list[AgentSpec]) -> list[str]:
        """D65: a verify step's helpers get the tools to re-check what the earlier steps made: calc for numbers, web
        for cited facts, local run/read for code and files (the same sandbox gate as every local call)."""
        reg = self.i.tools
        names = [t for t in ("calc", *WEB_TOOLS, "local:Bash", "local:Read") if t in reg]
        if self.local is not None:
            for t in ("local:Bash", "local:Read"):
                if t.removeprefix("local:") in getattr(self.local, "exposed", []) and t not in names:
                    self.local.register(reg, t)
                    names.append(t)
        granted = []
        for a in agents:
            new = [t for t in names if t not in a.tools]
            if new:
                a.tools = [*a.tools, *new]
                granted.append({"agent": a.name, "tools": new})
        return granted

    # box: plan_step
    def grant_web_tools(self) -> None:
        """D32: a role whose missing tools or capability requests normalise to web_search gets web_search and
        fetch_url when this run has them. Recorded as `capability_mapped` events."""
        asked = self.cfg.meta.get("capability_requests", [])
        for a in self.agents.values():
            names = list(a.missing_tools) + [q["name"] for q in asked if q.get("for_role") == a.name]
            hits = [n for n in names if normalise(n)[0] == "web_search"]
            if not hits:
                continue
            a.tools = list(dict.fromkeys([*a.tools, *WEB_TOOLS]))
            a.missing_tools = [t for t in a.missing_tools if t not in hits]
            self.i.trace.event("capability_mapped", {"gen_ai.agent.id": a.agent_id, "gen_ai.agent.name": a.name,
                                                     "amoeba.requested": hits, "amoeba.canonical": "web_search",
                                                     "amoeba.granted": list(WEB_TOOLS)})

    # ---- the whole plan -------------------------------------------------------------------------------------
    # box: ov_run, plan_graph
    def run(self) -> tuple[str | None, str | None]:
        for e in self.cfg.meta.get("dependency_relinked", []):
            self.i.trace.event("dependency_relinked", e)
        if self.web is not None:
            self.grant_web_tools()
            self.i.trace.event("web_tools", {"amoeba.web.provider": self.web.provider.name, **self.web.limits.as_trace()})
        ws = waves(self.cfg.plan)
        deps = dependencies(self.cfg.plan)
        self.answer_n = self._answer_step(ws)
        self.i.trace.event("plan_graph", {"amoeba.waves": ws, "amoeba.depends_on": {str(k): v for k, v in deps.items()},
                                          "amoeba.max_turns": self._max_turns(), "amoeba.max_tokens": PLAN_MAX_TOKENS,
                                          **{f"amoeba.options.{k}": v for k, v in asdict(self.opt).items()}})
        replan = self.opt.replan == "on"
        if replan:
            self.known = self.plan_items()                                  # D63: what the plan knew of at the start
            self.save_plan_version(None)
        w = 0
        while True:     # D63: the waves are recomputed after each wave, so an accepted re-plan takes effect
            nums = next((x for x in ([n for n in wave if n not in self.artifacts] for wave in waves(self.cfg.plan))
                         if x), None)
            if nums is None:
                break
            w += 1
            deps = dependencies(self.cfg.plan)
            for n in nums:   # sequential for now; the wave number is recorded so parallel runs keep the same trace
                self.run_step(self.steps[n], w, deps[n])
            if replan:
                self.action_observer(w)
        ws = waves(self.cfg.plan)
        if replan:
            self.ep.replan = self.replan_summary()
        self.ep.figure_ledger = self.ledger
        counts: dict[str, int] = {}
        for e in self.ledger.values():
            counts[e["status"]] = counts.get(e["status"], 0) + 1
        self.i.trace.event("figure_ledger", {"amoeba.figures": len(self.ledger), **{f"amoeba.first_{k}": v
                                                                                   for k, v in sorted(counts.items())}})
        if self.answer_n is None:                          # D41: several final steps, none the summariser's
            return self.assemble_by_code(ws[-1])
        art = self.artifacts[self.answer_n]
        status = art["meta"]["status"]
        return art["text"], (None if status == "done" else status)

    def _answer_step(self, ws: list[list[int]]) -> int | None:
        """The summariser's step if it owns one in the last wave; else the last wave's only step; else None: the
        answer is assembled by code from every step of the last wave (D41)."""
        summ = {a.agent_id for a in self.agents.values() if a.is_summariser}
        final = [n for n in ws[-1] if summ & set(self.steps[n].agent_ids)]
        if final:
            return final[-1]
        return ws[-1][0] if len(ws[-1]) == 1 else None

    # box: plan_summary
    def assemble_by_code(self, last: list[int]) -> tuple[str, str | None]:
        """D41: no summariser step to write the answer, so plain code puts the last wave's outputs under one heading
        each, in plan order, then completes the Limitations section (D36). The run's error is the worst status."""
        parts = []
        for n in last:
            title = re.sub(r"^\s*\[.*?\]\s*:\s*", "", self.steps[n].text).strip() or f"Step {n}"
            parts.append(f"## Step {n}: {title}\n\n{self.artifacts[n]['text'].strip()}")
        text = "\n\n".join(parts)
        if self.opt.contract == "on":                      # D61 (G5): files made but named by no final step
            text = self.add_files_section(text, [f for f in self.files_of() if Path(f["path"]).name not in text])
        text, added = self.enforce_limitations(text)
        self.ep.answer_assembled_by_code = list(last)
        statuses = [self.artifacts[n]["meta"]["status"] for n in last]
        worst = next((s for s in ("incomplete", "partial") if s in statuses), "done")
        self.i.trace.event("answer_assembled_by_code", {"amoeba.steps": list(last), "amoeba.statuses": statuses,
                                                        "amoeba.limitations_added": added["limitations_added_by_code"]})
        if self.dir:
            (self.dir / "answer.md").write_text(text + "\n", encoding="utf-8")
        return text, (None if worst == "done" else worst)

    def _max_turns(self) -> int:
        return next(iter(self.agents.values())).limits.max_turns

    # ---- one step -------------------------------------------------------------------------------------------
    def cap(self, text: str, limit: int, step: int, source: int, what: str) -> str:
        """D44: an input over `limit` characters is shortened, with a trace event. D64: head AND tail are kept with
        "[… N characters omitted …]" marks, and so is every line with a final result (a count, a total, a result,
        an "=" line) and the last lines of program output, so a result is never cut away."""
        if len(text) <= limit:
            return text
        out = shorten(text, limit)
        self.i.trace.event("input_truncated", {"amoeba.step": step, "amoeba.from_step": source, "amoeba.limit": limit,
                                               "amoeba.chars": len(text), "amoeba.what": what,
                                               "amoeba.chars_passed": len(out)})
        return f"{out}\n[shortened by plain code from {len(text):,} characters: head, result lines and tail kept]"

    def inputs_text(self, deps: list[int], n: int | None = None, evidence: bool = False) -> str:
        if not deps:
            return "None: this step starts from the task alone."
        parts = []
        for d in deps:
            a = self.artifacts[d]
            m = a["meta"]
            body = self.cap(a["text"], self.opt.max_input_chars, n or 0, d, "input")
            stale = f", STALE (built on step(s) {', '.join(map(str, m['stale_because']))} before their rework)" \
                if m.get("stale") else ""
            parts.append(f"## Step {d} ({', '.join(m['roles'])}), status: {m['status']}{stale}\n{body}")
            if evidence and self.opt.contract == "on":          # D61 (G4): the verifier sees what the step used
                parts[-1] += "\n\n" + self.evidence_text(d)
        return "\n\n".join(parts)

    # box: plan_step
    def run_step(self, step: PlanStep, wave: int, deps: list[int], rework: dict | None = None,
                 reverify: dict | None = None, rerun: dict | None = None) -> dict:
        n = number(step)
        agents = [self.agents[a] for a in step.agent_ids]
        summarising = self.is_summary_step(step)                                  # D35
        verifier = self.is_verification(step) and not summarising
        inputs = self.all_inputs_text(n) if summarising else self.inputs_text(deps, n, evidence=verifier)
        on = self.opt.contract == "on"                                             # D61
        answer_step = n == getattr(self, "answer_n", None)
        if self.web is not None:
            self.web.begin_step(n, self.i.trace)
        if self.pool is not None:
            self.pool.begin_step(n, self.i.trace)
        if self.local is not None:
            self.local.begin_step(n, self.i.trace)
        self.i.trace.event("step_input", {"amoeba.step": n, "amoeba.wave": wave, "amoeba.depends_on": deps,
                                          "amoeba.received": deps, "amoeba.input_chars": len(inputs),
                                          "amoeba.verification": verifier, "amoeba.rework": bool(rework)})
        extra = VERIFY_NOTE if verifier else ""
        if verifier and on:                        # D65: a check step gets the tools and the raw results to re-check
            granted = self.verifier_tools(agents)
            extra += VERIFY_TOOLS_NOTE
            raw = self.raw_results_text(n)
            if raw:
                inputs += "\n\n" + raw
            self.i.trace.event("verifier_tools", {"amoeba.step": n, "amoeba.granted": granted,
                                                  "amoeba.upstream": self.upstream(n),
                                                  "amoeba.raw_results_chars": len(raw)})
        if self.opt.replan == "on" and deps and not summarising:                  # D63: a missing input is a trigger
            extra += MISSING_INPUT_NOTE
        if reverify:
            extra += REVERIFY_NOTE.format(steps=", ".join(map(str, reverify["reworked"])),
                                          issues=reverify["first_issues"].strip())
        if rework:
            extra += REWORK_NOTE.format(by=rework["by_step"], issues=rework["issues"].strip(),
                                        previous=self.artifacts[n]["text"].strip())
        w = _Work(max_turns=agents[0].limits.max_turns)
        template = PROMPT.plan_summarise if summarising else PROMPT.plan_step
        # D51: with critique, the first role drafts and the others review; the step's output is the drafter's
        writers = agents[:1] if self.opt.collab == "critique" and len(agents) > 1 else agents
        contract = self.contract(writers) if on and not summarising else {}       # D61: before the step
        self.current_contract = contract
        if contract:
            self.i.trace.event("step_contract", {"amoeba.step": n, "amoeba.contract": {
                who: {"needs": c["needs"], "items": [x["name"] for x in c["items"]]} for who, c in contract.items()}})
        self._loop(step, n, writers, inputs, extra, w, template)
        collab = self.critique(step, n, agents[0], agents[1:], inputs, extra, w, template) \
            if writers is not agents else None
        agents_all, agents = agents, writers
        exact = computed_values(self.computed_results(w))                          # D66
        text, removed = strip_unverified(self._text(agents, w), exact)
        checks = step_checks(step, text, deps, self.artifacts, verifier)          # D34
        own, visible = self._sources(n, deps)
        prov = check_provenance(text, visible, self.task.prompt, inputs, w.tool_results,   # D33
                                self.computed_results(w), self.web_ids())
        found = self.contract_check(contract, w, text) if contract else None                # D61 (G1, G2)
        produced = self.answer_gaps(n, text) if on and answer_step else None               # D61 (G5)
        items = (self.contract_findings(found) if found else []) + (self.answer_findings(produced) if produced else [])
        refine = self.refine(step, n, agents, inputs, extra, w, template, checks, prov, items)   # D42 / D50 / D61
        if refine:
            exact = computed_values(self.computed_results(w))
            text, again = strip_unverified(self._text(agents, w), exact)
            removed += again
            checks = step_checks(step, text, deps, self.artifacts, verifier)
            own, visible = self._sources(n, deps)
            prov = check_provenance(text, visible, self.task.prompt, inputs, w.tool_results,
                                    self.computed_results(w), self.web_ids())
            found = self.contract_check(contract, w, text) if contract else None
            produced = self.answer_gaps(n, text) if produced is not None else None
            refine["after"] = refine_counts(checks, prov, len((self.contract_findings(found) if found else [])
                                                              + (self.answer_findings(produced) if produced else []))
                                            if on else None)
            self.i.trace.event("refine", {"amoeba.step": n, "amoeba.reason": refine["reason"],
                                          "amoeba.findings": len(refine["findings"]),
                                          **{f"amoeba.before.{k}": v for k, v in refine["before"].items()},
                                          **{f"amoeba.after.{k}": v for k, v in refine["after"].items()}})
        failed = [c["name"] for c in checks if not c["pass"]]
        retried = bool(refine)
        # D36: what the step could not do for lack of a capability — BLOCKED as an action or marked in the output.
        # D40: not for the answer step: its Limitations section names the producers' gaps on purpose
        mentions = blocked_marks(text)
        gaps = [] if answer_step else sorted(set(w.blocked.values()) | set(mentions))
        # D61 (G1): a capability the helper lacked and did not account for is a gap, answer step included
        undeclared = list(dict.fromkeys(m["name"] for m in found["missing"])) if found else []
        gaps = sorted(set(gaps) | set(undeclared))
        unused = list(dict.fromkeys(u["name"] for u in found["unused"])) if found else []   # D61 (G2)
        wrote = bool(w.done) or any(v for v in w.partial.values())
        finished = len(w.done) + len(w.blocked) == len(agents)
        if gaps:
            status = "partial" if wrote else "incomplete"
            reason = "lacked: " + ", ".join(gaps) + ("; checks failed: " + ", ".join(failed) if failed else "")
        elif not finished:
            status, reason = "incomplete", "max_turns"
        elif failed:
            status, reason = "incomplete", "checks failed: " + ", ".join(failed)
        else:
            status, reason = "done", ""
        if undeclared:
            reason += "; not declared by the helper: " + ", ".join(undeclared)
        if unused:
            status = "partial" if status == "done" else status
            reason = "; ".join(x for x in (reason, "attached unused: " + ", ".join(unused)) if x)
        unchecked = verifier and on and parse_verdict_block(text)[0] == "PASS" and not w.calls \
            and self.checkable(n)                      # D65: a PASS that re-checked nothing is an unverified check
        if unchecked:
            status = "partial" if status == "done" else status
            reason = "; ".join(x for x in (reason, "unverified check: PASS with no re-checking tool call on "
                                                   + self.checkable(n)) if x)
        if on:
            text = strip_not_needed(text) or text
        if found is not None:
            self.i.trace.event("contract_check", {"amoeba.step": n, "amoeba.missing": undeclared,
                                                  "amoeba.unused": unused, "amoeba.not_needed": found["not_needed"],
                                                  "amoeba.tool_calls": len(w.calls),
                                                  "amoeba.tool_calls_ok": sum(c["ok"] for c in w.calls)})
        claimed = missing = None
        if self.local is not None:                # D59: a file the step says it made must be in the workspace
            claimed = claimed_files(text)
            missing = [f for f in claimed if not self.local.has_file(f)]
            if missing:
                status = "incomplete"
                reason = "; ".join(x for x in (reason, "claimed_file_missing: " + ", ".join(missing)) if x)
                self.i.trace.event("claimed_file_missing", {"amoeba.step": n, "amoeba.files": missing})
        # D61 (G6): what went wrong, for rework — a step that only lacked a capability cannot be fixed by a rework
        causes = [c for c, hit in (("capability", bool(gaps)), ("checks", bool(failed)),
                                   ("max_turns", not finished and not gaps), ("unused_tool", bool(unused)),
                                   ("claimed_file_missing", bool(missing))) if hit]
        origins = self.ledger_update(n, prov.pop("figures"))                               # D43
        meta = {"step": n, "wave": wave, "roles": [a.name for a in agents_all], "covers": step.covers,
                "collab": collab,
                "depends_on": deps, "received": deps, "output_spec": step.output, "status": status,
                "status_reason": reason, "turns": w.turn, "blocked": gaps, "answer_step": answer_step,
                "check_source": checks[0]["source"] if checks else "",
                "blocked_mentions": mentions if answer_step else [],
                "blocked_canonical": sorted({normalise(g)[0] for g in gaps}), "sources": own,
                "visible_source_ids": sorted(visible), "provenance": prov, "figure_origins": origins,
                "checks": checks, "retried": retried, "refine": refine,
                "unverified_tags_removed": removed,                                # D66
                "refine_reason": refine["reason"] if refine else "",
                "verification": verifier, "rework_of": rework, "reverify_of": reverify, "rerun_of_stale": rerun,
                "stale": False, "stale_because": [],
                "contributions": w.contributions}
        if claimed is not None:
            meta["claimed_files"], meta["claimed_files_missing"] = claimed, missing
        if on:                                                                     # D61: contract and evidence
            meta.update({"contract": {who: {"needs": c["needs"], "items": [x["name"] for x in c["items"]]}
                                      for who, c in contract.items()},
                         "contract_missing": undeclared, "unused": unused,
                         "not_needed": found["not_needed"] if found else [], "causes": causes,
                         "tool_calls": w.calls, "files_made": self.files_of(n),
                         # D65: what the step's tools returned, for the steps that check it
                         "tool_results": [{"agent": c["agent"], "tool": c["tool"], "input": c["input"],
                                           "result": shorten(r or "", 1500)}
                                          for c, r in zip(w.calls, w.tool_results) if c["ok"]][:8],
                         "unverified_check": bool(unchecked)})
        if verifier:
            meta["verdict"], meta["issues"] = parse_verdict_block(text)
            # D38: both verdicts are kept; `verdict` is always the latest one
            meta["verdict_first"] = reverify["first_verdict"] if reverify else meta["verdict"]
            meta["verdict_after_rework"] = meta["verdict"] if reverify else None
        if summarising or (on and answer_step):
            if produced is not None:                                               # D61 (G5)
                text = self.add_files_section(text, produced["files"])
            text, added = self.enforce_limitations(text)                          # D36 / D61 (G3)
            meta["summary_check"] = {**self.summary_check(n, text), **added}
            if produced is not None:
                meta["summary_check"].update({"files_listed_by_code": [f["path"] for f in produced["files"]],
                                              "cited_figures_left_out": [g["figure"] for g in produced["figures"]]})
        self._save(n, wave, text, meta, prov)
        if verifier and meta["verdict"] == "FAIL" and not reverify:
            reworked = self.rework_producers(n, deps, meta["issues"])
            if reworked:                                   # D38: check once more what the rework produced
                self.i.trace.event("reverify", {"amoeba.step": n, "amoeba.reworked": reworked})
                self.run_step(step, wave, deps, reverify={"first_verdict": meta["verdict"],
                                                          "first_issues": meta["issues"], "reworked": reworked})
                self.mark_stale(reworked, verifier_step=n)                           # D39
        return self.artifacts[n]

    @staticmethod
    def computed_results(w: "_Work") -> list[str]:
        """D66: what the step's calc and local tools returned (a number equal to one of them is derived)."""
        return [r for c, r in zip(w.calls, w.tool_results) if c["ok"] and (c["tool"] == "calc"
                                                                          or c["tool"].startswith("local:"))]

    def web_ids(self) -> set[str]:
        """D66: the ids of search and fetched-page sources in the run."""
        books = [b for b in (self.web, getattr(self.pool, "book", None), getattr(self.local, "book", None)) if b]
        return {x["id"] for b in books for x in getattr(b, "sources", []) if x.get("kind") in ("search", "fetch")}

    def _sources(self, n: int, deps: list[int]) -> tuple[list[dict], set[str]]:
        """The step's own sources and every source id it could have seen (its own and its inputs')."""
        books = [b for b in (self.web, self.pool.book if self.pool is not None else None,
                             getattr(self.local, "book", None)) if b is not None]      # D61 (G7): local results too
        books = [b for i, b in enumerate(books) if all(b is not c for c in books[:i])]   # one list when shared
        own = [{k: s[k] for k in ("id", "url", "title", "kind", "fetched_at")}
               for b in books for s in b.sources_for(n)]
        visible = {s["id"] for s in own}.union(*(self.artifacts[d]["meta"]["visible_source_ids"] for d in deps)) \
            if deps else {s["id"] for s in own}
        return own, visible

    # box: plan_step
    def critique(self, step: PlanStep, n: int, drafter: AgentSpec, reviewers: list[AgentSpec], inputs: str,
                 extra: str, w: "_Work", template: str) -> dict:
        """D51: the reviewers answer AGREE or REVISE (numbered issues against done_when and their own success
        criteria); on any REVISE the drafter revises with the issues listed, with turns of its own
        (check_retry_turns). At most collab_rounds review rounds; plain code ends it when everyone agrees or the
        rounds run out (the last revision is then not reviewed). Nothing to review when the drafter never gave a
        Final Output."""
        objections: dict[str, list[int]] = {r.name: [] for r in reviewers}
        rounds, agreed, revisions = 0, False, 0
        for rnd in range(1, self.opt.collab_rounds + 1):
            draft = w.done.get(drafter.agent_id)
            if not draft:
                break
            rounds = rnd
            asks = []
            for rv in reviewers:
                verdict, issues = self._review(rv, step, n, drafter, draft, inputs)
                objections[rv.name].append(len(issues) if verdict == "REVISE" else 0)
                w.contributions.append({"turn": w.turn, "agent": rv.name, "action": "review", "verdict": verdict,
                                        "issues": len(issues), "round": rnd})
                if verdict == "REVISE":
                    asks.append((rv.name, issues or ["(no specific issue given)"]))
            self.i.trace.event("collab_round", {"amoeba.step": n, "amoeba.round": rnd, "amoeba.drafter": drafter.name,
                                                "amoeba.revise": [a for a, _ in asks],
                                                "amoeba.objections": sum(len(i) for _, i in asks)})
            if not asks:
                agreed = True
                break
            lines = "\n".join(f"- {who}: {i}. {x}" for who, items in asks for i, x in enumerate(items, 1))
            w.completed += REVISION_NOTE.format(issues=lines)
            w.done.clear()
            w.max_turns = w.turn + self.opt.check_retry_turns
            self._loop(step, n, [drafter], inputs, extra, w, template)
            revisions += 1
        return {"mode": "critique", "drafter": drafter.name, "reviewers": [r.name for r in reviewers],
                "rounds": rounds, "revisions": revisions, "objections": objections, "agreed": agreed}

    # box: plan_step
    def _review(self, rv: AgentSpec, step: PlanStep, n: int, drafter: AgentSpec, draft: str, inputs: str
                ) -> tuple[str, list[str]]:
        """D51: one reviewer's verdict and numbered issues. An unreadable reply counts as AGREE (recorded)."""
        criteria = "; ".join(rv.success_criteria) or "none written"
        user = render(PROMPT.plan_critique, task=self.task.prompt, card=plan_card(rv), number=n,
                      step=step_detail(step), inputs=inputs, drafter=drafter.name, draft=draft,
                      done_when=step.done_when or "none written", criteria=criteria)
        system = render(PROMPT.plan_step_system, name=rv.name)
        with self.i.trace.span("invoke_agent", {"gen_ai.agent.id": rv.agent_id, "gen_ai.agent.name": rv.name,
                                                "amoeba.box": "plan_step",
                                                "amoeba.step": n, "amoeba.review": True}):
            before = self.i.trace.n_llm_calls
            try:
                raw, sec = self.i.llm.chat_sections(system, user, ["Verdict"], self.ep.seed, agent_id=rv.agent_id,
                                                    agent_name=rv.name, max_tokens=PLAN_MAX_TOKENS,
                                                    role=role_group(reviewing=True))   # D54
            except MissingSections as e:
                raw, sec = getattr(e, "raw", "") or "", {}
            for rec in self.i.trace.spans("chat")[before:]:
                self.i._record(rv, self.ep, raw, rec.get("gen_ai.usage.input_tokens", 0),
                               rec.get("gen_ai.usage.output_tokens", 0))
        word = (sec.get("Verdict") or "").strip().upper()
        verdict = "REVISE" if "REVISE" in word else "AGREE" if "AGREE" in word else "UNREADABLE"
        head = raw.rfind("## Issues")
        body = raw[head + len("## Issues"):] if head >= 0 else ""
        issues = [m.group(1).strip() for m in re.finditer(r"^\s*\d+[.)]\s+(.+)$", body, re.M)]
        if verdict == "UNREADABLE":
            self.i.trace.event("review_unreadable", {"amoeba.step": n, "gen_ai.agent.name": rv.name})
            verdict = "AGREE"
        return verdict, issues if verdict == "REVISE" else []

    # box: plan_step
    def refine(self, step: PlanStep, n: int, agents: list[AgentSpec], inputs: str, extra: str, w: "_Work",
               template: str, checks: list[dict], prov: dict, contract_items: list[str] = ()) -> dict | None:
        """D50: one refine turn for the helper(s) of a finished step, with turns of its own (check_retry_turns, not
        the step's cap). The helper is given exactly what plain code found: failed checks and — unless
        self_refine is "off" — untagged figures and citations of sources it never saw. With "always" and no
        finding it gets a self-review against done_when and its success criteria instead. Returns the reason, the
        findings and the before-counts (the caller adds the after-counts), or None when there is no refine.
        D61: contract_items (what the step contract left unaccounted for, or what the answer leaves out) always
        earn the turn, whatever self_refine says; they share it with the other findings."""
        mode = self.opt.self_refine
        check_items, prov_items = refine_findings(checks, prov)
        if mode == "off":
            prov_items = []
        contract_items = list(contract_items)
        reason = "+".join(k for k, v in (("checks", check_items), ("provenance", prov_items),
                                         ("contract", contract_items)) if v)
        if not reason and mode == "always":
            reason = "self_review"
        if not reason or not w.done:
            return None
        if check_items:
            self.i.trace.event("check_retry", {"amoeba.step": n, "amoeba.failed_checks": [c["name"] for c in checks
                                                                                         if not c["pass"]],
                                               "amoeba.retry_turns": self.opt.check_retry_turns})
        if reason == "self_review":
            criteria = "; ".join(c for a in agents for c in a.success_criteria) or "none written"
            note = SELF_REVIEW_NOTE.format(done_when=step.done_when or "none written", criteria=criteria)
        elif not prov_items and not contract_items:
            note = RETRY_NOTE.format(failed="; ".join(check_items))
        else:
            note = REFINE_NOTE.format(findings="\n".join(f"{i}. {x}" for i, x in
                                                          enumerate(check_items + prov_items + contract_items, 1)))
        w.max_turns = w.turn + self.opt.check_retry_turns
        w.completed += note
        w.done.clear()
        self._loop(step, n, agents, inputs, extra, w, template)
        return {"reason": reason, "findings": check_items + prov_items + contract_items,
                "before": refine_counts(checks, prov, len(contract_items) if self.opt.contract == "on" else None)}

    # box: step_check
    def mark_stale(self, reworked: list[int], verifier_step: int) -> None:
        """D39: a step that already ran on the output of a step that was later reworked (directly or through other
        steps) is stale. It is marked in its metadata and the trace; with --rerun-stale it is re-run once, in plan
        order. The verifier that asked for the rework is not stale (it checks again, D38)."""
        deps = dependencies(self.cfg.plan)
        users: dict[int, set[int]] = {}
        for s, ds in deps.items():
            for d in ds:
                users.setdefault(d, set()).add(s)
        because: dict[int, set[int]] = {}
        for r in reworked:
            todo, seen = list(users.get(r, ())), set()
            while todo:
                x = todo.pop()
                if x in seen:
                    continue
                seen.add(x)
                todo.extend(users.get(x, ()))
                if x in self.artifacts and x != verifier_step:
                    because.setdefault(x, set()).add(r)
        order = [x for w in waves(self.cfg.plan) for x in w]
        for x in sorted(because, key=order.index):
            m = self.artifacts[x]["meta"]
            m["stale"], m["stale_because"] = True, sorted(because[x])
            self.i.trace.event("stale", {"amoeba.step": x, "amoeba.because_reworked": sorted(because[x]),
                                         "amoeba.will_rerun": self.opt.rerun_stale and x not in self.rerun_done})
            self._write(x)
        if self.opt.rerun_stale:
            for x in sorted(because, key=order.index):
                if x in self.rerun_done:
                    continue
                self.rerun_done.add(x)
                self.run_step(self.steps[x], self.artifacts[x]["meta"]["wave"], deps[x],
                              rerun={"because_reworked": sorted(because[x])})

    # box: plan_summary
    def is_summary_step(self, step: PlanStep) -> bool:
        """D35: the answer step, when the summariser owns it, only assembles."""
        summ = {a.agent_id for a in self.agents.values() if a.is_summariser}
        return number(step) == getattr(self, "answer_n", None) and bool(summ & set(step.agent_ids))

    # box: plan_summary
    def all_inputs_text(self, n: int) -> str:
        """The summariser sees every step's latest output, its status and where its figures come from. D44: each
        output is capped at max_input_chars, and when all of them together would pass max_summary_input_chars each
        gets an equal share instead."""
        parts = []
        items = [(d, a) for d, a in sorted(self.artifacts.items()) if d != n]
        total = sum(min(len(a["text"]), self.opt.max_input_chars) for _, a in items)
        share = self.opt.max_input_chars if total <= self.opt.max_summary_input_chars else \
            max(500, self.opt.max_summary_input_chars // max(1, len(items)))
        for d, a in items:
            m, p = a["meta"], a["meta"]["provenance"]
            why = f" ({m['status_reason']})" if m.get("status_reason") else ""
            gaps = f"; lacked: {', '.join(m['blocked'])}" if m.get("blocked") else ""
            verdict = f"; verdict: {m['verdict']}" if m.get("verdict") else ""
            if m.get("files_made"):                              # D61 (G5)
                verdict += f"; files made: {', '.join(f['path'] for f in m['files_made'])}"
            if m.get("unused"):
                verdict += f"; given but unused: {', '.join(m['unused'])}"
            if m.get("stale"):
                verdict += f"; STALE: built on step(s) {', '.join(map(str, m['stale_because']))} before their rework"
            if m.get("verdict_after_rework"):
                verdict += f" (after rework; first verdict {m['verdict_first']})"
            body = self.cap(a["text"], share, n, d, "summary input")
            parts.append(f"## Step {d} ({', '.join(m['roles'])}), status: {m['status']}{why}{gaps}{verdict}; figures: "
                         f"{p['cited']} cited, {p['unverified']} unverified, {p['untagged']} untagged\n{body}")
        return "\n\n".join(parts) or "None."

    def deliverables_text(self) -> str:
        req = self.cfg.requirements
        return "\n".join(f"{k}: {v}" for k, v in req.items()) if req else \
            "None listed by the plan; take the deliverables from the task."

    # box: plan_summary
    def ledger_update(self, n: int, figures: list[dict]) -> dict[str, int]:
        """D43: the first status of each figure in the run (cited / unverified / untagged / derived / given, and the
        step that first wrote it) goes into the ledger; a later step that repeats the figure inherits that first
        status, so a number that entered untagged stays untagged however often it is copied. Returns this step's
        figures counted by their ledger status."""
        origin: dict[str, int] = {}
        for f in figures:
            e = self.ledger.get(f["n"])
            if e is None and f["status"] != "inherited":
                e = self.ledger[f["n"]] = {"status": f["status"], "step": n, "as": f["as"], "sources": f["sources"]}
            key = e["status"] if e else "inherited"
            origin[key] = origin.get(key, 0) + 1
        return origin

    # box: plan_summary
    def summary_check(self, n: int, text: str) -> dict:
        """D35: a figure in the final answer that is in no step output and not in the task is new. D43: the answer's
        figures are also listed by their ledger status, so untagged and unverified figures in the answer show."""
        known = numbers_in(self.task.prompt).union(*(numbers_in(a["text"]) for d, a in self.artifacts.items() if d != n))
        claims = claim_numbers(text)
        new = sorted(claims - known, key=lambda x: (len(x), x))
        by = lambda st: sorted((x for x in claims if self.ledger.get(x, {}).get("status") == st), key=lambda x: (len(x), x))
        out = {"new_number_in_summary": len(new), "new_numbers": new[:30],
               "limitations_section": bool(re.search(r"^\s*#+\s*limitations", text or "", re.I | re.M)),
               "answer_figures": len(claims), "answer_cited": len(by("cited")),
               "answer_unverified": by("unverified")[:30], "answer_untagged": by("untagged")[:30]}
        self.i.trace.event("summary_check", {"amoeba.step": n, "amoeba.new_number_in_summary": len(new),
                                             "amoeba.new_numbers": new[:30],
                                             "amoeba.limitations_section": out["limitations_section"]})
        return out

    def blocked_capabilities(self) -> dict[str, list[str]]:
        """D36: canonical capability -> the names the steps used for it, over every step's latest output. D61: the
        answer step's own undeclared gaps (G1) count too; its BLOCKED mentions still do not (D40)."""
        out: dict[str, list[str]] = {}
        for d, a in self.artifacts.items():
            m = a["meta"]
            names = m.get("contract_missing", []) if d == getattr(self, "answer_n", None) else m.get("blocked", [])
            for g in names:
                out.setdefault(normalise(g)[0], [])
                if g not in out[normalise(g)[0]]:
                    out[normalise(g)[0]].append(g)
        return out

    # box: plan_summary
    def unused_items(self) -> dict[str, list[int]]:
        """D61 (G2/G3): item attached to a helper -> the steps that left it unused and unaccounted for."""
        out: dict[str, list[int]] = {}
        for d, a in sorted(self.artifacts.items()):
            for u in a["meta"].get("unused", []):
                out.setdefault(u, []).append(d)
        return out

    # box: plan_summary
    def enforce_limitations(self, text: str) -> tuple[str, dict]:
        """D36: the final answer's Limitations section must name every capability a step lacked. Names it leaves
        out are appended by plain code (and recorded), so a gap is never silently dropped. D61 (G3): also every
        attached item a step left unused, and names are matched by their canonical form too (prefix and case
        ignored, '_' or '-' as a space)."""
        caps, unused = self.blocked_capabilities(), self.unused_items()
        m = re.search(r"^\s*#+\s*limitations\b.*$", text or "", re.I | re.M)
        section = (text[m.end():] if m else "").lower()
        flat = re.sub(r"[\s_-]+", " ", section)
        def named(names):
            for x in names:
                bare = re.sub(r"^(?:pool|local|skill)\s*:\s*", "", x.strip(), flags=re.I)
                if x.lower() in section or re.sub(r"[\s_-]+", " ", bare.lower()) in flat:
                    return True
            return False
        missing = sorted(c for c, names in caps.items() if not named({c, *names}))
        not_used = sorted(u for u in unused if not named({u, re.sub(r"\s*\(.*\)$", "", u)}))
        lines = [f"- BLOCKED: {c} (the team had no such capability; added by plain code)" for c in missing]
        unmet = {r: why for r, why in getattr(self, "unmet", {}).items()           # D63: dropped by a re-plan
                 if not re.search(rf"\b{re.escape(r)}\b[^\n]*not met", section, re.I)}
        lines += [f"- NOT MET: {r} — {self.cfg.requirements.get(r, '')} ({why}; added by plain code)"
                  for r, why in unmet.items()]
        lines += [f"- NOT USED: {u} (given to the team for step {', '.join(map(str, unused[u]))} but never used; "
                  f"added by plain code)" for u in not_used]
        if lines:
            body = "\n".join(lines)
            text = f"{text.rstrip()}\n\n{body}\n" if m else f"{text.rstrip()}\n\n## Limitations\n{body}\n"
            self.i.trace.event("limitations_added", {"amoeba.capabilities": missing, "amoeba.unused": not_used})
        return text, {"blocked_capabilities": sorted(caps), "limitations_added_by_code": missing,
                      **({"unused_added_by_code": not_used} if unused else {})}

    # box: step_check
    def is_verification(self, step: PlanStep) -> bool:
        """D37: a step the planner declared `kind: verify` that depends on the steps it checks. Only when the step
        plan declares no kind at all (an older draft) is the keyword rule used — verify, check, review, validate, reconcile … in its
        text — and then a `verification_inferred` event is logged. The summariser's own step is never one."""
        summ = {a.agent_id for a in self.agents.values() if a.is_summariser}
        if set(step.agent_ids) <= summ or not step.depends_on:
            return False
        if any(s.kind for s in self.cfg.plan):          # the planner declared kinds: an undeclared step is work
            return step.kind == "verify"
        inferred = bool(VERIFY_WORDS.search(f"{step.text}\n{step.do}\n{step.done_when}"))
        if inferred and number(step) not in self.inferred_logged:
            self.inferred_logged.add(number(step))
            self.i.trace.event("verification_inferred", {"amoeba.step": number(step), "amoeba.text": step.text[:120]})
        return inferred

    # box: step_check
    def rework_producers(self, n: int, deps: list[int], issues: str) -> list[int]:
        """D34: on a FAIL verdict each producer step it checked is re-run once with the issues. Returns the steps
        reworked; the verifier then checks once more (D38) and the run goes on whatever the second verdict."""
        all_deps = dependencies(self.cfg.plan)
        done = []
        for d in deps:
            if d in self.reworked or self.artifacts[d]["meta"].get("verification"):
                continue
            if self.artifacts[d]["meta"].get("causes") == ["capability"]:   # D61 (G6): a rework cannot add it
                self.i.trace.event("rework_skipped", {"amoeba.step": d, "amoeba.by_step": n,
                                                      "amoeba.reason": "capability_missing",
                                                      "amoeba.lacked": self.artifacts[d]["meta"]["blocked"]})
                continue
            self.reworked.add(d)
            done.append(d)
            self.i.trace.event("rework", {"amoeba.step": d, "amoeba.by_step": n, "amoeba.issues_chars": len(issues)})
            self.run_step(self.steps[d], self.artifacts[d]["meta"]["wave"], all_deps[d],
                          rework={"by_step": n, "issues": issues})
        return done

    # box: plan_step
    def _loop(self, step: PlanStep, n: int, agents: list[AgentSpec], inputs: str, extra: str, w: "_Work",
              template: str = "") -> None:
        while len(w.done) + len(w.blocked) < len(agents) and w.turn < w.max_turns:
            for agent in agents:           # the roles take turns; one that has finished is not asked again
                if agent.agent_id in w.done or agent.agent_id in w.blocked:
                    continue
                act, inp, resp, gap = self._turn(agent, step, n, inputs, w.completed, w.max_turns - w.turn, extra,
                                                 template)
                w.contributions.append({"turn": w.turn + 1, "agent": agent.name, "action": act,
                                        "input": inp[:400], "final": FINAL_OUTPUT in act, "blocked": gap})
                w.last_message = inp.strip()
                if gap is not None:
                    w.blocked[agent.agent_id] = gap
                    w.partial[agent.agent_id] = inp.strip()
                    w.completed += f">{agent.name} {BLOCKED}: {gap}\n{inp.strip()}\n"
                elif act in agent.tools:
                    w.tool_results.append(resp)
                    w.calls.append({"agent_id": agent.agent_id, "agent": agent.name, "tool": act, "ok": tool_ok(resp),
                                    "input": inp.strip()[:200], "result": re.sub(r"\s+", " ", resp or "").strip()[:300]})
                    w.completed += f">{agent.name} ({act}):\n{inp.strip()}\n>Result:\n{resp.strip()}\n"
                elif FINAL_OUTPUT in act:
                    w.done[agent.agent_id] = inp.strip()
                    w.completed += f">{agent.name} Final Output:\n{inp.strip()}\n"
                else:
                    w.completed += f">{agent.name} ({act or 'no action'}):\n{inp.strip()}\n>Result:\n{resp.strip()}\n"
            w.turn += 1

    @staticmethod
    def _text(agents: list[AgentSpec], w: "_Work") -> str:
        written = {a.agent_id: w.done.get(a.agent_id) or w.partial.get(a.agent_id) for a in agents}
        written = {k: v for k, v in written.items() if v}
        # D44: no Final Output from anyone → only the last helper message goes on, not the whole work log
        if len(agents) == 1:
            return next(iter(written.values()), "") or w.last_message
        return "\n\n".join(f"### {a.name}\n{written[a.agent_id]}" for a in agents
                           if a.agent_id in written) or w.last_message

    # box: artifacts
    def _save(self, n: int, wave: int, text: str, meta: dict, prov: dict) -> None:
        self.artifacts[n] = {"text": text, "meta": meta}
        self.ep.steps.append(meta)
        self.i.trace.event("step_done", {"amoeba.step": n, "amoeba.wave": wave, "amoeba.status": meta["status"],
                                         "amoeba.status_reason": meta["status_reason"], "amoeba.turns": meta["turns"],
                                         "amoeba.output_chars": len(text), "amoeba.rework": bool(meta["rework_of"]),
                                         "amoeba.checks_failed": [c["name"] for c in meta["checks"] if not c["pass"]],
                                         "amoeba.verdict": meta.get("verdict")})
        self.i.trace.event("provenance", {"amoeba.step": n, **{f"amoeba.provenance.{k}": v for k, v in prov.items()
                                                               if k != "untagged_examples"}})
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)
            suffix = ".rework" if meta["rework_of"] or meta.get("reverify_of") or meta.get("rerun_of_stale") else ""
            if suffix and (self.dir / f"step_{n}.md").exists():      # keep the first version next to the rework
                (self.dir / f"step_{n}.md").rename(self.dir / f"step_{n}.first.md")
                (self.dir / f"step_{n}.json").rename(self.dir / f"step_{n}.first.json")
            (self.dir / f"step_{n}.md").write_text(text + "\n", encoding="utf-8")
            self._write(n)

    def _write(self, n: int) -> None:
        if self.dir:
            (self.dir / f"step_{n}.json").write_text(json.dumps(self.artifacts[n]["meta"], indent=2, ensure_ascii=False),
                                                   encoding="utf-8")

    # box: plan_step
    def _turn(self, agent: AgentSpec, step: PlanStep, n: int, inputs: str, completed: str, turns_left: int,
              extra: str = "", template: str = "") -> tuple[str, str, str, str | None]:
        tools = list(agent.tools) + [PRINT, FINAL_OUTPUT]
        user = render(template or PROMPT.plan_step, task=self.task.prompt, deliverables=self.deliverables_text(), card=plan_card(agent), number=n,
                      step=step_detail(step) + extra, inputs=inputs, completed=completed.strip() or "Nothing yet.",
                      tools=str(tools), turns_left=turns_left,
                      unavailable="\n".join([UNAVAILABLE.format(name=t) for t in agent.missing_tools]
                                             + pool_tool_notes(agent)))   # D56
        c = self.current_contract.get(agent.name)
        if c and (c["needs"] or c["items"]):     # D61: what plain code will check, on the helper's prompt
            items = [*(f"{x} (asked for, not available)" for x in c["needs"]),
                     *(f"{x['name']} (given to you)" for x in c["items"])]
            user = user.replace("\n# Format\n", f"\n{CONTRACT_LINE.format(items='; '.join(items))}\n\n# Format\n", 1)
        system = render(PROMPT.plan_step_system, name=agent.name)
        with self.i.trace.span("invoke_agent", {"gen_ai.agent.id": agent.agent_id, "gen_ai.agent.name": agent.name,
                                                "amoeba.box": "plan_summary" if self.is_summary_step(step) else "plan_step",
                                                "amoeba.step": n}):
            before = self.i.trace.n_llm_calls
            group = role_group(is_summariser=agent.is_summariser, reviewing=self.is_verification(step))   # D54
            raw, sec = self.i.llm.chat_sections(system, user, PLAN_SECTIONS, self.ep.seed, agent_id=agent.agent_id,
                                              agent_name=agent.name, max_tokens=PLAN_MAX_TOKENS, role=group)
            for rec in self.i.trace.spans("chat")[before:]:
                self.i._record(agent, self.ep, raw, rec.get("gen_ai.usage.input_tokens", 0),
                               rec.get("gen_ai.usage.output_tokens", 0))
            act, inp = sec["Action"].strip(), full_action_input(raw, sec["ActionInput"])
            resp, gap = self.i._dispatch(agent, act, inp, step.index, self.ep)
        return act, inp, resp, gap

    # ---- D63: the Action Observer (mid-run re-plan) ----------------------------------------------------------------
    # box: action_obs
    def plan_items(self) -> set[str]:
        """What the plan names: every role's drafted tools and missing tools and every capability request (name and
        standard name); not the items the toolbox step attached. web_search stands for both web tools (D32 grants them
        together)."""
        names = {t for a in self.agents.values() for t in (*a.tools, *a.missing_tools)
                 if t not in {p["name"] for p in a.pool}}          # what the toolbox step attached is not the plan's
        for q in self.cfg.meta.get("capability_requests", []):
            names.update(x for x in (q.get("name"), q.get("canonical")) if x)
        if any(normalise(n)[0] == "web_search" for n in names):
            names.update(WEB_TOOLS)
        return names

    # box: action_obs
    def held_items(self) -> dict[str, list[str]]:
        """Each tool or skill a helper holds now -> the helpers holding it."""
        out: dict[str, list[str]] = {}
        for a in self.agents.values():
            for t in [*a.tools, *(p["name"] for p in a.pool if p["kind"] == "skill")]:
                out.setdefault(t, []).append(a.name)
        return out

    # box: action_obs
    def replan_triggers(self, wave_steps: list[int]) -> list[dict]:
        """D63: what plain code found after a wave. Each trigger fires once per step (or item)."""
        out = []
        for n in wave_steps:
            m = self.artifacts[n]["meta"]
            if m["status"] in ("partial", "incomplete") and m.get("blocked"):
                out.append({"kind": "missing_capability", "step": n, "detail": f"step {n} is {m['status']}: lacked "
                                                                                f"{', '.join(m['blocked'])}"})
            if m.get("verification") and m.get("verdict") == "FAIL":
                again = " after rework" if m.get("verdict_after_rework") else " (no rework was possible)"
                out.append({"kind": "verify_fail", "step": n, "detail": f"verify step {n} still says FAIL{again}: "
                                                                          f"{(m.get('issues') or '')[:300]}"})
            for miss in missing_input_marks(self.artifacts[n]["text"]):
                out.append({"kind": "missing_input", "step": n, "detail": f"step {n} reports a missing input: {miss}"})
        unrun = {a for s in self.cfg.plan if number(s) not in self.artifacts for a in s.agent_ids}
        holders = {a.name for a in self.agents.values() if a.agent_id in unrun}
        for item, who in sorted(self.held_items().items()):
            if item in (PRINT, FINAL_OUTPUT) or any(names_match(item, k) for k in self.known):
                continue
            later = [h for h in who if h in holders]
            if later:
                out.append({"kind": "new_tool", "item": item, "detail": f"{', '.join(later)} now hold(s) {item}, "
                                                                        f"which the plan never named"})
        fresh = []
        for t in out:
            key = (t["kind"], t.get("step"), t.get("item"))
            if key not in self.triggered:
                self.triggered.add(key)
                fresh.append(t)
        return fresh

    # box: action_obs
    def action_observer(self, wave: int) -> None:
        """D63: after a wave, one planner call when plain code found a trigger and steps remain; the decision is
        validated and applied by code, or recorded as rejected (then the plan stays as it is)."""
        wave_steps = [m["step"] for m in self.ep.steps if m["wave"] == wave]
        triggers = self.replan_triggers(list(dict.fromkeys(wave_steps)))
        unrun = [number(s) for s in self.cfg.plan if number(s) not in self.artifacts]
        if not triggers:
            return
        self.i.trace.event("replan_trigger", {"amoeba.wave": wave, "amoeba.triggers": [t["detail"] for t in triggers],
                                              "amoeba.kinds": [t["kind"] for t in triggers],
                                              "amoeba.called": bool(unrun) and len(self.replans) < self.opt.max_replans})
        if not unrun or len(self.replans) >= self.opt.max_replans:
            return
        record = {"wave": wave, "triggers": triggers}
        raw = self._observer_call(triggers)
        dec = parse_decision(raw)
        record["decision"], record["reason"] = dec["decision"], dec["reason"]
        self.i.trace.event("replan_decision", {"amoeba.wave": wave, "amoeba.decision": dec["decision"],
                                               "amoeba.reason": dec["reason"][:300], "amoeba.readable": dec["readable"]})
        if dec["decision"] == "CONTINUE":
            record.update(accepted=True, errors=[] if dec["readable"] else ["unreadable reply: treated as CONTINUE"],
                          changes={})
        else:
            errors, change = self.validate_decision(dec)
            record.update(accepted=not errors, errors=errors, changes=change.get("summary", {}) if not errors else {})
            if not errors:
                self.apply_decision(dec, change)
        self.i.trace.event("replan_validated", {"amoeba.wave": wave, "amoeba.decision": dec["decision"],
                                                "amoeba.accepted": record["accepted"], "amoeba.errors": record["errors"],
                                                "amoeba.changes": record["changes"]})
        self.replans.append(record)

    def _observer_call(self, triggers: list[dict]) -> str:
        user = render(PROMPT.plan_replan, task=self.task.prompt, requirements=self.deliverables_text(),
                      triggers="\n".join(f"- {t['detail']}" for t in triggers), plan=self.plan_text(),
                      outputs=self.finished_text(), blocked=self.blocked_text(), tools=self.tools_text(),
                      roles=self.roles_text(),
                      left=(f"{self.opt.max_replans - len(self.replans) - 1} more re-plan(s) after this one; "
                              f"{self.opt.max_added_steps - self.added_steps} step(s) may still be added; "
                              f"{'no' if self.roles_added else 'one'} new role may still be added"),
                      next=str(self.max_num + 1))
        with self.i.trace.span("invoke_agent", {"gen_ai.agent.name": "action_observer", "amoeba.box": "action_obs"}):
            resp = self.i.llm.chat_messages([{"role": "user", "content": user}], self.ep.seed,
                                            agent_name="action_observer", max_tokens=PLAN_MAX_TOKENS, role="planner")
        self.ep.total_tokens += resp.input_tokens + resp.output_tokens
        self.ep.n_llm_calls += 1
        return resp.content or ""

    # ---- what the observer is shown --------------------------------------------------------------------------------
    def plan_text(self) -> str:
        lines = []
        for s in self.cfg.plan:
            n = number(s)
            st = self.artifacts[n]["meta"]["status"] if n in self.artifacts else "not run"
            roles = ", ".join(self.agents[a].name for a in s.agent_ids)
            head = re.sub(r"^\s*\[.*?\]\s*:\s*", "", s.text).strip()
            lines.append(f"{n}. [{roles}]: {head} — status: {st}; kind: {s.kind or 'work'}; covers: "
                         f"{', '.join(s.covers) or '-'}; depends_on: {', '.join(map(str, s.depends_on)) or 'none'}")
        return "\n".join(lines)

    def finished_text(self) -> str:
        parts = []
        for n, a in sorted(self.artifacts.items()):
            m = a["meta"]
            src = "; ".join(f"[{x['id']}] {x['title'][:60]} ({x['url'][:80]})" for x in m.get("sources", [])[:5])
            files = ", ".join(f["path"] for f in m.get("files_made", []) or self.files_of(n))
            parts.append(f"## Step {n}, status {m['status']}{' (' + m['status_reason'] + ')' if m['status_reason'] else ''}"
                         f"{'; verdict ' + m['verdict'] if m.get('verdict') else ''}\n"
                         f"{head_tail(a['text'], 700)}\nsources: {src or 'none'}; files: {files or 'none'}")
        return "\n\n".join(parts) or "None yet."

    def blocked_text(self) -> str:
        lines = [f"- step {n}: lacked {', '.join(a['meta']['blocked'])}" for n, a in sorted(self.artifacts.items())
                 if a["meta"].get("blocked")]
        asked = [q for q in self.cfg.meta.get("capability_requests", []) if q.get("status") == "unfilled"]
        lines += [f"- request {q['name']} for {q['for_role']}: unfilled ({q.get('reason') or 'no reason'})" for q in asked]
        return "\n".join(lines) or "Nothing."

    def tools_text(self) -> str:
        held = self.held_items()
        lines = [f"- {t}: held by {', '.join(w)}" for t, w in sorted(held.items())]
        spare = [t for t in self.i.tools.names() if t not in held] if hasattr(self.i.tools, "names") else []
        if spare:
            lines.append(f"- in this run but held by no role (a step can use them if its role gets them): "
                         f"{', '.join(sorted(spare))}")
        if self.local is not None and getattr(self.local, "exposed", None):
            lines.append(f"- local tools a new request can be filled with: "
                         f"{', '.join('local:' + n for n in self.local.exposed)}; local skills: "
                         f"{', '.join(s['name'] for s in getattr(self.local, 'skills', [])[:20]) or 'none'}")
        if self.pool is not None or getattr(self.i, "stock", None):
            lines.append("- a tool pool exists: a capability request is tried against it by plain code")
        return "\n".join(lines)

    def roles_text(self) -> str:
        return "\n".join(f"- {a.name}{' (writes the final answer)' if a.is_summariser else ''}: {a.goal or a.description[:120]}"
                         for a in self.agents.values())

    # ---- validation and application -------------------------------------------------------------------------------
    # box: action_obs
    def validate_decision(self, dec: dict) -> tuple[list[str], dict]:
        """D63: the Box 2 rules for a proposed change, and the change itself when they all hold. Finished steps are
        never touched; new steps may depend only on finished or new steps; roles must exist (or be the one role this
        decision adds, with a complete card); the team stays within its size; the graph has no cycle; at most 3 added
        steps per run and one added role."""
        errors: list[str] = []
        finished = set(self.artifacts)
        unrun = {number(s) for s in self.cfg.plan if number(s) not in finished}
        kind = dec["decision"]
        roles = {a.name: a.agent_id for a in self.agents.values()}
        new_role = None
        if kind == "ADD_ROLE":
            if self.roles_added >= 1:
                errors.append("a role was already added in this run (at most one)")
            blobs = parse_json_objects(dec["role"])
            if not blobs:
                errors.append("ADD_ROLE without a role JSON blob")
            else:
                new_role = DraftedRole(**blobs[0])
                missing = [k for k in ("name", "goal", "outputs", "success_criteria") if not getattr(new_role, k)]
                if not (new_role.prompt or new_role.description):
                    missing.append("prompt")
                if missing:
                    errors.append(f"incomplete role card: no {', '.join(missing)}")
                if new_role.name in roles:
                    errors.append(f"role {new_role.name!r} already exists")
                if len(self.agents) + 1 > getattr(self.i, "max_agents", 5):
                    errors.append(f"the team would have {len(self.agents) + 1} roles (at most "
                                  f"{getattr(self.i, 'max_agents', 5)})")
                roles = {**roles, new_role.name: "NEW"}
        requests = [q for q in parse_json_objects(dec["requests"]) if str(q.get("name", "")).strip()]
        for q in requests:
            if q.get("for_role") and q["for_role"] not in roles:
                errors.append(f"capability request {q['name']!r} is for an unknown role {q['for_role']!r}")
        change: dict = {"kind": kind, "new_role": new_role, "requests": requests, "steps": [], "drop": [],
                        "reassign": None, "feeds": {}}
        if kind in ("REVISE_REMAINING", "ADD_STEP", "ADD_ROLE"):
            parsed = parse_plan_d24(re.sub(r"(?im)^\s*feeds\s*:.*$", "", dec["steps"]))
            if not parsed:
                errors.append(f"{kind} without steps in the Execution Plan format")
            numbered = [int(x) for x in re.findall(r"(?m)^\s*(\d+)\.\s", "\n" + dec["steps"])]
            new_nums = numbered[:len(parsed)] if len(numbered) >= len(parsed) else \
                list(range(self.max_num + 1, self.max_num + 1 + len(parsed)))
            batch = set(new_nums)
            for num, (names, first, fields) in zip(new_nums, parsed):
                who = [r for r in roles if r in names] or [r for r in roles if r.replace("_", " ") in first.split(":")[0]]
                if not who:
                    errors.append(f"step {num} names no role on the team ({', '.join(names) or first[:40]!r})")
                if num in finished:
                    errors.append(f"step {num} has already run; finished steps cannot change")
                if kind != "REVISE_REMAINING" and num in unrun:
                    errors.append(f"step {num} already exists; number new steps from {self.max_num + 1}")
                bad = [d for d in fields["depends_on"] if d not in finished and d not in batch]
                if bad:
                    errors.append(f"step {num} depends on step(s) {bad}, which are neither finished nor new")
                if num in fields["depends_on"]:
                    errors.append(f"step {num} depends on itself")
                change["steps"].append({"number": num, "roles": who, "text": first.strip(), "fields": fields})
            if kind == "ADD_STEP":
                if len(parsed) > 1:
                    errors.append("ADD_STEP adds exactly one step")
                feeds = re.search(r"(?im)^\s*feeds\s*:\s*(.+)$", dec["steps"])
                targets = [int(x) for x in re.findall(r"\d+", feeds.group(1))] if feeds else []
                wrong = [t for t in targets if t not in unrun]
                if wrong:
                    errors.append(f"feeds names step(s) {wrong} that are not waiting to run")
                if new_nums:
                    change["feeds"] = {new_nums[0]: [t for t in targets if t in unrun]}
            if kind == "ADD_ROLE" and new_role and not any(new_role.name in s["roles"] for s in change["steps"]):
                errors.append(f"no step for the new role {new_role.name!r}")
            added = len([n for n in batch if n not in unrun])
            if self.added_steps + added > self.opt.max_added_steps:
                errors.append(f"{added} new step(s) would pass the cap of {self.opt.max_added_steps} added steps per run "
                              f"({self.added_steps} added so far)")
            if kind == "REVISE_REMAINING":
                change["drop"] = sorted(unrun - batch)
            change["added"] = added
        elif kind == "REASSIGN_STEP":
            num, role = step_field(dec["steps"], "step"), (step_field(dec["steps"], "role", as_text=True) or "").strip()
            if num not in unrun:
                errors.append(f"step {num} is not waiting to run; only such a step can be reassigned")
            if role not in roles:
                errors.append(f"role {role!r} is not on the team")
            change["reassign"] = (num, role)
        elif kind == "DROP_STEP":
            num = step_field(dec["steps"], "step")
            if num not in unrun:
                errors.append(f"step {num} is not waiting to run; only such a step can be dropped")
            elif num == self.answer_n:
                errors.append(f"step {num} writes the final answer and cannot be dropped")
            else:
                reqs = re.findall(r"R\d+", dec["unmet"]) or list(self.steps[num].covers)
                change["unmet"] = {r: re.sub(r"\s+", " ", dec["unmet"]).strip()[:200] or dec["reason"][:200] for r in reqs}
            change["drop"] = [num] if num in unrun else []
        else:
            errors.append(f"unknown decision {kind!r}")
        if not errors and kind in ("REVISE_REMAINING", "ADD_STEP", "ADD_ROLE", "DROP_STEP"):
            if self.answer_n is not None and self.answer_n in change["drop"]:
                errors.append(f"step {self.answer_n} writes the final answer and cannot be dropped")
            else:
                try:
                    waves(self.proposed_plan(change, {**{a.name: a.agent_id for a in self.agents.values()},
                                                      **({new_role.name: "NEW"} if new_role else {})}))
                except PlanGraphError as e:
                    errors.append(f"the new plan is unusable: {e}")
        change["summary"] = {"steps_added": sorted(s["number"] for s in change["steps"] if s["number"] not in unrun),
                             "steps_rewritten": sorted(s["number"] for s in change["steps"] if s["number"] in unrun),
                             "steps_dropped": change["drop"], "reassigned": change["reassign"],
                             "role_added": new_role.name if new_role else None,
                             "requests": [q["name"] for q in requests]}
        return errors, change

    def proposed_plan(self, change: dict, ids: dict[str, str]) -> list[PlanStep]:
        """The plan after `change` (steps sorted by number; a dropped step's dependants point at its dependencies)."""
        drop = set(change["drop"])
        written = {number(s): list(s.depends_on) for s in self.cfg.plan}
        by = {number(s): s for s in self.cfg.plan if number(s) not in drop}
        for s in change["steps"]:
            f = s["fields"]
            text = re.sub(r"^\s*\d+\.\s*", "", s["text"])
            by[s["number"]] = PlanStep(index=s["number"] - 1, agent_ids=[ids[r] for r in s["roles"]], text=text,
                                       kind=f.get("kind", ""), covers=f.get("covers", []),
                                       depends_on=f.get("depends_on", []), do=f.get("do", ""),
                                       output=f.get("output", ""), done_when=f.get("done_when", ""))
        if change.get("reassign"):
            num, role = change["reassign"]
            s = by[num]
            text = re.sub(r"^\s*\[.*?\]", f"[{role}]", s.text) if s.text.lstrip().startswith("[") else s.text
            by[num] = s.model_copy(update={"agent_ids": [ids[role]], "text": text})
        new = {s["number"] for s in change["steps"] if s["number"] not in {number(x) for x in self.cfg.plan}}
        for n, targets in change.get("feeds", {}).items():
            for t in targets:
                by[t] = by[t].model_copy(update={"depends_on": list(dict.fromkeys([*by[t].depends_on, n]))})
        if self.answer_n is not None and self.answer_n in by and self.answer_n not in self.artifacts:
            a = by[self.answer_n]                       # the answer step waits for every new step
            by[self.answer_n] = a.model_copy(update={"depends_on": list(dict.fromkeys([*a.depends_on, *sorted(new)]))})
        plan = [by[n] for n in sorted(by)]
        plan, _ = relink(plan, written)
        return plan

    # box: action_obs
    def apply_decision(self, dec: dict, change: dict) -> None:
        """D63: an accepted decision takes effect: the new role joins the team, capability requests go through the
        normal toolbox step, the plan is replaced (finished steps unchanged), a dropped requirement is recorded as
        not met, and the new version of the plan is saved with its diff."""
        ids = {a.name: a.agent_id for a in self.agents.values()}
        if change["new_role"] is not None:
            r = change["new_role"]
            known = set(self.i.tools.names()) if hasattr(self.i.tools, "names") else set()
            have, lack = [t for t in r.tools if t in known], [t for t in r.tools if t not in known]
            template = next(iter(self.agents.values()))
            aid = str(uuid4())
            agent = template.model_copy(deep=True, update={
                "agent_id": aid, "name": r.name, "tools": have, "missing_tools": lack, "is_summariser": False,
                "goal": r.goal, "skills": list(r.skills), "outputs": list(r.outputs),
                "success_criteria": list(r.success_criteria), "constraints": list(r.constraints),
                "role_prompt": r.prompt or r.description, "description": r.description or r.prompt,
                "suggestions": r.suggestions, "pool": [], "created_by": "drafter"})
            self.agents[aid] = agent
            self.cfg.agents[aid] = agent.model_copy(deep=True)
            ids[r.name] = aid
            self.roles_added += 1
            change["requests"] += [{"name": t, "kind": "tool", "for_role": r.name,
                                    "what_it_does": "named in the new role's tools; no such tool is registered"}
                                   for t in lack if not any(q.get("name") == t for q in change["requests"])]
        if change["requests"]:
            self.restock([CapabilityRequest(**{**q, "source": "planner"}) for q in change["requests"]])
        if change["kind"] != "CONTINUE":
            old = {number(s): s for s in self.cfg.plan}
            self.cfg.plan = self.proposed_plan(change, ids)
            self.steps = {number(s): s for s in self.cfg.plan}
            self.max_num = max(self.max_num, *self.steps)
            self.added_steps += change.get("added", 0)
            for r, why in change.get("unmet", {}).items():
                self.unmet[r] = why
            for n in change["drop"]:                     # a requirement only the dropped step covered is not met
                for r in old[n].covers:
                    if not any(r in s.covers for s in self.cfg.plan):
                        self.unmet.setdefault(r, f"step {n} was dropped by a re-plan: {dec['reason'][:160]}")
            self.save_plan_version(change["summary"])

    def restock(self, requests: list) -> None:
        """D63: new capability requests go through the normal toolbox step (pool and local tools), mid-run."""
        stock = getattr(self.i, "stock", None)
        cfg = self.cfg.model_copy(update={"agents": self.agents})
        if stock is None:
            for q in requests:
                q.status, q.reason = "unfilled", "no_toolbox"
        else:
            reg, summary = stock(requests, cfg, self.i.tools)
            self.i.tools = reg
            self.pool = getattr(reg, "pool", None)
            self.local = getattr(reg, "local", None)
        for q in requests:
            self.cfg.meta.setdefault("capability_requests", []).append(
                {"name": q.name, "for_role": q.for_role, "canonical": q.canonical, "status": q.status,
                 "reason": q.reason, "source": "replan"})
            self.known.update(x for x in (q.name, q.canonical) if x)
        if self.web is not None:
            self.grant_web_tools()
        for a in self.agents.values():                  # what the toolbox step attached is known to the plan now
            self.known.update(a.tools)
            self.known.update(p["name"] for p in a.pool)

    def save_plan_version(self, diff: dict | None) -> None:
        """plan.v1.json is the plan the run started with; each accepted re-plan writes the next version and its diff."""
        if diff is not None:
            self.plan_version += 1
        rec = {"version": self.plan_version, "diff": diff,
               "roles": [{"name": a.name, "tools": a.tools, "missing_tools": a.missing_tools} for a in self.agents.values()],
               "steps": [{"number": number(s), "roles": [self.agents[x].name for x in s.agent_ids], "text": s.text,
                          "kind": s.kind, "covers": s.covers, "depends_on": s.depends_on, "do": s.do,
                          "output": s.output, "done_when": s.done_when,
                          "status": self.artifacts[number(s)]["meta"]["status"] if number(s) in self.artifacts
                          else "not run"} for s in self.cfg.plan]}
        self.i.trace.event("plan_version", {"amoeba.version": self.plan_version, "amoeba.diff": diff})
        if self.run_dir is not None:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            (self.run_dir / f"plan.v{self.plan_version}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False),
                                                                          encoding="utf-8")

    # box: action_obs
    def requirement_status(self) -> dict[str, dict]:
        """D63: each requirement's final status — met (a covering step is done, and no failing check says
        otherwise), partly (only partial or incomplete covering steps), not met (no covering step ran, or a re-plan
        dropped it) — and the step(s) that met it."""
        out = {}
        for r in self.cfg.requirements or {}:
            if r in self.unmet:
                out[r] = {"status": "not met", "steps": [], "why": self.unmet[r]}
                continue
            cover = [n for n, a in sorted(self.artifacts.items()) if r in a["meta"].get("covers", [])]
            done = [n for n in cover if self.artifacts[n]["meta"]["status"] == "done"
                    and self.artifacts[n]["meta"].get("verdict") != "FAIL"]
            out[r] = {"status": "met" if done else "partly" if cover else "not met", "steps": done or cover}
            if not cover:
                out[r]["why"] = "no step that ran covers it"
        return out

    def replan_summary(self) -> dict:
        status = self.requirement_status()
        for r, v in status.items():
            self.i.trace.event("requirement_status", {"amoeba.requirement": r, "amoeba.status": v["status"],
                                                      "amoeba.steps": v["steps"]})
        return {"calls": len(self.replans), "accepted": sum(1 for x in self.replans if x["accepted"]
                                                            and x["decision"] != "CONTINUE"),
                "rejected": sum(1 for x in self.replans if not x["accepted"]),
                "decisions": [{k: x.get(k) for k in ("wave", "decision", "reason", "accepted", "errors", "changes")}
                              | {"triggers": [t["detail"] for t in x["triggers"]]} for x in self.replans],
                "steps_added": self.added_steps, "roles_added": self.roles_added, "plan_versions": self.plan_version,
                "requirements": status}


MISSING_INPUT_NOTE = """

If an input this step needs is missing from your inputs (a step you depend on did not deliver it), do what you can and
put a line "MISSING INPUT: <what> — <which step should have given it>" in your Final Output."""
DECISIONS = ("CONTINUE", "REVISE_REMAINING", "ADD_STEP", "REASSIGN_STEP", "DROP_STEP", "ADD_ROLE")


# box: step_check
def missing_input_marks(text: str) -> list[str]:
    """D63: the 'MISSING INPUT: <what>' lines of a step's output."""
    return [m.group(1).strip() for m in re.finditer(r"MISSING\s+INPUT\s*[:：]\s*(.+)", text or "", re.I)]


def head_tail(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit // 2].rstrip()}\n[… {len(text) - limit:,} characters omitted …]\n{text[-limit // 2:].lstrip()}"


def step_field(body: str, key: str, as_text: bool = False):
    """'step: 3' / 'role: Analyst' lines of a REASSIGN or DROP decision."""
    m = re.search(rf"(?im)^\s*[-*]?\s*{key}\s*:\s*(.+)$", body or "")
    if not m:
        return None
    if as_text:
        return m.group(1).strip().strip("[]`\"'")
    d = re.search(r"\d+", m.group(1))
    return int(d.group(0)) if d else None


# box: action_obs
def parse_decision(raw: str) -> dict:
    """D63: the observer's reply → {decision, reason, steps, role, unmet, requests, readable}. A reply without a known
    decision is unreadable and counts as CONTINUE."""
    body = re.sub(r"<(thought|think|thinking)\b[^>]*>.*?</\1\s*>", "", raw or "", flags=re.S | re.I)
    sec = {k.lower().rstrip(":").strip(): v for k, v in parse_sections(body).items()}
    word = re.search(r"\b(" + "|".join(DECISIONS) + r")\b", (sec.get("decision") or "").upper())
    none = lambda v: "" if re.fullmatch(r"\s*(none\.?|n/a|-)?\s*", v or "", re.I) else (v or "").strip()
    return {"decision": word.group(1) if word else "CONTINUE", "readable": bool(word),
            "reason": none(sec.get("reason")), "steps": none(sec.get("steps")), "role": none(sec.get("role")),
            "unmet": none(sec.get("unmet")), "requests": none(sec.get("capability requests"))}
