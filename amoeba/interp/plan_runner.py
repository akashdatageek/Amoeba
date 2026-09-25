"""BOX 3 — the `plan` topology (D31): carry out a d24 plan over its depends_on graph.

`run_flat` (AutoAgents) walks the steps in list order and hands every helper the whole history; this runner builds
a graph from `depends_on`, runs the steps in topological waves, and gives each step only the task, its own step
detail and the artifacts of the steps it depends on. Each step's result is an artifact (runs/<id>/artifacts/
step_<n>.md plus step_<n>.json metadata). Plain code owns the graph, the order, the turn cap and what each step sees.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from amoeba.capabilities import normalise
from amoeba.config.prompts import PROMPT, render
from amoeba.config.schema import AgentSpec, PlanStep, TeamConfig
from amoeba.interp.provenance import check_provenance, claim_numbers, numbers_in
from amoeba.llm.profiles import role_group
from amoeba.interp.runtime import BLOCKED, FINAL_OUTPUT, PRINT, UNAVAILABLE, _output_text
from amoeba.task.models import Episode, Task
from amoeba.task.parsers import MissingSections
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
             f"Suggestions: {agent.suggestions}" if agent.suggestions else ""]
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
    if prov.get("hallucinated_citations"):
        prov_items.append(f"these citations name sources you never saw: {', '.join(prov['hallucinated_citations'])}. "
                          f"Cite only [S#] ids from your tool results or your inputs, or mark the figure [unverified].")
    return check_items, prov_items


def refine_counts(checks: list[dict], prov: dict) -> dict:
    return {"failed_checks": sum(not c["pass"] for c in checks), "untagged": prov.get("untagged", 0),
            "hallucinated": len(prov.get("hallucinated_citations", []))}


class _Work:
    """The state of one step's turn loop, kept across a retry."""

    def __init__(self, max_turns: int):
        self.max_turns, self.turn, self.completed = max_turns, 0, ""
        self.done: dict[str, str] = {}          # agent_id -> its Final Output text
        self.blocked: dict[str, str] = {}       # agent_id -> the capability it answered BLOCKED on
        self.partial: dict[str, str] = {}       # agent_id -> what it wrote alongside BLOCKED
        self.contributions: list[dict] = []
        self.tool_results: list[str] = []       # what the step's tools returned (D33: their numbers count as derived)
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
        for w, nums in enumerate(ws, 1):
            for n in nums:   # sequential for now; the wave number is recorded so parallel runs keep the same trace
                self.run_step(self.steps[n], w, deps[n])
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
        text, added = self.enforce_limitations("\n\n".join(parts))
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
        """D44: the first `limit` characters of an input, with a marker saying how much was cut (and a trace event)."""
        if len(text) <= limit:
            return text
        self.i.trace.event("input_truncated", {"amoeba.step": step, "amoeba.from_step": source, "amoeba.limit": limit,
                                               "amoeba.chars": len(text), "amoeba.what": what})
        return f"{text[:limit].rstrip()}\n[... cut by plain code: first {limit:,} of {len(text):,} characters shown]"

    def inputs_text(self, deps: list[int], n: int | None = None) -> str:
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
        return "\n\n".join(parts)

    # box: plan_step
    def run_step(self, step: PlanStep, wave: int, deps: list[int], rework: dict | None = None,
                 reverify: dict | None = None, rerun: dict | None = None) -> dict:
        n = number(step)
        agents = [self.agents[a] for a in step.agent_ids]
        summarising = self.is_summary_step(step)                                  # D35
        inputs = self.all_inputs_text(n) if summarising else self.inputs_text(deps, n)
        verifier = self.is_verification(step) and not summarising
        if self.web is not None:
            self.web.begin_step(n, self.i.trace)
        self.i.trace.event("step_input", {"amoeba.step": n, "amoeba.wave": wave, "amoeba.depends_on": deps,
                                          "amoeba.received": deps, "amoeba.input_chars": len(inputs),
                                          "amoeba.verification": verifier, "amoeba.rework": bool(rework)})
        extra = VERIFY_NOTE if verifier else ""
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
        self._loop(step, n, writers, inputs, extra, w, template)
        collab = self.critique(step, n, agents[0], agents[1:], inputs, extra, w, template) \
            if writers is not agents else None
        agents_all, agents = agents, writers
        text = self._text(agents, w)
        checks = step_checks(step, text, deps, self.artifacts, verifier)          # D34
        own, visible = self._sources(n, deps)
        prov = check_provenance(text, visible, self.task.prompt, inputs, w.tool_results)   # D33
        refine = self.refine(step, n, agents, inputs, extra, w, template, checks, prov)    # D42 / D50
        if refine:
            text = self._text(agents, w)
            checks = step_checks(step, text, deps, self.artifacts, verifier)
            own, visible = self._sources(n, deps)
            prov = check_provenance(text, visible, self.task.prompt, inputs, w.tool_results)
            refine["after"] = refine_counts(checks, prov)
            self.i.trace.event("refine", {"amoeba.step": n, "amoeba.reason": refine["reason"],
                                          "amoeba.findings": len(refine["findings"]),
                                          **{f"amoeba.before.{k}": v for k, v in refine["before"].items()},
                                          **{f"amoeba.after.{k}": v for k, v in refine["after"].items()}})
        failed = [c["name"] for c in checks if not c["pass"]]
        retried = bool(refine)
        # D36: what the step could not do for lack of a capability — BLOCKED as an action or marked in the output.
        # D40: not for the answer step: its Limitations section names the producers' gaps on purpose
        answer_step = n == getattr(self, "answer_n", None)
        mentions = blocked_marks(text)
        gaps = [] if answer_step else sorted(set(w.blocked.values()) | set(mentions))
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
                "refine_reason": refine["reason"] if refine else "",
                "verification": verifier, "rework_of": rework, "reverify_of": reverify, "rerun_of_stale": rerun,
                "stale": False, "stale_because": [],
                "contributions": w.contributions}
        if verifier:
            meta["verdict"], meta["issues"] = parse_verdict_block(text)
            # D38: both verdicts are kept; `verdict` is always the latest one
            meta["verdict_first"] = reverify["first_verdict"] if reverify else meta["verdict"]
            meta["verdict_after_rework"] = meta["verdict"] if reverify else None
        if summarising:
            text, added = self.enforce_limitations(text)                          # D36
            meta["summary_check"] = {**self.summary_check(n, text), **added}
        self._save(n, wave, text, meta, prov)
        if verifier and meta["verdict"] == "FAIL" and not reverify:
            reworked = self.rework_producers(n, deps, meta["issues"])
            if reworked:                                   # D38: check once more what the rework produced
                self.i.trace.event("reverify", {"amoeba.step": n, "amoeba.reworked": reworked})
                self.run_step(step, wave, deps, reverify={"first_verdict": meta["verdict"],
                                                          "first_issues": meta["issues"], "reworked": reworked})
                self.mark_stale(reworked, verifier_step=n)                           # D39
        return self.artifacts[n]

    def _sources(self, n: int, deps: list[int]) -> tuple[list[dict], set[str]]:
        """The step's own sources and every source id it could have seen (its own and its inputs')."""
        own = [{k: s[k] for k in ("id", "url", "title", "kind", "fetched_at")}
               for s in (self.web.sources_for(n) if self.web is not None else [])]
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
               template: str, checks: list[dict], prov: dict) -> dict | None:
        """D50: one refine turn for the helper(s) of a finished step, with turns of its own (check_retry_turns, not
        the step's cap). The helper is given exactly what plain code found: failed checks and — unless
        self_refine is "off" — untagged figures and citations of sources it never saw. With "always" and no
        finding it gets a self-review against done_when and its success criteria instead. Returns the reason, the
        findings and the before-counts (the caller adds the after-counts), or None when there is no refine."""
        mode = self.opt.self_refine
        check_items, prov_items = refine_findings(checks, prov)
        if mode == "off":
            prov_items = []
        reason = "+".join(k for k, v in (("checks", check_items), ("provenance", prov_items)) if v)
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
        elif not prov_items:
            note = RETRY_NOTE.format(failed="; ".join(check_items))
        else:
            note = REFINE_NOTE.format(findings="\n".join(f"{i}. {x}" for i, x in enumerate(check_items + prov_items, 1)))
        w.max_turns = w.turn + self.opt.check_retry_turns
        w.completed += note
        w.done.clear()
        self._loop(step, n, agents, inputs, extra, w, template)
        return {"reason": reason, "findings": check_items + prov_items, "before": refine_counts(checks, prov)}

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
        """D36: canonical capability -> the names the steps used for it, over every step's latest output."""
        out: dict[str, list[str]] = {}
        for d, a in self.artifacts.items():
            if d == getattr(self, "answer_n", None):       # D40: producer steps only
                continue
            for g in a["meta"].get("blocked", []):
                out.setdefault(normalise(g)[0], [])
                if g not in out[normalise(g)[0]]:
                    out[normalise(g)[0]].append(g)
        return out

    # box: plan_summary
    def enforce_limitations(self, text: str) -> tuple[str, dict]:
        """D36: the final answer's Limitations section must name every capability a step lacked. Names it leaves
        out are appended by plain code (and recorded), so a gap is never silently dropped."""
        caps = self.blocked_capabilities()
        m = re.search(r"^\s*#+\s*limitations\b.*$", text or "", re.I | re.M)
        section = text[m.end():] if m else ""
        spell = lambda c, names: {c, c.replace("_", " "), *names}
        missing = sorted(c for c, names in caps.items()
                         if not any(x.lower() in section.lower() for x in spell(c, names)))
        if missing:
            lines = "\n".join(f"- BLOCKED: {c} (the team had no such capability; added by plain code)" for c in missing)
            text = f"{text.rstrip()}\n\n{lines}\n" if m else f"{text.rstrip()}\n\n## Limitations\n{lines}\n"
            self.i.trace.event("limitations_added", {"amoeba.capabilities": missing})
        return text, {"blocked_capabilities": sorted(caps), "limitations_added_by_code": missing}

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
                      unavailable="\n".join(UNAVAILABLE.format(name=t) for t in agent.missing_tools))
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
