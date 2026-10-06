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
from datetime import date
from pathlib import Path

from amoeba.adapt.evidence import EvidenceLog
from amoeba.adapt.fixes import POOL_OFF, candidates, fix_key, limits as fix_limits
from amoeba.adapt.stuck import diagnose, file_sig, is_stuck, step_signals
from amoeba.capabilities import normalise
from amoeba.config.prompts import PROMPT, render
from amoeba.config.schema import AgentSpec, PlanStep, TeamConfig
from amoeba.interp.citecheck import mislabelled_citations
from amoeba.interp.dates import undated_figures
from amoeba.task.deliverables import final_findings
from amoeba.interp.disputes import disputed_figures, disputes_text, replace_figure, settle
from amoeba.interp.replan_method import failed_method, failed_methods_text, method_change, replaces
from amoeba.interp.provenance import (check_provenance, claim_numbers, computed_values, numbers_in,
                                      strip_unverified)
from amoeba.interp.freshness import stale_figure, time_sensitive
from amoeba.interp.shorten import shorten
from amoeba.llm.limits import estimate
from amoeba.llm.profiles import role_group
from amoeba.llm.router import NoModelAvailable
from amoeba.pool.stock import pool_skill_notes, pool_tool_notes
from amoeba.localtools.claims import claimed_files
from amoeba.interp.runtime import BLOCKED, FINAL_OUTPUT, PRINT, UNAVAILABLE, _output_text, full_action_input
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
    # D90: on = a verify step first works out its own result from the checked steps' inputs and its tools, without
    # their outputs (a separate turn loop, plan_verify_own.txt); only then are the outputs shown and compared. Both
    # are recorded in step_N.json. The CLI default is on; this library default keeps the earlier behaviour.
    verify_first: str = "off"
    # D109 (amended): on = plain code compares the verifier's own result (D90) with the checked outputs' figures by
    # label; each disagreement goes to the resolver, one fresh call that settles it against the source text or a re-run
    # (code checks the evidence); a settled value replaces the wrong one, an unresolved one makes the step partial and
    # stays. A PASS never overrides it. The CLI default is on; this library default keeps the earlier behaviour.
    disputes: str = "off"
    # D108: on = a step a re-plan adds or rewrites for a failed step must change the method (a different tool, source
    # type or a decomposed query, stated in the step); the observer is shown each failed step's method. The CLI
    # default is on; this library default keeps the earlier behaviour.
    replan_method: str = "off"
    # D110: on = every web-sourced figure of the final answer must carry its source's date (publication or data
    # period); missing → the refine turn, then listed in Limitations. The CLI default is on; this library default
    # keeps the earlier behaviour.
    dated: str = "off"
    # D105 (amended): on = after the summariser, plain code checks each Box 2 requirement and each promised file
    # against the FINAL answer and the workspace (with D110's dates: one final-answer requirement check); missing →
    # the refine turn, then Limitations, and no_deliverable when a core deliverable is missing. CLI default on.
    final_check: str = "off"
    # D104: on = the citation check (D74) leaves out calculation results shown on the line, powers and year ranges.
    # The CLI default is on; this library default keeps the earlier behaviour.
    cite_arithmetic: str = "off"
    # D113: on = after a step that made an .xlsx file, plain code checks that totals and derived cells are formulas,
    # not typed numbers (amoeba/checks/xlsx_formulas.py); a typed one fails the check. The CLI default is on; this
    # library default keeps the earlier behaviour.
    xlsx_formulas: str = "off"
    # D117 Stage B: on = after each step attempt plain code looks for the stuck signals (amoeba/adapt/stuck.py); a
    # step that did not end done with a signal is STUCK: one cause is diagnosed from adapt.yaml, the event goes to the
    # trace, step_N.json and the run's hash-chained events.jsonl. Stage C: a stuck step then gets code fixes, cheapest
    # first (amoeba/adapt/fixes.py), within the limits of adapt.yaml `adapt`; when they all fail the task stops with a
    # report. The CLI default is on; this library default keeps the earlier behaviour.
    adapt: str = "off"
    max_replans: int = 2             # D63: observer calls per run
    max_added_steps: int = 3         # D63: steps added per run, over all accepted decisions
    domain_checks: tuple = ()        # D102: the niche profile's checks (amoeba/checks/<name>.py) after each step


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
FRESH_NOTE = """

This task asks for today's, the current or the latest value. Find the most recent official figure and write its date
next to it ("as of <date>"). If the figure you found is dated before today, make one more search for a newer value
before you use it, and say which date you settled on."""
RESEARCH_NOTE = """

Research (plain code helps here): search one entity, one year or period and one data series at a time — never pack
several places, years or series into one web_search (plain code splits a packed query anyway). Each search also
shows excerpts of its top results, official sources first, and the tables of any data files (.csv, .xlsx, .json)
they link, each with its own [S#]. Prefer the official source and the data file over a news story or a snippet;
when a figure rests only on a search snippet, say so."""
SOURCES_NOTE = """

Fetched data is in your workspace: every page and data file the web tools have read so far is saved read-only under
sources/ (data tables as CSV, pages as text); sources/index.json lists each file with its [S#], url and date. Read
and compute from these files with your local tools, and cite a figure from a file by that file's [S#]: {files}"""
LAST_TURN_NOTE = ("THIS IS YOUR LAST TURN. No more tool calls: choose Final Output and write your conclusion from what "
                  "you have found so far, with the [S#] of what supports each fact, and say plainly what you could not "
                  "confirm.")
LAST_TURN_AGAIN = ("Your last turn must be Final Output with a written conclusion (not a search query or a tool "
                   "request). Answer now from what you have.")

VERIFY_COMPARE_NOTE = """
Your inputs end with your own result, which you worked out before you saw the steps' outputs. Compare the outputs with
it: where they differ, find out which one is right (re-check with your tools) and list each difference that would
change a number or a conclusion as an issue. Name the differences you found, and which side was right."""
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


# box: step_check
def compare_figures(own: str, outputs: dict[int, str]) -> dict:
    """D90: plain code's comparison of the verifier's own result with the outputs it checks: the figures of its own
    result (labels and [S#] tags left out) that some checked output states too — equal at the coarser of the two
    precisions written (41.60 = 41.6, 1230 ≠ 1229) — and the ones none does."""
    def floats(text):
        out = []
        for tok in claim_numbers(text):
            bare = tok.replace(",", "").strip("$€£%")
            try:
                out.append((tok, float(bare), len(bare.partition(".")[2])))
            except ValueError:
                pass
        return out
    theirs = [(v, d) for text in outputs.values() for _, v, d in floats(text)]
    same = lambda a, da, b, db: abs(round(a, min(da, db)) - round(b, min(da, db))) < 1e-9
    matched, own_only = [], []
    for tok, v, d in sorted(floats(own), key=lambda x: x[1]):
        (matched if any(same(v, d, x, dx) for x, dx in theirs) else own_only).append(tok)
    total = len(matched) + len(own_only)
    return {"own_figures": total, "matched": matched[:30], "own_only": own_only[:30],
            "agreement": round(len(matched) / total, 3) if total else None}


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
        self.requests: list[str] = []           # D76: every tool request / non-final message of the step


# box: step_check
def no_conclusion(text: str, requests: list[str]) -> bool:
    """D76: the step's output is only a search query or a tool request, not a written conclusion: empty, the same as
    one of the step's tool inputs or unanswered requests, Action/ActionInput syntax, or a lone search string (one
    short line with search operators or quoted terms and no sentence)."""
    flat = lambda x: re.sub(r"\s+", " ", x or "").strip().strip("\"'`").strip()
    t = flat(text)
    if not t:
        return True
    if t in {flat(r) for r in requests if r}:
        return True
    if re.match(r"^(?:#+\s*)?(?:Action|ActionInput)\b", t, re.I) or re.fullmatch(r"https?://\S+", t):
        return True
    one_line = "\n" not in (text or "").strip() and len(t.split()) <= 15
    searchy = re.search(r"\bsite:\S|\bintitle:|\"[^\"]+\"\s+\S|\bOR\b", text or "")
    return bool(one_line and searchy and not re.search(r"[.!?]\s|[.!?]$|\[S\d+\]", t))


EVIDENCE_CAP = 20_000     # D76: characters of raw evidence a verify step gets in all
STOP = set("that this with from have were will your their there which about would could should these those than "
           "then them they been into only also more most such other what when where while after before under over "
           "each some very just here step steps source sources result results output figure figures".split())


# box: step_check
def claim_terms(text: str) -> dict:
    """D76: what the claims being checked are made of: their numbers and times, quoted phrases, and the words of the
    lines that cite a source."""
    nums = {m.group(0).strip("$€£%") for m in re.finditer(r"(?<![\w.])[$€£]?\d[\d,:.]*\d%?|(?<![\w.])\d{2,}", text or "")}
    quotes = [q.lower() for q in re.findall(r"[\"“]([^\"”\n]{6,120})[\"”]", text or "")]
    cited = [l for l in (text or "").splitlines() if re.search(r"\[S\d+", l)]
    words = {w for l in cited for w in re.findall(r"[a-z]{4,}", l.lower()) if w not in STOP}
    return {"numbers": nums, "quotes": quotes, "words": words}


# box: step_check
def excerpt(result: str, wanted: dict, keep_head: int = 240) -> str:
    """D76: the parts of one raw tool result that bear on the claims: its first line (what it is), and every line or
    300-character piece holding one of their numbers, a quoted phrase, or two of their cited words. Omitted parts
    are marked. A result with nothing relevant keeps its head."""
    lines = []
    for line in (result or "").splitlines():
        while len(line) > 400:
            cut = line.rfind(" ", 200, 320)
            cut = cut if cut > 0 else 300
            lines.append(line[:cut])
            line = line[cut:]
        lines.append(line)
    if not lines:
        return ""
    def hit(x: str) -> bool:
        low = x.lower()
        return (any(re.search(rf"(?<![\d.]){re.escape(v)}(?![\d])", x) for v in wanted["numbers"])
                or any(q in low for q in wanted["quotes"])
                or len({w for w in wanted["words"] if w in low}) >= 2)
    keep = [0] + [i for i in range(1, len(lines)) if lines[i].strip() and hit(lines[i])]
    if len(keep) == 1:
        head = "\n".join(lines)[:keep_head]
        return head + ("\n[… rest of this result left out: nothing in it matches the claims checked …]"
                       if len("\n".join(lines)) > keep_head else "")
    out, prev = [], -1
    for i in keep:
        if i > prev + 1:
            out.append("[…]")
        out.append(lines[i])
        prev = i
    if prev < len(lines) - 1:
        out.append("[…]")
    return "\n".join(out)


# box: step_check
def conclusion_check(text: str, w: "_Work") -> list[dict]:
    """D76: a failing `conclusion` check when the output is only a query or a tool request (no check when it passes,
    so step outputs that conclude look as before)."""
    if not no_conclusion(text, [*w.requests, *(c["input"] for c in w.calls)]):
        return []
    return [{"name": "conclusion", "pass": False, "source": "code",
             "detail": "the step's output is a search query or a tool request, not a written conclusion"}]


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
        self.own_results: dict[int, dict] = {}   # D90: each verify step's own result, made once
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
        self.mislabelled: dict[int, list] = {}            # D74: step -> its mislabelled citations (latest version)
        self.disputes: dict[int, list] = {}               # D109: verify step -> its disagreements still open
        self.undated: list[dict] = []                     # D110: web-sourced figures of the answer without a date
        self.final: dict = {}                             # D105 + D110: the final-answer requirement check
        self.max_num = max((number(s) for s in cfg.plan), default=0)
        self.stuck: list[dict] = []                       # D117: every stuck event of this run, in order
        self.step_opts: dict[int, dict] = {}              # D117 Stage C: run options a fix changed, per step
        self.capped: dict[int, set] = {}                  # D117 Stage C: step -> the inputs shortened for it
        self.fixes: list[dict] = []                       # D117 Stage C: every fix tried in this task, in order
        self.fix_keys: set[str] = set()                   # a fix is never tried twice
        self.fix_notes: set[tuple] = set()                # (step, note) of rungs skipped, logged once
        self.upstream_rerun: set[int] = set()             # steps re-run once for a missing input
        self.attached_ids: dict[int, list] = {}           # step -> pool ids a grant gave it
        self.adapt_tokens, self.adapt_spans = 0, []       # what the fix attempts used
        self.exhausted: dict | None = None                # the stuck step no fix recovered (the task stops)

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
            needs = list(dict.fromkeys([*(t for t in a.missing_tools if t not in a.tools), *(q["name"] for q in asked
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
        """D65: the raw tool results every upstream step used (not only their text), for a verify step. D76: as the
        excerpts that bear on the claims being checked (their numbers, times, quotes and the words of the lines
        they cite), at most EVIDENCE_CAP characters in all, with a marker when cut."""
        ups = self.upstream(n)
        wanted = claim_terms("\n".join(self.artifacts[d]["text"] for d in ups))
        parts = []
        for d in ups:
            for r in self.artifacts[d]["meta"].get("tool_results", []):
                parts.append(f"### Step {d} · {r['agent']} → {r['tool']} ({r['input'][:120]!r})\n"
                             f"{excerpt(r['result'], wanted)}")
        if not parts:
            return ""
        body = "\n\n".join(parts)
        if len(body) > EVIDENCE_CAP:
            body = body[:EVIDENCE_CAP].rstrip() + (f"\n[… {len(body) - EVIDENCE_CAP:,} characters of raw evidence left "
                                                   f"out: cap {EVIDENCE_CAP:,} characters …]")
        return ("## Raw tool results of the steps you check (plain code copied the parts that bear on their claims)\n"
                + body)

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
            a.missing_tools = [t for t in a.missing_tools if t not in hits and t not in WEB_TOOLS]
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
                if self.opt.adapt == "on" and self.fix_stuck(n, w):              # D117 Stage C: no fix recovered it
                    return self.stop_report(n)
            if replan:
                self.action_observer(w)
        ws = waves(self.cfg.plan)
        if self.opt.adapt == "on":
            self.ep.adaptation = self.adapt_summary()
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
        self.capped.setdefault(step, set()).add(source)                           # D117 Stage C: larger input
        self.i.trace.event("input_truncated", {"amoeba.step": step, "amoeba.from_step": source, "amoeba.limit": limit,
                                               "amoeba.chars": len(text), "amoeba.what": what,
                                               "amoeba.chars_passed": len(out)})
        return f"{out}\n[shortened by plain code from {len(text):,} characters: head, result lines and tail kept]"

    # box: step_check
    def blind_inputs_text(self, deps: list[int], n: int) -> tuple[str, list[int]]:
        """D90: what a verify step sees before its own result: each step it checks (its instruction, not its output)
        and the outputs that step was given, except those of other steps it checks. Returns the text and the steps
        whose outputs it shows."""
        checked = set(deps)
        all_deps = dependencies(self.cfg.plan)
        given = [d for d in sorted({g for c in deps for g in all_deps.get(c, [])} - checked) if d in self.artifacts]
        parts = []
        for c in deps:
            gets = all_deps.get(c, [])
            names = ", ".join(f"step {g}" + (" (one you check: output not shown)" if g in checked else "")
                              for g in gets) or "the task alone"
            parts.append(f"## Step {c} ({', '.join(self.agents[a].name for a in self.steps[c].agent_ids)}): you check "
                         f"it; its output is not shown yet\n{step_detail(self.steps[c])}\nGiven: {names}")
        for g in given:
            body = self.cap(self.artifacts[g]["text"], self.opt.max_input_chars, n, g, "blind_input")
            parts.append(f"## Output of step {g} (an input of the steps you check)\n{body}")
        return "\n\n".join(parts), given

    # box: step_check
    def own_result(self, step: PlanStep, n: int, deps: list[int], writers: list[AgentSpec], extra: str) -> dict:
        """D90: the verifier's own result, made in a fresh turn loop that never sees the checked steps' outputs (nor
        the team's history). Made once per verify step: a re-check after rework reuses it."""
        if n in self.own_results:
            return {**self.own_results[n], "reused": True}
        inputs, given = self.blind_inputs_text(deps, n)
        w0 = _Work(max_turns=writers[0].limits.max_turns)
        self._loop(step, n, writers, inputs, extra, w0, PROMPT.plan_verify_own)
        text = self._text(writers, w0)
        rec = {"text": text, "turns": w0.turn, "tool_calls": w0.calls, "tool_results": w0.tool_results,
               "outputs_shown": given, "outputs_hidden": list(deps), "input_chars": len(inputs), "reused": False}
        self.own_results[n] = rec
        self.i.trace.event("verifier_own", {"amoeba.step": n, "amoeba.turns": w0.turn,
                                            "amoeba.tool_calls": len(w0.calls), "amoeba.chars": len(text),
                                            "amoeba.outputs_hidden": list(deps), "amoeba.outputs_shown": given})
        return rec

    def inputs_text(self, deps: list[int], n: int | None = None, evidence: bool = False) -> str:
        if not deps:
            return "None: this step starts from the task alone."
        parts = []
        for d in deps:
            a = self.artifacts[d]
            m = a["meta"]
            body = a["text"] if d in self.step_opts.get(n, {}).get("full_from", ()) else \
                self.cap(a["text"], self.so(n, "max_input_chars"), n or 0, d, "input")     # D117: a fix may widen it
            stale = f", STALE (built on step(s) {', '.join(map(str, m['stale_because']))} before their rework)" \
                if m.get("stale") else ""
            parts.append(f"## Step {d} ({', '.join(m['roles'])}), status: {m['status']}{stale}\n{body}")
            if evidence and self.opt.contract == "on":          # D61 (G4): the verifier sees what the step used
                parts[-1] += "\n\n" + self.evidence_text(d)
        return "\n\n".join(parts)

    # box: fixes
    def so(self, n: int | None, name: str):
        """D117 Stage C: a run option for step n — the value a fix set for it, else the run's."""
        v = self.step_opts.get(n, {}).get(name) if n is not None else None
        return getattr(self.opt, name) if v is None else v

    # box: plan_step
    def run_step(self, step: PlanStep, wave: int, deps: list[int], rework: dict | None = None,
                 reverify: dict | None = None, rerun: dict | None = None, fixing: dict | None = None) -> dict:
        n = number(step)
        previous = (self.artifacts.get(n) or {}).get("meta")                     # D117: the attempt before, if any
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
        if not summarising and time_sensitive(self.task.prompt) and any(set(WEB_TOOLS) & set(a.tools)
                                                                       for a in agents):
            extra += FRESH_NOTE                                                    # D67: the latest figure, dated
        if not summarising and getattr(self.web, "research", False) and any(set(WEB_TOOLS) & set(a.tools)
                                                                            for a in agents):
            extra += RESEARCH_NOTE                                                 # D106: one entity per search
        inputs_saved = getattr(self.local, "inputs", None) or []
        if not summarising and inputs_saved and any(t.startswith("local:") for a in agents for t in a.tools):
            extra += SOURCES_NOTE.format(files=", ".join(f"{x['file']} [{x['source']}]" for x in inputs_saved[-12:]))   # D107
        if self.opt.replan == "on" and deps and not summarising:                  # D63: a missing input is a trigger
            extra += MISSING_INPUT_NOTE
        mine = None
        if verifier and self.opt.verify_first == "on":        # D90: the verifier's own result before the outputs
            own_writers = agents[:1] if self.opt.collab == "critique" and len(agents) > 1 else agents
            mine = self.own_result(step, n, deps, own_writers, extra.replace(VERIFY_NOTE, "").replace(VERIFY_TOOLS_NOTE, ""))
            inputs += ("\n\n## Your own result (you worked it out before you saw the outputs above)\n"
                       + (mine["text"].strip() or "(you wrote no result)"))
            extra += VERIFY_COMPARE_NOTE
        if reverify:
            extra += REVERIFY_NOTE.format(steps=", ".join(map(str, reverify["reworked"])),
                                          issues=reverify["first_issues"].strip())
        if rework:
            extra += REWORK_NOTE.format(by=rework["by_step"], issues=rework["issues"].strip(),
                                        previous=self.artifacts[n]["text"].strip())
        if fixing and fixing.get("note"):                                       # D117 Stage C: what the fix changed
            extra += "\n\n" + fixing["note"]
        w = _Work(max_turns=self.step_opts.get(n, {}).get("max_turns") or agents[0].limits.max_turns)
        if mine and not mine["reused"]:          # D90: the re-checks of the verifier's own result are its tool calls too
            w.calls, w.tool_results = list(mine["tool_calls"]), list(mine["tool_results"])
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
        checks += conclusion_check(text, w)                                       # D76
        checks += self.domain_checks(n, text, inputs, w, answer_step)             # D102
        checks += self.xlsx_checks(n, text)                                       # D113
        own, visible = self._sources(n, deps)
        prov = check_provenance(text, visible, self.task.prompt, inputs, w.tool_results,   # D33
                                self.computed_results(w), self.web_ids())
        found = self.contract_check(contract, w, text) if contract else None                # D61 (G1, G2)
        produced = self.answer_gaps(n, text) if on and answer_step else None               # D61 (G5)
        items = (self.contract_findings(found) if found else []) + (self.answer_findings(produced) if produced else [])
        final = answer_step and (self.opt.final_check == "on" or self.opt.dated == "on")
        if final and (missing := final_findings(self.final_answer_check(text))):  # D105 + D110: earns the refine turn
            items = items + missing
        files_before = file_sig(self.files_of(n))                                  # D117: across the refine turn
        refine = self.refine(step, n, agents, inputs, extra, w, template, checks, prov, items)   # D42 / D50 / D61
        if refine:
            exact = computed_values(self.computed_results(w))
            text, again = strip_unverified(self._text(agents, w), exact)
            removed += again
            checks = step_checks(step, text, deps, self.artifacts, verifier)
            checks += conclusion_check(text, w)
            checks += self.domain_checks(n, text, inputs, w, answer_step)
            checks += self.xlsx_checks(n, text)
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
        if final:                                       # still missing after the refine turn → Limitations
            self.final = self.final_answer_check(text)
            self.undated = self.final["undated"]
            self.ep.final_check = self.final
            self.i.trace.event("final_check", {"amoeba.step": n, "amoeba.unmet": self.final["unmet"],
                                               "amoeba.files_missing": self.final["files_missing"],
                                               "amoeba.undated": len(self.undated),
                                               "amoeba.core_missing": self.final["core_missing"]})
            if self.undated:
                self.i.trace.event("undated_figures", {"amoeba.step": n, "amoeba.count": len(self.undated),
                                                       "amoeba.figures": self.undated[:10]})
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
        mislabelled = mislabelled_citations(text, self.source_texts(), self.citation_exempt(),     # D74
                                            computed_values(self.computed_results(w)),
                                            arithmetic=self.opt.cite_arithmetic == "on")   # D104
        if mislabelled:
            status = "partial" if status == "done" else status
            reason = "; ".join(x for x in (reason, "mislabelled citation: " + "; ".join(
                f"{x['claim']!r} not in {x['source']}" for x in mislabelled[:4])) if x)
            self.i.trace.event("mislabelled_citation", {"amoeba.step": n, "amoeba.count": len(mislabelled),
                                                        "amoeba.citations": mislabelled[:10]})
        self.mislabelled[n] = mislabelled
        disputes, resolutions, unresolved = [], [], []
        if verifier and mine is not None and self.opt.disputes == "on":           # D109: blind result vs outputs
            disputes = disputed_figures(mine["text"], {d: self.artifacts[d]["text"] for d in deps if d in self.artifacts})
            if disputes:
                self.i.trace.event("disputed", {"amoeba.step": n, "amoeba.disputes": disputes})
                resolutions = self.resolve_disputes(step, n, writers, disputes)
                unresolved = [d for d, r in zip(disputes, resolutions) if r["verdict"] == "unresolved"]
            if unresolved:                              # never PASS: partial, and both values go to Limitations
                status = "partial" if status == "done" else status
                reason = "; ".join(x for x in (reason, "disputed, unresolved: " + "; ".join(
                    f"{x['label']}: step {x['step']} {x['worker']} vs check {x['verifier']}" for x in unresolved[:4])) if x)
                self.disputes[n] = unresolved
            else:
                self.disputes.pop(n, None)
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
                "mislabelled_citations": mislabelled,                              # D74
                "refine_reason": refine["reason"] if refine else "",
                "verification": verifier, "rework_of": rework, "reverify_of": reverify, "rerun_of_stale": rerun,
                "stale": False, "stale_because": [],
                "missing_inputs": missing_input_marks(text),                       # D63 marks, read by D117
                "fix_of": {k: v for k, v in fixing.items() if k != "note"} if fixing else None,
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
                                           "result": shorten(r or "", 6000)}   # D76: excerpted for the checker
                                          for c, r in zip(w.calls, w.tool_results) if c["ok"]][:8],
                         "unverified_check": bool(unchecked)})
        if verifier:
            meta["verdict"], meta["issues"] = parse_verdict_block(text)
            if mine is not None:                                                   # D90: both sides, recorded
                meta["verifier_own"] = {k: v for k, v in mine.items() if k != "tool_results"}
                meta["comparison"] = {"verdict": meta["verdict"], "issues": meta["issues"],
                                      "figures": compare_figures(mine["text"], {d: self.artifacts[d]["text"]
                                                                              for d in deps if d in self.artifacts})}
                if self.opt.disputes == "on":                                      # D109
                    meta["comparison"]["disputes"] = disputes
                    if disputes:
                        meta["dispute"] = {"state": "unresolved" if unresolved else "resolved", "figures": disputes,
                                           "resolutions": resolutions}
                    if unresolved and meta["verdict"] == "PASS":
                        meta["verdict_model"], meta["verdict"] = "PASS", "DISPUTED"   # a PASS never overrides it
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
        if self.opt.domain_checks:                    # D102: the run's calc results, for later domain checks
            meta["computed"] = self.computed_results(w)
        if self.opt.adapt == "on":                    # D117 Stage B: watch and diagnose, no fix yet
            self.watch(n, meta, previous, file_sig(self.files_of(n)) == files_before if refine else None)
        self._save(n, wave, text, meta, prov)
        if verifier and meta["verdict"] == "FAIL" and not reverify:
            reworked = self.rework_producers(n, deps, meta["issues"])
            if reworked:                                   # D38: check once more what the rework produced
                self.i.trace.event("reverify", {"amoeba.step": n, "amoeba.reworked": reworked})
                self.run_step(step, wave, deps, reverify={"first_verdict": meta["verdict"],
                                                          "first_issues": meta["issues"], "reworked": reworked})
                self.mark_stale(reworked, verifier_step=n)                           # D39
        return self.artifacts[n]

    # box: niche
    def domain_checks(self, n: int, text: str, inputs: str, w: "_Work", answer_step: bool) -> list[dict]:
        """D102: the niche profile's domain checks over this step's output and evidence (the task, the step's inputs,
        every calc and local-tool result of the run so far)."""
        if not self.opt.domain_checks:
            return []
        from amoeba.checks import run_checks
        done = [r for m in self.ep.steps for r in m.get("computed", [])]
        ev = {"task": self.task.prompt, "inputs": inputs, "computed": done + self.computed_results(w),
              "answer_step": answer_step, "step": n}
        return run_checks(self.opt.domain_checks, text, ev)

    # box: niche
    def xlsx_checks(self, n: int, text: str) -> list[dict]:
        """D113: totals and derived cells of the workbooks this step made must be formulas."""
        if self.opt.xlsx_formulas != "on" or self.local is None:
            return []
        books = [str(self.local.workspace / f["path"]) for f in self.files_of(n)
                 if f["path"].lower().endswith((".xlsx", ".xlsm"))]
        if not books:
            return []
        from amoeba.checks import run_checks
        return run_checks(["xlsx_formulas"], text, {"xlsx_files": books, "task": self.task.prompt, "step": n})

    # box: plan_summary
    def final_answer_check(self, text: str) -> dict:
        """D105 + D110 (amended): the final answer against Box 2's requirements, the promised files against the
        workspace, and the dates of its web-sourced figures."""
        from amoeba.task.deliverables import final_check
        texts = {**{f"step {number(s)} output": s.output for s in self.cfg.plan if s.output},
                 **{f"requirement {k}": v for k, v in (self.cfg.requirements or {}).items()}}
        made = [Path(f["path"]).name for f in self.files_of()] if self.local is not None else None
        undated = undated_figures(text, self.web_ids()) if self.opt.dated == "on" else []
        return final_check(text, self.cfg.requirements or {}, texts, made, undated,
                           check_requirements=self.opt.final_check == "on")

    @staticmethod
    def computed_results(w: "_Work") -> list[str]:
        """D66: what the step's calc and local tools returned (a number equal to one of them is derived)."""
        return [r for c, r in zip(w.calls, w.tool_results) if c["ok"] and (c["tool"] == "calc"
                                                                          or c["tool"].startswith("local:"))]

    # box: step_check
    def source_texts(self) -> dict[str, str]:
        """D74: S# -> the text the team was shown for it, across web, pool and local results."""
        books = [b for b in (self.web, getattr(self.pool, "book", None), getattr(self.local, "book", None)) if b]
        out: dict[str, str] = {}
        for b in books:
            out.update(b.source_texts() if hasattr(b, "source_texts") else {})
        return out

    # box: step_check
    def citation_exempt(self) -> set[str]:
        """D74: numbers no source has to back: those given in the task and today's date parts (D75 gives it)."""
        today = getattr(self.i, "today", None) or date.today()
        return numbers_in(self.task.prompt) | {str(today.year), str(today.day), f"{today.day:02d}", str(today.month),
                                               f"{today.month:02d}"}

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
            w.max_turns = w.turn + self.so(n, "check_retry_turns")
            self._loop(step, n, [drafter], inputs, extra, w, template)
            revisions += 1
        return {"mode": "critique", "drafter": drafter.name, "reviewers": [r.name for r in reviewers],
                "rounds": rounds, "revisions": revisions, "objections": objections, "agreed": agreed}

    # box: plan_step
    def _review(self, rv: AgentSpec, step: PlanStep, n: int, drafter: AgentSpec, draft: str, inputs: str
                ) -> tuple[str, list[str]]:
        """D51: one reviewer's verdict and numbered issues. An unreadable reply counts as AGREE (recorded)."""
        criteria = "; ".join(rv.success_criteria) or "none written"
        user = render(PROMPT.plan_critique, task=self.task.prompt, today=self.i.clock["line"], card=plan_card(rv), number=n,
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
                                               "amoeba.retry_turns": self.so(n, "check_retry_turns")})
        if reason == "self_review":
            criteria = "; ".join(c for a in agents for c in a.success_criteria) or "none written"
            note = SELF_REVIEW_NOTE.format(done_when=step.done_when or "none written", criteria=criteria)
        elif not prov_items and not contract_items:
            note = RETRY_NOTE.format(failed="; ".join(check_items))
        else:
            note = REFINE_NOTE.format(findings="\n".join(f"{i}. {x}" for i, x in
                                                          enumerate(check_items + prov_items + contract_items, 1)))
        w.max_turns = w.turn + self.so(n, "check_retry_turns")
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
        if "mislabel" not in section:                                            # D74: cited to the wrong source
            for d, items in sorted(getattr(self, "mislabelled", {}).items()):
                for x in items[:5]:
                    where = f"; it is in {', '.join(x['found_in'])}" if x["found_in"] else ""
                    lines.append(f"- Mislabelled citation: step {d} cites {x['source']} for {x['claim']!r}, which "
                                 f"{x['source']} does not contain{where} (added by plain code)")
        for r in getattr(self, "final", {}).get("unmet", []):                    # D105: checked on the final answer
            x = self.final["requirements"][r]
            if not re.search(rf"\b{re.escape(r)}\b[^\n]*not met", section, re.I):
                why = "marked BLOCKED" if x["status"] == "blocked" else \
                    f"file not made: {', '.join(x['files_missing'])}" if x["files_missing"] else "the final answer does not cover it"
                lines.append(f"- NOT MET: {r} — {x['text'][:160]} ({why}; checked by plain code on the final answer)")
        for f in getattr(self, "final", {}).get("files_missing", []):
            if f.lower() not in section:
                lines.append(f"- MISSING FILE: {f} (promised by the plan, not in the workspace; checked by plain code)")
        if "undated" not in section:                                             # D110: no date after the refine
            for u in self.undated[:8]:
                lines.append(f"- UNDATED: {u['figure']} [{', '.join(u['sources'])}] — the source's date (publication or "
                             f"data period) is not stated (added by plain code)")
        if "disput" not in section:                                              # D109: both values, never dropped
            for d, items in sorted(self.disputes.items()):
                for x in items[:5]:
                    lines.append(f"- DISPUTED: {x['label']} — step {x['step']} gives {x['worker']}; the check in step "
                                 f"{d}, worked out independently, gives {x['verifier']}. Neither a source quote nor a "
                                 f"re-run settled it (added by plain code)")
        stale = None
        if time_sensitive(self.task.prompt):                                     # D67: possibly not the latest
            stale = stale_figure([a["text"] for a in self.artifacts.values()] + [text or ""],
                                 getattr(self.i, "today", None) or date.today())
            if stale and "possibly not the latest" not in section:
                lines.append(f"- Possibly not the latest (dated {stale['as']}, {stale['days']} days before this run): a "
                             f"newer figure may exist (added by plain code)")
                self.i.trace.event("freshness", {"amoeba.dated": stale["date"], "amoeba.days": stale["days"]})
        if lines:
            body = "\n".join(lines)
            text = f"{text.rstrip()}\n\n{body}\n" if m else f"{text.rstrip()}\n\n## Limitations\n{body}\n"
            self.i.trace.event("limitations_added", {"amoeba.capabilities": missing, "amoeba.unused": not_used})
        return text, {"blocked_capabilities": sorted(caps), "limitations_added_by_code": missing,
                      **({"stale_figure": stale} if stale else {}),
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
    def resolve_disputes(self, step: PlanStep, n: int, writers: list[AgentSpec], disputes: list[dict]) -> list[dict]:
        """D109 (amended): one fresh call (the verify step's first helper, plan_resolve.txt) settles each disputed
        figure against the source text, a fetch, a calculation or a re-run; plain code checks the evidence. A value it
        accepts that differs from the worker's replaces it in the producer's output. Every resolution is logged."""
        sources = self.source_texts()
        w = _Work(max_turns=writers[0].limits.max_turns)
        self._loop(step, n, writers[:1], disputes_text(disputes, sources), "", w, PROMPT.plan_resolve)
        records = settle(self._text(writers[:1], w), disputes, self.source_texts(), w.tool_results)
        for d, r in zip(disputes, records):
            r["replaced"] = False
            if r["verdict"] in ("verifier", "corrected") and r["step"] in self.artifacts:
                art = self.artifacts[r["step"]]
                new, done = replace_figure(art["text"], d["worker_line"], d["worker"], r["value"])
                if done:
                    art["text"], r["replaced"] = new, True
                    art["meta"].setdefault("resolved_figures", []).append({**r, "by_step": n})
                    if self.dir:
                        (self.dir / f"step_{r['step']}.md").write_text(new + "\n", encoding="utf-8")
                        self._write(r["step"])
            self.i.trace.event("dispute_resolution", {"amoeba.step": n, "amoeba.producer": r["step"],
                                                      "amoeba.label": r["label"], "amoeba.worker": r["worker"],
                                                      "amoeba.check": r["verifier"], "amoeba.value": r["value"],
                                                      "amoeba.verdict": r["verdict"], "amoeba.evidence": r["evidence"],
                                                      "amoeba.evidence_kind": r["evidence_kind"],
                                                      "amoeba.replaced": r["replaced"]})
        return records

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
                if FINAL_OUTPUT not in act:
                    w.requests.append(inp.strip())
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

    # box: stuck
    def watch(self, n: int, meta: dict, previous: dict | None, files_unchanged: bool | None) -> dict | None:
        """D117 Stage B: the stuck watch after one step attempt. A stuck step gets `meta["stuck"]` (cause, signals,
        allowed edits, evidence lines), a `stuck` trace event and a row in the run's hash-chained events.jsonl."""
        roles = set(meta.get("roles") or [])
        unfilled = [q for q in self.cfg.meta.get("capability_requests", []) if q.get("status") == "unfilled"]
        unfilled += [{**q.model_dump(), "status": "unfilled", "reason": "raised_during_run"}
                     for q in self.ep.requested_capabilities if q.for_role in roles and self.pool is not None]
        plan = {number(s): {"output": s.output, "roles": [self.agents[a].name for a in s.agent_ids],
                            "status": (self.artifacts.get(number(s)) or {}).get("meta", {}).get("status")}
                for s in self.cfg.plan}
        signals = step_signals(meta, previous=previous, unfilled=unfilled, files_unchanged=files_unchanged, plan=plan)
        if not is_stuck(meta, signals):
            return None
        d = {"step": n, "attempt": len([s for s in self.stuck if s["step"] == n]) + 1, **diagnose(signals)}
        meta["stuck"] = d
        self.stuck.append(d)
        self.ep.stuck = list(self.stuck)
        self.i.trace.event("stuck", {"amoeba.step": n, "amoeba.cause": d["cause"], "amoeba.signals": d["signals"],
                                     "amoeba.allowed_edits": d["allowed_edits"], "amoeba.evidence": d["evidence"]})
        if self.run_dir is not None:
            EvidenceLog(self.run_dir).append("stuck", {k: d[k] for k in ("step", "attempt", "cause", "signals",
                                                                        "evidence")})
        return d

    # ---- D117 Stage C: code fixes for a stuck step ------------------------------------------------------------
    # box: fixes
    def fix_stuck(self, n: int, wave: int) -> bool:
        """D117 Stage C: while step n is stuck, try the next code fix for its cause (cheapest first, allowed by the
        table, never one already tried, within the limits), re-run only step n and re-check it. True when the step
        is still stuck and no fix is left: the task stops (stop_when_exhausted)."""
        d = self.artifacts[n]["meta"].get("stuck")
        if not d:
            return False
        lim, why = fix_limits(), ""
        while d:
            usd = self.adapt_usd()
            if sum(f["step"] == n for f in self.fixes) >= int(lim["max_fixes_per_step"]):
                why = f"limit: {lim['max_fixes_per_step']} fixes per step"
            elif len(self.fixes) >= int(lim["max_fixes_per_task"]):
                why = f"limit: {lim['max_fixes_per_task']} fixes per task"
            elif self.adapt_tokens >= int(lim["max_tokens_per_task"]):
                why = f"limit: adaptation tokens {self.adapt_tokens:,} of {int(lim['max_tokens_per_task']):,}"
            elif usd is not None and usd >= float(lim["max_usd_per_task"]):
                why = f"limit: adaptation cost ${usd:.2f} of ${float(lim['max_usd_per_task']):.2f}"
            if why:
                break
            cands, notes = candidates(d, n, self.fix_ctx(n))
            for note in notes:
                if (n, note) not in self.fix_notes:
                    self.fix_notes.add((n, note))
                    self.i.trace.event("fix_skipped", {"amoeba.step": n, "amoeba.cause": d["cause"], "amoeba.why": note})
                    self.log_event("fix_skipped", {"step": n, "cause": d["cause"], "why": note})
            fix = next((f for f in cands if fix_key(f) not in self.fix_keys), None)
            if fix is None:
                why = "; ".join(notes) or f"no code fix left for {d['cause']}"
                break
            self.apply_fix(n, wave, d, fix)
            meta = self.artifacts[n]["meta"]
            if meta["status"] == "done":
                break
            d = meta.get("stuck")
        meta = self.artifacts[n]["meta"]
        self.ep.adaptation = self.adapt_summary()
        if meta["status"] == "done" or not meta.get("stuck"):
            return False
        self.exhausted = {"step": n, "cause": meta["stuck"]["cause"], "why": why,
                          "evidence": meta["stuck"]["evidence"]}
        self.ep.adaptation = self.adapt_summary()
        return bool(lim["stop_when_exhausted"])

    # box: fixes
    def fix_ctx(self, n: int) -> dict:
        agents = [self.agents[a] for a in self.steps[n].agent_ids]
        return {"deps": dependencies(self.cfg.plan).get(n, []),
                "steps": {k: {"status": a["meta"]["status"], "text": a["text"]} for k, a in self.artifacts.items()},
                "opts": {"max_turns": self.step_opts.get(n, {}).get("max_turns") or agents[0].limits.max_turns,
                         "check_retry_turns": self.so(n, "check_retry_turns"),
                         "max_input_chars": self.so(n, "max_input_chars")},
                "capped": bool(self.capped.get(n)), "stock": getattr(self.i, "stock", None) is not None,
                "upstream_rerun": set(self.upstream_rerun), "attached": self.attached_ids.get(n, [])}

    # box: fixes
    def apply_fix(self, n: int, wave: int, d: dict, fix: dict) -> dict:
        """Apply one code fix to the live plan, re-run step n (and, for rerun_upstream, its upstream step first),
        record what happened: the fix, its tokens, the status after and why it failed."""
        self.fix_keys.add(fix_key(fix))
        t0, s0 = self.i.trace.total_tokens, len(self.i.trace.spans("chat"))
        rec = {"step": n, "try": sum(f["step"] == n for f in self.fixes) + 1, "cause": d["cause"], "kind": fix["kind"],
               "rung": fix["rung"], "target": fix["target"], "params": fix.get("params", {}),
               "evidence": d["evidence"][:4]}
        self.i.trace.event("fix_try", {"amoeba.step": n, "amoeba.cause": d["cause"], "amoeba.fix": fix["kind"],
                                       "amoeba.rung": fix["rung"], "amoeba.target": fix["target"],
                                       "amoeba.params": json.dumps(fix.get("params", {}), default=str)})
        note, kind, p = "", fix["kind"], fix.get("params", {})
        if kind.startswith("set_run_option:"):
            self.step_opts.setdefault(n, {}).update(p)
        elif kind == "add_dependency":
            u = p["from"]
            if p["mode"] == "added":
                if not any(s.depends_on for s in self.cfg.plan):     # a chain plan: keep its implicit order
                    for s, ds in zip(self.cfg.plan, [dependencies(self.cfg.plan)[number(x)] for x in self.cfg.plan]):
                        s.depends_on = list(ds)
                self.steps[n].depends_on = sorted(set(self.steps[n].depends_on) | {u})
            self.step_opts.setdefault(n, {}).setdefault("full_from", set()).add(u)
            note = FIX_INPUT_NOTE.format(items="; ".join(x.partition(" — ")[0] for x in fix.get("items", [])), step=u)
        elif kind == "rerun_upstream":
            u, up = fix["target"], self.steps[fix["target"]]
            up.done_when = "; ".join(x for x in (up.done_when, "it must include: " + p["add_done_when"]) if x)
            self.upstream_rerun.add(u)
            self.keep_try(u)
            self.run_step(up, self.artifacts[u]["meta"]["wave"], dependencies(self.cfg.plan)[u],
                          fixing={**fix, "note": FIX_UPSTREAM_NOTE.format(items=p["add_done_when"], step=n)})
            rec["upstream_status"] = self.artifacts[u]["meta"]["status"]
            rec["left_on_old_output"] = sorted(k for k, a in self.artifacts.items() if k not in (n, u)
                                               and u in dependencies(self.cfg.plan).get(k, []))
            self.step_opts.setdefault(n, {}).setdefault("full_from", set()).add(u)
        elif kind == "grant_tool":
            rec["attached"] = self.attach_missing(n, fix)
            if not rec["attached"]:                     # nothing to give: the step is not re-run
                rec.update({"status_after": self.artifacts[n]["meta"]["status"],
                            "result": "failed: the pool shortlist had nothing to attach for "
                                      + ", ".join(p.get("items") or []) + " (no candidate passed the checks)"})
                return self._fix_done(rec, t0, s0)
        self.keep_try(n)
        self.run_step(self.steps[n], wave, dependencies(self.cfg.plan)[n], fixing={**fix, "note": note})
        m = self.artifacts[n]["meta"]
        rec["status_after"] = m["status"]
        rec["result"] = "recovered" if m["status"] == "done" else \
            f"failed: still stuck ({m['stuck']['cause']}: {'; '.join(m['stuck']['evidence'][:2])[:200]})" \
            if m.get("stuck") else f"failed: not stuck but {m['status']} ({m['status_reason'][:160]})"
        return self._fix_done(rec, t0, s0)

    # box: fixes
    def _fix_done(self, rec: dict, t0: int, s0: int) -> dict:
        spans = self.i.trace.spans("chat")[s0:]
        rec["tokens"] = self.i.trace.total_tokens - t0
        self.adapt_tokens += rec["tokens"]
        self.adapt_spans += spans
        self.fixes.append(rec)
        self.i.trace.event("fix_done", {"amoeba.step": rec["step"], "amoeba.fix": rec["kind"],
                                        "amoeba.result": rec["result"], "amoeba.tokens": rec["tokens"]})
        self.log_event("fix", {k: rec[k] for k in ("step", "try", "cause", "kind", "target", "params", "result",
                                                   "tokens") if k in rec})
        self.ep.adaptation = self.adapt_summary()
        return rec

    # box: fixes
    def keep_try(self, n: int) -> None:
        """Keep the attempt a fix replaces as step_N.tryK.md / .json next to the new one."""
        if self.dir and (self.dir / f"step_{n}.json").exists():
            k = 1 + len(list(self.dir.glob(f"step_{n}.try*.json")))
            for ext in ("md", "json"):
                if (self.dir / f"step_{n}.{ext}").exists():
                    (self.dir / f"step_{n}.{ext}").rename(self.dir / f"step_{n}.try{k}.{ext}")

    # box: fixes
    def attach_missing(self, n: int, fix: dict) -> list[str]:
        """Rung 2: give step n's helpers what they lacked. A tool the run's registry already has is granted; anything
        else goes through the toolbox step (pool and local tools) with the first vetted candidate of the shortlist
        that was not given before (plain code picks, no AI call)."""
        writers = [self.agents[a] for a in self.steps[n].agent_ids]
        got, reqs = [], []
        for item in fix["params"].get("items") or []:
            canon = normalise(item)[0]
            have = next((x for x in (item, canon) if x in self.i.tools), None)
            if have:
                for a in writers:
                    if have not in a.tools:
                        a.tools.append(have)
                    a.missing_tools = [t for t in a.missing_tools if t not in (item, canon)]
                got.append(have)
            else:
                reqs.append(CapabilityRequest(name=item, kind="skill" if "skill" in item.lower() else "tool",
                                              for_role=writers[0].name, source="planner"))
        if reqs:
            cfg = self.cfg.model_copy(update={"agents": self.agents})
            reg, summary = self.i.stock(reqs, cfg, self.i.tools, code_pick=True,
                                        exclude=set(fix["params"].get("exclude") or []))
            self.i.tools = reg
            self.pool = getattr(reg, "pool", None)
            self.local = getattr(reg, "local", None)
            for x in summary.get("attached", []):
                got.append(x["as"])
                self.attached_ids.setdefault(n, []).append(x["id"])
            for q in reqs:
                self.cfg.meta.setdefault("capability_requests", []).append(
                    {"name": q.name, "for_role": q.for_role, "canonical": q.canonical, "status": q.status,
                     "reason": q.reason, "source": "adapt"})
        if self.web is not None:
            self.grant_web_tools()
        return got

    # box: fixes
    def adapt_usd(self) -> float | None:
        if not self.adapt_spans:
            return 0.0
        return estimate(self.adapt_spans, getattr(self.i.llm, "model", "") or "").get("cost_usd")

    # box: fixes
    def adapt_summary(self) -> dict:
        recovered = sorted({f["step"] for f in self.fixes if f["result"] == "recovered"})
        return {"fixes": self.fixes, "recovered_steps": recovered,
                "stuck_steps": sorted({s["step"] for s in self.stuck}), "tokens": self.adapt_tokens,
                "cost_usd": self.adapt_usd(), "skipped": [{"step": s, "why": w} for s, w in sorted(self.fix_notes)],
                "stopped": self.exhausted}

    # box: fixes
    def log_event(self, event: str, data: dict) -> None:
        if self.run_dir is not None:
            EvidenceLog(self.run_dir).append(event, data)

    # box: fixes
    def stop_report(self, n: int) -> tuple[str, str]:
        """All fixes failed (or none was left): the task stops. The report says what was stuck, the cause, each fix
        tried and why it failed; it is the run's answer and <run>/adapt_report.md."""
        x = self.exhausted or {}
        title = re.sub(r"^\s*\[.*?\]\s*:\s*", "", self.steps[n].text).strip()[:300]
        tried = [f for f in self.fixes if f["step"] == n or f.get("params", {}).get("then") == n]
        lines = ["# The task stopped: a step stayed stuck", "",
                 f"**Stuck step:** {n} — {title}",
                 f"**Cause:** {x.get('cause')}", "", "**Evidence:**"] + [f"- {e}" for e in x.get("evidence", [])] + \
                ["", "**Fixes tried:**"]
        lines += [f"{i}. {f['kind']} (rung {f['rung']}, on step {f['target']}"
                  f"{', ' + json.dumps(f['params'], default=str) if f.get('params') else ''}): {f['result']}"
                  f" — {f.get('tokens', 0):,} tokens" for i, f in enumerate(tried, 1)] or ["- none"]
        skipped = sorted(w for s, w in self.fix_notes if s == n)
        if skipped:
            lines += ["", "**Not tried:**"] + [f"- {w}" for w in skipped]
        lines += ["", f"**Why it stopped:** {x.get('why') or 'no code fix recovered the step'}",
                  "", "**Steps finished before it:** " + (", ".join(str(k) for k, a in sorted(self.artifacts.items())
                                                              if a["meta"]["status"] == "done") or "none"),
                  "", "Nothing after this step was run. Stage D (the fix-proposer agent) is not built yet."]
        text = "\n".join(lines) + "\n"
        if self.run_dir is not None:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            (self.run_dir / "adapt_report.md").write_text(text, encoding="utf-8")
        self.i.trace.event("adapt_stop", {"amoeba.step": n, "amoeba.cause": x.get("cause"), "amoeba.why": x.get("why"),
                                          "amoeba.fixes": len(tried)})
        self.log_event("adapt_stop", {"step": n, "cause": x.get("cause"), "why": x.get("why"), "fixes": len(tried)})
        self.ep.adaptation = self.adapt_summary()
        return text, f"stuck: step {n} ({x.get('cause')}) — {x.get('why') or 'no fix recovered it'}"

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

    # box: router
    def route_ids(self, n: int, step: PlanStep) -> dict:
        """D97: what the router needs to know about a step's call: its number and, for a verify step, the steps it
        checks (verifier independence)."""
        if not hasattr(self.i.llm, "llm") or not hasattr(self.i.llm.llm, "registry"):
            return {}
        checks = tuple(dependencies(self.cfg.plan).get(n, [])) if self.is_verification(step) else ()
        return {"step": n, "checks": checks}

    # box: plan_step
    def _turn(self, agent: AgentSpec, step: PlanStep, n: int, inputs: str, completed: str, turns_left: int,
              extra: str = "", template: str = "") -> tuple[str, str, str, str | None]:
        last = turns_left <= 1                   # D76: the last turn ends the step with a written conclusion
        tools = [FINAL_OUTPUT] if last else list(agent.tools) + [PRINT, FINAL_OUTPUT]
        user = render(template or PROMPT.plan_step, task=self.task.prompt, today=self.i.clock["line"], deliverables=self.deliverables_text(), card=plan_card(agent), number=n,
                      step=step_detail(step) + extra, inputs=inputs, completed=completed.strip() or "Nothing yet.",
                      tools=str(tools), turns_left=turns_left,
                      unavailable="\n".join([UNAVAILABLE.format(name=t) for t in agent.missing_tools
                                              if t not in agent.tools]
                                             + pool_tool_notes(agent)))   # D56
        c = self.current_contract.get(agent.name)
        if c and (c["needs"] or c["items"]):     # D61: what plain code will check, on the helper's prompt
            items = [*(f"{x} (asked for, not available)" for x in c["needs"]),
                     *(f"{x['name']} (given to you)" for x in c["items"])]
            user = user.replace("\n# Format\n", f"\n{CONTRACT_LINE.format(items='; '.join(items))}\n\n# Format\n", 1)
        if last:
            user = user.replace("\n# Format\n", f"\n{LAST_TURN_NOTE}\n\n# Format\n", 1)
        system = render(PROMPT.plan_step_system, name=agent.name)
        with self.i.trace.span("invoke_agent", {"gen_ai.agent.id": agent.agent_id, "gen_ai.agent.name": agent.name,
                                                "amoeba.box": "plan_summary" if self.is_summary_step(step) else "plan_step",
                                                "amoeba.step": n}):
            before = self.i.trace.n_llm_calls
            group = role_group(is_summariser=agent.is_summariser, reviewing=self.is_verification(step))   # D54
            try:
                raw, sec = self.i.llm.chat_sections(system, user, PLAN_SECTIONS, self.ep.seed,
                                                  agent_id=agent.agent_id, agent_name=agent.name,
                                                  max_tokens=PLAN_MAX_TOKENS, role=group, **self.route_ids(n, step))
            except NoModelAvailable as e:                 # D97: no model passed the router's filters
                return "no_model", f"BLOCKED: no_model — {str(e)[:200]}", "", "no_model"
            for rec in self.i.trace.spans("chat")[before:]:
                self.i._record(agent, self.ep, raw, rec.get("gen_ai.usage.input_tokens", 0),
                               rec.get("gen_ai.usage.output_tokens", 0))
            act, inp = sec["Action"].strip(), full_action_input(raw, sec["ActionInput"])
            if last and FINAL_OUTPUT not in act:   # D76: a tool asked for on the last turn is not run; asked once more
                self.i.trace.event("last_turn_forced", {"amoeba.step": n, "gen_ai.agent.name": agent.name,
                                                        "amoeba.asked_for": act[:80]})
                before = self.i.trace.n_llm_calls
                raw, sec = self.i.llm.chat_sections(system, f"{user}\n\n{LAST_TURN_AGAIN}", PLAN_SECTIONS,
                                                    self.ep.seed, agent_id=agent.agent_id, agent_name=agent.name,
                                                    max_tokens=PLAN_MAX_TOKENS, role=group,
                                                    **self.route_ids(n, step))
                for rec in self.i.trace.spans("chat")[before:]:
                    self.i._record(agent, self.ep, raw, rec.get("gen_ai.usage.input_tokens", 0),
                                   rec.get("gen_ai.usage.output_tokens", 0))
                act, inp = sec["Action"].strip(), full_action_input(raw, sec["ActionInput"])
                if FINAL_OUTPUT not in act:
                    return "no action", inp, "", None
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
        user = render(PROMPT.plan_replan, task=self.task.prompt, today=self.i.clock["line"], requirements=self.deliverables_text(),
                      triggers="\n".join(f"- {t['detail']}" for t in triggers), plan=self.plan_text(),
                      outputs=self.finished_text(), blocked=self.blocked_text(), tools=self.tools_text(),
                      roles=self.roles_text(),
                      left=(f"{self.opt.max_replans - len(self.replans) - 1} more re-plan(s) after this one; "
                              f"{self.opt.max_added_steps - self.added_steps} step(s) may still be added; "
                              f"{'no' if self.roles_added else 'one'} new role may still be added"),
                      next=str(self.max_num + 1))
        failed = self.failed_steps() if self.opt.replan_method == "on" else {}
        if failed:                                     # D108: what failed, so a new step can do it differently
            user += ("\n\n# How the failed steps worked (plain code)\n" + failed_methods_text(failed) +
                     "\nA step you add or rewrite for one of these must change the method, and its text must say how: "
                     "a different tool, a different source type (a data file or table, an official source, an API, "
                     "another named site) or one search per entity, year or series. A step that repeats the method is "
                     "rejected.")
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
            errors += self.same_method(change["steps"], new_role)                 # D108
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

    # box: action_obs
    def failed_steps(self) -> dict[int, dict]:
        """D108: each finished step that failed (partial, incomplete, lacking a capability, or a verify step still
        failing or disputed), with its method."""
        out = {}
        for n, a in sorted(self.artifacts.items()):
            m = a["meta"]
            if m["status"] in ("partial", "incomplete") or m.get("blocked") or m.get("verdict") in ("FAIL", "DISPUTED"):
                held = {t for aid in self.steps[n].agent_ids for t in self.agents[aid].tools} if n in self.steps else set()
                queries = [x["query"] for x in getattr(self.web, "sources", []) if n in x.get("steps", []) and x.get("query")]
                out[n] = failed_method(m, held, list(dict.fromkeys(queries)))
        return out

    # box: action_obs
    def same_method(self, steps: list[dict], new_role=None) -> list[str]:
        """D108: an error for each proposed step that replaces a failed step without changing its method."""
        if self.opt.replan_method != "on":
            return []
        failed = self.failed_steps()
        errors = []
        for st in steps:
            n = replaces(st, failed)
            if n is None:
                continue
            tools = {t for r in st["roles"] for a in self.agents.values() if a.name == r for t in a.tools}
            if new_role is not None and new_role.name in st["roles"]:
                tools |= set(getattr(new_role, "tools", []) or [])
            how = method_change(st, failed[n], tools)
            self.i.trace.event("replan_method", {"amoeba.step": st["number"], "amoeba.replaces": n,
                                                 "amoeba.changes": how, "amoeba.failed_method": failed[n]})
            if not how:
                f = failed[n]
                errors.append(f"step {st['number']} repeats the method of failed step {n} (tools "
                              f"{', '.join(f['tools']) or 'none'}; sources {', '.join(f['sites'][:3]) or 'none'}): it "
                              f"must name a different tool, a different source type or one search per entity, year "
                              f"or series (D108)")
        return errors

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
        final = self.final_step(by)
        if final is not None and final not in self.artifacts:
            later = self.dependants(by, final)           # the answer step waits for every new step not built on it
            a = by[final]
            add = [n for n in sorted(new) if n != final and n not in later]
            by[final] = a.model_copy(update={"depends_on": list(dict.fromkeys([*a.depends_on, *add]))})
        plan = [by[n] for n in sorted(by)]
        plan, _ = relink(plan, written)
        return plan

    # box: action_obs
    def final_step(self, by: dict[int, PlanStep]) -> int | None:
        """The step that writes the answer in a proposed plan: a revision may renumber it (the old answer step
        rewritten as another step, the summariser's step moved to a new number), so it is found again: the
        summariser's step that no other step builds on, else the old answer step."""
        summ = {a.agent_id for a in self.agents.values() if a.is_summariser}
        used = {d for s in by.values() for d in s.depends_on}
        sinks = [n for n in sorted(by) if n not in used and summ & set(by[n].agent_ids)]
        if sinks:
            return sinks[-1]
        return self.answer_n if self.answer_n in by else None

    # box: action_obs
    @staticmethod
    def dependants(by: dict[int, PlanStep], n: int) -> set[int]:
        """Every step that builds on step n, directly or through other steps."""
        out, todo = set(), [n]
        while todo:
            x = todo.pop()
            for k, s in by.items():
                if x in s.depends_on and k not in out:
                    out.add(k)
                    todo.append(k)
        return out

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
            if self.answer_n not in self.artifacts:      # a revision may have moved the answer step
                self.answer_n = self._answer_step(waves(self.cfg.plan))
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
        dropped it) — and the step(s) that met it. The answer step counts only when no other step covers it."""
        out = {}
        for r in self.cfg.requirements or {}:
            if r in self.unmet:
                out[r] = {"status": "not met", "steps": [], "why": self.unmet[r]}
                continue
            cover = [n for n, a in sorted(self.artifacts.items()) if r in a["meta"].get("covers", [])]
            made = [n for n in cover if n != self.answer_n]   # the answer step only restates: a producer counts first
            cover = made or cover
            done = [n for n in cover if self.artifacts[n]["meta"]["status"] == "done"
                    and self.artifacts[n]["meta"].get("verdict") != "FAIL"]
            out[r] = {"status": "met" if done else "partly" if cover else "not met", "steps": done or cover}
            if not cover:
                out[r]["why"] = "no step that ran covers it"
        for r, x in (getattr(self, "final", {}).get("requirements") or {}).items():   # D105: the final answer decides
            if r in out:
                out[r] = {**out[r], "steps_claim": out[r]["status"],
                          "status": "met" if x["status"] == "met" else "not met", "final_answer": x["status"]}
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


FIX_INPUT_NOTE = """Plain code re-runs this step because it lacked an input: {items}. Step {step}'s output is now among your
inputs in full; the data is there. Use it."""
FIX_UPSTREAM_NOTE = """Plain code re-runs this step because a later step (step {step}) lacked data it should have got from
it: {items}. Your output must include it."""
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
