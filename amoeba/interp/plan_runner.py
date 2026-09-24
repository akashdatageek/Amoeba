"""BOX 3 — the `plan` topology (D31): carry out a d24 plan over its depends_on graph.

`run_flat` (AutoAgents) walks the steps in list order and hands every helper the whole history; this runner builds
a graph from `depends_on`, runs the steps in topological waves, and gives each step only the task, its own step
detail and the artifacts of the steps it depends on. Each step's result is an artifact (runs/<id>/artifacts/
step_<n>.md plus step_<n>.json metadata). Plain code owns the graph, the order, the turn cap and what each step sees.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from amoeba.capabilities import normalise
from amoeba.config.prompts import PROMPT, render
from amoeba.config.schema import AgentSpec, PlanStep, TeamConfig
from amoeba.interp.provenance import check_provenance, claim_numbers, numbers_in
from amoeba.interp.runtime import BLOCKED, FINAL_OUTPUT, PRINT, UNAVAILABLE, _output_text
from amoeba.task.models import Episode, Task
from amoeba.task.quality import VERIFY_WORDS
from amoeba.tools.web import WEB_TOOLS

PLAN_SECTIONS = ["CurrentStep", "Action", "ActionInput"]   # Thought is asked for but not required
PLAN_MAX_TOKENS = 8192                                     # per helper call (D27 room; flat keeps the client default)


class PlanGraphError(ValueError):
    """The plan's depends_on graph is unusable: an unknown step or a cycle. Raised before any LLM call."""


def number(step: PlanStep) -> int:
    """A step's number as the planner wrote it (depends_on uses these numbers)."""
    return step.index + 1


def dependencies(plan: list[PlanStep]) -> dict[int, list[int]]:
    """step number -> the step numbers it depends on. A plan with no depends_on at all (a d19 draft) is a chain."""
    if not any(s.depends_on for s in plan):
        nums = [number(s) for s in plan]
        return {n: ([nums[i - 1]] if i else []) for i, n in enumerate(nums)}
    return {number(s): list(dict.fromkeys(s.depends_on)) for s in plan}


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


def step_detail(step: PlanStep) -> str:
    extra = [f"{k}: {getattr(step, k)}" for k in ("do", "output", "done_when") if getattr(step, k)]
    return "\n".join([step.text, *extra])


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
RETRY_NOTE = ("Plain code checked this step's output and it failed: {failed}. Fix that and give the whole step "
              "output again as Final Output.\n")


class _Work:
    """The state of one step's turn loop, kept across a retry."""

    def __init__(self, max_turns: int):
        self.max_turns, self.turn, self.completed = max_turns, 0, ""
        self.done: dict[str, str] = {}          # agent_id -> its Final Output text
        self.blocked: dict[str, str] = {}       # agent_id -> the capability it answered BLOCKED on
        self.partial: dict[str, str] = {}       # agent_id -> what it wrote alongside BLOCKED
        self.contributions: list[dict] = []
        self.tool_results: list[str] = []       # what the step's tools returned (D33: their numbers count as derived)


NUMERIC_WORDS = re.compile(r"\b(cost|costs|estimate|estimates|price|prices|pricing|number|numbers|figure|figures|"
                           r"metric|metrics|latency|revenue|size|sizing|storage|volume|tb|gb|usd|eur|percent|rate|rates|"
                           r"tariff|tariffs|benchmark|benchmarks|p95|throughput)\b|%|\$", re.I)


def step_checks(step: PlanStep, text: str, deps: list[int], artifacts: dict, verifier: bool = False) -> list[dict]:
    """D34: deterministic checks of a step's output against its `output` / `done_when` lines. Only checks that
    apply are listed; each is {name, pass, detail}."""
    spec = f"{step.output}\n{step.done_when}".lower()
    body = text or ""
    out = [{"name": "output_present", "pass": bool(body.strip()), "detail": "the step output is empty"}]
    if "table" in spec:
        ok = bool(re.search(r"^\s*\|.*\|\s*$", body, re.M)) and bool(re.search(r"^\s*\|?\s*:?-{3,}", body, re.M))
        out.append({"name": "format_table", "pass": ok, "detail": "the output line asks for a table; there is no "
                                                                   "markdown table (| a | b | with a |---| row)"})
    if re.search(r"\b(list|bullets?|checklist)\b", spec):
        ok = len(re.findall(r"^\s*(?:[-*]|\d+[.)])\s+\S", body, re.M)) >= 2
        out.append({"name": "format_list", "pass": ok, "detail": "the output line asks for a list; there are fewer "
                                                                  "than 2 list items"})
    if re.search(r"\b(code|script|sql|query|queries|schema|ddl)\b", spec):
        ok = "```" in body or bool(re.search(r"\b(SELECT|CREATE TABLE|def |INSERT INTO)\b", body))
        out.append({"name": "format_code", "pass": ok, "detail": "the output line asks for code; there is no code "
                                                                  "block or statement"})
    if re.search(r"\b(memo|report|runbook|plan|document)\b", spec):
        ok = len(re.findall(r"^\s*#{1,4}\s+\S|^\s*\*\*[^*]+\*\*\s*$", body, re.M)) >= 2
        out.append({"name": "format_headings", "pass": ok, "detail": "the output line asks for a document; it has "
                                                                      "fewer than 2 headings"})
    if NUMERIC_WORDS.search(spec):
        ok = bool(re.search(r"\d", re.sub(r"\[S\d+\]", "", body)))
        out.append({"name": "numbers_present", "pass": ok, "detail": "the output line asks for figures; the output "
                                                                      "has no number"})
    if deps:
        ids = set().union(*(set(artifacts[d]["meta"]["visible_source_ids"]) for d in deps))
        roles = {r for d in deps for r in artifacts[d]["meta"]["roles"]}
        dep_nums = set().union(*(numbers_in(artifacts[d]["text"]) for d in deps))
        dep_text = "\n".join(artifacts[d]["text"] for d in deps)
        ok = (any(re.search(rf"\bstep\s*{d}\b", body, re.I) for d in deps) or any(f"[{i}]" in body for i in ids)
              or any(r in body for r in roles) or bool(numbers_in(body) & dep_nums)
              or (bool(body.strip()) and body.strip() in dep_text)
              or any(len(x.strip()) >= 3 and x.strip() in dep_text for x in body.splitlines()))
        out.append({"name": "inputs_referenced", "pass": ok, "detail": "the output uses nothing from the steps it "
                                                                        "depends on (no step, role, source or figure)"})
    if verifier:
        out.append({"name": "verdict", "pass": parse_verdict_block(body)[0] is not None,
                    "detail": 'a verification step must start with "Verdict: PASS" or "Verdict: FAIL"'})
    return out


def blocked_marks(text: str) -> list[str]:
    """D36: the capabilities named in 'BLOCKED: <capability> — ...' lines of a step's output."""
    names = []
    for m in re.finditer(r"BLOCKED\s*[:：]\s*`?([A-Za-z][\w ./+-]{0,60}?)`?\s*(?:[—–:;,(\n]|-\s|$)", text or ""):
        name = m.group(1).strip(" .-")
        if name and name.lower() not in names and name.lower() not in ("none", "n/a"):
            names.append(name)
    return names


def parse_verdict_block(text: str) -> tuple[str | None, str]:
    m = re.search(r"verdict\s*[:*]*\s*\**\s*(PASS|FAIL)", text or "", re.I)
    issues = re.split(r"issues\s*[:*]*", text or "", maxsplit=1, flags=re.I)
    return (m.group(1).upper() if m else None), (issues[1].strip() if len(issues) > 1 else "")


class PlanRunner:
    """Runs one TeamConfig with topology "plan" for an Interpreter (which owns the LLM, tools, trace and dispatch)."""

    def __init__(self, interp, cfg: TeamConfig, task: Task, ep: Episode, run_dir: Path | None = None):
        self.i, self.cfg, self.task, self.ep = interp, cfg, task, ep
        self.dir = Path(run_dir) / "artifacts" if run_dir else None
        self.steps = {number(s): s for s in cfg.plan}
        self.artifacts: dict[int, dict] = {}     # step number -> {"text", "meta"}
        self.reworked: set[int] = set()          # D34: at most one rework per step
        self.agents = {k: a.model_copy(deep=True) for k, a in cfg.agents.items()}   # tools may be granted (D32)
        self.web = getattr(interp.tools, "web", None)

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
                                          "amoeba.max_turns": self._max_turns(), "amoeba.max_tokens": PLAN_MAX_TOKENS})
        for w, nums in enumerate(ws, 1):
            for n in nums:   # sequential for now; the wave number is recorded so parallel runs keep the same trace
                self.run_step(self.steps[n], w, deps[n])
        art = self.artifacts[self.answer_n]
        status = art["meta"]["status"]
        return art["text"], (None if status == "done" else status)

    def _answer_step(self, ws: list[list[int]]) -> int:
        """The summariser's step if it owns one in the last wave, else the last step of the last wave."""
        summ = {a.agent_id for a in self.agents.values() if a.is_summariser}
        final = [n for n in ws[-1] if summ & set(self.steps[n].agent_ids)]
        return (final or ws[-1])[-1]

    def _max_turns(self) -> int:
        return next(iter(self.agents.values())).limits.max_turns

    # ---- one step -------------------------------------------------------------------------------------------
    def inputs_text(self, deps: list[int]) -> str:
        if not deps:
            return "None: this step starts from the task alone."
        parts = []
        for d in deps:
            a = self.artifacts[d]
            m = a["meta"]
            parts.append(f"## Step {d} ({', '.join(m['roles'])}), status: {m['status']}\n{a['text']}")
        return "\n\n".join(parts)

    def run_step(self, step: PlanStep, wave: int, deps: list[int], rework: dict | None = None) -> dict:
        n = number(step)
        agents = [self.agents[a] for a in step.agent_ids]
        summarising = self.is_summary_step(step)                                  # D35
        inputs = self.all_inputs_text(n) if summarising else self.inputs_text(deps)
        verifier = self.is_verification(step) and not summarising
        if self.web is not None:
            self.web.begin_step(n, self.i.trace)
        self.i.trace.event("step_input", {"amoeba.step": n, "amoeba.wave": wave, "amoeba.depends_on": deps,
                                          "amoeba.received": deps, "amoeba.input_chars": len(inputs),
                                          "amoeba.verification": verifier, "amoeba.rework": bool(rework)})
        extra = VERIFY_NOTE if verifier else ""
        if rework:
            extra += REWORK_NOTE.format(by=rework["by_step"], issues=rework["issues"].strip(),
                                        previous=self.artifacts[n]["text"].strip())
        w = _Work(max_turns=agents[0].limits.max_turns)
        template = PROMPT.plan_summarise if summarising else PROMPT.plan_step
        self._loop(step, n, agents, inputs, extra, w, template)
        text = self._text(agents, w)
        checks = step_checks(step, text, deps, self.artifacts, verifier)          # D34
        failed = [c["name"] for c in checks if not c["pass"]]
        retried = False
        if failed and w.turn < w.max_turns and w.done:
            retried = True                                                          # one retry with the failed checks
            self.i.trace.event("check_retry", {"amoeba.step": n, "amoeba.failed_checks": failed})
            w.completed += RETRY_NOTE.format(failed="; ".join(c["detail"] for c in checks if not c["pass"]))
            w.done.clear()
            self._loop(step, n, agents, inputs, extra, w, template)
            text = self._text(agents, w)
            checks = step_checks(step, text, deps, self.artifacts, verifier)
            failed = [c["name"] for c in checks if not c["pass"]]
        # D36: what the step could not do for lack of a capability — BLOCKED as an action or marked in the output
        gaps = sorted(set(w.blocked.values()) | set(blocked_marks(text)))
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
        own = [{k: s[k] for k in ("id", "url", "title", "kind", "fetched_at")}
               for s in (self.web.sources_for(n) if self.web is not None else [])]
        visible = {s["id"] for s in own}.union(*(self.artifacts[d]["meta"]["visible_source_ids"] for d in deps)) \
            if deps else {s["id"] for s in own}
        prov = check_provenance(text, visible, self.task.prompt, inputs, w.tool_results)   # D33
        meta = {"step": n, "wave": wave, "roles": [a.name for a in agents], "covers": step.covers,
                "depends_on": deps, "received": deps, "output_spec": step.output, "status": status,
                "status_reason": reason, "turns": w.turn, "blocked": gaps,
                "blocked_canonical": sorted({normalise(g)[0] for g in gaps}), "sources": own,
                "visible_source_ids": sorted(visible), "provenance": prov, "checks": checks, "retried": retried,
                "verification": verifier, "rework_of": rework, "contributions": w.contributions}
        if verifier:
            meta["verdict"], meta["issues"] = parse_verdict_block(text)
        if summarising:
            text, added = self.enforce_limitations(text)                          # D36
            meta["summary_check"] = {**self.summary_check(n, text), **added}
        self._save(n, wave, text, meta, prov)
        if verifier and meta["verdict"] == "FAIL":
            self.rework_producers(n, deps, meta["issues"])
        return self.artifacts[n]

    def is_summary_step(self, step: PlanStep) -> bool:
        """D35: the answer step, when the summariser owns it, only assembles."""
        summ = {a.agent_id for a in self.agents.values() if a.is_summariser}
        return number(step) == getattr(self, "answer_n", None) and bool(summ & set(step.agent_ids))

    def all_inputs_text(self, n: int) -> str:
        """The summariser sees every step's latest output, its status and where its figures come from."""
        parts = []
        for d, a in sorted(self.artifacts.items()):
            if d == n:
                continue
            m, p = a["meta"], a["meta"]["provenance"]
            why = f" ({m['status_reason']})" if m.get("status_reason") else ""
            gaps = f"; lacked: {', '.join(m['blocked'])}" if m.get("blocked") else ""
            verdict = f"; verdict: {m['verdict']}" if m.get("verdict") else ""
            parts.append(f"## Step {d} ({', '.join(m['roles'])}), status: {m['status']}{why}{gaps}{verdict}; figures: "
                         f"{p['cited']} cited, {p['unverified']} unverified, {p['untagged']} untagged\n{a['text']}")
        return "\n\n".join(parts) or "None."

    def deliverables_text(self) -> str:
        req = self.cfg.requirements
        return "\n".join(f"{k}: {v}" for k, v in req.items()) if req else \
            "None listed by the plan; take the deliverables from the task."

    def summary_check(self, n: int, text: str) -> dict:
        """D35: a figure in the final answer that is in no step output and not in the task is new."""
        known = numbers_in(self.task.prompt).union(*(numbers_in(a["text"]) for d, a in self.artifacts.items() if d != n))
        new = sorted(claim_numbers(text) - known, key=lambda x: (len(x), x))
        out = {"new_number_in_summary": len(new), "new_numbers": new[:30],
               "limitations_section": bool(re.search(r"^\s*#+\s*limitations", text or "", re.I | re.M))}
        self.i.trace.event("summary_check", {"amoeba.step": n, "amoeba.new_number_in_summary": len(new),
                                             "amoeba.new_numbers": new[:30],
                                             "amoeba.limitations_section": out["limitations_section"]})
        return out

    def blocked_capabilities(self) -> dict[str, list[str]]:
        """D36: canonical capability -> the names the steps used for it, over every step's latest output."""
        out: dict[str, list[str]] = {}
        for a in self.artifacts.values():
            for g in a["meta"].get("blocked", []):
                out.setdefault(normalise(g)[0], [])
                if g not in out[normalise(g)[0]]:
                    out[normalise(g)[0]].append(g)
        return out

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

    def is_verification(self, step: PlanStep) -> bool:
        """The d24 'independent verification' shape (as draft_quality reads it): a step that depends on others and
        says it verifies, checks, reviews, validates or reconciles them; the summariser's own step is not one."""
        summ = {a.agent_id for a in self.agents.values() if a.is_summariser}
        text = f"{step.text}\n{step.do}\n{step.done_when}"
        return bool(step.depends_on) and bool(VERIFY_WORDS.search(text)) and not set(step.agent_ids) <= summ

    def rework_producers(self, n: int, deps: list[int], issues: str) -> None:
        """D34: on a FAIL verdict each producer step it checked is re-run once with the issues; the run then goes on
        whatever the result (the verifier is not asked again)."""
        all_deps = dependencies(self.cfg.plan)
        for d in deps:
            if d in self.reworked or self.artifacts[d]["meta"].get("verification"):
                continue
            self.reworked.add(d)
            self.i.trace.event("rework", {"amoeba.step": d, "amoeba.by_step": n, "amoeba.issues_chars": len(issues)})
            self.run_step(self.steps[d], self.artifacts[d]["meta"]["wave"], all_deps[d],
                          rework={"by_step": n, "issues": issues})

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
        if len(agents) == 1:
            return next(iter(written.values()), "") or w.completed.strip()
        return "\n\n".join(f"### {a.name}\n{written[a.agent_id]}" for a in agents
                           if a.agent_id in written) or w.completed.strip()

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
            suffix = f".rework" if meta["rework_of"] else ""
            if suffix and (self.dir / f"step_{n}.md").exists():      # keep the first version next to the rework
                (self.dir / f"step_{n}.md").rename(self.dir / f"step_{n}.first.md")
                (self.dir / f"step_{n}.json").rename(self.dir / f"step_{n}.first.json")
            (self.dir / f"step_{n}.md").write_text(text + "\n", encoding="utf-8")
            (self.dir / f"step_{n}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    def _turn(self, agent: AgentSpec, step: PlanStep, n: int, inputs: str, completed: str, turns_left: int,
              extra: str = "", template: str = "") -> tuple[str, str, str, str | None]:
        tools = list(agent.tools) + [PRINT, FINAL_OUTPUT]
        user = render(template or PROMPT.plan_step, task=self.task.prompt, deliverables=self.deliverables_text(), card=plan_card(agent), number=n,
                      step=step_detail(step) + extra, inputs=inputs, completed=completed.strip() or "Nothing yet.",
                      tools=str(tools), turns_left=turns_left,
                      unavailable="\n".join(UNAVAILABLE.format(name=t) for t in agent.missing_tools))
        system = render(PROMPT.plan_step_system, name=agent.name)
        with self.i.trace.span("invoke_agent", {"gen_ai.agent.id": agent.agent_id, "gen_ai.agent.name": agent.name,
                                                "amoeba.step": n}):
            before = self.i.trace.n_llm_calls
            raw, sec = self.i.llm.chat_sections(system, user, PLAN_SECTIONS, self.ep.seed, agent_id=agent.agent_id,
                                              agent_name=agent.name, max_tokens=PLAN_MAX_TOKENS)
            for rec in self.i.trace.spans("chat")[before:]:
                self.i._record(agent, self.ep, raw, rec.get("gen_ai.usage.input_tokens", 0),
                               rec.get("gen_ai.usage.output_tokens", 0))
            act, inp = sec["Action"].strip(), full_action_input(raw, sec["ActionInput"])
            resp, gap = self.i._dispatch(agent, act, inp, step.index, self.ep)
        return act, inp, resp, gap
