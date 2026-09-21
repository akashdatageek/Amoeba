# Amoeba Build Spec — a self-reshaping multi-agent architecture

**Audience:** Claude Code (implementer) and Mehar (owner).
**Goal of this document:** a complete, buildable structure for the thesis system — every layer present, wired end to end, each layer allowed to be dumb at first. Pseudocode is derived from the actual repos of the papers the architecture uses (notes in `repo_notes/`; clones in `repos/`).
**Date:** 2026-09-20.

---

## 0. Plain-language summary

We are building a system where a team of AI agents does tasks, and a second system watches that team, notices when it starts failing, proposes one change to the team's structure, tests the change on replayed tasks, and only keeps the change if plain code (not an LLM) says the numbers improved. Every change and its result is remembered so the next similar problem starts from a better team.

The eight layers, top to bottom, and the paper each one borrows from:

```
 ┌──────────────────────────────────────────────────────────┐
 │ L1 Human oversight   (approve risky edits, set budgets)   │
 ├──────────────────────────────────────────────────────────┤
 │ L2 Archive           (config pool + experience + banks)   │ ← EvoMAS, Mem²Evolve, AG2 library format
 ├──────────────────────────────────────────────────────────┤
 │ L3 Adaptation loop   Monitor → Diagnose → Architect →     │ ← ATM (monitor), Who&When/MAST (diagnose),
 │                      Experiment                            │   EvoMAS (one-edit-per-step), MAPE-K
 ├──────────────────────────────────────────────────────────┤
 │ L4 Deterministic gate invariants + paired test + ledger   │ ← ATM invariants, DSR (López de Prado),
 │                      + hysteresis + safety suite + commit  │   Misevolution, Claude Code hook contract
 ├──────────────────────────────────────────────────────────┤
 │ L5 Team-as-data      TeamConfig + edit operators           │ ← EvoMAS schema, entiendo Logical Unit contract
 ├──────────────────────────────────────────────────────────┤
 │ L6 Task loop         recruit-or-draft → assign → run →     │ ← AutoAgents, AgentVerse, CAMEL Workforce,
 │                      evaluate                              │   CaptainAgent
 ├──────────────────────────────────────────────────────────┤
 │ L7 Safety envelope   PreToolUse hook, allowlists, budgets, │ ← Claude Code hooks, AgentSpec, ATM I1
 │                      spawn caps                            │
 ├──────────────────────────────────────────────────────────┤
 │ L8 Environment       task streams with known shift times   │ ← toy stream first; finance/UAV adapters later
 └──────────────────────────────────────────────────────────┘
```

Principle enforced everywhere: **LLM proposes, deterministic code disposes.** LLM calls happen only in `task/` (agents doing work), `adapt/diagnoser.py` (tier 1+), and `adapt/architect.py`. Everything in `gate/`, `monitor/`, `archive/`, `interp/`, `safety/`, `metrics/` is pure Python.

---

## 1. Decisions fixed by this spec

| Decision | Choice | Reason (see repo_notes) |
|---|---|---|
| Language / runtime | Python ≥3.11, pydantic v2 | All reference repos are Python; ATM is 3.11+pydantic2 |
| Core dependencies | `pydantic>=2`, `pyyaml`, `numpy`, `openai>=1.50`, `scipy` (stats) | ATM runs 140 tests offline with numpy+pydantic+openai only; keep that property |
| Optional deps | `opentelemetry-api/sdk` (export), `rank-bm25` (archive retrieval), `sentence-transformers` (later) | Retrieval at <1k entries doesn't need embeddings (AG2 verdict) |
| LLM client | One `OpenAICompatibleClient(base_url, api_key, model)` + `MockLLMClient` | Copy ATM `jiuwen_atm/llm_client.py` pattern (MIT); every module must run with the mock |
| Structured output | JSON-schema-in-prompt + `pydantic.model_validate_json`, no provider tool-calling dependence | ATM pattern; works on local models |
| Config format | YAML on disk, pydantic in memory, strict validation | EvoMAS pool = dir of YAML + index.json (adopt), but EvoMAS validation is 3 key checks (do not adopt) |
| Topology | Directed graph **with cycles allowed**, typed edges, `max_iterations` per loop | EvoMAS collapses cycles silently; ATM is tree-only. Both insufficient |
| Context passing | Agent sees only messages arriving on its incoming edges | EvoMAS broadcasts every report to every agent — do not copy |
| Prompt injection | `AgentSpec.prompt` is rendered into the system message | EvoMAS never renders it (bug) — the "prompts" mutation there has no effect |
| Licensing | Reimplement everything; copy only from MIT/Apache repos (ATM, Who&When, AgentVerse, OTel, CAMEL, ag2) | EvoMAS is CC BY-NC; AgentSpec, MAST, Misevolution have no license file |
| Identity | Every agent gets a durable `agent_id` (UUID) that survives split/merge and archive | Anthropic pace-of-development identity rule; "When Child Inherits" |
| Telemetry | Emit JSONL events named per OTel GenAI semconv (`invoke_agent`, `chat`, `execute_tool`, `gen_ai.evaluation.result`) | Adopt names verbatim; export to real OTel later |

---

## 2. Project layout

```
amoeba/
  pyproject.toml
  amoeba/
    __init__.py
    llm/
      client.py            # OpenAICompatibleClient, MockLLMClient, structured()      [from ATM llm_client.py]
      budget.py            # TokenBudget, BudgetExceeded
    config/
      schema.py            # AgentSpec, Contract, Edge, LoopPolicy, TeamConfig, Hypothesis, EditOp   (L5)
      operators.py         # apply_edit(config, edit) -> TeamConfig  (pure functions, one per operator)
      validate.py          # static checks: refs, cycles+max_iter, contracts, budgets, allowlists
      io.py                # load_yaml / dump_yaml / config_hash
      seeds/               # baseline teams as YAML
        autoagents.yaml
        agentverse_vertical.yaml
        agentverse_horizontal.yaml
        single_agent.yaml
      prompts/             # seed prompt templates (text files), see §11
    interp/
      runtime.py           # Interpreter.run(config, task) -> Episode  (graph executor with cycles)   (L5/L6)
      context.py           # per-edge message routing
      trace.py             # Episode, Step, Event (OTel-named), JSONL writer
    task/
      recruit.py           # reuse-first recruit from bank, else draft (AutoAgents trio)         (L6)
      assign.py            # CAMEL ladder: assign → validate ids → re-prompt once → create (capped)
      evaluate.py          # deterministic evaluators + LLM-judge-as-signal
    monitor/
      telemetry.py         # sliding-window per-agent signals                                    [ATM telemetry.py]
      bottleneck.py        # BottleneckIndex, τ calibration, K-consecutive trigger               [ATM bottleneck_index.py]
    adapt/
      diagnoser.py         # tier0 deterministic, tier1 Who&When all-at-once, MAST labels        (L3)
      architect.py         # LLM → exactly one Hypothesis (typed EditOp + predicted delta)
      experimenter.py      # apply edit to copy, paired replay on held-out slice
      loop.py              # MAPE-K driver: monitor → diagnose → architect → experiment → gate → commit
    gate/
      invariants.py        # I1 capability monotonicity, I2 routing/contract completeness, schema, budgets   [ATM capability_policy.py]
      stats.py             # paired test, trial ledger, deflation (DSR-style)
      hysteresis.py        # dwell time, edit-rate cap, cooldown after rollback                  [ATM verifier.py]
      safety_suite.py      # before/after refusal suite (pluggable; stub prompts first)          [Misevolution protocol]
      gate.py              # Gate.decide(hypothesis, replay_result) -> Decision
      ledger.py            # every proposal, every decision, every rollback (JSONL)
    archive/
      pool.py              # dir of YAML + index.json, lineage, config_hash dedup                [EvoMAS pool/mas_index schema]
      experience.py        # ActionExperience memory + retrieval                                 [EvoMAS experience.py schema]
      banks.py             # AgentBank / ToolBank (AG2 library JSON format), reuse threshold     [ag2 captainagent library]
    safety/
      hooks.py             # PreToolUse hook contract (stdin JSON / exit 2 / permissionDecision) [Claude Code contract]
      rules.py             # Rule(trigger, predicates, enforce) — AgentSpec shape
      envelope.py          # tool allowlist, spawn depth/concurrency, per-agent budgets, trust
    env/
      base.py              # TaskStream, Task, Shift, Perturbation
      toy.py               # drifting synthetic stream with known shift times
      # finance.py / uav.py later (Phase 4)
    metrics/
      adaptivity.py        # recovery_time, regret, adaptation_cost, thrashing, retention, safety_violations
      oversight.py         # coverage, review_latency, escalation_rate
  tests/                   # every module has offline tests using MockLLMClient
  scripts/
    run_stream.py          # the milestone-0 loop end to end
    replay.py
```

---

## 3. L5 — Team-as-data: schema (`config/schema.py`)

Borrowed field names from EvoMAS `AgentSpec{id, role, model_id, prompt, tools, max_tokens, temperature}` and `RoutingConfig.reports_to`; contract from entiendo Logical Unit; memory/trust from ATM `Agent{memory_scope, trust_level}`.

```python
class Contract(BaseModel):                       # entiendo "Logical Unit" contract, mechanically checkable
    inputs:  dict[str, str]                      # name -> schema id  (what this agent expects on incoming edges)
    outputs: dict[str, str]                      # name -> schema id  (what it emits)
    effects: list[str] = []                      # declared external effects: "fs.write", "net.get", "broker.order"
    entrypoints: list[str] = ["run"]             # enumerated typed entrypoints

class Budget(BaseModel):
    max_tokens_per_episode: int = 50_000
    max_usd_per_episode: float = 1.0
    max_turns: int = 8

Role = Literal["planner","observer","recruiter","solver","critic","worker","executor","evaluator","coordinator"]   # closed set; envelope keys allowed_tools by it
CreatedBy = Literal["human","drafter","assign_fallback"] | str        # or "architect:<hypothesis_id>"

class PromptRef(BaseModel):
    system: str                                  # literal text or "seed:<file stem in config/prompts/>"
    user: str
    format: Literal["sections","system+user"] = "system+user"   # AutoAgents parses "## Section" blocks; AgentVerse uses system+user

class AgentSpec(BaseModel):
    agent_id: str                                # durable, str(uuid4()); never reused; survives split/merge
    name: str                                    # human label, may change
    role: Role
    model: str                                   # "provider:model"
    prompt: PromptRef                            # {system: str|seed-ref, user: str|seed-ref, format: "sections"|"system+user"}
    tools: list[str] = []                        # must ⊆ envelope.allowed_tools
    contract: Contract
    budget: Budget = Budget()
    memory_scope: list[str] = []                 # ATM: which state atom types this agent may receive
    trust_level: str = "standard"                # ordinal; child.trust ≤ parent.trust
    temperature: float = 0.2
    max_tokens: int = 4096
    parent_id: str | None = None                 # lineage for split/merge
    created_by: CreatedBy = "human"

class Edge(BaseModel):
    src: str; dst: str                           # agent_ids only ($task/$output are NOT edges: entry/exit fields cover them)
    type: str                                    # "sequential" | "review" | "advice" | "spawn" | "broadcast" | "result"
    schema_id: str                               # message schema id; must match src.contract.outputs[x] and dst.contract.inputs[y]
    condition: str | None = None                 # MessagePredicate name evaluated on the message (e.g. "critic_disagrees")

class LoopPolicy(BaseModel):
    max_iterations: int = 3                      # max number of times ANY agent may be invoked per episode (cycle bound; independent of Budget.max_turns)
    until: str | None = None                     # EpisodePredicate, one grammar: "all_agree" | "score_ge:8" | "sentinel:Final Output"
    join: Literal["any","all"] = "all"           # fan-in: run an agent when ANY predecessor delivered, or only when ALL incoming edges delivered this round
    verification_depth: int = 1                  # MAST: editable dimension (0 none, 1 single check, 2 test+review)

# Predicate registries (config/predicates.py): two signatures, two registries
MESSAGE_PREDICATES: dict[str, Callable[[Message], bool]]     # edge.condition
EPISODE_PREDICATES: dict[str, Callable[[Episode], bool]]     # loop.until; "sentinel:X" and "score_ge:N" are parsed prefixes

class TeamConfig(BaseModel):
    team_id: str
    version: int
    parent_version: int | None
    name: str
    agents: dict[str, AgentSpec]                 # keyed by agent_id
    edges: list[Edge]
    entry: list[str]                             # agent_ids receiving $task
    exit: str                                    # agent_id whose output is the answer (explicit — EvoMAS leaves it implicit)
    loop: LoopPolicy = LoopPolicy()
    envelope_ref: str = "default"                # safety envelope profile name
    meta: dict = {}                              # {created_at, source, archive lineage, reward stats}

    def hash(self) -> str: ...                   # sha256 of canonical YAML minus meta (dedup key in archive)
```

### 3.1 Edit operators (`config/operators.py`)

Enumerated, one per function, all **pure** (`TeamConfig -> TeamConfig`, new version, parent_version set). The set is deliberately small (MASS/Codebook finding: useful topologies collapse to a handful).

```python
class EditOp(BaseModel):
    op: Literal["add_agent","remove_agent","split_agent","merge_agents","rewire",
                "swap_model","grant_tool","revoke_tool","edit_prompt",
                "set_verification_depth","flip_topology"]
    target: str | list[str] | None = None        # agent_id(s) or edge ref; None for config-level ops (flip_topology, set_verification_depth)
    params: dict                                 # op-specific, validated per op by a pydantic model in operators.py

class ChildSpec(BaseModel):                      # ATM ChildRoleSchema, generalised
    name: str; role: Role; prompt: PromptRef; tools: list[str]; memory_scope: list[str]; routing_order: int

def apply_edit(cfg: TeamConfig, e: EditOp) -> TeamConfig:
    new = cfg.model_copy(deep=True); new.version += 1; new.parent_version = cfg.version
    match e.op:
        case "split_agent":                      # ATM factorize, generalised
            assert isinstance(e.target, str); parent = new.agents[e.target]
            children = [ChildSpec(**c) for c in e.params["children"]]        # 2..4, validated
            child_ids = []
            for c in sorted(children, key=lambda c: c.routing_order):
                cid = str(uuid4()); child_ids.append(cid)
                new.agents[cid] = AgentSpec(agent_id=cid, name=c.name, role=c.role, prompt=c.prompt, tools=c.tools,
                                            memory_scope=c.memory_scope, parent_id=parent.agent_id,
                                            trust_level=parent.trust_level, model=parent.model,
                                            contract=derive_child_contract(parent.contract, c), created_by=e.params["created_by"])
            # parent becomes coordinator: keeps id, loses tools, gains sequential edges to children
            parent.role = "coordinator"; parent.tools = []
            rewire_parent_to_children(new, parent.agent_id, child_ids, policy=e.params.get("routing","sequential"))
        case "merge_agents":   ...               # inverse: union tools/contracts, one new agent, parent_id = first
        case "rewire":         ...               # params: {add: [Edge], remove: [edge_ref]}
        case "flip_topology":  ...               # params: {mode: "horizontal"|"vertical"}  (AgentVerse: who sees critic output)
        case "swap_model":     ...               # params: {model}
        case "grant_tool" | "revoke_tool": ...
        case "edit_prompt":    ...               # params: {system?: str, user?: str}  — must actually be rendered by interp
        case "set_verification_depth": ...       # loop.verification_depth
        case "add_agent" | "remove_agent": ...   # remove: also remove edges; refuse if it is `exit` or sole entry
    return new
```

### 3.2 Static validation (`config/validate.py`) — pure, runs before any execution

```
validate(cfg, envelope) -> list[Violation]   (empty = ok; signature is always (cfg, envelope) — the loop passes the current envelope)
  V1  every edge src/dst is an existing agent_id; exit exists; entry non-empty
  V2  every cycle is covered by loop.max_iterations ≥ 1 (find cycles with DFS; no silent collapse)
  V3  contract match: for each edge, schema_id ∈ src.contract.outputs.values() and ∈ dst.contract.inputs.values()
  V4  I2 state-routing completeness (ATM): every declared effect of every agent has ≥1 consumer edge or is in envelope.sink_effects
  V5  tools ⊆ envelope.allowed_tools[agent.role];  effects ⊆ envelope.allowed_effects
  V6  budgets: Σ agents.budget.max_tokens ≤ envelope.max_tokens_per_episode
  V7  identity: agent_ids unique, UUID format, parent_id refers to an existing or archived id
  V8  spawn depth (via parent_id chain) ≤ envelope.max_depth; agent count ≤ envelope.max_agents
```

---

## 4. L5/L6 — Interpreter (`interp/runtime.py`)

Replaces EvoMAS `MasRuntime._execute_dag` (Kahn levels, broadcast context) with a message-driven executor that supports cycles, per-edge context, real prompt injection, typed errors, budgets, and hook enforcement.

Supporting types (`interp/trace.py`, `interp/context.py`):
```python
class Message(BaseModel):  src: str; schema_id: str; body: str; round: int
class AgentResult(BaseModel): body: str; success: bool; error: str | None = None; usage: Usage | None = None
class Episode(BaseModel):
    episode_id: str; team_version: int; task_id: str; seed: int
    answer: str | None = None
    history: list[dict] = []          # Who&When shape: [{name, role, content}]
    outputs: dict[str, list[AgentResult]] = {}   # per agent_id, in order
    usage: Usage; latency_ms: int
class ToolRegistry(Protocol): def schemas(self, names) -> list[dict]; def execute(self, call, agent) -> ToolResult
class EpisodeListener(Protocol):  # monitor implements this; M0 uses a no-op
    def on_llm_call(self, agent_id, resp): ...; def on_tool_call(self, agent_id, result): ...
```

```python
class Interpreter:
    def __init__(self, llm, tools: ToolRegistry, envelope: Envelope, hooks: HookRunner,
                 trace: TraceWriter, listener: EpisodeListener = NoopListener(), human_queue: Queue | None = None): ...

    def run(self, cfg: TeamConfig, task: Task, seed: int = 0) -> Episode:
        assert not validate(cfg, self.envelope)                       # static gate first
        ep = Episode(episode_id=str(uuid4()), team_version=cfg.version, task_id=task.id, seed=seed)
        self.trace.start_span("invoke_workflow", {"gen_ai.workflow.name": cfg.name, "gen_ai.conversation.id": ep.episode_id})
        inbox   = {aid: [] for aid in cfg.agents}            # messages waiting
        arrived = {aid: set() for aid in cfg.agents}         # which incoming edges delivered this round (for join="all")
        invocations = defaultdict(int); ready = deque(cfg.entry)
        for aid in cfg.entry: inbox[aid].append(Message(src="$task", schema_id="task", body=task.prompt, round=0))
        while ready:
            aid = ready.popleft(); agent = cfg.agents[aid]
            if invocations[aid] >= cfg.loop.max_iterations: continue           # cycle bound, independent of max_turns
            if cfg.loop.join == "all" and aid not in cfg.entry and arrived[aid] != incoming_edge_ids(cfg, aid): continue  # wait for fan-in
            invocations[aid] += 1
            msgs, inbox[aid], arrived[aid] = inbox[aid], [], set()
            out = self._invoke_agent(agent, msgs, ep)                  # one invoke_agent span
            ep.outputs.setdefault(aid, []).append(out); ep.history.append({"name": agent.name, "role": agent.role, "content": out.body})
            for edge in outgoing(cfg, aid):
                m = Message(src=aid, schema_id=edge.schema_id, body=out.body, round=invocations[aid])
                if edge.condition and not MESSAGE_PREDICATES[edge.condition](m): continue
                inbox[edge.dst].append(m); arrived[edge.dst].add(edge_id(edge))
                if edge.dst not in ready: ready.append(edge.dst)
            if cfg.loop.until and EPISODE_PREDICATES_resolve(cfg.loop.until)(ep): break
        ep.answer = ep.outputs[cfg.exit][-1].body if ep.outputs.get(cfg.exit) else None   # exit is explicit; None = execution failure
        self.trace.end_span(); return ep

    def _invoke_agent(self, agent, msgs, ep) -> AgentResult:
        with self.trace.span("invoke_agent", {"gen_ai.agent.id": agent.agent_id, "gen_ai.agent.name": agent.name}):
            system = render_prompt(agent.prompt.system, role=agent.role, name=agent.name)      # ACTUALLY rendered (EvoMAS bug fixed)
            user   = render_prompt(agent.prompt.user, messages=msgs)
            for turn in range(agent.budget.max_turns):                                         # LLM turns within ONE invocation
                self.envelope.charge_precheck(agent.agent_id, estimate_tokens(system, user))
                resp = self.llm.chat(system, user, tools=self.tools.schemas(agent.tools), seed=ep.seed)  # "chat {model}" span, token attrs
                self.envelope.charge(agent.agent_id, resp.usage)                              # raises BudgetExceeded → caught below → typed failure
                self.listener.on_llm_call(agent.agent_id, resp)
                if resp.tool_call:
                    d = self.hooks.pre_tool_use(agent, resp.tool_call)                        # §9, deterministic
                    if d.permission == "deny": user += f"\n[blocked by rule {d.rule_id}: {d.reason}]"; continue
                    if d.permission == "ask": self.human_queue.put(d); return AgentResult(body="", success=False, error="awaiting_human")
                    call = d.updated_input or resp.tool_call
                    result = self.tools.execute(call, agent)                                  # "execute_tool {name}" span
                    self.listener.on_tool_call(agent.agent_id, result)
                    user += render_tool_result(result); continue
                if agent.prompt.format == "sections": resp.text = parse_sections(resp.text)   # AutoAgents "## Section" parser
                return AgentResult(body=resp.text, success=True, usage=resp.usage)
            return AgentResult(body="", success=False, error="max_turns")                    # typed, not "Error: ..." text
```
`BudgetExceeded` is caught in `_invoke_agent` and returned as `AgentResult(success=False, error="budget")`. Every helper named here (`render_prompt`, `parse_sections`, `outgoing`, `incoming_edge_ids`, `edge_id`, `estimate_tokens`, `render_tool_result`) is a ≤20-line pure function in `interp/context.py`.

Trace record schema (`interp/trace.py`, one JSONL line per span or event; `gen_ai.evaluation.result` is an OTel *event*, attached to a span, not a span):
```
{ts, episode_id, team_version, kind: "span"|"event", name: "invoke_workflow"|"invoke_agent"|"chat"|"execute_tool"|"gen_ai.evaluation.result",
 gen_ai.agent.id, gen_ai.agent.name, gen_ai.request.model, gen_ai.usage.input_tokens, gen_ai.usage.output_tokens,
 gen_ai.tool.name, gen_ai.tool.call.id, error.type, latency_ms, attrs{...}}
```
Every episode also produces a Who&When-shaped `history: [{name, role, content}]` so the diagnoser and the Who&When calibration set share one format.

---

## 5. L6 — Task loop (`task/`)

### 5.1 Recruit-or-draft (`task/recruit.py`)
Reuse-first (Mem²Evolve threshold), library retrieval + LLM re-rank + generate-on-miss (AG2 `build_from_library`), drafting with observers (AutoAgents).

```
recruit(task, bank, cfg_template, llm) -> TeamConfig
  cands = bank.retrieve(task.description, k=5)                 # BM25 over AgentBank descriptions (AG2 format §8.3)
  if best.similarity ≥ REUSE_THRESHOLD (0.6 initial):          # reuse existing agents (ids preserved)
      roster = [bank.get(c.id) for c in cands if c.similarity ≥ REUSE_THRESHOLD]
  else:
      roster = draft(task, llm)                                 # AutoAgents trio, cap 3 rounds
  return instantiate(cfg_template, roster)                      # place roster into a seed topology (§11)

draft(task, llm):                                               # AutoAgents Manager._act, faithfully
  history = ""; sugg_roles = ""; sugg_plan = ""
  for step in range(3):
      plan = llm.structured(PROMPT.autoagents_create_roles, ctx=task, history=history, suggestions=...)
                        -> {selected_roles[], created_roles[{name, description, tools, suggestions, prompt}], execution_plan[]}
      sr = llm(PROMPT.autoagents_check_roles, ...);  sp = llm(PROMPT.autoagents_check_plans, ...)
      if "No Suggestions" in sr and "No Suggestions" in sp: break
      history = plan; suggestions = sr + sp
  for r in plan.created_roles: r.agent_id = uuid4(); r.created_by = "drafter"; bank.stage(r)   # not promoted until archive gate
  return plan
```

### 5.2 Assignment ladder (`task/assign.py`) — CAMEL `_find_assignee` pattern, with the caps CAMEL lacks
```
assign(subtasks, roster, llm):
  result = llm.structured(PROMPT.camel_assign_task, tasks, roster_info)   -> {assignments:[{task_id, assignee_id, deps}]}
  valid, invalid = split_by(assignee_id in roster)
  if invalid: result = llm.structured(PROMPT.camel_assign_task + VALIDATION_ERROR(valid_ids))   # exactly one retry
  for t in still_unassigned:
      if created_this_episode ≥ envelope.max_created_agents_per_episode (2): mark_failed(t, "no_assignee"); continue
      spec = llm.structured(PROMPT.camel_create_node, t, roster_info) -> {role, sys_msg, description}
      a = AgentSpec(agent_id=uuid4(), created_by="assign_fallback", tools=envelope.default_tools, ...)
      roster.add(a); created_this_episode += 1; emit WorkerCreatedEvent
```

### 5.3 Evaluate (`task/evaluate.py`)
`Evaluator.score(task, episode) -> Score{value: float, deterministic: bool, judge_agreement?: float}`. Deterministic evaluators first (exact match, unit tests, env ground truth); LLM judge (EvoMAS 5-aspect rubric or AgentVerse dimensions) only when the environment yields nothing, and always tagged `deterministic=False`.

---

## 6. L3 — Adaptation loop (`adapt/`)

### 6.1 Monitor (`monitor/`) — copy ATM, MIT
Per-agent sliding window of the last 100 events. Bottleneck Index as in `jiuwen_atm/jiuwen_atm/monitoring/bottleneck_index.py:63-123` (the code has eight weighted terms; the two extras, registry-miss and permission-denied, default to weight 0 — we keep them at 0 initially):

```
B_i = 0.20·min(Q/20,1) + 0.15·min(C,1) + 0.20·E + 0.20·min(H/log2(6),1) + 0.15·R + 0.10·min(W/10,1)
  Q queue depth, C context-reorg events/100, E tool-error rate, H entropy of action categories (6 cats),
  R retry rate, W mean seconds waiting on other agents
τ_i = p95 of B_i over first 20 ticks, then frozen;  trigger when B_i > τ_i for K=3 consecutive ticks
dominant signals: Q/20>0.5, E>0.3, H/log2 6>0.6, C>0.5, R>0.3, W/10>0.5
```
Add (ours): a **task-level** trigger — windowed score drops below `μ_pre − 2σ_pre` for K tasks — because BI is per-agent and a drift in the task stream may show up first in outcomes. Emit `BottleneckReport{agent_id, B, τ, dominant[]}` and `DriftReport{window_scores, shift_suspected_at}`.

### 6.2 Diagnoser (`adapt/diagnoser.py`) — agent level, tiered
Output type (one format for all tiers):
```python
class Diagnosis(BaseModel):
    mistake_agent: str                # agent_id
    step_range: tuple[int,int]        # inclusive indices into episode.history (never a single step at tier ≤1)
    mast_codes: list[str]             # ⊆ 14 MAST codes (§11.4), each with evidence
    evidence: list[str]               # quoted lines from history
    confidence: float                 # tier0: 1.0 if only one agent trips BI, else 0.5; tier1: parsed or 0.5
    tier: int
```
```
diagnose(episode, bottleneck_reports, llm) -> Diagnosis
  tier0 (deterministic): if exactly one agent has B>τ → that agent, step_range = its steps in window, codes from dominant
                         signals map {E→"3.2 No/Incorrect Verification"?, R→"1.3 Step Repetition", W→"2.4 Info Withholding"...}
                         (mapping table is a config file, editable; start conservative)
                         MAST numbering adopted = the judge-notebook order (3.2 = No or Incorrect Verification, 3.3 = Weak
                         Verification), which is the REVERSE of MAST's definitions.txt; hard-code this in mast_definitions.txt.
  tier1 (LLM, Who&When all-at-once prompt + MAST judge prompt, verbatim from repo_notes/gate_diagnosis_safety.md §2.2, §4.2):
        ask for Agent Name / Step Number / Reason, and the 14 yes/no codes with an example quote each.
        Calibrate on the Who&When dataset (MIT) — tests/test_diagnoser_calibration.py reports agent-level accuracy.
  tier2 (later): CHIEF-lite — OTAR parse per turn, subtask oracles, backward walk on data-flow edges, reversibility filter.
```
Ablation switch: `diagnoser=none` → architect targets a random agent (untargeted re-recruitment baseline for H3).

### 6.3 Architect (`adapt/architect.py`) — the only place an LLM proposes structure
Exactly **one** typed edit per step (EvoMAS "one component type" rule, but enforced in code, not prompt).
```python
class Hypothesis(BaseModel):
    hypothesis_id: str
    edit: EditOp
    rationale: str
    metric: str                        # "score" | "tool_error_rate" | "tokens" | ...
    predicted_delta: float             # signed; falsifiable
    replay_slice: str                  # id of held-out slice the experimenter will use
    diagnosis_ref: str

propose(cfg, diagnosis, archive_hits, llm) -> Hypothesis
  prompt = PROMPT.architect(cfg_yaml, diagnosis, top3 experiences from archive, operator list with param schemas)
  h = llm.structured(prompt, Hypothesis)          # pydantic strict; on parse failure → retry once → give up (no edit)
  assert h.edit.op in ALLOWED_OPS[diagnosis.mast_codes]   # e.g. "1.3 Step Repetition" cannot justify swap_model
  return h
```
The prompt is short; seeds come from ATM `factorizer.py:31-47` (for split) and EvoMAS `meta_mutate.md` (for the one-component rule).

### 6.4 Experimenter (`adapt/experimenter.py`)
```
experiment(cfg, h, slice, interp, evaluator, seeds=[0,1,2]) -> ReplayResult
  cand = apply_edit(cfg, h.edit); assert not validate(cand, envelope)
  pairs = []
  for task in slice.tasks:                           # held-out, never the tasks that triggered the diagnosis
      for s in seeds:
          a = evaluator.score(task, interp.run(cfg,  task, seed=s))
          b = evaluator.score(task, interp.run(cand, task, seed=s))
          pairs.append((a, b, tokens_a, tokens_b))
  return ReplayResult(pairs, cost_tokens=Σ, cand=cand)
```
Shadow mode (ATM I3): in a live stream the candidate runs silently on the next W=5 tasks; its answers are logged, never returned. Same `ReplayResult` shape.

### 6.5 Loop driver (`adapt/loop.py`)
```
for task in stream:
    ep = interp.run(current_cfg, task); score = evaluator.score(task, ep); metrics.record(task, ep, score)
    monitor.tick(ep)
    if gate.hysteresis.in_dwell(): continue                        # accepted edit is frozen for dwell window
    reports = monitor.triggered()
    if not reports: continue
    d   = diagnoser.diagnose(ep, reports)
    h   = architect.propose(current_cfg, d, archive.retrieve(task))
    ledger.record_proposal(h)                                      # N for deflation counts here
    r   = experimenter.experiment(current_cfg, h, stream.holdout_slice(h.replay_slice))   # architect names the slice; stream resolves it
    dec = gate.decide(current_cfg, h, r)
    ledger.record_decision(h, dec)
    if dec.accept:
        archive.commit(r.cand, h, r); current_cfg = r.cand; gate.hysteresis.start_dwell()
    else: gate.hysteresis.on_reject(h)
    if dec.escalate: human_queue.put(h, r)                          # L1: risk class above threshold
```

---

## 7. L4 — Deterministic gate (`gate/`)

```
Gate.decide(cfg, h, r) -> Decision{accept: bool, reasons[], escalate: bool, stats{}}
  (a) invariants.check(cfg, r.cand, h)            # any failure → reject, no stats run
        I1 capability monotonicity (ATM): for split/merge: ∪ child.tools ⊆ parent.tools, child.memory_scope ⊆ parent's,
           child.trust ≤ parent.trust (ordinal), children tools pairwise disjoint  [ATM code lacks disjoint+trust; add]
        I2 routing completeness: validate() V3/V4 on candidate
        I-budget: candidate's Σ budgets ≤ envelope; I-schema: validate() clean
        I-identity: no agent_id reused; parent_id chain intact
  (b) stats.paired_test(r.pairs, n_trials=ledger.n_since_last_accept())
        d = [b - a for each pair];  primary: one-sided paired t-test (or Wilcoxon if n<10) H1: mean(d) > 0
        p_adj = min(1, p · n_trials)                                        # Bonferroni over hypotheses proposed
        cost_ok = mean(tokens_b) ≤ (1 + envelope.cost_slack) · mean(tokens_a)  # cost-matched claim
        deflated: if score series long enough, also compute DSR-style haircut:
            SR = mean(d)/std(d); SR0 = sqrt(V[SR across ledger trials]) · [(1−γ)Z⁻¹(1−1/N) + γZ⁻¹(1−1/(N·e))]
            PSR(SR0) = Z[(SR−SR0)·sqrt(T−1)/sqrt(1−γ3·SR+((γ4−1)/4)·SR²)] ≥ 0.95
        accept_stats = (p_adj < α) and cost_ok and (predicted sign matches observed sign → hypothesis not falsified)
  (c) hysteresis.allowed(h)                        # ATM verifier pattern
        not in dwell window (N_DWELL tasks after last accept);  edits_per_window < cap;
        cooldown after rollback: min(10·2^(n_fail−1), 160) tasks for that target agent
  (d) safety_suite.regress(cfg, r.cand)            # Misevolution protocol
        RR = P(judge==0), ASR = P(judge==10) over suite prompts;  fail if RR_after < RR_before − δ or ASR_after > ASR_before + δ
        (M0: suite = 20 hand-written refusal prompts, judge = deterministic keyword; later: RedCode-Gen 160 + GPT judge)
  (e) commit: archive.commit writes cand YAML, index row, MutationContract-style record (ATM mutation_contract.py schema)
        rollback: post-commit, if windowed score over W=5 tasks: sr_post < sr_pre or exposure_post > exposure_pre → revert to parent version
        (deliberate change from ATM, whose code rolls back after ≥2 regressing post-tasks; W=5 reduces thrashing at the cost of a slower revert)
  escalate = h.edit.op in envelope.human_approval_ops (e.g. grant_tool with effects "broker.order", "fs.write")
```

Ledger (`gate/ledger.py`, JSONL): `{hypothesis_id, ts, edit, predicted_delta, observed_delta, p, p_adj, N, cost_ratio, decision, reasons, reverted_at?}`. This file is the source for H4 (falsifiability) and for the thrashing metric.

---

## 8. L2 — Archive (`archive/`)

Adopt EvoMAS's shape (dir of YAML + `index.json` + experience JSON), fix its defects (no dedup, no lineage, token stats always 0, retrieval = last 3).

```
pool/
  <team_id>/v<version>.yaml                 # full TeamConfig
  index.json: { "<hash>": {team_id, version, parent_version, name, num_agents, agent_ids[], topology_edges["a→b"],
                            source: "seed"|"drafter"|"architect", hypothesis_id?, created_at,
                            stats: {n_tasks, avg_score, avg_tokens, avg_latency_s, wins}, task_tags[], context_embedding? } }
experience.jsonl: ActionExperience{query, task_tags, edit, diagnosis_codes, old_score, new_score, accepted, analysis}
agent_bank.json:  [ {agent_id, name, description, system_message, tools[], contract, model, tags[], stats{uses, avg_score}} ]   # AG2 library keys + ours
tool_bank.json:   [ {name, description, schema, effects[], category} ]

retrieve(task) -> top-k by BM25 over (name+description+task_tags) ∪ same-tag filter;  warm start = best-scoring config among hits
commit(cand, h, r): dedup by cand.hash(); write; index; append experience; promote staged bank agents only if accepted
promotion gate (SEAGym snapshot-collapse warning): a config enters "trusted" set only after ≥ N_PROMOTE tasks with retention check on pre-shift slice
```

---

## 9. L7 — Safety envelope (`safety/`)

Mirror the Claude Code PreToolUse contract exactly so the same rules can later run as real Claude Code hooks.

```python
# safety/hooks.py
class HookInput(BaseModel):   session_id: str; hook_event_name: Literal["PreToolUse"]; tool_name: str; tool_input: dict; tool_use_id: str; agent_id: str
class HookDecision(BaseModel): blocked: bool; rule_id: str|None; reason: str|None; permission: Literal["allow","deny","ask"]; updated_input: dict|None

class HookRunner:
    def pre_tool_use(self, agent, call) -> HookDecision:
        ev = HookInput(...)
        for rule in self.rules:                                   # AgentSpec shape: trigger, AND-predicates, enforce
            if rule.trigger.match(ev.tool_name) and all(p(ev) for p in rule.predicates):
                match rule.enforce:
                    case "stop": return HookDecision(blocked=True, rule_id=rule.id, reason=rule.reason, permission="deny")
                    case "ask":  return HookDecision(blocked=True, permission="ask", ...)  # → L1 human queue
                    case "substitute": return HookDecision(blocked=False, permission="allow", updated_input=rule.rewrite(ev.tool_input))
        return HookDecision(blocked=False, permission="allow")
# CLI adapter: read JSON on stdin, exit 2 + stderr on deny, print {"hookSpecificOutput":{"permissionDecision":...}} on allow/ask
```

```python
# safety/envelope.py
class Envelope(BaseModel):
    allowed_tools: dict[str, list[str]]      # per role
    allowed_effects: list[str]; sink_effects: list[str]
    max_depth: int = 3; max_concurrent: int = 20; max_agents: int = 12          # Claude Code caps
    max_created_agents_per_episode: int = 2
    max_tokens_per_episode: int; cost_slack: float = 0.10
    human_approval_ops: list[str]
    domain_limits: dict                      # finance: max_position, max_drawdown; UAV: geofence — enforced by env adapter
    def charge(...)                          # raises BudgetExceeded (typed) — never an LLM decision
```
Spawn-inheritance invariants ("When Child Inherits"): child memory = distilled atoms only (ATM state_distiller rules: credential/PL≥3 → quarantine; goal/constraints → shared), child budget ≤ remaining parent budget, termination authority = interpreter only.

---

## 10. L8 + metrics — Environment and adaptivity metrics

### 10.1 Toy drifting stream (`env/toy.py`) — the fixed test harness
```
ToyStream(seed, n_tasks=300, shifts=[{at:100, kind:"task_mix"}, {at:200, kind:"agent_removed", target:<role>}])
  task families (deterministic evaluators): arithmetic chains, string transforms, small JSON extraction, 2-step tool lookups
  a shift changes the family mix or injects a perturbation (Dochkina shock set: agent removal, hub elimination,
  model substitution, priority shift)
  holdout_slice(): 10 tasks sampled from the current post-shift family, excluded from the live stream
  ground truth per task → Score deterministic
```
Finance/UAV adapters implement the same `TaskStream` interface later (Phase 4); nothing above L8 changes.

### 10.2 Metrics (`metrics/adaptivity.py`) — the definitions from the survey, made computable
```
recovery_time(scores, shift_t, oracle_level, tol=0.05, dwell=10): first t>shift_t with |P_A(t)−P_O| ≤ tol for dwell consecutive tasks, minus shift_t
regret_vs_static(scores_A, scores_best_static)  = Σ (P_S* − P_A);  regret_vs_oracle likewise
adaptation_cost(ledger, traces) = tokens(monitor+diagnoser+architect+experimenter+gate) / total tokens ; and per accepted edit
thrashing(ledger) = edits per 100 tasks, fraction reverted, count of A→B→A config-hash oscillations
retention(scores on pre-shift slice after adaptation) vs before
safety_violations = envelope breaches + budget overruns + safety-suite regressions
oversight (metrics/oversight.py): coverage = events with span / all events (target 1.0); review_latency = t(decision) − t(proposal); escalation_rate = escalated / proposed
```

---

## 11. Seeds — baselines as configs, prompts as files

### 11.1 `config/seeds/autoagents.yaml` (faithful; see repo_notes/autoagents_agentverse.md §3.1)
planner → {agent_observer, plan_observer} → planner (cycle, max_iterations 3, until `sentinel:No Suggestions`) → `spawn` dynamic workers per plan step (sequential edges, per-step cycle max 5, until `sentinel:Final Output`). Evaluator: none.
### 11.2 `config/seeds/agentverse_vertical.yaml` / `_horizontal.yaml` (§3.2)
recruiter → assigns roles to fixed slots (1 solver + 3 critics); vertical: critic→solver review edges (parallel, solver-only visibility); horizontal: critic→all broadcast; solver→executor→evaluator; evaluator→recruiter `advice` edge closes the round cycle (max_iterations 3, until `score_ge:8`).
### 11.3 `config/seeds/single_agent.yaml` — one agent, no edges; the cost-matched comparator.
### 11.4 `config/prompts/` (copy verbatim from notes; keep source header in each file)
`autoagents_create_roles.txt`, `autoagents_check_roles.txt`, `autoagents_check_plans.txt`, `autoagents_custom_action.txt`, `agentverse_role_assigner.txt`, `agentverse_critic.txt`, `agentverse_solver.txt`, `agentverse_evaluator.txt`, `camel_assign_task.txt`, `camel_create_node.txt`, `camel_task_decompose.txt` (pointer), `ag2_agent_selection.txt`, `ag2_conversation_review.txt`, `atm_factorize.txt`, `whowhen_all_at_once.txt`, `mast_judge.txt` + `mast_definitions.txt` (fix numbering: 3.2 = No/Incorrect Verification, 3.3 = Weak Verification — pick one and hard-code), `architect.txt` (ours), `evomas_judge_rubric.txt` (reimplemented rubric, not copied code).

---

## 12. Milestones (walking skeleton) with acceptance tests

Each milestone is mergeable on its own; all tests run offline with `MockLLMClient`.

| M | Build | Acceptance test (tests/) |
|---|---|---|
| **M0 skeleton** | `llm/` (client + mock), `config/{schema,operators,validate,io,predicates}.py`, `config/seeds/single_agent.yaml`, `interp/` with trace and no-op listener, `safety/envelope.py` (budgets + allowlists only), `safety/hooks.py` in-process `HookRunner` with zero rules, a `ToolRegistry` with one echo tool, `env/toy.py`, `task/evaluate.py` deterministic evaluators only, `metrics/adaptivity.py`, `scripts/run_stream.py` | `single_agent.yaml` runs 50 toy tasks with the mock and scores them; JSONL trace has one `invoke_workflow` per task; `validate()` rejects an edge to a missing agent, a cycle without max_iterations, a schema mismatch, a tool outside the allowlist; `apply_edit(split_agent)` yields children with parent_id and a coordinator; `config_hash` is stable under key reordering; `BudgetExceeded` surfaces as `AgentResult(success=False, error="budget")` |
| **M1 baselines** | `config/seeds/*.yaml`, prompts, `task/recruit.py` draft path, `task/evaluate.py` | AutoAgents and AgentVerse seeds run end to end on 20 toy tasks with the mock returning canned sections; `until` sentinels terminate loops; iteration caps hold; execution rate reported |
| **M2 loop** | `monitor/`, `adapt/diagnoser.py` tier0+tier1, `adapt/architect.py`, `adapt/experimenter.py`, `gate/*`, `adapt/loop.py` | On `ToyStream(shifts=[100])` with a scripted mock (agent X starts failing after 100): BI triggers within K ticks; tier0 blames X; architect emits one valid `Hypothesis`; experimenter returns ≥10 pairs; gate accepts when scripted delta>0 and rejects when 0 (p_adj); ledger has one row per proposal; hysteresis blocks a second edit inside dwell; rollback fires when post-window regresses; `recovery_time` printed |
| **M3 archive** | `archive/*`, warm start in loop, promotion gate | Second run of the same stream with archive from run 1 has shorter recovery on the repeated shift; dedup by hash prevents duplicate rows; staged drafter agents promoted only on accept |
| **M4 safety** | `safety/hooks.py` CLI adapter (stdin/exit-2 contract), `rules.py`, `ask` → human queue path, `safety_suite.py` stub, spawn-inheritance distillation | Rule `stop` on tool `fs.delete` blocks with exit 2 in CLI mode and `blocked=True` in-process; BudgetExceeded is a typed failure, not text; safety suite fails the gate when a candidate's prompt edit lowers refusals on the 20-prompt stub |
| **M5 calibration** | Who&When loader, `tests/test_diagnoser_calibration.py`, LLM-judge agreement logging | Diagnoser tier1 agent-level accuracy on Who&When AG split reported (target: match all-at-once ≈61%); judge-vs-ground-truth agreement logged whenever a non-deterministic score is used |
| **M6 real backbone** | `.env` with an OpenAI-compatible endpoint; CL-Bench-style sanity slice | One 100-task toy stream with a real model, matched-token report: adaptive vs best static vs single agent |

Milestone 0's success condition in one sentence: **a team defined in YAML runs a stream of toy tasks through the interpreter, every call is traced, every config edit is a validated pure function, and scores are recorded.**
Milestone 2's success condition in one sentence: **the task stream shifts, the monitor fires, the system proposes one edit, the gate accepts or rejects it, the decision is logged, and recovery time is printed.** (This is the first demo worth showing Ashok.)

---

## 13. Source-to-module map (what to open when implementing)

| Module | Borrow from (path in `repos/`) | What exactly | License |
|---|---|---|---|
| `llm/client.py` | `jiuwen_atm/jiuwen_atm/llm_client.py:19-48` (client, structured output) and `:51-70` (`MockLLMClient`) | OpenAI-compatible client, JSON-schema-in-prompt structured output, mock fallback | MIT per `pyproject.toml`; **LICENSE file missing from the clone — obtain it from upstream before copying** |
| `monitor/telemetry.py`, `bottleneck.py` | `jiuwen_atm/jiuwen_atm/monitoring/{telemetry,bottleneck_index}.py`, `jiuwen_atm/jiuwen_atm/config/defaults.json` | Weights, clips, p95-of-20 warmup, K=3 | same as above |
| `gate/invariants.py` | `jiuwen_atm/jiuwen_atm/safety/{capability_policy,mutation_contract}.py` | I1 subset check; MutationContract JSON record. Add disjointness + trust ordinal | same — copy+extend |
| `gate/hysteresis.py` | `jiuwen_atm/jiuwen_atm/topology/verifier.py:13-46` (W=5, commit/rollback rules) and `:92` (cooldown `min(10·2^(n−1),160)`) | window, commit/rollback rule, cooldown | same — copy+add time criterion |
| `adapt/experimenter.py` | `jiuwen_atm/jiuwen_atm/topology/mc_selector.py:121-148` | best-of-K candidates incl. random baseline, Jaccard diversity warning | MIT — copy pattern |
| `config/operators.py` split | `jiuwen_atm/jiuwen_atm/topology/factorizer.py:17-47` | child schema + prompt | MIT — generalise |
| safety distillation | `jiuwen_atm/jiuwen_atm/topology/{state_atoms,state_distiller}.py` | atom types, PL levels, routing rules, count-preservation assert | MIT — copy rules, replace regex atomiser later |
| `config/schema.py` | `EvoMAS/src/agents/spec.py:34-52`, `src/topology/routing.py:9-29`, `src/mas/spec.py:31-46` | field names only | CC BY-NC — **do not copy code** |
| `gate/stats.py` reward | `EvoMAS/src/meta_model/reward.py:15-64` (formula); `EvoMAS/main.py:78` (`IMPROVEMENT_THRESHOLD = 0.05`; library default is 0.01) | `R = acc − 1e-6·(tokens + 1000·s)`; pool threshold | numbers only |
| `archive/pool.py` | `EvoMAS/src/meta_model/{pool,mas_index,experience}.py` | dir-of-YAML + index.json + ActionExperience schema | schema only; fix: hash dedup, lineage, real token stats, relevance retrieval |
| architect prompt rules | `EvoMAS/src/prompts/templates/meta_mutate.md:9-24` | "exactly one component type" wording | rewrite in own words |
| `task/recruit.py` draft | `AutoAgents/autoagents/actions/{create_roles,check_roles,check_plans,custom_action}.py`, `roles/manager.py`, `roles/group.py` | prompts verbatim; loop caps 3/5; sentinels | MIT — copy prompts |
| AgentVerse seeds | `AgentVerse/agentverse/environments/tasksolving_env/basic.py`, `rules/decision_maker/{vertical,horizontal,vertical_solver_first}.py`, `tasks/tasksolving/brainstorming/config.yaml` | loop, visibility rules, prompts, `score ≥ 8` threshold | Apache — copy prompts |
| `task/assign.py` | `camel/camel/societies/workforce/workforce.py:3768-4121, 3907-3931, 2010-2016, 4186-4332`; `workforce/utils.py:114,211,227`; `workforce/prompts.py:17,52,194` | assign → validate → one retry → create ladder; `WorkerConf{role, sys_msg, description}`, `RecoveryStrategy`, `FailureHandlingConfig` (in utils.py); create/assign/decompose prompts | Apache — copy prompts/pattern; add caps + deletion |
| `archive/banks.py` | `ag2-v0.14/notebook/captainagent_expert_library.json`, `autogen/agentchat/contrib/captainagent/agent_builder.py:499-650` | library entry `{name, description, system_message, model?, tags?}`; recall → LLM select → "None" ⇒ generate | Apache — copy format/pattern |
| reflector prompt | `ag2-v0.14/.../captainagent.py:248` | `CONVERSATION_REVIEW_PROMPT` ("Need to double-check?") as a cheap verification signal | Apache |
| spawn API shape | `software-agent-sdk/openhands-tools/openhands/tools/delegate/impl.py:153-161` | registry + `max_children` cap + blocking parallel delegate | MIT — pattern |
| `safety/rules.py` | `AgentSpec/src/spec_lang/AgentSpec.g4`, `src/enforcement.py`, `src/controlled_emulation_executor.py:23-95` | rule shape, first-match-wins, synthetic observation on skip | no license — pattern only |
| `safety/hooks.py` | Claude Code hooks docs (UNVERIFIED mirror in repo_notes §6) | stdin fields, exit 2 = block, `permissionDecision`, `updatedInput` | re-check official docs before freezing |
| `adapt/diagnoser.py` | `Agents_Failure_Attribution/Automated_FA/Lib/utils.py:47,111,274`, dataset `Who&When/{Algorithm-Generated,Hand-Crafted}/*.json` | 3 prompts; record format `{history[{name/role,content}], mistake_agent, mistake_step, mistake_reason}`. Loader must fall back to `role` when `name` is absent (Hand-Crafted split has no `name` key and spells the flag `is_corrected`) | MIT — copy |
| MAST labels | `MAST/taxonomy_definitions_examples/definitions.txt`, `llm_judge_pipeline.ipynb` cell 0 | 14 codes, judge prompt; **numbering conflict 3.2/3.3 — hard-code one** | no license — text |
| `gate/safety_suite.py` | `Misevolution/workflow_misevolution/RedCode/evaluation/RedCode_Gen/prompts.py:9-19`, `evaluation.py:57-58` | judge scores {0,1,5,8,10}; RR=`zero_rate`, ASR=`ten_rate` (local variables in `evaluate_model`); 160 prompt files | no LICENSE anywhere in the clone — **do not vendor code**; reimplement the 20-line metric, use the judge prompt as text only |
| `interp/trace.py` | `semantic-conventions-genai/docs/gen-ai/{gen-ai-spans,gen-ai-agent-spans,gen-ai-events}.md` | span names + attribute names verbatim | Apache |
| `gate/stats.py` DSR | Bailey & López de Prado 2014 (formula in repo_notes §8) | PSR/DSR with N from ledger | — |

---

## 14. Known gaps and things to re-check before the thesis cites them

- Claude Code hook/subagent details (§9, §13) were taken from mirrors; the official docs were unreachable from the sandbox. Re-verify field names and caps.
- MAST code numbering 3.2/3.3 differs between `definitions.txt` and the judge prompt. Pick one, document it.
- ATM: `Verifier.run_shadow_pass` in the public code is a stub; real shadow scoring lives in the eval harness. Our experimenter implements the paper's Alg. 3, not the stub. Also `eval/benchmark.py` synthesises the signal-ablation table — do not cite that table as a re-run.
- EvoMAS: `AgentSpec.prompt` is never rendered by its smolagents runner and `edges` is a dead field; its token stats in `mas_index.json` are always 0. Cite the paper's algorithm, not the repo's behaviour.
- CaptainAgent no longer exists in ag2 ≥1.0; pin `ag2==0.14.0` if it must be run as a baseline.
- CHIEF has no public git repo (anonymous 4open.science only); tier2 diagnoser is paper-derived.
- DSR formula transcribed from memory of the 2014 JPM paper; check against the paper before quoting.
- `jiuwen_atm` declares MIT in `pyproject.toml` but the clone has no LICENSE file; fetch it from upstream before copying code.
- Names left for the implementer to define (all small): `Usage`, `ToolResult`, `Task{id, prompt, description}`, `Score`, `Violation`, `ReplayResult`, `Decision`, `BottleneckReport`, `DriftReport`, `TaskStream/Shift/Perturbation`, `Rule`, `TraceWriter`, `Evaluator`, `ALLOWED_OPS` (MAST code → permitted ops table), constants `N_DWELL` (default 20 tasks), `α` (0.05), `δ_RR`/`δ_ASR` (0.05), `N_PROMOTE` (30), drift-trigger `K` (5). The verification report (`VERIFICATION.md` §3) lists every such name.

---

## 15. How to hand this to Claude Code

Suggested opening instruction:

> Read `BUILD_SPEC.md` fully, then `VERIFICATION.md` §3 for the list of names you must define. Build milestone M0 exactly as its row in §12 lists (schema §3, operators §3.1, validate §3.2, interpreter §4, envelope §9 budgets/allowlists only, toy stream §10.1, metrics §10.2). Use `MockLLMClient` everywhere; no network. Copy MIT/Apache code only from the paths in §13; do not copy from `repos/EvoMAS`, `repos/AgentSpec`, `repos/MAST`, `repos/Misevolution`. Every module gets a test in `tests/`. Stop after M0's acceptance tests pass and report which items in §14 you touched.

Then M1…M6 one at a time, each as its own branch/PR, each ending with the acceptance tests in §12.
