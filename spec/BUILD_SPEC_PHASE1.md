# Amoeba Phase-1 Build Spec — three boxes only (v2, verified against the clones)

**Scope:** boxes **Task → Plan a new team → Team runs the task** from the proposal diagram. No memory, monitor, diagnoser, architect, gate, logbook, or person. **No cost handling**: nothing enforces a budget in this phase; the trace merely records the token counts the API returns (free to keep, impossible to reconstruct later).
**Audience:** Claude Code (implementer). Names match the full `BUILD_SPEC.md` so later phases add files, not renames.
**Verification:** every line of §5–§7 was checked against `repos/AutoAgents` and `repos/AgentVerse` (report: `VERIFICATION_PHASE1.md`). Where we depart from the original code on purpose it is marked `DEVIATION` and the reason is given. Where the original has a bug we fixed, it says so.
**Sources used:** AutoAgents (MIT) for drafting and flat execution; AgentVerse (Apache-2.0) for boss+reviewers; ATM `llm_client.py` pattern (MIT-declared) for the client.

---

## 0. Plain-language summary

A task comes in. Three AI calls, repeated up to three times, design a small team: a **Planner** drafts roles and a step plan, an **Agent Observer** critiques the roles, a **Plan Observer** critiques the plan, and the Planner redrafts using their comments. Plain code then builds the team from the final draft and runs it one of two ways:

- **flat** (AutoAgents): the plan's steps run in order; each step's helper(s) work in a small loop of up to 5 turns until they say "Final Output"; the next step sees what came before.
- **boss+reviewers** (AgentVerse): one solver writes an answer, the other helpers review it in parallel; if anyone disagrees, the solver revises, up to 3 rounds.

The last output is the answer. Every LLM call is traced.

Rule kept even in this small phase: **the LLM fills text fields; plain code owns loops, caps, parsing and the trace.**

---

## 1. Architecture of the three boxes

```
                 ┌────────────────────────────────────────────────────────────────┐
                 │                    BOX 2 · Plan a new team                      │
                 │            (AutoAgents drafting, ≤3 rounds, 3 LLM calls/round)  │
  ┌──────────┐   │  ┌──────────┐ draft  ┌─────────────────┐  suggestions           │
  │  BOX 1   │   │  │ Planner  │──────▶│ Agent Observer  │────────┐               │
  │  Task    │──▶│  │ (LLM)    │       └─────────────────┘        │  fed back to  │
  │ prompt + │   │  │          │ draft  ┌─────────────────┐        ├──▶ Planner    │
  │ optional │   │  │          │──────▶│ Plan Observer   │────────┘  next round   │
  │ truth    │   │  └──────────┘       └─────────────────┘                        │
  └──────────┘   │        │ final draft: roles[] + plan steps[]                    │
                 │        ▼                                                        │
                 │  ┌──────────────────────────────┐   plain code: parse, filter   │
                 │  │ instantiate() → TeamConfig    │   tools, cap 2–5, add        │
                 │  └──────────────────────────────┘   summariser, resolve steps   │
                 └────────────────┬───────────────────────────────────────────────┘
                                  │ TeamConfig (agents with durable ids, edges, entry, exit)
                                  ▼
                 ┌────────────────────────────────────────────────────────────────┐
                 │                    BOX 3 · Team runs the task                   │
                 │                                                                 │
                 │   topology = flat                     topology = boss_reviewers │
                 │   ┌────┐  ┌────┐  ┌────┐             ┌────────┐  review        │
                 │   │step│─▶│step│─▶│step│             │ solver │──────▶ critic1 │
                 │   │ 1  │  │ 2  │  │ n  │             │ (LLM)  │──────▶ critic2 │
                 │   └────┘  └────┘  └────┘             │        │◀────── revise  │
                 │   ≤5 turns per step,                 └────────┘  (only if a    │
                 │   "Final Output" ends a step          ≤3 review rounds  critic │
                 │                                                   disagrees)   │
                 │   Interpreter (code): routes messages, parses sections,        │
                 │   writes trace.jsonl (token counts recorded, not enforced)      │
                 └────────────────┬───────────────────────────────────────────────┘
                                  ▼
                        Answer + runs/<id>/{team.yaml, plan.json, trace.jsonl, result.json}
```
Purple boxes in the diagram (LLM): Planner, Agent Observer, Plan Observer, each helper. Green (code): instantiate, Interpreter, parsers, trace.

---

## 2. Fixed decisions

| Decision | Choice |
|---|---|
| Python ≥3.11, pydantic v2; deps `pydantic`, `pyyaml`, `openai>=1.50` | runs offline with the mock |
| LLM client | `OpenAICompatibleClient(base_url, api_key, model)` + `MockLLMClient`; both expose `chat(system, user, seed)` and `chat_messages(messages, seed)` (the second is needed for AgentVerse-style history) |
| Prompt rendering | one `render(template, **kw)` supporting `{x}` (AutoAgents, rendered exactly once so `{{{{ }}}}` collapses correctly) and `${x}` (AgentVerse, `string.Template.safe_substitute`) |
| Topologies | `flat` (AutoAgents Group) and `boss_reviewers` (AgentVerse vertical-solver-first). Chosen by flag, not by LLM |
| Tools | registry with `echo` and `calc`. AutoAgents routes *every* drafted tool name to SerpAPI at run time (`custom_action.py:207-211`); dispatch-by-name through a registry is new behaviour (DEVIATION) |
| Persistence | each run writes `runs/<run_id>/` so Phase 2's memory box has raw material |
| Cost | **ignored in Phase 1.** No budgets, no `BudgetExceeded`, no envelope charging. `chat` spans still carry `gen_ai.usage.input_tokens/output_tokens` from the API response, and `RunResult.total_tokens` sums them, so Phase 3's cost-matched comparisons have data |

---

## 3. Layout

```
amoeba/
  amoeba/
    llm/client.py            # OpenAICompatibleClient, MockLLMClient
    llm/toy_mock.py          # scripted stand-in model so `--toy` runs offline (added in the build)
    config/schema.py         # §4
    config/validate.py       # §4.1
    config/io.py             # load_yaml, dump_yaml, config_hash
    config/prompts/          # §7 prompt files + __init__.py (PROMPT.<stem>, render)
    task/models.py           # Task, Answer, RunResult, Episode, Message, AgentResult
    task/source.py           # ToyTaskSource (3 families), solve_toy oracle
    task/evaluate.py         # normalise / score: exact match → 1.0 | 0.0, None without ground truth (added in the build)
    task/draft.py            # BOX 2: draft_team()           §5
    task/parsers.py          # parse_sections, parse_role_blobs, parse_plan, parse_critic   §5.1
    task/instantiate.py      # Draft → TeamConfig            §5.3
    interp/runtime.py        # BOX 3: Interpreter.run() → run_flat / run_boss_reviewers   §6
    interp/trace.py          # TraceWriter (JSONL, OTel names)
    tools/registry.py        # echo, calc
    safety/envelope.py       # allowed_tools, max_agents (no budgets in Phase 1)
  scripts/run_task.py
  tests/  (+ tests/fixtures/)
```

---

## 4. Schema (`config/schema.py`)

```python
Role = Literal["planner","observer","solver","critic","worker"]

class Contract(BaseModel):
    inputs:  dict[str, str] = {"prior": "text"}
    outputs: dict[str, str] = {"result": "text"}
    effects: list[str] = []

class Limits(BaseModel):                   # loop caps only — not cost. (Renamed from Budget; Phase 3 adds token/usd fields here.)
    max_turns: int = 5                     # inner LLM turns per step (AutoAgents group.py:75 num_steps = 5)

class PromptRef(BaseModel):
    system: str                            # literal or "seed:<stem>"
    user: str
    format: Literal["sections","history+append"] = "sections"
    # "sections": AutoAgents — one user prompt, output parsed into "## Section" blocks
    # "history+append": AgentVerse — system=prepend, then chat-history messages, then user=append

class AgentSpec(BaseModel):
    agent_id: str                          # str(uuid4()); durable
    name: str
    role: Role
    model: str
    prompt: PromptRef
    tools: list[str] = []
    contract: Contract = Contract()
    limits: Limits = Limits()
    suggestions: str = ""                  # AutoAgents role field
    description: str = ""                  # AutoAgents role field (observers only) / AgentVerse role_description
    role_prompt: str = ""                  # AutoAgents drafted `prompt` field; rendered into {role} of the worker USER message (custom_action.py:148)
    max_history: int = 5                   # AgentVerse: solver 5, critic 3 (solver.py:23, critic.py:22)
    created_by: Literal["human","drafter"] = "drafter"
    temperature: float = 0.2
    max_tokens: int = 2048

class Edge(BaseModel):
    src: str; dst: str
    type: Literal["sequential","review","revise"]
    schema_id: str = "text"
    condition: str | None = None           # "critic_disagrees" only

class PlanStep(BaseModel):
    index: int; agent_ids: list[str]; text: str    # text = the raw "[Role A, Role B]: STEP TEXT" line

class TeamConfig(BaseModel):
    team_id: str; version: int = 1; parent_version: int | None = None
    name: str
    topology: Literal["flat","boss_reviewers"]
    agents: dict[str, AgentSpec]
    edges: list[Edge]
    entry: list[str]; exit: str
    plan: list[PlanStep] = []              # flat only
    max_inner_turns: int = 3               # boss_reviewers only (vertical_solver_first.py:24)
    meta: dict = {}
```

### 4.1 Validation (`config/validate.py`)
```
V1  edges reference existing agent_ids; exit exists; entry non-empty
V3  edge.schema_id ∈ src.contract.outputs.values() and ∈ dst.contract.inputs.values()
V5  agent.tools ⊆ envelope.allowed_tools[agent.role]
V6  2 ≤ len(agents) ≤ envelope.max_agents (5)
V7  agent_ids unique, UUID-shaped
V8  flat: every plan step has ≥1 agent_id and plan is non-empty; boss_reviewers: exactly one solver, ≥1 critic
```

---

## 5. BOX 2 — Plan a new team (`task/draft.py`)

Source: AutoAgents `roles/manager.py` `Manager._act` (loop), `environment.py` `publish_message/_parser_roles/_parser_plan` (parsing), `actions/{create_roles,check_roles,check_plans}.py` (prompts), `actions/action/action.py` `_aask_v1` (section parsing, LLM repair).

### 5.1 Parsers (`task/parsers.py`) — regexes copied from the code
```python
def parse_sections(text) -> dict[str, str]:
    """AutoAgents OutputParser.parse_blocks + parse_code (system/utils/common.py:31-59)."""
    out = {}
    for block in text.split("##"):                            # common.py:33
        if not block.strip(): continue
        title, body = block.split("\n", 1)                    # common.py:43
        if title.endswith(":"): title = title[:-1]            # common.py:45-46
        body = body.strip()
        m = re.search(r'```.*?\s+(.*?)```', body, re.DOTALL)  # common.py:53 — first fenced block, tag dropped
        if m: body = m.group(1)
        out[title.strip()] = body
    return out
# require(sections, keys): missing key → one LLM repair call with the error appended (action.py:69-75), then DraftError

def parse_role_blobs(text) -> list[dict]:
    """environment._parser_roles (environment.py:60-73)."""
    roles = []
    for blob in re.findall(r'{[\s\S]*?}', text):             # environment.py:62 — non-greedy; nested {} truncates
        try: d = json.loads(blob.strip())                     # environment.py:65 — uncaught in the original
        except json.JSONDecodeError: continue                 # DEVIATION: skip bad blobs (FORMAT_EXAMPLE's trailing comma would crash the original)
        if d: roles.append(d)
    return roles
# DEVIATION: we run it on sections["Created Roles List"] only; the original scans the whole planner output,
# so blobs from "Selected Roles List" and even from "Thought" get included.

def parse_plan(text) -> list[tuple[list[str], str]]:
    """environment._parser_plan (environment.py:75-84) + our bracket parser."""
    steps = [v.split("\n")[0] for v in re.split(r"\n\d+\. ", "\n" + text)[1:]]   # environment.py:78
    # original: re.findall(r'## Execution Plan([\s\S]*?)##', raw)[0] then steps.insert(0, '') sentinel (:77, :83)
    # DEVIATION: we take the parsed section (no trailing-## dependence) and drop the '' sentinel
    out = []
    for s in steps:
        m = re.match(r'\s*\[(.*?)\]\s*:\s*(.*)', s)           # DEVIATION: explicit "[A, B]: text" parser
        names = [n.strip() for n in m.group(1).split(",")] if m else []
        out.append((names, s))
    return out
# The original never parses the bracket: at run time it matches roster names by SUBSTRING, case-sensitive,
# against the text before the first ':' (group.py:61-64), so "Analyst" matches "[Data Analyst]". We resolve names
# exactly, then fall back to the substring rule if exact fails.

def parse_critic(text) -> tuple[bool, str]:
    """AgentVerse 'critic' parser = CommonParser3 (output_parser/output_parser.py:541-561)."""
    text = re.sub(r"\n+", "\n", text.strip())                 # :544
    first = text.split("\n")[0]                               # :545
    if not first.startswith("Action:"): raise ParseError      # :546-547
    if first.strip(". ") == "Action: Agree":    return True, ""            # :548-549 exact, case-sensitive
    if first.strip(". ") == "Action: Disagree":                            # :550
        m = re.findall(r"Action Input: ([\S\n ]+)", text)                  # :551 — to end of text
        return False, (m[0].strip() if m else "I think it is not correct. Please think carefully and improve it.")  # :552-557
    raise ParseError                                          # :560-561
```

### 5.2 Drafting loop
```python
MANAGER_PREFIX = "You are a Manager, named Ethan, your goal is Efficiently to finish the tasks or solve the problem, and the constraint is . "   # role.py:17, manager.py:17 — system msg for all 3 calls (action.py:60)

def draft_team(task, llm, envelope, trace) -> Draft:
    ctx = f"[Question/Task: {task.prompt}]"        # manager.py:32 str(important_memory) — keep the bracketed form
    history = ""; sugg_roles = ""; sugg_plan = ""  # manager.py:26 — cumulative strings
    suggestions = ""                               # manager.py:27 — what the planner sees: LATEST round only
    consensus, rounds, last = False, 0, None
    with trace.span("invoke_agent", {"gen_ai.agent.name": "planner"}):
      while not consensus and rounds < 3:          # manager.py:27,30
        # state 0 — Planner (CreateRoles)
        raw = llm.chat(MANAGER_PREFIX, render(PROMPT.autoagents_create_roles,
                  context=ctx, existing_roles="[]", tools=envelope.tool_catalog_string(),
                  history=history, suggestions=suggestions, format_example=PROMPT.autoagents_create_roles_format))
        sec = require(parse_sections(raw), ["Selected Roles List","Created Roles List","Execution Plan","RoleFeedback","PlanFeedback"])
        last = (raw, sec)
        history = raw                              # original: str(instruct_content) pydantic repr (manager.py:33). DEVIATION: raw text is cleaner
        # state 1 — Agent Observer (CheckRoles). Always runs: the guard at manager.py:34 is dead code.
        hist_roles = f"## Role Suggestions\n{sugg_roles}\n\n## Feedback\n{sec['RoleFeedback']}"      # manager.py:36
        sr = require(parse_sections(llm.chat(MANAGER_PREFIX, render(PROMPT.autoagents_check_roles,
                  question=task.prompt,                                  # original: regex '## Question or Task:([\s\S]*?)##' on raw (check_roles.py:95); DEVIATION: pass task directly
                  existing_roles="[]", selected_roles=sec["Selected Roles List"], created_roles=sec["Created Roles List"],
                  history=hist_roles, tools=envelope.tool_catalog_string(),   # original TOOLS='None' for observers (check_roles.py:86); DEVIATION: give observers the real catalog
                  format_example=PROMPT.autoagents_check_roles_format))), ["Suggestions"])["Suggestions"]
        sugg_roles += sr                           # manager.py:38
        # state 2 — Plan Observer (CheckPlans)
        hist_plan = f"## Plan Suggestions\n{sugg_plan}\n\n## Feedback\n{sec['PlanFeedback']}"
        # original passes sugg_ROLES here (manager.py:41) — a bug; fixed.
        sp = require(parse_sections(llm.chat(MANAGER_PREFIX, render(PROMPT.autoagents_check_plans,
                  context=task.prompt, roles=sec["Selected Roles List"] + sec["Created Roles List"],   # check_plans.py:72-75
                  plan=sec["Execution Plan"], history=hist_plan, tools=envelope.tool_catalog_string(),
                  format_example=PROMPT.autoagents_check_plans_format))), ["Suggestions"])["Suggestions"]
        sugg_plan += sp                            # manager.py:43
        suggestions = f"## Role Suggestions\n{sr}\n\n## Plan Suggestions\n{sp}"   # manager.py:45
        if "No Suggestions" in sr and "No Suggestions" in sp: consensus = True
        # original tests the CUMULATIVE strings (manager.py:47): one early "No Suggestions" sticks forever.
        # DEVIATION: current-round test (stricter, saner).
        rounds += 1
    # publish: the LAST draft is used whether or not consensus was reached (manager.py:52-59)
    raw, sec = last
    roles = parse_role_blobs(sec["Created Roles List"]) + parse_role_blobs(sec["Selected Roles List"])
    steps = parse_plan(sec["Execution Plan"])
    # DEVIATION — deterministic post-checks; none exist in AutoAgents (all are prompt-only there):
    for r in roles: r["tools"] = [t for t in r.get("tools", []) if t in envelope.allowed_tool_names]
    if not any(not r["tools"] for r in roles): roles.append(LANGUAGE_EXPERT)          # summariser guaranteed by code
    if not 2 <= len(roles) <= envelope.max_agents: raise DraftError("roster size")
    names = [r["name"] for r in roles]
    plan = []
    for i, (bracket, text) in enumerate(steps):
        who = [n for n in names if n in bracket] or [n for n in names if n.replace("_", " ") in text.split(":")[0]]  # exact, then AutoAgents substring rule
        if who: plan.append(PlanStep(index=i, agent_names=who, text=text))      # original: empty match → UnboundLocalError (group.py:104)
    if not plan: raise DraftError("empty plan")
    return Draft(created_roles=[DraftedRole(**r) for r in roles], plan=plan, rounds_used=rounds, consensus=consensus,
                 role_feedback=sugg_roles, plan_feedback=sugg_plan)
```
LLM calls: 3 per round, ≤9, plus at most one repair call per parse failure.

### 5.3 Instantiate (`task/instantiate.py`)
```python
def instantiate(draft, topology, task, envelope) -> TeamConfig:
    agents, by_name = {}, {}
    for r in draft.created_roles:
        aid = str(uuid4()); by_name[r.name] = aid
        agents[aid] = AgentSpec(agent_id=aid, name=r.name, role="worker", model=envelope.default_model,
                                prompt=PromptRef(system=GROUP_PREFIX, user="seed:autoagents_custom_action", format="sections"),
                                # GROUP_PREFIX = "You are a Group, named Alex, your goal is Effectively delivering information according to plan., and the constraint is . " (group.py:23, role.py:17)
                                # the drafted role prompt goes into the USER message as {role} (custom_action.py:148), as in the original
                                tools=r.tools, suggestions=r.suggestions, description=r.description)
    if topology == "flat":
        plan = [PlanStep(index=s.index, agent_ids=[by_name[n] for n in s.agent_names], text=s.text) for s in draft.plan]
        edges = [Edge(src=a, dst=b, type="sequential") for s1, s2 in pairwise(plan) for a in s1.agent_ids for b in s2.agent_ids]
        entry = plan[0].agent_ids; exit = plan[-1].agent_ids[-1]
        cfg = TeamConfig(..., topology="flat", agents=agents, edges=edges, entry=entry, exit=exit, plan=plan)
    else:  # boss_reviewers — AgentVerse vertical-solver-first
        solver_id = by_name[first role with no tools (the summariser)]
        agents[solver_id].role = "solver"; agents[solver_id].max_history = 5
        agents[solver_id].prompt = PromptRef(system="seed:agentverse_solver_prepend", user="seed:agentverse_solver_append", format="history+append")
        critics = [a for a in agents if a != solver_id]
        for c in critics:
            agents[c].role = "critic"; agents[c].max_history = 3
            agents[c].prompt = PromptRef(system="seed:agentverse_critic_prepend", user="seed:agentverse_critic_append", format="history+append")
        edges = [Edge(src=solver_id, dst=c, type="review") for c in critics] + \
                [Edge(src=c, dst=solver_id, type="revise", condition="critic_disagrees") for c in critics]
        cfg = TeamConfig(..., topology="boss_reviewers", agents=agents, edges=edges, entry=[solver_id], exit=solver_id, max_inner_turns=3)
    assert not validate(cfg, envelope); return cfg
```
`description` for AgentVerse's `${role_description}` = the drafted `description` field (or the `prompt` field if description is empty).

---

## 6. BOX 3 — Team runs the task (`interp/runtime.py`)

`Interpreter.run(cfg, task, seed)` opens the `invoke_workflow` span, dispatches on `cfg.topology`, and closes the span. Both runners call the same `_llm(agent, ...)` helper that emits a `chat` span with the token counts from the response (recorded only, never enforced in Phase 1) and appends `{name, role, content}` to `episode.history`.

### 6.1 `run_flat` — AutoAgents `Group._think/_act` + `CustomAction.run`
```python
def run_flat(cfg, task, ep):
    previous_msgs = [f"Question/Task: {task.prompt}"]      # group.py:76 str(important_memory): task + every step's published message
    published = None; final_inp = None
    for step in cfg.plan:                                  # environment.py:256 while Group.steps
        agents = [cfg.agents[a] for a in step.agent_ids]
        previous = "[" + ", ".join(previous_msgs) + "]"    # group.py:76 — full history, not just the last edge
        completed_steps = ""                               # group.py:75 — SHARED by all agents of the step
        consensus = [0] * len(agents); it = 0; response = None
        while sum(consensus) < len(agents) and it < agents[0].limits.max_turns:    # group.py:80, num_steps = 5
            if it > 3:                                     # group.py:82-83 — fires once, at the start of the 5th iteration
                completed_steps += "\n You should synthesize the responses of previous steps and provide the final feedback."
            for i, agent in enumerate(agents):             # group.py:85 — every agent each iteration, even ones already done
                user = render(PROMPT.autoagents_custom_action,
                              role=agent.prompt_text_from_draft,            # custom_action.py:148 — role prompt is in the USER msg
                              context=step.text,                            # :146 — the STEP string, not the task (task is inside `previous`)
                              suggestions=agent.suggestions, previous=previous, completed_steps=completed_steps,
                              tool=str(agent.tools + ["Print", "Final Output"]),   # :144 (original also adds "Write File"; DEVIATION: dropped)
                              format_example=PROMPT.autoagents_custom_action_format)   # its "[{tool}]" stays literal, as in the original
                raw = self._llm(agent, system=GROUP_PREFIX, user=user, ep=ep)
                sec = require(parse_sections(raw), ["CurrentStep", "Action", "ActionInput"])   # custom_action.py:79-83
                act, inp = sec["Action"], sec["ActionInput"]
                if act in agent.tools:  resp = self.tools.execute(act, inp, agent)   # :207 exact membership; original always calls SerpAPI here (DEVIATION: registry)
                else:                   resp = f"\n{inp}\n"                          # :213 — Print, Final Output, unknown → echo
                if "Final Output" in act:                                            # :215 substring
                    info = f"\n## Step\n{step.text}\n## Response\n{completed_steps}>>>> Final Output\n{resp}\n>>>>"   # :216
                    consensus[i] = 1; final_inp = inp
                else:
                    info = f"\n## Step\n{step.text}\n## Response\n{resp}\n## Action\n{sec['CurrentStep']}\n"          # :220
                    completed_steps += f">{agent.name} Substep:\n{sec['CurrentStep']}\n>Subresponse:\n{resp}\n"     # group.py:94
                response = info
                # original sleeps 30 s here (group.py:12,98) — dropped
            it += 1
        published = response                               # group.py:104-110 — the last agent's last response, final or not
        previous_msgs.append(f"user: {published}")         # Message role defaults to 'user' (schema.py:27)
    # original has no answer object; Explorer.run returns the whole history (explorer.py:58)
    # DEVIATION: answer = the last step's Final Output ActionInput; if the last step never reached Final Output, error="max_turns"
    return (final_inp if consensus_reached_on_last_step else published), (None if consensus_reached_on_last_step else "max_turns")
```

### 6.2 `run_boss_reviewers` — AgentVerse `VerticalSolverFirstDecisionMaker.astep`
```python
def run_boss_reviewers(cfg, task, ep):
    solver = cfg.agents[cfg.exit]; critics = [cfg.agents[e.dst] for e in cfg.edges if e.type == "review"]
    memory = {a.agent_id: [] for a in [solver, *critics]}   # ChatHistoryMemory per agent; persists for the whole run (never reset in-episode)
    def broadcast(msgs):                                    # vertical_solver_first.py:74-76
        for a in [solver, *critics]: memory[a.agent_id] += msgs
    def call(agent, kw):                                    # solver.py:38-59 / critic.py:65-91 + llms/openai.py:436-446
        system = render(agent.prompt.system, **kw)          # prepend template
        hist = [{"role": "assistant", "content": f"[{m.sender}]: {m.content}"} for m in memory[agent.agent_id][-agent.max_history:]]   # chat_history.py:102-107
        user = render(agent.prompt.user, **kw)              # append template
        return self._llm_messages(agent, [{"role":"system","content":system}, *hist, {"role":"user","content":user}], ep)
        # This is why format="history+append": the plan and reviews reach agents as chat history, NOT via placeholders.
    def solve(plan_text):
        raw = call(solver, dict(task_description=task.prompt, role_description=solver.description))
        # parser 'dummy' → raw text (output_parser.py:300-303). One retry on empty. On failure content "" (solver.py:70-76)
        return Msg(sender=solver.name, content=raw or "")
    def review(c):
        for attempt in range(2):                            # original max_retry from config (1000!); DEVIATION: 2
            try: agree, crit = parse_critic(call(c, dict(task_description=task.prompt, role_description=c.description))); break
            except ParseError: continue
        else: agree, crit = False, ""                       # critic.py:100-108 → treated as SILENT (== agree) at vertical_solver_first.py:62
        return CriticMsg(sender=c.name, content=crit, is_agree=agree)

    plan = solve("No solution yet."); broadcast([plan])     # :41-42
    for i in range(cfg.max_inner_turns):                    # :44 — 3
        reviews = [review(c) for c in critics]              # :45-49 parallel in the original; sequential is fine here
        nonempty = [r for r in reviews if not r.is_agree and r.content != ""]   # :60-63 — agreeing critics are silent
        if not nonempty: break                              # :64-66 "Consensus Reached"
        broadcast(nonempty)                                 # :67 — only the disagreements, to everyone
        plan = solve(plan.content); broadcast([plan])       # :68-70
    return plan.content, None                               # :71-72 → answer. NB the last revision is never reviewed.
```
Counts: solver ≤ 1 + max_inner_turns = **4** invocations, each critic ≤ 3. (Earlier draft said 3 for the solver — wrong.)

**Why not the generic edge executor from the full spec here?** With `join="all"` and a conditional `revise` edge, the solver would wait for every critic's edge, but agreeing critics send nothing, so it would never revise unless *all* critics disagreed. The two topology runners above are explicit and correct; the generic executor comes in Phase 3 with proper fan-in semantics, and these two become its regression tests.

### 6.3 Trace and run record
One JSONL line per span: `{ts, episode_id, kind:"span", name: invoke_workflow|invoke_agent|chat|execute_tool, gen_ai.agent.id, gen_ai.agent.name, gen_ai.request.model, gen_ai.usage.input_tokens, gen_ai.usage.output_tokens, gen_ai.tool.name, latency_ms, error.type}`.
`RunResult{run_id, task_id, team_id, topology, answer, error, score|None, total_tokens, latency_ms, n_llm_calls, draft_rounds, consensus}` → `runs/<run_id>/result.json` next to `team.yaml`, `plan.json`, `trace.jsonl`.

---

## 7. Prompt files (`config/prompts/`) — verbatim copies, one source header line each

| File | Source (in `repos/`) | Placeholders (exact) |
|---|---|---|
| `autoagents_create_roles.txt` + `_format.txt` | `AutoAgents/autoagents/actions/create_roles.py:9-59` (PROMPT_TEMPLATE), `:61-95` (FORMAT_EXAMPLE) | `{context} {existing_roles} {history} {tools} {format_example} {suggestions}`; the `{{{{ }}}}` in the template collapse correctly only if rendered exactly once with `str.format` |
| `autoagents_check_roles.txt` + `_format.txt` | `.../check_roles.py:9-62`, `:64-74` | `{question} {existing_roles} {selected_roles} {created_roles} {history} {tools} {format_example}` |
| `autoagents_check_plans.txt` + `_format.txt` | `.../check_plans.py:8-44`, `:46-56` | `{context} {roles} {plan} {history} {tools} {format_example}` |
| `autoagents_custom_action.txt` + `_format.txt` | `.../custom_action.py:18-58`, `:60-77` | `{role} {context} {suggestions} {previous} {completed_steps} {tool} {format_example}` |
| `agentverse_critic_prepend.txt`, `agentverse_critic_append.txt` | `AgentVerse/agentverse/tasks/tasksolving/pythoncalculator/config.yaml:37-64` (this config actually pairs vertical-solver-first with the `critic` parser; `brainstorming/config.yaml:44-62` has the same text but a different loop) | prepend `${role_description} ${task_description}`; append `${role_description}` |
| `agentverse_solver_prepend.txt`, `agentverse_solver_append.txt` | `.../pythoncalculator/config.yaml:28-35` (generic; the humaneval one is code-specific and its `${former_solution}/${advice}` are commented out) | prepend `${task_description}` ("You are faced with the task … Below is the chat history among you and other teammates."); append has no placeholder ("Now you are going to give a new solution, based upon your former solution and the critics' opinions. Write the code step by step." — drop the last sentence for non-code tasks, DEVIATION) |
| `language_expert.txt` | ours | — |

Store PROMPT_TEMPLATE and FORMAT_EXAMPLE as separate files so T11 can compare each verbatim before rendering.

---

## 8. Mock fixtures (`tests/fixtures/`)
Drafting: `draft_consensus_round1`, `draft_consensus_round3` (observers complain twice under the **current-round** rule, then agree), `draft_never` (3 rounds, no consensus, last draft used), `draft_bad_json_blob` (trailing comma → skipped, not crashed).
Flat workers: `worker_final_output` (Final Output on turn 1), `worker_calc_then_final`, `worker_never_final` (5 turns → `error="max_turns"`, published = last intermediate info).
Reviewers: `critic_agree`, `critic_disagree`, `critic_unparseable` (→ silent = agree), `critic_agree_with_period` ("Action: Agree." must parse as agree).
A captured **real** AutoAgents Manager output (from the paper's example or a one-off run) as `manager_output_real.txt` for T3.

---

## 9. Acceptance tests (offline, `pytest -q`)

| # | Test | Passes when |
|---|---|---|
| T1 | schema roundtrip | `TeamConfig` → YAML → equal; `config_hash` stable under key reordering |
| T2 | validate | rejects unknown edge id, tool outside allowlist, >5 agents, duplicate id, empty plan, boss_reviewers with 2 solvers |
| T3 | parsers vs original | `parse_sections`/`parse_role_blobs`/`parse_plan` on `manager_output_real.txt` reproduce what `environment.py` would produce (minus the `''` sentinel); `parse_critic` passes: `"Action: Agree."`→agree, `"Action: Disagree\nAction Input: x\ny"`→(False,"x\ny"), `"Thought: ..\nAction: Agree"`→ParseError |
| T4 | draft loop | rounds_used = 1 / 3 / 3 for the three fixtures; ≤9 chat spans; observers called every round; unknown tools stripped; summariser present; step with no matching role dropped |
| T5 | instantiate flat | edges follow plan order; entry = step-0 agents; exit = last agent of last step; UUIDs; `created_by="drafter"`; role prompt appears in the **user** message, system is `GROUP_PREFIX` |
| T6 | instantiate boss_reviewers | solver = the no-tool role; review + conditional revise edges; solver max_history 5, critics 3 |
| T7 | run_flat | answer = last step's Final Output ActionInput; the worker prompt's `{context}` is the step text and `{previous}` contains the task and every prior step's published message; hint text present in the 5th iteration's prompt only; `worker_never_final` → `error="max_turns"` |
| T8 | run_boss_reviewers | with `critic_disagree` ×1 then `critic_agree`: solver invoked 2×; all-agree from the start: 1×; always-disagree: solver 4×, each critic 3×; critics' prompts contain the plan as an `assistant` history message `"[<solver name>]: ..."`; `critic_unparseable` counts as agree |
| T9 | token accounting | every `chat` span has `gen_ai.usage.input_tokens/output_tokens`; `RunResult.total_tokens` equals their sum; nothing in the code path reads a budget |
| T10 | end-to-end toy | `scripts/run_task.py --toy --seed 0 --n 20 --topology flat` and `... boss_reviewers` write `runs/<id>/` with four files and print mean score / tokens / calls |
| T11 | prompts verbatim | each prompt file body equals the string sliced from the source file at the cited lines |

---

## 10. CLI
```
python -m scripts.run_task "Reverse the string 'adaptive' then uppercase it" --topology flat
python -m scripts.run_task --toy --seed 0 --n 20 --topology boss_reviewers
python -m scripts.run_task ... --llm openai --base-url http://localhost:8000/v1 --model qwen2.5
```

---

## 11. Deliberate deviations from the originals (collected)

| # | Original behaviour | Ours | Why |
|---|---|---|---|
| D1 | Planner's `history` = pydantic repr of last draft | raw text | readable |
| D2 | Consensus on cumulative suggestion strings (one early "No Suggestions" sticks) | current round only | the original rule lets a later complaint be ignored |
| D3 | Plan observer receives role suggestions under the "Plan Suggestions" heading (bug) | plan suggestions | bug fix |
| D4 | Observers see regex-sliced raw sections needing a trailing colon; `TOOLS='None'` | parsed sections; real tool catalog | robustness; observers can't check tools they can't see |
| D5 | Roles parsed from the whole output; bad JSON crashes; no tool filter; no summariser check; no roster cap | Created section; skip bad blobs; filter; ensure summariser; 2–5 cap | "plain code decides" |
| D6 | Step→role match by substring, case-sensitive, roster order | bracket parse + exact match, substring fallback; empty match drops the step (original: crash) | correctness |
| D7 | `Write File` built-in; every drafted tool → SerpAPI | no file tool; registry dispatch by name | safety, no SerpAPI |
| D8 | 30 s sleep per agent call | none | — |
| D9 | No answer object; Final Output text includes the whole scratchpad | answer = last step's `ActionInput` | Phase 2 needs a scorable answer |
| D10 | AgentVerse critic `max_retry` 1000 | 2 | — |
| D11 | AgentVerse critics reviewed in parallel | sequential | simplicity; same semantics |
| D12 | Spec §4 as first written: no field for the drafted `prompt` | `AgentSpec.role_prompt` | §6.1 renders it into `{role}`; `description` is already AgentVerse's `${role_description}` |
| D13 | Spec §7: drop "Write the code step by step." from the stored solver append file | file verbatim; the sentence is dropped at load time as `seed:agentverse_solver_append_generic` | keeps T11 byte-exact while applying the deviation |
| D14 | AutoAgents: every `{…}` blob becomes a role, duplicates included | a blob without a `name` is skipped; duplicate names keep the first | a step cannot address a nameless role; duplicate names collide in the roster |
| D15 | `parse_blocks` raises `ValueError` on a title-only block (common.py:43) | empty body | one malformed heading should not abort the run |
| D16 | AgentVerse `memory[-max_history:]` with `max_history=0` means *all* history (`[-0:]`) | 0 means no history | Python slice foot-gun |
| D17 | §8: `manager_output_real.txt` = a captured Manager run | at first hand-composed in the `FORMAT_EXAMPLE` shape, then replaced by a real capture from the first live run | no API access during the offline build; provenance in `tests/fixtures/README.md` |
| D18 | §3 layout as first written | plus `task/evaluate.py` and `llm/toy_mock.py` | the diagram already named `task/evaluate.py`; the CLI must run offline |

Everything else — caps 3/5/3, the "No Suggestions" and "Final Output" sentinels, the observer history strings, the 5th-iteration hint, the shared `completed_steps`, `{context}` = step text, role prompt in the user message, chat-history delivery of plans/reviews, silent-agree, solver ≤4 — follows the code.

---

## 12. Not built now → where it lands
Memory lookup / reuse / save (Phase 2, reads `runs/`); LLM judge and non-toy scoring (Phase 2); **cost: per-helper token/usd budgets, `BudgetExceeded`, envelope charging, cost-matched reporting (Phase 3, alongside the monitor — add fields to `Limits`, no renames); Monitor (Phase 3 — add a no-op `listener` parameter to `Interpreter.__init__` now); diagnoser / architect / experimenter / gate / logbook / person (Phase 3–4); edit operators and the generic edge executor with fan-in (Phase 3; `run_flat`/`run_boss_reviewers` become its regression tests); web search tool (Phase 2); PreToolUse hook (Phase 4; `ToolRegistry.execute` is the single call site).

---

## 13. Instruction to Claude Code

> Read `BUILD_SPEC_PHASE1.md` fully, then `VERIFICATION_PHASE1.md` Part B (the verified pseudocode with file:line citations). Build §3–§10. Use `MockLLMClient` for all tests; no network. Copy prompt text verbatim from the paths in §7 (AutoAgents MIT, AgentVerse Apache-2.0) with a source header line; keep template and format-example as separate files. Do not import from `repos/`. Add the no-op `listener` parameter to `Interpreter.__init__`. Stop when T1–T11 pass and `scripts/run_task.py --toy --n 20` runs for both topologies; report mean toy score, tokens and LLM calls per topology, and any place you had to depart from §5–§6.
