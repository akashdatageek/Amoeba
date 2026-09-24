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
                 │  ┌──────────────────────────────┐   plain code: parse, record   │
                 │  │ instantiate() → TeamConfig    │   missing tools, cap 2–5,    │
                 │  └──────────────────────────────┘   flag summariser, resolve   │
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
                        Answer + runs/<id>/{team.yaml, plan.json, trace.jsonl, capability_requests.json, result.json}
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
    task/draft.py            # BOX 2: draft_team(prompts="d19"|"d24")   §5, D24
    task/parsers.py          # parse_sections, parse_role_blobs, parse_plan, parse_critic   §5.1
                             # + parse_json_objects, parse_plan_d24, parse_requirements, parse_bullets, parse_verdict (D22–D24)
    task/quality.py          # draft_quality(): deterministic checks on a finished draft, recorded only (D24)
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
    missing_tools: list[str] = []          # tools the draft named that the registry lacks — recorded as capability requests (D19)
    is_summariser: bool = False            # writes the final answer; boss_reviewers makes it the solver (D20)
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
    for r in roles:                                   # D19: an unregistered tool is recorded, never dropped silently
        r["missing_tools"] = [t for t in r.get("tools", []) if t not in envelope.allowed_tool_names]
        r["tools"] = [t for t in r.get("tools", []) if t in envelope.allowed_tool_names]
    requests = parse_capability_requests(sec.get("Capability Requests", ""))   # optional section: no repair call
    requests += [CapabilityRequest(name=t, for_role=r["name"], source="unregistered_tool") for r in roles for t in r["missing_tools"]]
    if not 2 <= len(roles) <= envelope.max_agents: raise DraftError("roster size")
    names = [r["name"] for r in roles]
    plan = []
    for i, (bracket, text) in enumerate(steps):
        who = [n for n in names if n in bracket] or [n for n in names if n.replace("_", " ") in text.split(":")[0]]  # exact, then AutoAgents substring rule
        if who: plan.append(PlanStep(index=i, agent_names=who, text=text))      # original: empty match → UnboundLocalError (group.py:104)
    if not plan: raise DraftError("empty plan")
    pick_summariser(roles, plan)   # D20: the role flagged "is_summariser": true, else the last role of the last step
    for q in requests: trace.event("capability_request", {...})
    return Draft(capability_requests=requests, created_roles=[DraftedRole(**r) for r in roles], plan=plan, rounds_used=rounds, consensus=consensus,
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
        solver_id = by_name[the role with is_summariser]      # D20 (first written: the first role with no tools)
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
                elif act or inp starts with "BLOCKED": record in ep.blocked_steps, trace event "blocked", helper done (D21)
                elif act in ("Print", "") or "Final Output" in act: resp = f"\n{inp}\n"   # :213 echo
                else:                   trace event "unknown_tool"; a notice instead of the echo; record a request (D21)
                # the {suggestions} of a helper with missing_tools gains one line per tool:
                # "Tool X is unavailable this run; proceed without it or answer BLOCKED: X"   (D21)
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
One JSONL line per span: `{ts, episode_id, kind:"span", name: invoke_workflow|invoke_agent|chat|execute_tool, gen_ai.agent.id, gen_ai.agent.name, gen_ai.request.model, gen_ai.usage.input_tokens, gen_ai.usage.output_tokens, gen_ai.tool.name, latency_ms, error.type}`, plus point events `{kind:"event", name: capability_request|blocked|unknown_tool, …}` (D19, D21).
`RunResult{run_id, task_id, team_id, topology, answer, error, score|None, total_tokens, latency_ms, n_llm_calls, draft_rounds, consensus, blocked_steps, requested_capabilities, requests_proposed, requests_dropped_by_observers}` → `runs/<run_id>/result.json` next to `team.yaml`, `plan.json`, `trace.jsonl`, `capability_requests.json` (every `CapabilityRequest{name, kind: tool|skill, for_role, what_it_does, input, output, example_input, example_output, source}` from the draft and the run; `[]` when none — recorded, never fetched).

**What is kept of drafting.** `plan.json` is the `Draft` with `rounds: list[DraftRound]`, one per round: `index`, `planner_raw`, the `roles` and `plan` as parsed from that reply (before the checks), its `capability_requests`, `agent_observer_raw`/`agent_observer` (Suggestions), `plan_observer_raw`/`plan_observer`, and `consensus`. A failed draft is kept too: `DraftError.rounds` carries every round up to the failure, and `plan.json` becomes `{error, rounds}` (`draft_rounds` counts the rounds that completed). With content logging, each `chat` line in `trace.jsonl` also holds `gen_ai.input.messages` (the exact system and user prompt) and `gen_ai.output.messages` (the reply), the OpenTelemetry GenAI opt-in content fields. The CLI logs content by default (`--no-log-content` turns it off); `TraceWriter` and `run_one` default to off.

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
| ~~`language_expert.txt`~~ | ours | removed with the code-appended summariser (D20) |

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
| T4 | draft loop | rounds_used = 1 / 3 / 3 for the three fixtures; ≤9 chat spans; observers called every round; unknown tools recorded as capability requests (not dropped); summariser flagged; step with no matching role dropped |
| T5 | instantiate flat | edges follow plan order; entry = step-0 agents; exit = last agent of last step; UUIDs; `created_by="drafter"`; role prompt appears in the **user** message, system is `GROUP_PREFIX` |
| T6 | instantiate boss_reviewers | solver = the `is_summariser` role; review + conditional revise edges; solver max_history 5, critics 3 |
| T7 | run_flat | answer = last step's Final Output ActionInput; the worker prompt's `{context}` is the step text and `{previous}` contains the task and every prior step's published message; hint text present in the 5th iteration's prompt only; `worker_never_final` → `error="max_turns"` |
| T8 | run_boss_reviewers | with `critic_disagree` ×1 then `critic_agree`: solver invoked 2×; all-agree from the start: 1×; always-disagree: solver 4×, each critic 3×; critics' prompts contain the plan as an `assistant` history message `"[<solver name>]: ..."`; `critic_unparseable` counts as agree |
| T9 | token accounting | every `chat` span has `gen_ai.usage.input_tokens/output_tokens`; `RunResult.total_tokens` equals their sum; nothing in the code path reads a budget |
| T10 | end-to-end toy | `scripts/run_task.py --toy --seed 0 --n 20 --topology flat` and `... boss_reviewers` write `runs/<id>/` with five files and print mean score / tokens / calls |
| T11 | prompts verbatim | each prompt file body equals the string sliced from the source file at the cited lines; each D19 `*_d19` variant equals the file plus exactly its listed replacements |

---

## 10. CLI
```
python -m scripts.run_task "Reverse the string 'adaptive' then uppercase it" --topology flat
python -m scripts.run_task --toy --seed 0 --n 20 --topology boss_reviewers
python -m scripts.run_task ... --llm openai --base-url http://localhost:8000/v1 --model qwen2.5
python -m scripts.run_task --toy --n 1 --no-log-content          # keep prompts and replies out of trace.jsonl
python -m scripts.eval_draft --tasks tasks/draft_eval.jsonl --repeats 3 --llm openai   # Box 2 only
python -m scripts.eval_draft --tasks tasks/draft_eval_complex.jsonl --draft-prompts d24 --llm openai   # D24 prompts
python -m scripts.run_task --toy --n 1 --draft-prompts d24                                           # (default d19)
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
| D17 | §8: `manager_output_real.txt` = a captured Manager run | at first hand-composed in the `FORMAT_EXAMPLE` shape; replaced 2026-09-23 by a real `gemini-3.1-flash-lite` Planner reply from the first live run | no API access during the offline build; provenance in `tests/fixtures/README.md` |
| D18 | §3 layout as first written | plus `task/evaluate.py` and `llm/toy_mock.py` | the diagram already named `task/evaluate.py`; the CLI must run offline |
| D19 | AutoAgents: "Use only existing tools {tools}; do NOT invent new tools" (create_roles, check_roles, check_plans); D5 then dropped unknown tool names silently | the prompts (as `*_d19` variants built at load time from the verbatim files, `CAPABILITY_EDITS`) say *prefer* existing tools and list a missing tool or skill under an optional `## Capability Requests` section as JSON `{name, kind: tool\|skill, for_role, what_it_does, input, output, example_input, example_output}`; observers see the requests and judge them on need only: a role using an unlisted tool gets "ADD a Capability Request", never "remove the tool", and a request is not to be dropped only because an existing tool could work around it. The source's `Select existing expert roles (from {tools})` slip is corrected to `{existing_roles}`. The draft records `requests_proposed` (distinct names asked for in round 1) and `requests_dropped_by_observers` (of those, absent from the final draft), also in `result.json`. An unregistered tool in a role's `tools` becomes `missing_tools` + a recorded request. All go to `runs/<id>/capability_requests.json` and one `capability_request` trace event each | a planner forbidden to name what it lacks hides the gap; recording it is the input a later phase needs to fetch or build tools (not done in Phase 1) |
| D20 | D5 as first built: the summariser is "the first role with no tools"; if none, code appends a Language Expert | `is_summariser` flag on the drafted role / `AgentSpec`: the role the planner marks `"is_summariser": true`, else the last role of the last plan step (= the flat exit). Nothing is appended; `language_expert.txt` removed | having no tools says nothing about who writes the answer; a tool-using last step was wrongly given a stranger as boss |
| D21 | AutoAgents echoes any non-tool action (custom_action.py:213) | a helper with `missing_tools` gets one line per tool in `{suggestions}`: "Tool X is unavailable this run; proceed without it or answer BLOCKED: X". An action or input starting `BLOCKED` ends that helper's step, is recorded in `blocked_steps` and a `blocked` event; a blocked last step without a Final Output gives `error="blocked"`. An action naming a tool the helper lacks → `unknown_tool` event and a notice instead of the echo; if unregistered, a `runtime_unknown_tool` request. Print and Final Output still echo | a silent echo hides a missing capability; boss_reviewers ignores tools, as before |
| D22 | AutoAgents parses role blobs with the non-greedy regex `{[\s\S]*?}` (environment.py:62) | brace-balanced JSON scan (`parse_json_objects`) on both d19 and d24; the regex stays as `parse_role_blobs` so T3 still checks it | a `{placeholder}` in a role prompt or a nested object cut the blob at the first `}`: 17/40 real drafts failed (docs/real_runs/2026-09-23_gemini-3.1-flash-lite.md) |
| D23 | `parse_blocks` keeps everything after a heading (common.py:31-59) | a bare `---` block is not a section, and a closing `---` line is dropped from a section body | models copy the FORMAT_EXAMPLE's `---` fences; the closing one ended up in the answer (`"EPOLEVNE\n---"`), 11/11 flat answers scored 0 |
| D24 | Box 2 prompts are AutoAgents' (with the D19 edits): one "Manager Ethan" system message, "prefer existing tools", a concise one-line-per-step plan, five-key role blobs, "No Suggestions" consensus | `--draft-prompts d24` (default stays d19): our prompts (`config/prompts/d24_*.txt`, `${}` Template syntax) with a system message per role; the Planner writes Requirements (R ids), Givens and Assumptions (with arithmetic), full role records (goal, skills, inputs, outputs, success_criteria, constraints, covers, prompt), a plan with `covers / depends_on / do / output / done_when` per step, Capability Requests and Risks and Decisions, planning the ideal before mapping to installed tools; observers check against a list and end with `## Verdict APPROVE|REVISE` — consensus = both exactly APPROVE (a verdict still missing after one repair counts as REVISE). The fields are kept (`DraftedRole`, `DraftPlanStep`, `Draft.requirements/givens/risks`, `parse_plan_d24`), checked by `draft_quality` (recorded in plan.json, result.json and the trace, never used to reject), and reach Box 3 (a role card in `{role}`, the step detail in `{context}`, the card in critics' `${role_description}`). Planner calls ask for 8192 tokens, observers 2048; a reply with `finish_reason == "length"` is flagged (`truncated` event) | the db-choice transcript: plans bent to the installed tools, no capability requests, thin roles, one-line steps, wrong arithmetic, no convergence (spec/BOX2_PROMPT_UPGRADE_D24.md) |
| D25 | Consensus when both Suggestions contain the substring "No Suggestions" (manager.py:47, with D2) | d19: a reply that also lists any numbered suggestion is not an approval ("1. No Suggestions" still is) | 3 of 9 real observer replies listed fixes and then said "No Suggestions." |
| D26 | `parse_blocks` keeps only the first fenced block of a section (common.py:53) | `parse_sections(..., all_fences=True)` joins every fenced block of a section in order; drafting reads Planner replies this way (d19 and d24) | gemini-3.5-flash wrote each role in its own ```` ```json ```` block, so roles 2..n were lost and 2/9 d19 drafts failed "roster size 1" (docs/real_runs/2026-09-23_d19_vs_d24.md) |
| D27 | (ours) D24 gave observers 2048 tokens per reply | every drafting role defaults to 8192, set per role with `--planner-max-tokens` / `--observer-max-tokens` or `AMOEBA_MAX_TOKENS_PLANNER` / `_OBSERVER` / `_AGENT_OBSERVER` / `_PLAN_OBSERVER` (CLI > role env > observer env > default). A reply with `finish_reason == "length"` is retried once with double `max_tokens` and the second reply is accepted; both calls are traced (`truncated` events, `amoeba.retry_of_truncated`). Hidden reasoning tokens are recorded per call (`amoeba.usage.reasoning_tokens`: the API's `completion_tokens_details.reasoning_tokens`, else `total_tokens − prompt − completion`), kept apart from `total_tokens` | 17 gemini-3.5-flash d19 observer replies stopped at 2048 while showing < 600 output tokens: the hidden reasoning counts against the limit (a max_tokens=40 call returned empty text with 48 total tokens) |
| D28 | (ours) D24 observers were told only "a different role checks numbers, sources or test results"; draft_quality's verification check was a proxy and nothing acted on it | the d24 Plan Observer must answer REVISE when no step verifies numbers, sources or test results by a role that did not produce them. `draft_quality` adds `independent_verification`: a step whose text/do/done_when says it verifies (check, review, validate, reconcile, audit …), depends on the producing steps, and shares no role with their producers (the summariser's own step does not count). Hard checks: `requirements_covered`, `independent_verification`, `summariser` (d19 is judged on tools and last-step ownership, since its prompt never asks for a declaration). `--quality-gate` (default off): after each round, a failed hard check blocks consensus and is sent to the Planner as a "## Quality Gate" suggestion list, within MAX_ROUNDS; the last draft is still published. Gate hits are recorded per round (`DraftRound.gate_failed`, `Draft.gate_hits`, a `quality_gate` trace event) | only 1/9 and 3/9 d24 drafts had a verification step by a non-producer, yet both observers approved (docs/real_runs/2026-09-23_d19_vs_d24.md) |
| D29 | (ours) capability requests were recorded under whatever name the model wrote | each `CapabilityRequest` also carries `canonical` and `mapped`: `normalise()` (amoeba/capabilities) = lowercase snake_case key, looked up in `amoeba/capabilities/aliases.yaml` (canonical → aliases; starts with web_search, code_execution, database_sandbox, pricing_api, spreadsheet, load_testing, trade_database). An unknown name is kept as written and listed as unmapped (`result.json.unmapped_capabilities`, the CLI's last lines, eval_draft's `unmapped_names`) so the file can be extended. `name` keeps the raw name in capability_requests.json; request survival and `tools_accounted` compare canonical names | 67 distinct names in the first real runs, e.g. "Web Search", "web_search", "Web Research", "Market Research Tool" for one capability |
| D30 | (ours) Phase 1 scored only tasks with a ground_truth; D24's derived-number check matched listed spellings ("21.9 TB") and missed the same bytes written in binary units | `Task.rubric` (optional; replaces `Task.expected`): required_deliverables and constraints_to_respect (regex any_of), expected_numbers (value + unit + tolerance, default 5%; a decimal byte unit also matches its binary reading, money accepts $/USD/million/M), must_not (a pattern that fails unless `unless_nearby`, e.g. a source, is within `window` chars). `evaluate.rubric_score(answer, rubric)` → per-item pass/fail with evidence + overall fraction; `run_one` stores it as `result.json` `rubric` and uses its fraction as `score` when there is no ground_truth. `eval_draft.derived_correct` uses the same `number_found`. No LLM judge: `rubric_score(judge=...)` stores a judge result under `judge` without changing the score. The rubric is read only by Box 1 scoring; `tests/test_rubric.py` renders every d19/d24 drafting prompt and every flat and boss_reviewers worker prompt for a task whose rubric holds sentinels and asserts none is sent | complex tasks have no single right answer; the v1 string match marked a correct GiB/TiB answer wrong; a rubric the team could see would be graded against itself |
| D31 | AutoAgents runs the steps in list order and gives every helper the whole history (group.py:76 `previous`); `depends_on`, `output` and `done_when` are never used | new topology `plan` (`amoeba/interp/plan_runner.py`, `--topology plan`; `run_flat` and `run_boss_reviewers` unchanged as baselines). The step graph comes from `depends_on` (a plan with none is a chain); an unknown step number or a cycle fails validation (V8 plan) before any Box 3 call. A dependency on a step Box 2 dropped (it named no known role; numbers are kept) is re-linked to that step's own dependencies as written, with a `dependency_relinked` event. Steps run in topological waves, sequentially for now; the wave is recorded (`plan_graph`, `step_input`, `step_done` events). Each step's helper sees only the task, a role card (name, goal, skills, constraints, outputs, success criteria, prompt, suggestions), its own step with `do / output / done_when`, and the artifacts of the steps it depends on (`amoeba/config/prompts/plan_step*.txt`, ours); Thought / CurrentStep / Action / ActionInput and the 5-turn cap are kept. Multi-role steps: the roles take turns in roster order within the cap, and a helper that has answered Final Output or BLOCKED is not asked again (flat asks every helper every turn). Each step's result is saved as `runs/<id>/artifacts/step_<n>.md` with `step_<n>.json` (step, wave, roles, covers, depends_on, received, output_spec, status done/blocked/max_turns, turns, sources, contributions) and in `Episode.steps`. The answer is the summariser's step in the last wave. ActionInput is read to the end of the reply (it is the last section): the AutoAgents parser splits on every `##`, so a markdown Final Output is cut at its first `##`/`###` heading — the flat baseline loses most of its answers this way (docs/real_runs/2026-09-24_box3_baseline.md). Plan helpers get `max_tokens` 8192 per call (the D27 retry applies); flat and boss_reviewers keep the client default 2048 | the d24 plan says which step needs which input; passing only those keeps each helper's context on its own job, and the artifacts make each step's contribution inspectable |
| D32 | AutoAgents routes every drafted tool to SerpAPI (custom_action.py:207-213); Phase 1 had only `echo` and `calc` (D7) | `amoeba/tools/web.py`: `web_search(query)` → top results as `[S#] title — url` + snippet and `fetch_url(url or S#)` → the page's clean text, behind a `SearchProvider` interface; the provider is Tavily (`/search`, `/extract` on `api.tavily.com`, key from `TAVILY_API_KEY`). Every result gets a run-wide source id (S1, S2, …; the same url keeps its id) with url, title, kind and time fetched; a plan step's artifact lists its sources. Limits in code and in the trace (`web_tools` event): 5 results per search, 4 searches and 3 fetches per step, 6000 characters per fetched page, 20 s timeout. A failure or a spent limit returns an `error: …` string to the helper with a `tool_error` / `tool_limit` event, never an exception. `run_task --web-tools` builds a fresh Box 3 registry per run; Box 2 never sees the web tools (its envelope is built from `echo`/`calc`), so both plan arms draw from the same drafts. At Box 3 start the plan runner gives `web_search` + `fetch_url` to each role whose missing tools or capability requests normalise (D29) to `web_search` (`capability_mapped` event); the saved team.yaml is unchanged. Tests use a fake provider; `scripts/smoke_web.py` is the one real check | current facts (prices, laws, benchmarks) need a real lookup; a source id makes each fact traceable (D33) |
| D33 | (ours) nothing tied a figure in an answer to where it came from | the plan-step prompt requires every number, price, date, law or benchmark figure to carry `[S#]` (a tool result) or `[unverified]` (model knowledge); a computed number needs no tag if the calculation is shown or `calc` was used. After each step `amoeba/interp/provenance.py` classifies every number in the step output line by line: cited (the line has a valid `[S#]`), unverified, given (in the task text), derived (a `calc` result or after `=`/`≈` on the line), inherited (already in an input artifact), else untagged. A number is a digit run with optional thousands commas, decimals, a leading currency sign and a trailing %; a letter suffix is not part of it (`$1.45M` → 1.45, `10TB` → 10). List markers and labels (S3, R2, p95, step 4, Phase 1) are not counted. An `[S#]` the step could not have seen is a hallucinated citation; a step can see its own sources and those visible to the steps it depends on (the spec said the step's own sources; inputs carry their tags forward, so their ids count too). Counts go into `step_<n>.json` (`provenance`, `visible_source_ids`), a `provenance` trace event per step, and `result.json` `provenance` {total, steps}. Measured, never enforced | a model-memory figure should be visible as one; the count of untagged numbers is the size of the invention problem |
| D34 | (ours) nothing checked a step's output against its `output` / `done_when`, and the d24 verification step was prose | after each plan step, deterministic checks (`plan_runner.step_checks`), only those that apply: output present; a markdown table when `output`/`done_when` say table; ≥ 2 list items for list/bullets; a code block or statement for code/script/SQL/schema; ≥ 2 headings for memo/report/runbook/plan/document; a number when they name costs, prices, sizes, rates, benchmarks and the like; and, for a step with dependencies, some use of its inputs (a step number, role name, source id or figure from them, or a line copied from them). A failed check with turns left gets one retry: the reasons are added to the step's work so far and every helper is asked again (`check_retry` event). A step that still fails, or runs out of turns, is `incomplete` with a `status_reason`; the run goes on and later steps see each input's status. A verification step (depends on others and its text says verify/check/review/validate/reconcile, as in draft_quality; not the summariser's step) is told to start its output with `Verdict: PASS|FAIL` and `Issues:`; on FAIL each producer step it depends on is re-run once with the issues and its earlier output (`rework` event; the first version is kept as `step_<n>.first.md`), at most one rework per step, and the verifier is not asked again. Records: `checks`, `retried`, `verification`, `verdict`, `issues`, `rework_of` in each step's metadata and in `Episode.steps` (a reworked step appears twice) | a plan line that says what done looks like should be checked by code where it can; a verdict that changes nothing is decoration |
| D35 | AutoAgents' last step (the Language Expert) re-derives and embellishes the answer | the answer step, when the summariser owns it, uses its own prompt (`plan_summarise.txt`, ours): it receives every step's latest output with its status, reason, lacked capabilities, verdict and provenance counts, and the deliverable list from the Box 2 requirements (`TeamConfig.requirements`; never the rubric). It is told to assemble and edit only (no new analysis, facts or numbers; figures copied with their tags), to answer in exactly the form the task asks for (only a value when it asks for a value), to say where a step is missing or incomplete, and — only when there is something to list — to end with `## Limitations` (blocked, partial or incomplete steps, lacked capabilities, main unverified figures). A first Gemini toy run with an always-present Limitations section scored 0/20 ("199\n\n## Limitations\nNone." is not "199"). Code check (`summary_check`): every figure in the final answer that is in no step output and not in the task is counted as `new_number_in_summary` (examples listed), and whether a Limitations section exists; recorded in the trace and `result.json` `summary_check` | the summariser has no tools and no sources, so any figure it adds is invented; its job is to carry the team's work to the reader, gaps included |
| D36 | D21 recorded a BLOCKED step but a blocked helper's partial work and the gap reached no one downstream | a plan helper that lacks a capability does the rest and writes `BLOCKED: <capability> — <what could not be done>` in its output (or answers BLOCKED as its action, D21). The step's gaps are the union of both (`plan_runner.blocked_marks`); a step with gaps is `partial` when a helper wrote anything and `incomplete` otherwise, with `status_reason` `lacked: …` and `blocked` / `blocked_canonical` (D29 names) in its metadata. The run always continues; the summariser sees each step's gaps. After the summariser writes, plain code checks that its `## Limitations` section names every lacked capability (canonical name, its spaced form or a name the step used) and appends a `- BLOCKED: <capability> (… added by plain code)` line for each it left out, creating the section if needed (`limitations_added` event, `summary_check.limitations_added_by_code`). `result.json` `blocked_capabilities` counts, per canonical capability, the plan steps (latest version) that lacked it — the input for the later tool-building queue | a missing capability should shrink the answer, visibly, rather than be papered over with invented results |
| D37 | **Explicit verification steps.** D34 found verification steps by keywords (verify, check, review …), so "Review current tariff schedules" became a verifier | the d24 step format gains `kind: work \| verify` (Planner prompt and format example, `parse_plan_d24`, `DraftPlanStep.kind`, `PlanStep.kind`). The plan runner treats a step as a verifier only when it is `kind: verify`, depends on other steps and is not the summariser's; when the plan declares kinds, an undeclared step is work. Only a plan with no kinds at all (older drafts) falls back to the keyword rule, and each step so judged logs `verification_inferred`. `draft_quality`'s independent-verification check uses the same rule | a word in a step title is not a decision; the planner says which steps check others |
| D38 | **Check again after rework.** D34 reworked the producer steps after a FAIL but never asked the verifier again, so a fixed step still reached the summariser under a FAIL verdict | after the producer steps are reworked, the verifier runs once more with a `RE-CHECK` note (its earlier issues and which steps were reworked); no further rework follows, whatever the second verdict. The verifier's metadata keeps `verdict_first` and `verdict_after_rework`; `verdict` is always the latest, and the summariser sees e.g. "verdict: PASS (after rework; first verdict FAIL)". The first verifier output is kept as `step_<n>.first.md`; a `reverify` event names the reworked steps | a rework is only worth something if someone checks it; the answer should carry the verdict that applies to what it uses |
| D39 | **Stale inputs after rework.** A step that ran on a producer's first output kept using it after the producer was reworked, and nothing said so | after a verifier's FAIL reworks producer steps (D34/D38), every step that already ran and depends on a reworked step directly or through other steps — except that verifier, which checks again — is marked `stale` with `stale_because` in its metadata (rewritten on disk) and a `stale` trace event. `run_task --rerun-stale` (default off) re-runs each stale step once, in plan order, on the reworked inputs (`rerun_of_stale`; the old version kept as `step_<n>.first.md`). Later steps see "STALE (built on step(s) … before their rework)" on that input and the summariser sees "STALE: …". Plan-runner settings travel as `PlanOptions` (`Interpreter(plan_options=…)`), all recorded in the `plan_graph` event | an answer built on outputs that were later corrected should say so, and re-running is a cost the user chooses |
| D40 | **The answer step is not a blocked step.** D36 scanned every step's output for `BLOCKED:` lines, including the summariser's Limitations section, which names the producers' gaps on purpose — so a good final answer was marked partial and its gaps were counted twice | the answer step is never scanned for BLOCKED: its status is `done` unless it ran out of turns or failed a check. The names it mentions are kept as `blocked_mentions` (information only); `blocked` stays empty and the step carries `answer_step: true`. `blocked_capabilities` in result.json and the capabilities the Limitations section must name count producer steps only | a step's status says what that step failed to do; reporting other steps' gaps is the answer step's job |
| D41 | **Answer put together by code when no one writes it.** D31 took the last step of the last wave as the answer, so when the last wave held several steps and the summariser owned none of them, all but one step's output was dropped | when the summariser owns a step in the last wave, that step is the answer (D35); when the last wave has one step, it is; otherwise plain code assembles the answer from every last-wave step in plan order, one `## Step <n>: <title>` heading each, then completes the Limitations section with the producers' lacked capabilities (D36). Recorded as `answer_assembled_by_code` (the step numbers) in result.json, an `answer_assembled_by_code` trace event and `artifacts/answer.md`; the run's error is the worst status among those steps | no step's work is dropped silently, and no AI is asked to write what code can put together |
| D42 | **Checks from the planner's format markers.** D34 guessed format checks from words in `output`/`done_when` ("plan", "report", "cost"…), accepted any copied line as "using the inputs", and allowed a retry only when turns were left | the d24 prompt asks each step's `output` line to start with one or more markers — `table:`, `list:`, `code:`, `memo:` — and the format checks come from those (a table, ≥ 2 list items, a code block or statement, ≥ 2 headings); only an `output` line with no marker falls back to the D34 keyword rules. Each check records its `source` (markers/keywords) and the step its `check_source`. `inputs_referenced` now needs a real match: a figure from an input (not a single digit), one of its source ids, a dependency's step number or role name, or 8 consecutive shared words; a whole output under 8 words copied from an input (a value) still counts, a copied line inside other text no longer does. A failed check's retry gets its own `check_retry_turns` (default 2) on top of the turns used | the planner says what each step must produce, so code checks exactly that; a check that anything passes checks nothing |
| D43 | **Figure ledger.** D33 judged each step's numbers on their own line, so a figure that entered untagged was counted "inherited" (clean) as soon as a later step or the summary copied it | the plan runner keeps a ledger of every figure in the run: its first status (cited / unverified / untagged / derived / given), the step that first wrote it and its sources (`provenance.check_provenance` now returns each figure's status). A later step or the summary that repeats a figure inherits that first status: each step records `figure_origins` (its figures counted by ledger status), and `summary_check` adds `answer_figures`, `answer_cited`, `answer_unverified` and `answer_untagged` (the figures in the final answer by their first status). The ledger is written to result.json (`figure_ledger`) and summarised in a `figure_ledger` trace event | copying a number does not make it any more sourced; the answer should be judged by where its figures first came from |
| D44 | **Size limits on what a step is shown.** D31 passed every input artifact whole, the summariser saw every output whole, and a step that never gave a Final Output passed on its entire work log | a step with no Final Output passes on only its last helper message. Each input artifact shown to a step is cut at `max_input_chars` (default 6,000; `run_task --max-input-chars`); the summariser's inputs are cut the same way and, when together they would pass `max_summary_input_chars` (default 30,000; `--max-summary-input-chars`), each step's output gets an equal share (at least 500). A cut keeps the beginning and ends with "[... cut by plain code: first N of M characters shown]", with an `input_truncated` trace event (step, source step, limit, length); both limits are in the `plan_graph` event | prompt size, and so cost, must not grow with how much the previous step wrote; a cut must be visible to the helper and in the trace |
| D45 | **Reuse saved drafts.** Every run drafted its team again, so comparing Box 3 arms paid for Box 2 each time and each arm ran on a different draft | `run_task --drafts-from DIR [--draft-pick K]` reuses a saved Box 2 draft instead of drafting (`amoeba/task/saved_drafts.py`): DIR is an eval_draft output folder (read directly: `drafts/<task>.<n>.json`) or a runs folder (`<run_id>/plan.json`, or `draft.json` when present; one run folder works too). Each task takes its K-th saved draft (repeat order for eval_draft, run start order for runs); failed drafts are skipped, and a task with no K-th draft is skipped with a message. `plan.json` already holds the whole draft; `team.yaml` is not reused because it is built per topology, so every topology builds its team from the same draft. No drafting call is made; a `draft_reused` event and result.json `draft_source` (the eval_draft file stem or the run id) record where it came from | the arms of a comparison should differ only in Box 3, and a draft already paid for should not be paid for again |
| D46 | **Response cache.** Every evaluation paid the model (and the search provider) again for identical calls, and a run could not be repeated offline | `amoeba/llm/cache.py`: `--llm-cache DIR` stores every LLM reply under a hash of (model, messages, max_tokens, temperature) plus an optional `--llm-cache-namespace` (e.g. the repeat number, so repeats of one prompt are not collapsed; the seed is not keyed), and every web_search / fetch_url result under a hash of (provider, operation, query or url, max_results, namespace). `--llm-cache-mode record` answers from the cache when it can and otherwise calls and stores; `replay` answers only from the cache — a miss raises `CacheMiss`, the run stops with `error="cache_miss: …"` (a `cache_miss` event) and nothing reaches the network (the web provider is not even built, so no key is needed); `off` passes through. A replayed reply is marked `amoeba.cache_hit` on its chat span. The same flags exist on eval_draft (shared `add_client_args`) | a result that was paid for once can be re-scored, re-analysed and re-run for free, and replay proves a run used nothing new |
| D47 | **Per-run limits and a cost estimate.** Spec §2 recorded tokens and never enforced them; a runaway run could only be stopped by the provider's spending cap (it was, on 2026-09-24) | opt-in limits in `amoeba/llm/limits.py`: `run_task --max-tokens-per-run N` / `--max-calls-per-run N` are checked by `TracedLLM` before every call (billed tokens = input + output + reasoning of live calls; cache hits (D46) are free and do not count). When a limit is reached the call is not made, a `budget_stop` event is logged, and the run ends with `error="budget"` — the draft, every finished plan step, the trace and result.json are saved. With no limit set nothing reads the token count (T9 now allows the word only in this module and checks that an unlimited run is never stopped). After every run the CLI prints its billed tokens and an estimated cost from `amoeba/config/prices.yaml` (US$ per 1M tokens, reasoning priced as output; shipped with null prices to fill in — a model without a price gets tokens only); result.json `usage` holds the same | the user decides the most a run may spend; stopping cleanly keeps what was already paid for |
| D48 | **Wait out rate limits.** The OpenAI SDK retried twice on its own, invisibly; run_task gave up on the next 429; only eval_draft had a (fixed-wait) retry | `OpenAICompatibleClient` turns the SDK's retries off and retries HTTP 429 and 503 itself: up to `--max-rate-retries` (default 5) times, waiting the server's `Retry-After` when given, else 2, 4, 8, 16, 32 s (capped at 60). A 429 that names a spending cap is not retried (it will not clear in seconds), nor is any other error. Each wait is a `rate_limited` trace event (status, wait, attempt, Retry-After, whether it finally gave up) and the chat span carries `amoeba.rate_limit_retries`. `--min-seconds-between-calls` (default 0) spaces model calls out for free tiers (`amoeba.throttle_wait_s`). eval_draft's own retry now covers only HTTP 500 | free and paid tiers both throttle; waiting is cheaper than losing a half-done run, and every wait should be visible |
| D49 | **Gemma 4 support.** The client always sent a system message and never a reasoning setting; Gemma models served through the Gemini API do not take a system instruction | two `OpenAICompatibleClient` options, on run_task and eval_draft: `--merge-system` puts the system message at the top of the first user message (or makes it the user message) and sends no system role (`client.merge_system`); `--reasoning-effort off\|low\|medium\|high` is sent as `reasoning_effort` only when set, `off` as `none` (the value Gemini's OpenAI-compatible layer takes to turn thinking off). Both are part of the response-cache key (D46). README: how to run Gemma 4 through the Gemini API and through OpenRouter | a model that cannot take a system role still gets the whole prompt; thinking is a cost the user can turn down |

Everything else — caps 3/5/3, the "No Suggestions" and "Final Output" sentinels, the observer history strings, the 5th-iteration hint, the shared `completed_steps`, `{context}` = step text, role prompt in the user message, chat-history delivery of plans/reviews, silent-agree, solver ≤4 — follows the code.

---

## 12. Not built now → where it lands
Memory lookup / reuse / save (Phase 2, reads `runs/`); LLM judge and non-toy scoring (Phase 2); **cost: per-helper token/usd budgets, `BudgetExceeded`, envelope charging, cost-matched reporting (Phase 3, alongside the monitor — add fields to `Limits`, no renames); Monitor (Phase 3 — add a no-op `listener` parameter to `Interpreter.__init__` now); diagnoser / architect / experimenter / gate / logbook / person (Phase 3–4); edit operators and the generic edge executor with fan-in (Phase 3; `run_flat`/`run_boss_reviewers` become its regression tests); web search tool (Phase 2); fetching or creating the tools and skills listed in `capability_requests.json` (a later phase — Phase 1 only records them); PreToolUse hook (Phase 4; `ToolRegistry.execute` is the single call site).

---

## 13. Instruction to Claude Code

> Read `BUILD_SPEC_PHASE1.md` fully, then `VERIFICATION_PHASE1.md` Part B (the verified pseudocode with file:line citations). Build §3–§10. Use `MockLLMClient` for all tests; no network. Copy prompt text verbatim from the paths in §7 (AutoAgents MIT, AgentVerse Apache-2.0) with a source header line; keep template and format-example as separate files. Do not import from `repos/`. Add the no-op `listener` parameter to `Interpreter.__init__`. Stop when T1–T11 pass and `scripts/run_task.py --toy --n 20` runs for both topologies; report mean toy score, tokens and LLM calls per topology, and any place you had to depart from §5–§6.
