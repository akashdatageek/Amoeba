"""BOX 3 — Team runs the task (spec §6). Two explicit topology runners; plain code owns loops, caps, parsing, trace."""
from __future__ import annotations

import time
from dataclasses import dataclass

from amoeba.config.prompts import PROMPT, render, resolve
from amoeba.config.schema import AgentSpec, PlanStep, TeamConfig
from amoeba.interp.trace import NoopListener, TracedLLM, TraceWriter
from amoeba.llm.client import LLMClient, Messages, api_error, describe_api_error
from amoeba.task.models import AgentResult, CapabilityRequest, Episode, Message, Task
from amoeba.task.parsers import MissingSections, ParseError, parse_critic
from amoeba.llm.limits import RunLimitReached
from amoeba.llm.profiles import role_group
from amoeba.pool.stock import pool_skill_notes, pool_tool_notes
from amoeba.tools.registry import ToolError, ToolRegistry

WORKER_SECTIONS = ["CurrentStep", "Action", "ActionInput"]           # custom_action.py:79-83
SYNTHESIZE_HINT = "\n You should synthesize the responses of previous steps and provide the final feedback."  # group.py:83
FINAL_OUTPUT = "Final Output"
PRINT = "Print"
BLOCKED = "BLOCKED"
UNAVAILABLE = "Tool {name} is unavailable this run; proceed without it or answer BLOCKED: {name}"   # D21


@dataclass
class _Msg:
    sender: str
    content: str
    is_agree: bool | None = None


# box: resolver, helper
def with_unavailable(agent: AgentSpec) -> str:
    """The agent's suggestions plus one line per tool its role named that is not registered (D21), and how to use
    each pool tool Box 3 attached to it (D56)."""
    lines = [UNAVAILABLE.format(name=t) for t in agent.missing_tools] + pool_tool_notes(agent)
    return "\n".join([agent.suggestions, *lines]) if lines else agent.suggestions


def _output_text(o) -> str:
    if isinstance(o, dict):
        art, fmt = o.get("artifact", ""), o.get("format", "")
        return f"{art} ({fmt})" if art and fmt else (art or fmt or str(o))
    return str(o)


def role_card(agent: AgentSpec) -> str:
    """D24: what the draft says this helper must achieve and produce. Empty for a d19 team, so its prompt is
    unchanged."""
    lines = [f"Goal: {agent.goal}" if agent.goal else "",
             f"Skills: {'; '.join(agent.skills)}" if agent.skills else "",
             f"Outputs: {'; '.join(_output_text(o) for o in agent.outputs)}" if agent.outputs else "",
             f"Success criteria: {'; '.join(agent.success_criteria)}" if agent.success_criteria else "",
             *pool_skill_notes(agent)]   # D56: skills from the pool, as data
    return "\n".join(x for x in lines if x)


def with_card(text: str, agent: AgentSpec) -> str:
    card = role_card(agent)
    return f"{text}\n\n{card}" if card else text


def step_context(step: PlanStep) -> str:
    """D24: the step line plus its do / output / done_when lines. Just the step line for a d19 team."""
    extra = [f"{k}: {getattr(step, k)}" for k in ("do", "output", "done_when") if getattr(step, k)]
    return "\n".join([step.text, *extra])


class Interpreter:
    # box: interpreter
    def __init__(self, llm: LLMClient, tools: ToolRegistry, trace: TraceWriter | None = None,
                 listener: NoopListener | None = None, run_dir: str | None = None, plan_options=None):
        self.run_dir = run_dir   # D31: the plan runner writes its step artifacts under <run_dir>/artifacts
        self.plan_options = plan_options   # D39+: PlanOptions for --topology plan (None = defaults)
        self.trace = trace or TraceWriter(None)
        self.listener = listener or NoopListener()   # spec §12: Phase 3's monitor plugs in here; no-op now
        self.llm = TracedLLM(llm, self.trace, self.listener)
        self.tools = tools

    # ---- entry -------------------------------------------------------------------------------------------
    # box: ov_run, interpreter
    def run(self, cfg: TeamConfig, task: Task, seed: int = 0) -> Episode:
        ep = Episode(episode_id=self.trace.episode_id, team_id=cfg.team_id, team_version=cfg.version,
                     task_id=task.id, seed=seed)
        t0 = time.perf_counter()
        with self.trace.span("invoke_workflow", {"gen_ai.workflow.name": cfg.name,
                                                 "gen_ai.conversation.id": ep.episode_id}):
            try:
                if cfg.topology == "flat":
                    ep.answer, ep.error = self.run_flat(cfg, task, ep)
                elif cfg.topology == "plan":                 # D31
                    from amoeba.interp.plan_runner import PlanRunner
                    ep.answer, ep.error = PlanRunner(self, cfg, task, ep, self.run_dir, self.plan_options).run()
                else:
                    ep.answer, ep.error = self.run_boss_reviewers(cfg, task, ep)
            except (ParseError, MissingSections) as e:
                ep.answer, ep.error = None, f"parse: {e}"
            except RunLimitReached as e:                     # D47: stop cleanly; what ran so far stays in ep
                ep.answer, ep.error = None, e.code
            except Exception as e:                           # D57: the model service failed after its retries
                if not api_error(e):
                    raise
                ep.answer, ep.error = None, f"api: {describe_api_error(e)}"
                self.trace.event("api_error", {"error.type": ep.error[:300]})
        ep.latency_ms = int((time.perf_counter() - t0) * 1000)
        return ep

    # ---- shared LLM helper: one chat span, history + outputs + token sums ---------------------------------
    def _record(self, agent: AgentSpec, ep: Episode, content: str, n_in: int, n_out: int) -> None:
        ep.history.append(Message(name=agent.name, role=agent.role, content=content))
        ep.outputs.setdefault(agent.agent_id, []).append(
            AgentResult(agent_id=agent.agent_id, body=content, input_tokens=n_in, output_tokens=n_out))
        ep.total_tokens += n_in + n_out
        ep.n_llm_calls += 1

    def _llm_messages(self, agent: AgentSpec, messages: Messages, ep: Episode) -> str:
        resp = self.llm.chat_messages(messages, ep.seed, agent_id=agent.agent_id, agent_name=agent.name,
                                      role=role_group(role=agent.role, is_summariser=agent.is_summariser))   # D54
        self._record(agent, ep, resp.content, resp.input_tokens, resp.output_tokens)
        return resp.content

    def _llm_sections(self, agent: AgentSpec, system: str, user: str, keys: list[str], ep: Episode
                      ) -> tuple[str, dict[str, str]]:
        before = self.trace.n_llm_calls
        raw, sec = self.llm.chat_sections(system, user, keys, ep.seed, agent_id=agent.agent_id,
                                          agent_name=agent.name,
                                          role=role_group(role=agent.role, is_summariser=agent.is_summariser))
        for rec in self.trace.spans("chat")[before:]:   # the repair call, if any, is a call too
            self._record(agent, ep, raw, rec.get("gen_ai.usage.input_tokens", 0),
                         rec.get("gen_ai.usage.output_tokens", 0))
        return raw, sec

    # ---- flat: AutoAgents Group._think/_act + CustomAction.run -------------------------------------------
    # box: ov_run, each_step, helper, read_action
    def run_flat(self, cfg: TeamConfig, task: Task, ep: Episode) -> tuple[str | None, str | None]:
        previous_msgs = [f"Question/Task: {task.prompt}"]   # group.py:76 str(important_memory): task + every step's message
        published: str | None = None
        answer: str | None = None
        last_step_done = last_step_blocked = False
        for step in cfg.plan:                                # environment.py:256 while Group.steps
            if getattr(self.tools, "pool", None) is not None:   # D56: pool tool call caps are per step
                self.tools.pool.begin_step(step.index, self.trace)
            agents = [cfg.agents[a] for a in step.agent_ids]
            previous = "[" + ", ".join(previous_msgs) + "]"  # group.py:76 — full history, not just the last edge
            completed_steps = ""                             # group.py:75 — SHARED by all agents of the step
            consensus = [0] * len(agents)
            it, response, final_inp, blocked = 0, None, None, False
            max_turns = agents[0].limits.max_turns           # group.py:75 num_steps = 5
            while sum(consensus) < len(agents) and it < max_turns:   # group.py:80
                if it > max_turns - 2:                       # group.py:82-83 — fires once, at the start of the 5th iteration
                    completed_steps += SYNTHESIZE_HINT
                for i, agent in enumerate(agents):           # group.py:85 — every agent each iteration, even ones already done
                    user = render(PROMPT.autoagents_custom_action,
                                  role=with_card(agent.role_prompt, agent),   # custom_action.py:148 — role prompt in the USER msg (+ D24 card)
                                  context=step_context(step),             # :146 — the STEP string (task is inside `previous`; + D24 detail)
                                  suggestions=with_unavailable(agent), previous=previous,
                                  completed_steps=completed_steps,
                                  tool=str(list(agent.tools) + [PRINT, FINAL_OUTPUT]),   # :144 (DEVIATION D7: no "Write File")
                                  format_example=PROMPT.autoagents_custom_action_format)  # its "[{tool}]" stays literal
                    with self.trace.span("invoke_agent", {"gen_ai.agent.id": agent.agent_id,
                                                          "gen_ai.agent.name": agent.name, "amoeba.box": "helper"}):
                        _, sec = self._llm_sections(agent, resolve(agent.prompt.system), user, WORKER_SECTIONS, ep)
                        act, inp = sec["Action"], sec["ActionInput"]
                        resp, gap = self._dispatch(agent, act, inp, step.index, ep)
                    if gap is not None:                      # D21: the helper answered BLOCKED: X — done for this step
                        info = f"\n## Step\n{step.text}\n## Response\n{completed_steps}>>>> {BLOCKED}: {gap}\n{resp}\n>>>>"
                        completed_steps += f">{agent.name} {BLOCKED}: {gap}\n"
                        consensus[i] = 1
                        blocked = True
                    elif FINAL_OUTPUT in act:                # :215 substring
                        info = f"\n## Step\n{step.text}\n## Response\n{completed_steps}>>>> Final Output\n{resp}\n>>>>"  # :216
                        consensus[i] = 1
                        final_inp = inp
                    else:
                        info = f"\n## Step\n{step.text}\n## Response\n{resp}\n## Action\n{sec['CurrentStep']}\n"   # :220
                        completed_steps += f">{agent.name} Substep:\n{sec['CurrentStep']}\n>Subresponse:\n{resp}\n"  # group.py:94
                    response = info
                    # original sleeps 30 s here (group.py:12,98) — dropped (D8)
                it += 1
            published = response                             # group.py:104-110 — the last agent's last response, final or not
            previous_msgs.append(f"user: {published}")       # Message role defaults to 'user' (schema.py:27)
            last_step_done = sum(consensus) == len(agents)
            last_step_blocked = blocked and final_inp is None
            answer = final_inp
        # original has no answer object (explorer.py:58). DEVIATION D9: answer = the last step's Final Output
        # ActionInput; if the last step never reached Final Output, the published text with error="max_turns"
        if last_step_done and not last_step_blocked:
            return answer, None
        return published, "blocked" if last_step_blocked else "max_turns"   # D21: a blocked last step is not an answer

    # box: resolver, read_action
    def _dispatch(self, agent: AgentSpec, act: str, inp: str, step: int, ep: Episode) -> tuple[str, str | None]:
        """Route one "## Action". Returns (response, blocked tool or None). Original: a tool of the agent → SerpAPI,
        anything else → echo the input (custom_action.py:207-213). D21: BLOCKED and unknown actions are recorded."""
        if act in agent.tools:                               # :207 exact membership; original always calls SerpAPI (D7)
            return self._tool(agent, act, inp), None
        if act.strip().upper().startswith(BLOCKED) or inp.strip().startswith(f"{BLOCKED}:"):
            text = act if act.strip().upper().startswith(BLOCKED) else inp
            gap = text.strip()[len(BLOCKED):].lstrip(" :").split("\n")[0].strip() or "unspecified"
            ep.blocked_steps.append({"step": step, "agent": agent.name, "tool": gap, "text": inp.strip()})
            self.trace.event("blocked", {"gen_ai.agent.id": agent.agent_id, "gen_ai.agent.name": agent.name,
                                         "gen_ai.tool.name": gap, "amoeba.step": step})
            return f"\n{inp}\n", gap
        if act in (PRINT, "") or FINAL_OUTPUT in act:        # :213 — Print and Final Output echo the input
            return f"\n{inp}\n", None
        registered = act in self.tools                       # D21: not a silent echo — record it, run nothing
        self.trace.event("unknown_tool", {"gen_ai.agent.id": agent.agent_id, "gen_ai.agent.name": agent.name,
                                          "gen_ai.tool.name": act, "amoeba.tool.registered": registered,
                                          "amoeba.step": step})
        if not registered and not any(q.name == act and q.for_role == agent.name for q in ep.requested_capabilities):
            ep.requested_capabilities.append(CapabilityRequest(
                name=act, kind="tool", for_role=agent.name, source="runtime_unknown_tool", input=inp,
                what_it_does="chosen as an action during the run; no such tool is registered"))
        return f"\n[{act!r} is not a tool {agent.name} can use; nothing was run]\n{inp}\n", None

    # box: read_action
    def _tool(self, agent: AgentSpec, name: str, action_input: str) -> str:
        with self.trace.span("execute_tool", {"gen_ai.tool.name": name, "gen_ai.agent.id": agent.agent_id,
                                              "gen_ai.agent.name": agent.name}) as rec:
            try:
                result = self.tools.execute(name, action_input, agent)
            except ToolError as e:
                rec["error.type"] = type(e).__name__
                result = f"error: {e}"
        self.listener.on_tool_call(agent.agent_id, result)
        return result

    # ---- boss_reviewers: AgentVerse VerticalSolverFirstDecisionMaker.astep --------------------------------
    # box: ov_run, disagree
    def run_boss_reviewers(self, cfg: TeamConfig, task: Task, ep: Episode) -> tuple[str | None, str | None]:
        solver = cfg.agents[cfg.exit]
        critics = [cfg.agents[e.dst] for e in cfg.edges if e.type == "review"]
        memory: dict[str, list[_Msg]] = {a.agent_id: [] for a in [solver, *critics]}   # ChatHistoryMemory; never reset

        # box: disagree
        def broadcast(msgs: list[_Msg]) -> None:             # vertical_solver_first.py:74-76
            for a in [solver, *critics]:
                memory[a.agent_id].extend(msgs)

        # box: solver
        def call(agent: AgentSpec, kw: dict) -> str:         # solver.py:38-59 / critic.py:65-91 + llms/openai.py:436-446
            system = render(resolve(agent.prompt.system), **kw)          # prepend template
            if agent.role == "solver" and pool_skill_notes(agent):       # D56: the solver prompt has no card slot
                system += "\n\n" + "\n".join(pool_skill_notes(agent))
            recent = memory[agent.agent_id][-agent.max_history:] if agent.max_history > 0 else []
            hist = [{"role": "assistant", "content": f"[{m.sender}]: {m.content}"} for m in recent]   # chat_history.py:102-107
            user = render(resolve(agent.prompt.user), **kw)              # append template
            with self.trace.span("invoke_agent", {"gen_ai.agent.id": agent.agent_id, "gen_ai.agent.name": agent.name,
                                                  "amoeba.box": "critics" if agent.role == "critic" else "solver"}):
                return self._llm_messages(agent, [{"role": "system", "content": system}, *hist,
                                                  {"role": "user", "content": user}], ep)
            # This is why format="history+append": the plan and reviews reach agents as chat history, not placeholders.

        # box: solver
        def solve() -> _Msg:
            kw = dict(task_description=task.prompt, role_description=with_card(solver.description, solver))   # + D24 card
            raw = call(solver, kw)                           # parser 'dummy' → raw text (output_parser.py:300-303)
            if not raw.strip():                              # one retry on empty; on failure content "" (solver.py:70-76)
                raw = call(solver, kw)
            return _Msg(sender=solver.name, content=raw or "")

        # box: critics
        def review(c: AgentSpec) -> _Msg:
            kw = dict(task_description=task.prompt, role_description=with_card(c.description, c))   # + D24 card
            for _attempt in range(2):                        # original max_retry from config (1000!); DEVIATION D10: 2
                try:
                    agree, crit = parse_critic(call(c, kw))
                    break
                except ParseError:
                    continue
            else:
                agree, crit = False, ""                      # critic.py:100-108 → SILENT (== agree) at vertical_solver_first.py:62
            return _Msg(sender=c.name, content=crit, is_agree=agree)

        plan = solve()                                       # :41
        broadcast([plan])                                    # :42
        for _round in range(cfg.max_inner_turns):            # :44 — 3
            reviews = [review(c) for c in critics]           # :45-49 parallel in the original; sequential here (D11)
            nonempty = [r for r in reviews if not r.is_agree and r.content != ""]   # :60-63 — agreeing critics are silent
            if not nonempty:                                 # :64-66 "Consensus Reached"
                break
            broadcast(nonempty)                              # :67 — only the disagreements, to everyone
            plan = solve()                                   # :68
            broadcast([plan])                                # :70
        return plan.content, None                            # :71-72 → answer. NB the last revision is never reviewed.
