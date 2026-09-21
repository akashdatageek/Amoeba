# Repo notes: EvoMAS and ATM (jiuwen_atm)

Clones (shallow, `--depth 1`) under `/home/claude/adaptive-mas-spec/repos/`:
- `EvoMAS/` — https://github.com/amazon-science/EvoMAS @ `93fd9d6766b0` (2026-05-29)
- `jiuwen_atm/` — https://github.com/sidikbro/jiuwen_atm @ `951e9aa8c842` (2026-07-12). Found via the GitHub link in the arXiv HTML of 2607.20488.

Line numbers below are for those commits. "UNVERIFIED" marks anything not checked in code.

---

## 1. EvoMAS (arXiv 2602.06511, ICML 2026)

### 1.1 License / runtime facts
- License: **CC BY-NC 4.0** (`EvoMAS/LICENSE`, `README.md:10`). Non-commercial only. Code cannot be vendored into a commercial product; algorithms can be reimplemented.
- Python 3.11 (`README.md:24`). `requirements.txt` is a kitchen sink (torch, sentence-transformers, swebench, sweagent, mini-swe-agent, smolagents[toolkit,bedrock], litellm, langchain, mem0ai, fastapi…). The evolutionary core only needs `pydantic>=2`, `PyYAML`, `numpy` (numpy is imported but unused in `selection.py:14`).
- LLM providers: `src/models/model.py:1273-1323` `get_model()` dispatches on `provider:model` prefix → `bedrock` (boto3, default in all pool YAMLs and `main.py:44,52-56,75`), `openai`, `anthropic`, `azure`, `google`. **No generic OpenAI-compatible `base_url`** knob: `OpenAIModel.__init__` (`model.py:506`) is `openai.OpenAI(api_key=...)` with no `base_url`. Running against vLLM/Ollama requires a 1-line patch (or setting `OPENAI_BASE_URL` env var, which the openai SDK honours — UNVERIFIED in this codebase).
- Offline: the pure-Python modules (`src/topology/routing.py`, `src/meta_model/{reward,pool,experience,selection,mas_index}.py`, `src/mas/{spec,loader}.py`) import and run with only pydantic+yaml (verified: `python -c` import + `RoutingConfig`/`compute_reward` smoke test). The interpreter needs `smolagents` and a provider key.

### 1.2 Layout
```
main.py                       # the real pipeline: run_evolution_pipeline / _run_single_batch (1131 lines)
src/mas/spec.py               # MasSpec / ExecutionConfig (pydantic)
src/mas/loader.py             # load_mas_from_file / load_mas_from_dict
src/mas/runtime.py            # MasRuntime: DAG-level executor (the "interpreter" proper)
src/mas/interpreter.py        # interpret_mas(): config path + dataset → statistics dict (wraps MasRunner)
src/agents/spec.py            # AgentSpec / AgentResult
src/agents/runners/{base,smolagents,minisweagent,sweagent}.py
src/topology/routing.py       # RoutingConfig: reports_to → Kahn topo-sort / levels
src/topology/context.py       # Context: task / shared / reports / artifacts / trace
src/meta_model/metamodel.py   # MetaModel: select / generate / mutate / crossover / update_memory (all LLM calls)
src/meta_model/reward.py      # R = accuracy − β·cost
src/meta_model/pool.py        # ConfigurationPool (dir of YAML), add_to_pool_if_better
src/meta_model/mas_index.py   # MASIndex: mas_index.json alongside the pool
src/meta_model/experience.py  # ActionExperience / MemoryStore (JSON list) / consolidate_evolution_trace
src/meta_model/selection.py   # programmatic fallback selection (Jaccard keyword overlap)
src/prompts/templates/*.md    # meta_{select,generate,mutate,crossover,update_memory}.md + agent role prompts
src/utils/mas_runner.py       # MasRunner: per-task loop, timeouts, token/time accounting, evaluators (1839 lines)
src/dataset/llm_as_judge.py   # 5-aspect 0-100 judge
mas_pools/{bbeh,swebench,workbench/<domain>}/*.yaml + mas_index.json   # seed pools
```

### 1.3 Configuration schema (exact)

`src/agents/spec.py:34-52`:
```python
class AgentSpec(BaseModel):
    id: str
    role: str                                  # 'worker','aggregator','debater','judge','moderator','reviewer','processor','team_worker' (only used by MasSpec.get_*_agents helpers)
    agent_type: str = "CodeAgent"              # CodeAgent | ToolCallingAgent (smolagents) | DefaultAgent (minisweagent) | SWEAgent
    model_id: str                              # "provider:model"
    prompt: Optional[str] = None               # template name — see 1.5 caveat: NOT used by SmolagentsRunner
    tools: List[str] = []                      # names; only 'workbench_*' strings are resolved (smolagents.py:267-307)
    max_tokens: int = 4096
    temperature: float = 0.7
    device: Optional[str] = None
    backend: Optional[str] = None              # per-agent override
    additional_params: Dict[str, Any] = {}
    class Config: extra = "allow"
```
`src/topology/routing.py:9-29`:
```python
class RoutingConfig(BaseModel):
    reports_to: Dict[str, List[str]] = {}      # src_agent -> [dst agents]; edge u->v means v depends on u
    edges: Optional[List[Dict[str,str]]] = None # declared but NEVER read anywhere (grep confirms)
```
`src/mas/spec.py:31-46`:
```python
class MasSpec(BaseModel):
    name: str; description: Optional[str]; backend: str = "smolagents"
    agents: Dict[str, AgentSpec]; topology: RoutingConfig
    execution: ExecutionConfig   # parallel_workers=True, timeout, max_retries=0, debate_rounds, smoa_*, peer_review_stages, croto_*, agent_config="default"; extra="allow"
```
Pool YAML (e.g. `mas_pools/bbeh/debate.yaml`) is exactly `name/description/backend/agents{id:{…}}/topology{reports_to}/execution`. Pool entries additionally carry `successful_tasks: [{q, notes}]` and `meta: {reward, accuracy, total_tokens, evolution_source, added_at}` written by `pool.py:66-78`.
There is **no contract/IO-schema on edges** and **no explicit V_in/V_out**: entry agents are those with in-degree 0; the output is `context.reports[execution_order[-1]]` (`runtime.py:139-140`), i.e. the *last node in topological order* — with sorted tie-breaks (`routing.py:67,103,114`), so which agent is "the output" is implicit.

### 1.4 Interpreter (config → execution)
- `src/mas/runtime.py:112-149` `MasRuntime.run(task)`: `Context(task)`; `levels = spec.get_execution_levels()`; `_execute_dag`.
- `_execute_dag` (`runtime.py:151-184`): for each level, run pending agents in parallel via `ThreadPoolExecutor` (`:196`) if `execution.parallel_workers` and not a SWE-bench task, else sequentially. Each agent: `runner.run(agent_spec, task, context.model_dump())` → `AgentResult`; `context.add_report(agent_id, content, metadata)`; on failure the report is the string `"Error: …"` (`:214,294`) — errors are *not* propagated, downstream agents see the error text.
- Level computation `routing.py:86-118` (Kahn by waves). **Cycle handling**: if not all nodes are placed, returns `[agent_ids]` (one level with everything) — verified: `reports_to={a:[b], b:[a]}` → `[['a','b']]`. No iteration/loops; cycles silently degrade to "run everyone once, in parallel, with empty context".
- Context passing: `SmolagentsRunner.run` (`agents/runners/smolagents.py:316-329`) builds `full_prompt = task + "\n\nContext from other agents:\n" + "--- {agent_id} ---\n{report}"` for **all** reports currently in `context['reports']`, not just predecessors. So edges control *ordering only*; every agent sees everything already produced. Agents in the same level see nothing from each other.
- Specialised routines `_execute_debate/_execute_smoa/_execute_peer_review/_execute_croto` (`runtime.py:355-904`) exist but are **dead code**: `run()` only calls `_execute_dag`. The pool instead ships "DAG-unrolled" patterns (debate = 6 debaters × 3 rounds as 18 nodes + moderator, `mas_pools/bbeh/debate.yaml`).
- `interpret_mas()` (`src/mas/interpreter.py:356-440`): wraps `MasRunner`, returns `{"status","statistics":{…,'token_costs','time_costs'},"output_location"}`; statistics from `mas_runner.py:1741-1781` (`accuracy` = mean of judge scores 0-100, or fraction correct for bool evaluators).

### 1.5 Prompt caveat (important)
`AgentSpec.prompt` is read only by the dead debate/peer-review paths (`runtime.py:383-427,635,683,729`). `SmolagentsRunner.run` never looks at `spec.prompt`; the only per-agent instruction differentiation is the agent id label in the context block and the WorkBench system prompt (`smolagents.py:319-324`). `src/prompts/templates/{worker,aggregator,debater_*,…}.md` are never rendered for agents (grep: `render_prompt`/`PromptRegistry` are used only in `metamodel.py`). Consequently the meta-model's "prompts" mutation type changes YAML that has no runtime effect for the smolagents backend. Any reimplementation must actually inject the prompt.

### 1.6 Evolution loop (`main.py:370-914` `_run_single_batch`) — the paper's algorithm
Constants (`main.py:42-99`): `META_MODEL_TEMPERATURE=0.7`, `META_MODEL_MAX_TOKENS=8192`, `NUM_PARENTS=2`, `MAX_STEPS=3` (scripts use 2, `scripts/common.sh:44`), `NUM_EVAL_TASKS=1` (per-query evolution), `MUTATION_PROB=0.8`, `BETA=1e-6`, `COST_WEIGHT="both"`, `IMPROVEMENT_THRESHOLD=0.05` (comment says "1%", value is 0.05), `LLM_AS_JUDGE` = Sonnet 4.5 on Bedrock, `DIVERSITY_WEIGHT=0.3`.

1. **Select** (`:534-540`): `meta_model.select(task_query, task_description, pool_dir, k=2, mas_index)` — LLM chooses k names from `mas_index.get_selection_context(max_configs=20)` (entries sorted by `(total_wins, avg_accuracy)` desc, `mas_index.py:183-188`); prompt `meta_select.md`; parse ```json {"selected":[{"name":…}]}```; fallback `selection_operator` = Jaccard keyword overlap with `successful_tasks` (`selection.py:50-134`).
2. **Generate** (`:585-617`): for each parent, `meta_model.generate()` (prompt `meta_generate.md`) adapts the YAML to the task samples; each adapted config is evaluated with `interpret_mas(..., llm_as_judge=…)`; reward via `compute_reward`. Best of the k becomes `best_config`.
3. **Loop** `for step in 1..max_steps` (`:634-746`): `use_mutation = random.random() < 0.8`.
   - mutate: `meta_model.mutate(best_config, execution_logs=best_stats, observations, model_list)`.
   - crossover: two highest-reward configs so far → `meta_model.crossover(c1,c2,logs1,logs2)`.
   - evaluate offspring; append to `all_configs/all_stats/all_rewards`; update best if `offspring_reward > best_reward` (strict); record op dict `{type,step,accuracy,reward,improved,changes,accuracy_change}`; `update_memory(...)` every step.
4. **Select best** = argmax reward (`:755`).
5. **Consolidate** (`:774`): `consolidate_evolution_trace` — pure Python string summary (counts of ops, most effective op). The `meta_update_memory.md` LLM call happens per-step in `update_memory`, not here.
6. **Pool update** (`:792-824`): re-evaluates the *original* parents (another k interpreter runs), then `add_to_pool_if_better(threshold=0.05)`: add iff `R_new − max(R_parents) > threshold` (`pool.py:190-220`). New file `evolved_<ts>.yaml`; `mas_index.add_config`.
7. `mas_index.record_query_result(..., is_winner=True)` (`:833`), running averages (`mas_index.py:132-168`; keeps last 20 solved tasks).
8. Final ground-truth evaluation with dataset evaluator (`:859-869`).

Batching: `run_evolution_pipeline` (`:154-335`) chunks `task_ids` into batches; each batch runs `_run_single_batch` in a `ThreadPoolExecutor`; memory file gets `_batchNNN` suffix per worker (`:288-292`). Pool dir is shared without locking (timestamped filenames avoid collisions).

### 1.7 Mutation operators (they are prompts, not code)
The "operator list" lives in `src/prompts/templates/meta_mutate.md:9-24`:
> Select EXACTLY ONE component type to mutate: **Prompts** | **Model IDs** | **Tools** | **Topology** (reports_to). DO NOT modify multiple component types; DO NOT add or remove agents; don't change `name`/`backend`.

Crossover (`meta_crossover.md:9-26`): inherit the **entire topology from exactly one parent**; per agent position choose Parent 1 / Parent 2 / hybrid of properties; no new agents.
Generate (`meta_generate.md`) is unconstrained (may add agents). Output extraction: `extract_yaml_from_response` regex on ```yaml fences / "Updated Configuration:" (`metamodel.py:26-62`); validation is only `name`,`backend`,`agents` present and non-empty (`:65-97`) — **no check that reports_to references existing agents, no cycle check, no tool/model whitelist enforcement** (model whitelist is prompt-only, `:445-448`). On any failure the parent YAML is returned unchanged (`:409-418,496-505,599-608`).
Nothing in Python enforces "one component type" either; `_compare_configs` (`:720-786`) only produces a change description for memory.

### 1.8 Fitness / cost (exact)
`src/meta_model/reward.py:15-64`:
```python
accuracy = metrics.get('accuracy', 0.0)                     # 0-100 judge score (or 0-1 legacy)
total_tokens = metrics['token_costs']['total_tokens']       # if nested, else metrics['total_tokens']
total_time   = metrics['time_costs']['total_time']          # seconds (wall clock per batch)
cost = total_tokens                      if cost_weight=="tokens"
     = total_time                        if "time"
     = total_tokens + 1000 * total_time  if "both"          # "1 token ≈ 0.001 s"
reward = accuracy - beta * cost                              # beta default 1e-6
```
With defaults: 100k tokens + 60 s → penalty 0.16 on a 0-100 scale. `main.py:69` comment: "10⁻⁶ balances Metrics∈[0,100] vs Cost∈[100K–32M]". Token accounting: `runtime.py:296-353` sums `input/output/thinking` (+ OpenAI `prompt/completion/reasoning`, + sweagent `model_stats`) over `context.trace`; `mas_runner.py:1458-1462,1533-1542` aggregates per batch. Bug: `pool.py:275` stores `new_metrics.get('total_tokens',0)` (flat key) so `meta.total_tokens` and `mas_index.avg_tokens` are always 0 (see `mas_pools/bbeh/mas_index.json` — every `avg_tokens: 0`).
Judge (`src/dataset/llm_as_judge.py`): 5 aspects (Correctness 40 / Reasoning / Collaboration 10 / Efficiency / Completeness, dataset-specific splits) parsed by regex `Aspect\s*:\s*(\d+)`, summed to 0-100.

### 1.9 Pool / memory storage and retrieval
- **Pool** = a directory of YAML files (`pool.py:20-187`); `get_configurations()` = `glob("*.yaml")`. No dedup, no size cap, no pruning, no lineage beyond `meta.evolution_source="evolved"`.
- **Index** = `<pool>/mas_index.json` dict keyed by file stem (`mas_index.py:82-103`): `path,name,description,backend,num_agents,agent_roles,agent_models,topology_edges["a→b"],structure_summary,solved_tasks[≤20],total_queries,total_wins,avg_accuracy,avg_tokens,avg_time_seconds,source,created_at`. Retrieval: `get_selection_context(max_configs=20)` sorted by wins then accuracy — no similarity search.
- **Memory** = JSON list of `ActionExperience{query[:500],action,config_changes,old_accuracy,new_accuracy,success,analysis}` (`experience.py:15-133`); default path `dataset/<subset>/memory_<ts>.json` (fresh per run unless `MEMORY_PATH` given). Retrieval = **last N=3** entries (`to_context_string(max_experiences)`, `experiences[-max:]`; callers pass 3 at `metamodel.py:225,376,463,566`). No embedding/top-k relevance. `EvolutionTrace` dataclass exists but is never persisted.

### 1.10 Execution traces
`src/topology/context.py:29-48`: `trace` entries are `{"agent_id", "action":"report", "content_length", "metadata":{agent_type, model_id, input_tokens, output_tokens, total_tokens,…}}`. Reports themselves are in `context.reports[agent_id]` (final string only). No per-step tool-call trace is captured from smolagents (`agent.run()` returns only the final answer, `smolagents.py:335`). What the meta-model sees as "execution logs" is `str(best_stats)` (the statistics dict) plus a 3-line observations string (`main.py:656-660`). Per-task outputs: `output/<dataset>/<config>_<model>/<task_id>.txt` and `results.json` (`mas_runner.py:845-919`) with `query, ground_truth, error, raw_output[:500], correct`.

### 1.11 LLM boundary
LLM calls: `MetaModel.select/generate/mutate/crossover/update_memory` (`metamodel.py:161-718`, each via `self.model(prompt)`), `LLMAsJudgeEvaluator.evaluate_correctness`, and agent execution inside `SmolagentsRunner.run` → `agent.run()`. Pure Python: `routing.py`, `context.py`, `merge.py`, `reward.py`, `pool.py`, `experience.py` (incl. `consolidate_evolution_trace`), `selection.py`, `mas_index.py`, `spec.py`, `loader.py`, `extract_yaml_from_response`, `validate_mas_config`, `_compare_configs`, `MasRuntime._execute_dag` scheduling.

### 1.12 Reuse verdict (EvoMAS) — for a project needing cycles + contracts, interpreter, operator set, cost-penalised fitness, archive
| Piece | Verdict | Why |
|---|---|---|
| YAML schema (`AgentSpec`, `RoutingConfig.reports_to`, `MasSpec`) | **Reimplement** (borrow field names) | CC BY-NC; no edge contracts, `edges` field dead, cycles unsupported, output node implicit. Keep `reports_to` adjacency idea and `agent=(model_id,prompt,tools)` triple. |
| Level scheduler `RoutingConfig.get_execution_levels` | Reimplement (≈30 lines) | Fine algorithm but cycle fallback is wrong for our needs; need max-iterations / loop semantics. |
| `MasRuntime._execute_dag` + `Context` | Reimplement | Broadcasts all reports to everyone; prompt not injected; errors become text. Keep the `AgentResult{content,success,error,metadata}` shape. |
| `compute_reward` | Reimplement (trivial) | Formula `acc − β·(tokens + 1000·time)`, β=1e-6, threshold 0.05 are the reusable numbers. |
| Operator set | **Reuse the specification** (prompt text), reimplement enforcement in code | One-component-per-step rule, no add/remove agents in mutate, topology-from-one-parent crossover — none are enforced in Python. |
| Pool + `mas_index.json` schema | Reusable with modification (schema only) | Dir-of-YAML + JSON index is adequate; add lineage, dedup by config hash, real token stats. |
| `ActionExperience` memory | Reusable with modification | Add relevance retrieval; current is last-3. |
| `extract_yaml_from_response`/`validate_mas_config` | Reimplement with pydantic strict validation | Current validation is 3 key checks. |
| LLM-as-judge rubric (`llm_as_judge.py`) | Reusable with modification | Prompts are fine; needs own client. |

---

## 2. ATM — Autonomous Topology Mutation (arXiv 2607.20488)

Paper: Sidik, Levi, Kimhi (Toga Networks/Huawei). "Safe Runtime Restructuring for Multi-Agent LLM Systems with Capability, State, and Shadow Invariants." Code: **found** — https://github.com/sidikbro/jiuwen_atm (link is in the arXiv HTML; the abstract page could not be fetched: sandbox proxy returns 403 for arxiv.org via curl, and the WebFetch of `/abs/` needed a permission grant that did not arrive; the `/html/` fetch succeeded).

### 2.1 License / runtime facts
- **MIT** (`pyproject.toml:11`, README). `requires-python >= 3.11`. Deps: `numpy`, `pydantic>=2`, `openai>=1.50` only (`pyproject.toml:26-30`). `pip install -e .` then `pytest tests/` → **140 passed in 0.8 s offline** (verified; README says 55, repo has grown).
- LLM: `jiuwen_atm/llm_client.py:19-48` `OpenAICompatibleClient(api_key, base_url, model)` — any OpenAI-compatible endpoint via `LLM_BASE_URL`/`LLM_MODEL` env (`config/defaults.json` "llm": deepseek-chat @ api.deepseek.com, temperature 0.7, judge 0.1). `default_client()` falls back to `MockLLMClient` when no key. Structured output = JSON-schema-in-system-prompt + `pydantic.model_validate_json` (`:29-40`), no tool-calling API dependence.
- Host runtime "openjiuwen"/JiuwenSwarm is **not on PyPI**; `rails/base_compat.py` stubs it and `LiveTeamManagerAdapter` is `NotImplementedError` (`topology/team_manager_adapter.py:63-88`). Everything here is the standalone/eval path.

### 2.2 Layout (package `jiuwen_atm/`)
```
config/defaults.json      # all constants (weights, warmup, K, tau pct, W, cooldown, trust caps)
config.py                 # typed loader
models.py                 # Agent, AgentMetrics, BottleneckReport, PLLevel, MemorySpan, ShadowMode
monitoring/telemetry.py   # AgentTelemetry: sliding windows → AgentMetrics
monitoring/bottleneck_index.py   # B_i, tau calibration, K-consecutive trigger
monitoring/event_log.py   # InMemoryEventLog / FileEventLog (JSONL)
safety/capability_policy.py      # I1 check
safety/mutation_contract.py      # MutationContract / ChildSpec (JSON-serialisable audit record)
topology/factorizer.py    # LLM split (2-4 children) + I1 gate
topology/state_atoms.py   # decompose_context → StateAtom (type, security label, PL)
topology/state_distiller.py      # I2: shared / per_role / quarantine
topology/verifier.py      # I3: modes, W-window commit/rollback, exponential cooldown
topology/coordinator_wrapper.py  # hot-swap parent → coordinator_node
topology/topology_store.py       # profiles as JSON files
topology/mc_selector.py   # best-of-K candidate splits (post-paper addition)
topology/atm_pipeline.py  # orchestrator: on_tick / on_task_complete
integration/atm_monitor_rail.py  # hook-based tick (rail) variant
eval/                     # benchmark (A0-A3, W1-W3), real_task_runner, llm_judge, simulator
rails/                    # ToolRepair, MemoryGuard, LoopGuard, … (unrelated to topology)
```

### 2.3 Agent / topology schema (exact)
`models.py:16-25`:
```python
@dataclass
class Agent:
    agent_id: str; system_prompt: str; tools: list[str]; memory_scope: list[str]
    trust_level: str = "standard"; agent_type: str = "worker"   # "worker" | "coordinator_node"
    sub_agents: list[str] = []; routing_policy: str | None = None
```
There is **no graph object**: topology is a tree implied by `coordinator_node.sub_agents`; the only routing policy string produced is `"sequential_pipeline"` (`factorizer.py:27`, `coordinator_wrapper.py:18`). Coordinator prompt (`coordinator_wrapper.py:14-19`) is text: "delegate to sub-agent 1, pass output to 2, return final result." The coordinator's actual per-message routing is prompt-driven, not code (paper also does not specify it).
`safety/mutation_contract.py:8-29`: `ChildSpec{id,tools,memory_scope,forbidden_tools}`; `MutationContract{contract_id "mc_<ts>_<hex6>", parent_agent, mutation_reason: list[str], children, routing_policy, capability_invariant="children_union_subset_of_parent", rollback_trigger="success_rate_drop OR exposure_increase", shadow_completed, committed, created_at, invariant_check_passed}` with `to_json/from_json`.
Factoriser LLM output schema (`factorizer.py:17-28`): `FactorizationPlanSchema{children: list[ChildRoleSchema{id, system_prompt, tools, memory_scope, routing_order}] (2..4), routing_policy="sequential_pipeline", rationale}`. Prompts `_SYS`/`_USER` at `:31-47` (parent prompt truncated to 600 chars; bottleneck summary string appended).
Memory atoms `state_atoms.py:9-37`: `StateAtom{atom_id, type: AtomType(14 values), content, source_step, dependencies, security_label ∈ {public, web_untrusted, local_private, credential}, pl_level 0-4, metadata}`; `decompose_context` splits on blank lines and infers type/PL by keyword regex (`:47-81`). PL scale `models.py:52-57`: 0 PUBLIC, 1 SESSION_LOW, 2 SESSION_MID, 3 SESSION_HIGH (PII/paths), 4 RESTRICTED (credentials).

### 2.4 Bottleneck Index — exact
Paper Eq. 1 (§3.2): `B_i = α·Q_i + β·C_i + γ·E_i + δ·H_i + ε·R_i + ζ·W_i`, `(α,β,γ,δ,ε,ζ) = (0.20, 0.15, 0.20, 0.20, 0.15, 0.10)` (sum 1.00). Code adds two opt-in terms `η·registry_miss + θ·permission_denied`, both 0.0 by default (`defaults.json` "weights").
Code (`monitoring/bottleneck_index.py:63-74`), all terms clipped to [0,1]:
```python
B = α·min(queue_depth/20, 1) + β·min(context_thrash, 1) + γ·tool_error_rate
  + δ·min(role_entropy/log2(6), 1) + ε·retry_loop_rate + ζ·min(cross_agent_wait/10, 1)
  + η·min(registry_miss_rate,1) + θ·min(permission_denied_rate,1)
```
Signals (`monitoring/telemetry.py`), all over a sliding deque of the last `TELEMETRY_WINDOW_SIZE=100` events per agent (`:24-34`, `defaults.json` "telemetry"):
- `Q_i` = mean of recorded queue depths (`:90`), normalised by `max_queue_depth=20`.
- `C_i` = `len(context_events)/100` (`:91`) — count of context reorganisation events in window.
- `E_i` = fraction of tool calls with `success=False` (`:92,114-115`).
- `H_i` = Shannon entropy (bits) of action categories (`:46-53`); tool names map to 6 categories `{io_fetch, compute, reasoning, file_op, code_exec, other}` via `_ACTION_CATEGORIES` (`:15-21`); normalised by `log2(6)≈2.585`.
- `R_i` = fraction of tool calls flagged `is_retry` (`:94`).
- `W_i` = mean seconds blocked on other agents (`:95`), normalised by `max_cross_agent_wait=10`.
Paper gives no normalisation; these clip constants are code-only.
**Tick** = one call of `ATMPipeline.on_tick` ("every N agent interactions", `atm_pipeline.py:79`) or, in the rail variant, every `after_tool_call` (`integration/atm_monitor_rail.py:3-4,43`). Paper: "On every LLM call".
**Calibration** (`bottleneck_index.py:76-97`): record B each tick; when `len(b_values) >= warmup_ticks=20` (paper: first 20 ticks; module docstring says 50 — stale), `τ = np.percentile(warmup_B, 95)` frozen; warning if coefficient of variation of warmup < 0.05. Before warmup `τ=0.9` placeholder and nothing triggers.
**Trigger** (`:105-123`): `consecutive = consecutive+1 if B>τ else 0`; `should_mutate = warmup_done and consecutive >= K=3`. Dominant-signal labels use fixed thresholds: Q/20>0.5, E>0.3, H/log2(6)>0.6, C>0.5, R>0.3, W/10>0.5. After trigger `reset_consecutive`. No hysteresis band.

### 2.5 Invariants — definitions (paper §5 + code)
- **I1 Capability monotonicity**: paper: `T_{c_k} ⊆ T_p` and `trust(c_k) ≤ trust(p)`. Code `safety/capability_policy.py:38-55`: `∪_k tools(c_k) ⊆ allowed_tools(parent)` and each `memory_scope(c_k) ⊆ memory_scope(parent)`; violation ⇒ plan rejected with no retry (`factorizer.py:81-86`). Trust: children are created with `parent.trust_level` verbatim (`coordinator_wrapper.py:42`, `team_manager_adapter.py:48-54`); trust is an ordinal label mapped to max PL by `rails/memory_guard_rail.py:40-66` `{cloud_public:1, cloud_trusted:2, local:4}` (`defaults.json` "trust_caps"). No `trust(c)≤trust(p)` comparison is coded — equality by construction. Additionally `T_{c1} ∩ T_{c2} = ∅` is a paper assertion (Alg. 1 line 4); in code disjointness is only requested in the prompt ("mutually exclusive"), not asserted (UNVERIFIED that any test enforces it; `check_mutation_invariant` does not).
- **I2 State-routing completeness**: paper: every memory atom appears in ≥1 child's memory or is explicitly logged as dropped with a reason; atoms with PL ≥ 3 routed to at most one child. Code `topology/state_distiller.py:42-77`: each atom → exactly one of `_shared | child_id | _quarantine`; rule order: `type ∈ {CREDENTIAL, ERROR_TRACE}` → quarantine; `pl_level ≥ 3` → quarantine (stricter than paper: never routed); `type ∈ {USER_GOAL, CONSTRAINT, PENDING_STEPS, FORMAT_REQUIREMENT}` → shared (to all children); else first child whose `memory_scope` matches the atom type string; `web_untrusted` → first child with a search/scrape/browse tool; else quarantine. Completeness asserted: `len(shared)+Σ per_role+len(quarantine) == len(atoms)` (`:57-60`). Child context = `shared + per_role[child]` joined by blank lines (`:29-31`).
- **I3 Shadow-before-live**: paper: no candidate replaces the incumbent until it has run in shadow for ≥ W=5 tasks with non-regression on success; candidate responses logged, never returned upstream. Code: `apply_coordinator_wrapper` asserts `contract.shadow_completed` (`coordinator_wrapper.py:34-36`); modes `OBSERVE_ONLY → SHADOW_MUTATE → LIVE_MUTATE` (`models.py:104-107`), promotion to LIVE requires explicit `enable_live_mutate` (`atm_pipeline.py:181-183`).

### 2.6 Shadow validation — exact
Paper Alg. 3 (§4.3), per task t=1..W (W=5): run τ through incumbent T0 and return its answer; run τ through candidate T1 in parallel, silent, scored only; then
```
commit  iff  S1.success ≥ S0.success  and  (S1.time < S0.time  or  S1.exposure < S0.exposure)
else rollback + exponential cooldown 5 min → doubling → cap 60 min
```
Scores: success = LLM-as-judge (`eval/llm_judge.py`: `JudgeVerdict{success, score∈[0,1], rubric_matches, leakage_detected, reasoning}`, rubric = must-contain / must-exclude lists, substring fallback), time = median time-to-completion, exposure = count of PL≥3 events per task.
Code differs (paired-in-time, not paired-in-task): `topology/verifier.py:13-46`:
```python
W_VALIDATION=5; N_COOLDOWN_BASE=10; MAX_COOLDOWN=160        # units = tasks, not minutes
should_commit  : len(post) >= 5 and sr(post) >= sr(pre) and avg_exposure(post) <= avg_exposure(pre)
should_rollback: len(post) >= 2 and (sr(post) < sr(pre) or avg_exposure(post) > avg_exposure(pre))
cooldown on rollback: min(10 * 2**(n_failures-1), 160) tasks, decremented once per on_tick
```
`pre` = TaskMetrics recorded while in OBSERVE_ONLY, `post` = after mutation (`atm_pipeline.py:157-176`). **Time is not part of the code criterion.** `Verifier.run_shadow_pass` (`verifier.py:69-77`) is a stub: it only checks children exist and sets `shadow_completed=True` — the true parallel shadow execution exists only in the eval harness (`eval/real_task_runner.py:224-257` `_select_split_mc`: score = shadow success rate over W templates, distill=False, seeds `seed+1000+j`) and in `MonteCarloTopologySelector.select` (`mc_selector.py:121-148`: argmax over K=4 candidates incl. one random split; commit only if `winner.score > incumbent_score`; warns if mean pairwise Jaccard diversity < 0.05).

### 2.7 Full pipeline pseudocode (paper Alg. 1-4 reconciled with `atm_pipeline.py:79-176`)
```
on_tick(agent p, context_text, tick):
  if cooldown[p] > 0: cooldown[p] -= 1; return
  m = telemetry.snapshot(p)                     # windowed signals
  B = Σ w_k · clip(signal_k)                    # §2.4
  history[p].append(B)
  if len(history[p]) == 20: τ[p] = percentile(history[p], 95)   # frozen
  if not warmed: return
  consecutive = consecutive+1 if B > τ else 0
  if consecutive < 3: return
  consecutive = 0; log("bottleneck_detected", B, τ, dominant_signals)
  # Alg.1 factorise
  plan = LLM_structured(_SYS, _USER(p.id, p.system_prompt[:600], p.tools, p.memory_scope, report.summary()))
  children = sorted(plan.children, key=routing_order); forbidden_k = p.tools − tools_k
  if not (∪ tools_k ⊆ p.tools and ∀k memory_scope_k ⊆ p.memory_scope): log("I1_violated"); return   # no retry
  # Alg.2 distil
  atoms = decompose_context(context_text)
  for a in atoms: route(a) ∈ {shared, child_k, quarantine}   # rules §2.5
  assert count preserved                                       # I2
  # Alg.3 shadow (real impl: run candidate silently on next W tasks; code stub marks shadow_completed)
  if mode != LIVE_MUTATE: return "shadow passed, live not enabled"
  # Alg.4 hot-swap
  for k: child_k = Agent(id_k, "You are {id}.\n"+shared+per_role_k, tools_k, scope_k, trust=p.trust)
  p' = Agent(agent_id=p.agent_id, system_prompt=COORD_PROMPT, tools=[], agent_type="coordinator_node",
             sub_agents=[ids], routing_policy="sequential_pipeline")
  store.save(TopologyProfile(contract_id, p.id, contract, diff_log))   # JSON file /tmp/jiuwen_topology/<id>.json

on_task_complete(p, success, exposure_events):
  window[p].(pre|post).append((success, exposure))
  if should_commit: store.commit(profile)           # committed=True
  elif should_rollback: store.rollback; teardown children; cooldown[p] = min(10·2^(n−1), 160)
```
Not supported by paper or code: re-splitting a child, merging children back, >4 children, cyclic topologies, multi-parent graphs. `ATMMonitorRail` keeps `_mutated` set to avoid re-triggering a split agent (`atm_monitor_rail.py:38`).

### 2.8 Traces / logs
`monitoring/event_log.py`: `LogEntry{event_id, event_type, timestamp, agent_id, data}`; event types emitted: `bottleneck_detected{b_i,tau,signals}`, `mutation_proposed{status: accepted|I1_violated|llm_error, children|reason}`, `mutation_shadow_pass`, `mutation_live{contract_id, children}`, `mutation_committed`, `mutation_rollback{cooldown_tasks, failures}`. `FileEventLog` = JSONL. `TopologyStore` = one JSON per profile (`topology_store.py:26-35`). Per-tool-call telemetry is *not* persisted (in-memory deques only). Eval harness records `AgentTurn` per tool call (`eval/real_task_runner.py`).
Caveat for anyone citing the paper's Table 2: `eval/benchmark.py:85-127` `ablation_signal_impact` *synthesises* the signal-ablation numbers from hard-coded drops plus Gaussian noise rather than re-running with signals removed; `eval/bi_signal_ablation.py` exists separately (UNVERIFIED whether the paper's table comes from it).

### 2.9 LLM boundary
LLM calls: `Factorizer.factorize` (one structured call), `judge_task` (eval), `ToolRepairRail`/`ReferenceRepairRail` (unrelated), agents in `eval/real_task_runner._run_agent`. Pure Python: telemetry, `BottleneckIndex`, `CapabilityPolicy`, `StateDistiller`, `decompose_context`, `Verifier`, `coordinator_wrapper`, `TopologyStore`, `MonteCarloTopologySelector`, `MutationContract`.

### 2.10 Reuse verdict (ATM)
| Piece | Verdict | Notes |
|---|---|---|
| `monitoring/telemetry.py` + `bottleneck_index.py` (≈250 lines, MIT, numpy only) | **Reusable as-is** | Rename category map for our tools; consider EMA. Keep p95-of-20 warmup, K=3. |
| `safety/capability_policy.py` + `mutation_contract.py` | **Reusable as-is** | Add explicit disjointness + `trust(c) ≤ trust(p)` ordinal check (both missing). `MutationContract` JSON is a good "mutation record" schema for our archive. |
| `state_atoms.py` + `state_distiller.py` | Reusable with modification | Keyword-regex atomiser is toy-grade; routing rules + completeness assert are the reusable part. Paper's "high-PL to at most one child" is stricter-coded as quarantine. |
| `verifier.py` (modes, W-window, cooldown) | Reusable with modification | Add the paper's time criterion and true paired shadow runs (code stub). |
| `mc_selector.py` | Reusable as-is | Best-of-K with random baseline and Jaccard diversity; pair with our own `score_fn`. |
| `factorizer.py` prompt + pydantic schema | Reusable with modification | Generalise to N-ary split and to other operators (merge, rewire); enforce disjointness. |
| `coordinator_wrapper.py` | Reimplement | Sequential-pipeline-only, tree-only; our graph needs explicit edges/contracts. |
| `Agent` dataclass | Reimplement | No prompt/model/contract fields beyond system_prompt+tools+memory_scope. |
| `llm_client.py` | Reusable as-is | Minimal OpenAI-compatible + structured-JSON + mock; good for offline tests. |

---

## 3. Cross-cutting notes for the build spec
- Config algebra: EvoMAS = whole-config YAML rewritten by an LLM under a *stated* one-component rule (unenforced); ATM = a single, code-verified operator (split-with-coordinator) gated by three invariants. Neither has edge contracts, cycles, or a merge/rewire operator; both use "prompt text" as the only routing semantics.
- Numbers to carry: EvoMAS β=1e-6, cost=tokens+1000·s, pool threshold 0.05, MUTATION_PROB 0.8, k=2 parents, memory last-3; ATM weights (0.20,0.15,0.20,0.20,0.15,0.10), clips Q/20, W/10, H/log2 6, warmup 20 ticks, τ=p95, K=3, W=5, cooldown 10·2^n tasks cap 160 (paper: 5 min→60 min), commit rule `sr_post ≥ sr_pre ∧ exposure_post ≤ exposure_pre` (paper adds `∨ time_post < time_pre`).
- Both judge success with LLM-as-judge; EvoMAS 0-100 five-aspect, ATM boolean+rubric.
