"""BOX 3 — the `plan` topology (D31): carry out a d24 plan over its depends_on graph.

`run_flat` (AutoAgents) walks the steps in list order and hands every helper the whole history; this runner builds
a graph from `depends_on`, runs the steps in topological waves, and gives each step only the task, its own step
detail and the artifacts of the steps it depends on. Each step's result is an artifact (runs/<id>/artifacts/
step_<n>.md plus step_<n>.json metadata). Plain code owns the graph, the order, the turn cap and what each step sees.
"""
from __future__ import annotations

import json
from pathlib import Path

from amoeba.capabilities import normalise
from amoeba.config.prompts import PROMPT, render
from amoeba.config.schema import AgentSpec, PlanStep, TeamConfig
from amoeba.interp.provenance import check_provenance
from amoeba.interp.runtime import BLOCKED, FINAL_OUTPUT, PRINT, UNAVAILABLE, _output_text
from amoeba.task.models import Episode, Task
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


class PlanRunner:
    """Runs one TeamConfig with topology "plan" for an Interpreter (which owns the LLM, tools, trace and dispatch)."""

    def __init__(self, interp, cfg: TeamConfig, task: Task, ep: Episode, run_dir: Path | None = None):
        self.i, self.cfg, self.task, self.ep = interp, cfg, task, ep
        self.dir = Path(run_dir) / "artifacts" if run_dir else None
        self.steps = {number(s): s for s in cfg.plan}
        self.artifacts: dict[int, dict] = {}     # step number -> {"text", "meta"}
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
        self.i.trace.event("plan_graph", {"amoeba.waves": ws, "amoeba.depends_on": {str(k): v for k, v in deps.items()},
                                          "amoeba.max_turns": self._max_turns(), "amoeba.max_tokens": PLAN_MAX_TOKENS})
        for w, nums in enumerate(ws, 1):
            for n in nums:   # sequential for now; the wave number is recorded so parallel runs keep the same trace
                self.run_step(self.steps[n], w, deps[n])
        last = self._answer_step(ws)
        art = self.artifacts[last]
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

    def run_step(self, step: PlanStep, wave: int, deps: list[int]) -> dict:
        n = number(step)
        agents = [self.agents[a] for a in step.agent_ids]
        inputs = self.inputs_text(deps)
        if self.web is not None:
            self.web.begin_step(n, self.i.trace)
        self.i.trace.event("step_input", {"amoeba.step": n, "amoeba.wave": wave, "amoeba.depends_on": deps,
                                          "amoeba.received": deps, "amoeba.input_chars": len(inputs)})
        max_turns = agents[0].limits.max_turns
        completed = ""
        done: dict[str, str] = {}          # agent_id -> its Final Output text
        blocked: dict[str, str] = {}       # agent_id -> the capability it answered BLOCKED on
        partial: dict[str, str] = {}       # agent_id -> what it wrote alongside BLOCKED
        contributions: list[dict] = []
        tool_results: list[str] = []       # what the step's tools returned (D33: their numbers count as derived)
        turn = 0
        while len(done) + len(blocked) < len(agents) and turn < max_turns:
            for agent in agents:           # the roles take turns; one that has finished is not asked again
                if agent.agent_id in done or agent.agent_id in blocked:
                    continue
                act, inp, resp, gap = self._turn(agent, step, n, inputs, completed, max_turns - turn)
                contributions.append({"turn": turn + 1, "agent": agent.name, "action": act,
                                      "input": inp[:400], "final": FINAL_OUTPUT in act, "blocked": gap})
                if gap is not None:
                    blocked[agent.agent_id] = gap
                    partial[agent.agent_id] = inp.strip()
                    completed += f">{agent.name} {BLOCKED}: {gap}\n{inp.strip()}\n"
                elif act in agent.tools:
                    tool_results.append(resp)
                    completed += f">{agent.name} ({act}):\n{inp.strip()}\n>Result:\n{resp.strip()}\n"
                elif FINAL_OUTPUT in act:
                    done[agent.agent_id] = inp.strip()
                    completed += f">{agent.name} Final Output:\n{inp.strip()}\n"
                else:
                    completed += f">{agent.name} ({act or 'no action'}):\n{inp.strip()}\n>Result:\n{resp.strip()}\n"
            turn += 1
        written = {a.agent_id: done.get(a.agent_id) or partial.get(a.agent_id) for a in agents}
        written = {k: v for k, v in written.items() if v}
        if len(agents) == 1:
            text = next(iter(written.values()), "") or completed.strip()
        else:
            text = "\n\n".join(f"### {a.name}\n{written[a.agent_id]}" for a in agents
                               if a.agent_id in written) or completed.strip()
        status = ("done" if len(done) == len(agents) else
                  "blocked" if blocked and len(done) + len(blocked) == len(agents) else "max_turns")
        own = [{k: s[k] for k in ("id", "url", "title", "kind", "fetched_at")}
               for s in (self.web.sources_for(n) if self.web is not None else [])]
        visible = {s["id"] for s in own}.union(*(self.artifacts[d]["meta"]["visible_source_ids"] for d in deps)) \
            if deps else {s["id"] for s in own}
        prov = check_provenance(text, visible, self.task.prompt, inputs, tool_results)   # D33
        meta = {"step": n, "wave": wave, "roles": [a.name for a in agents], "covers": step.covers,
                "depends_on": deps, "received": deps, "output_spec": step.output, "status": status,
                "turns": turn, "blocked": sorted(set(blocked.values())), "sources": own,
                "visible_source_ids": sorted(visible), "provenance": prov,
                "contributions": contributions}
        self.artifacts[n] = {"text": text, "meta": meta}
        self.ep.steps.append(meta)
        self.i.trace.event("step_done", {"amoeba.step": n, "amoeba.wave": wave, "amoeba.status": status,
                                         "amoeba.turns": turn, "amoeba.output_chars": len(text)})
        self.i.trace.event("provenance", {"amoeba.step": n, **{f"amoeba.provenance.{k}": v for k, v in prov.items()
                                                               if k != "untagged_examples"}})
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / f"step_{n}.md").write_text(text + "\n", encoding="utf-8")
            (self.dir / f"step_{n}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.artifacts[n]

    def _turn(self, agent: AgentSpec, step: PlanStep, n: int, inputs: str, completed: str, turns_left: int
              ) -> tuple[str, str, str, str | None]:
        tools = list(agent.tools) + [PRINT, FINAL_OUTPUT]
        user = render(PROMPT.plan_step, task=self.task.prompt, card=plan_card(agent), number=n,
                      step=step_detail(step), inputs=inputs, completed=completed.strip() or "Nothing yet.",
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
            act, inp = sec["Action"].strip(), sec["ActionInput"]
            resp, gap = self.i._dispatch(agent, act, inp, step.index, self.ep)
        return act, inp, resp, gap
