# VERIFICATION_PHASE1 — spec §5–§7 checked against the clones

Checked against: `repos/AutoAgents` (manager.py, environment.py, actions/{create_roles,check_roles,check_plans,custom_action}.py, actions/action/{action,action_output}.py, roles/{group,role}.py, system/utils/common.py, system/memory/memory.py, system/schema.py, explorer.py) and `repos/AgentVerse` (environments/tasksolving_env/rules/decision_maker/{vertical_solver_first,base,brainstorming}.py, rules/base.py, basic.py, agents/base.py, agents/tasksolving_agent/{solver,critic}.py, output_parser/output_parser.py, memory/chat_history.py, llms/openai.py, message.py, utils.py, tasks/tasksolving/{brainstorming,humaneval/gpt-4,pythoncalculator,responsegen/gpt-4}/config.yaml).

Legend: **CONFIRMED** = code does this. **WRONG** = code does something else (stated). **NOT IN CODE** = our addition; fine if marked `# DEVIATION`.

---

## Part A — line-by-line verification

### A.1 Drafting trio (spec §5.2) vs `manager.py`, `environment.py`, actions

| Spec line | Verdict | What the code actually does |
|---|---|---|
| `history = ""; sugg_roles = ""; sugg_plan = ""; consensus = False` | CONFIRMED | `manager.py:26-29`: `roles_plan, suggestions_roles, suggestions_plan = '', '', ''`; `suggestions, num_steps = '', 3`; `steps, consensus = 0, False`. |
| `for round in range(3)` (cap 3) | CONFIRMED | `manager.py:27` `num_steps = 3`; `:30` `while not consensus and steps < num_steps`. |
| planner call: `llm.sections(create_roles, context=task.prompt, existing_roles="", tools=..., history=history, suggestions=join(sugg_roles, sugg_plan))` | WRONG (3 points) | (a) `context` is `self._rc.important_memory` (`manager.py:32`) = list of `Message` with `cause_by=Requirement`; formatted by `str()` → `"[Question/Task: <idea>]"` (`schema.py:32-34`, `role.py:78-80`), not the bare prompt. (b) `history` is `str(response.instruct_content)` of the previous round (`manager.py:33`), i.e. the pydantic field-repr `"Selected Roles List='…' Created Roles List='…' Execution Plan='…' RoleFeedback='…' PlanFeedback='…'"`, not the raw text. (c) `suggestions` is only the **latest** round's two suggestions, `"## Role Suggestions\n{sr}\n\n## Plan Suggestions\n{sp}"` (`manager.py:45`), not the cumulative strings. `existing_roles=ROLES_LIST=[]` (`role_bank/__init__.py:4`) and `tools=TOOLS` string (`create_roles.py:109`) CONFIRMED. Template also takes `{format_example}` (`create_roles.py:128`) — spec §7 omits it. |
| sections `{"Selected Roles List","Created Roles List","Execution Plan","RoleFeedback","PlanFeedback"}` | CONFIRMED | `create_roles.py:97-103` OUTPUT_MAPPING. Parsed by `OutputParser.parse_blocks` (`common.py:31-49`): split on `"##"`, title = first line with one trailing `:` stripped, `.strip()`; then `parse_code` strips the first ``` fence (`common.py:52-59`, regex ``rf'```{lang}.*?\s+(.*?)```'`` DOTALL). Extra sections (`Thought`, `Question or Task`) are parsed but ignored by the model (`action_output.py:25` `create_model`; the validators at `:27-42` are attached as plain attributes and never run). Missing section → pydantic error → `_repair_with_llm` (`action.py:69-75`) → tenacity retry ×2 (`action.py:53`). |
| `roles = parse_role_blobs(resp["Created Roles List"])` each round | WRONG | No per-round parsing. Roles are parsed **once**, after the loop, in `environment.publish_message` (`environment.py:194-197`) and over the **whole raw content** (`message.content`), not the Created section: `re.findall('{[\s\S]*?}', text)` (`environment.py:62`) + `json.loads(agent.strip())` (`:65`), keep dicts with ≥1 key. So blobs from *Selected Roles List* (and any `{…}` in Thought) are included; nested `{}` truncates a blob (non-greedy), trailing commas (as in the FORMAT_EXAMPLE) raise `JSONDecodeError`, uncaught. |
| `plan = parse_plan(resp["Execution Plan"])` split on `\n\d+\. `, first line, `"[A, B]: text"` | PARTLY WRONG | Also once, at publish (`environment.py:75-84`): `re.findall('## Execution Plan([\s\S]*?)##', str(context))[0]` (needs a following `##`, else `IndexError`), then `re.split("\n\d+\. ", plan_context)[1:]`, `v.split("\n")[0]`, then **`steps.insert(0, '')`** (`:83`) — the leading `''` sentinel is consumed by `Group._think`'s first `pop(0)` (`group.py:42-43`). The `[A, B]` role list is **not** parsed into names; it stays in the step string and is matched by substring later (A.2). |
| `if not roles or not plan: history = resp.raw; continue` | NOT IN CODE | Code has no malformed-round path; a malformed final draft crashes at publish. Keep as DEVIATION. |
| `if 'No Suggestions' not in …` guard (`manager.py:34`) — skips observers after they agreed? | CONFIRMED dead guard | It can never be false inside the loop: the only way both cumulative strings contain `'No Suggestions'` is line `:47-48`, which sets `consensus=True` and ends the loop. So observers run **every** round; ≤9 calls total CONFIRMED. (If it *were* false, `:45` would reference unbound `_suggestions_roles` → `UnboundLocalError`.) |
| roles observer: `history=f"## Role Suggestions\n{sugg_roles}\n\n## Feedback\n{resp['RoleFeedback']}"` | CONFIRMED | `manager.py:36`: cumulative `suggestions_roles` **before** this round's append + this draft's `RoleFeedback`. |
| roles observer inputs `question=task.prompt, selected_roles="", created_roles=roles_json` | WRONG | `CheckRoles.run(response.content, history)` (`manager.py:37`) regex-extracts from the **planner's raw text**: `'## Question or Task:([\s\S]*?)##'`, `'## Created Roles List:([\s\S]*?)##'`, `'## Selected Roles List:([\s\S]*?)##'` all `[0]` (`check_roles.py:95-97`; colon **required**, `IndexError` if missing). So the observer sees the planner's echo of the question, and the raw section text (still fenced), not JSON we built. Template also needs `{existing_roles}` and `{format_example}` (`check_roles.py:99`); observer `TOOLS='None'` (`check_roles.py:86`). |
| plan observer: `history=f"## Plan Suggestions\n{sugg_plan}\n\n## Feedback\n{resp['PlanFeedback']}"` and "original passes sugg_roles — bug" | CONFIRMED bug | `manager.py:41` uses `{suggestions_roles}` (already including this round's role suggestions, `:38`) under the heading "Plan Suggestions". `suggestions_plan` is never shown to anyone except via `:45`. Spec's fix is right; mark DEVIATION. |
| plan observer inputs `context=task.prompt, roles=roles_json, plan=plan_text` | WRONG (same as roles) | `check_plans.py:72-77`: `roles` = raw *Selected* section (if it contains ≥1 `{…}`) + raw *Created* section; `plan` = raw `'## Execution Plan:([\s\S]*?)##'` `[-1]`; `context` = raw `'## Question or Task:([\s\S]*?)##'` `[-1]`. Also needs `{format_example}`, `TOOLS='None'` (`:63`). |
| `["Suggestions"]` section, sentinel `No Suggestions` | CONFIRMED | `check_roles.py:76-78`, `check_plans.py:58-60`; prompt instruction `check_roles.py:49`, `check_plans.py:33`. |
| `sugg_roles += sr; sugg_plan += sp; history = resp.raw` | CONFIRMED except history | `manager.py:38,43` cumulative `+=` (no separator). `history` = `str(instruct_content)` (see above). |
| `if "No Suggestions" in sr and "No Suggestions" in sp: consensus=True; break` | WRONG | `manager.py:47` tests the **cumulative** strings: once either observer has ever said `No Suggestions`, that side counts as agreed forever, even if it complains in a later round. Spec's current-round check is stricter; mark DEVIATION. |
| final draft if no consensus | CONFIRMED | Loop exits at `steps==3`; `manager.py:52-59` publishes the **last planner output** (`response.content` + `instruct_content`, `role="Manager"`, `cause_by=CreateRoles`) whatever the last observers said; the last round's suggestions are never seen by the planner. `environment.publish_message` then parses & builds the Group (`environment.py:194-197`, `:86-90`). |
| "language expert" guaranteed | prompt-only | `create_roles.py:32,34,56,57`; `check_roles.py:39,57,60`; `check_plans.py:32,42`. No code check anywhere. `ensure_summariser` is NOT IN CODE (good DEVIATION). |
| tools validated | prompt-only | `create_roles.py:30,54`; `check_roles.py:31,35,37,48,59`; `check_plans.py:40`. No code filter. At run time **any** name in `role['tools']` dispatches to `SearchAndSummarize` (`custom_action.py:207-211`). Spec's filter is NOT IN CODE (good DEVIATION). |
| `2 ≤ len(roles) ≤ max_agents`, drop steps naming unknown roles | NOT IN CODE | A step naming no role gives `next_state=[]` → `Group._act` loop body never runs → `response` unbound → `UnboundLocalError` at `group.py:104`. |
| "Three LLM calls per round, ≤9 total" | CONFIRMED | Plus repair/retry calls inside `_aask_v1` (up to 2 attempts × (1 + repair)) which the spec's "retry once" also covers. |

**System prompt for all three drafting calls:** `Action._aask_v1` sends `system_msgs=[self.prefix]` (`action.py:60`), prefix = `PREFIX_TEMPLATE` of the Manager: `"You are a Manager, named Ethan, your goal is Efficiently to finish the tasks or solve the problem, and the constraint is . "` (`role.py:17,139-143`, `manager.py:17`). The spec's `PromptRef.system` for the planner is not stated; note it.

### A.2 AutoAgents flat execution (spec §6) vs `group.py`, `custom_action.py`

| Item | Verdict | Code |
|---|---|---|
| Which agents run a step | CONFIRMED (substring, case-sensitive) | `group.py:61-64`: for each action `i`, `name = str(action).replace('_Action','').replace('_',' ')` (class name built at `:32` as `role['name'].replace(' ','_')+'_Action'`, so a role name containing `_` comes back with spaces); `if name in self.next_step.split(':')[0]` — plain `in` on the text **before the first colon** of the step line, case-sensitive; `"Analyst"` matches `"[Data Analyst]: …"`. Order = order of roles in the roster, not order in the bracket. |
| step advance / sentinel | CONFIRMED | `group.py:42-43,53`: `if len(steps) > 1: steps.pop(0); next_step = steps[0]`; else pop and `next_step=''` → `_act` returns an empty `Message` (`:72-73`) that is still published. `environment.run` loops the Group `while len(Group.steps) > 0` (`environment.py:256`). No LLM `_think` (Group overrides it; `NextAction` at `:37` is unused). |
| ≤5 loop | CONFIRMED | `group.py:75` `num_steps = 5`; `:80` `while len(next_state) > sum(consensus) and steps < num_steps`. |
| hint text / when | WRONG (iteration index) | `group.py:82-83`: `if steps > num_steps - 2:` i.e. `steps > 3` → fires once at the **start of iteration index 4 (the 5th, last)**, appended to the **shared** `completed_steps`, before any agent in that iteration is called. Text: `'\n You should synthesize the responses of previous steps and provide the final feedback.'`. Spec fires it at the end of turn 3 (visible in turn 4 — same prompt effect) but only in the non-tool branch (the tool branch `continue`s before it) — fix. |
| consensus per agent | CONFIRMED, with a twist | `group.py:93-96`: `hasattr(response.instruct_content,'Action')` → intermediate (INTERMEDIATE_OUTPUT_MAPPING has `Action`, `custom_action.py:85-89`) → append to `completed_steps`; else (FINAL_OUTPUT_MAPPING, `:91-94`, chosen when `'Final Output' in Action`, `:215`) → `consensus[i]=1`. Twist: agents that already reached consensus are **still re-invoked** in later iterations (`:85` iterates all of `next_state`, no skip); the flag never resets. |
| `previous` | WRONG | `group.py:76`: `CONTENT_TEMPLATE.format(previous=str(self._rc.important_memory), step=next_step)` → `previous` = `str(list_of_Messages)` = `"[Question/Task: <task>, user: <step-1 info>, user: <step-2 info>, …]"` — the task **plus every prior step's published message** (all watched by `Requirement`/`Requirement_Group`, `group.py:27,36`, `memory.py:79-86`). Group messages have default role `'user'` (`group.py:105`, `schema.py:27`). Spec's per-edge `previous=join(msgs)` is a DEVIATION (T7 wants it). |
| `completed_steps` | CONFIRMED (format differs slightly) | Starts `''` per step (`:75`), shared by all agents in the step. Append: `f'>{self._rc.todo} Substep:\n' + Action + '\n>Subresponse:\n' + Response + '\n'` (`:94`) where `str(todo)` = class name (`Data_Analyst_Action`), `Action` = the model's **CurrentStep** (INTERMEDIATE info puts CurrentStep under `## Action`, `custom_action.py:220`), `Response` = `"\n{ActionInput}\n"` / search text / file text (`:213,211,200`). |
| `{context}` of custom_action | WRONG | `custom_action.py:124-128,146`: `context` = text of `## Current Step` = **the step string** (`"[Roles]: STEP TEXT"`), not the original task. The task only reaches the worker inside `previous`. Spec passes `context=task.prompt` — DEVIATION (arguably better; mark it). |
| `{role}` | CONFIRMED | `role=self.role_prompt` (`:148`) = drafted `prompt` field, inlined at the top of the **user** message. System message is the Group's prefix `"You are a Group, named Alex, your goal is Effectively delivering information according to plan., and the constraint is . "` (`group.py:23,33-35` → `role.py:114,139-143`). Spec's `PromptRef(system=r.prompt, user=custom_action)` moves the role prompt to system — DEVIATION. |
| tool list & built-ins | CONFIRMED | `custom_action.py:144`: `tools = list(self.tool) + ['Print','Write File','Final Output']`. Dispatch (`:157-213`): `'Write File' in Action` (substring) → parse `>>>name…>>>END` and save under WORKSPACE_ROOT; `Action in self.tool` (exact membership) → **always** `SearchAndSummarize`; else (`Print`, `Final Output`, unknown) → `response = "\n{ActionInput}\n"`. `Print` has no special code. |
| sections parsed | CONFIRMED | OUTPUT_MAPPING `CurrentStep, Action, ActionInput` (`:79-83`); FORMAT_EXAMPLE also shows `Thought`, `Task` (`:60-77`), ignored. Note FORMAT_EXAMPLE's `[{tool}]` is **not** substituted (inserted as a value of `.format`, `:152`), so the rendered prompt literally says `must be one of [{tool}]`. |
| what is published after a step | CONFIRMED / clarified | `group.py:104-110`: **one** Message whose content is the `info` string of the **last agent's last response** in the loop. If Final Output: `"\n## Step\n{step}\n## Response\n{completed_steps}>>>> Final Output\n\n{ActionInput}\n\n>>>>"` (`custom_action.py:216`) — i.e. the whole scratchpad plus the final; else the intermediate `"\n## Step\n{step}\n## Response\n{response}\n## Action\n{CurrentStep}\n"` (`:220`). If 5 iterations pass without consensus, the last intermediate is published. `cause_by=Requirement_Group` so the next step sees it via `important_memory`. |
| 30 s sleep | CONFIRMED | `group.py:12` `SLEEP_RATE = 30`; `:98` `await asyncio.sleep(SLEEP_RATE)` after **every** agent call. Drop (DEVIATION). |
| final answer | No explicit answer | `Explorer.run` returns `environment.history` (`explorer.py:58`), the concatenation of all messages. The de-facto answer is the content of the last non-empty Group message (last plan step, the language expert if the prompt was obeyed). `environment.py:176-189` writes `result.md` per role from `instruct_content.Response` — for a Final Output message that is `completed_steps + ">>>> Final Output\n…"`, not the bare `ActionInput`. Spec's `ep.answer = exit agent's ActionInput` is a DEVIATION. |
| `Interpreter._invoke_agent`: return on `Final Output` immediately; tool branch `continue` | NOT IN CODE (multi-agent semantics collapsed) | In code the 5-iteration loop is **per step, shared by all agents of the step** (round-robin, shared `completed_steps`, until all have said Final Output). The spec runs each agent alone with its own scratchpad. Acceptable DEVIATION but must be stated; the "join" of a multi-role step is lost. |
| `loop = LoopPolicy(max_iterations=5, until="sentinel:Final Output")` for flat | Mis-mapped | The 5 is AutoAgents' per-step inner cap (`group.py:75`) = spec's `Budget.max_turns`. `max_iterations` (invocations per agent per episode) has no AutoAgents counterpart; a role named in >5 steps would be silently cut. |

### A.3 AgentVerse vertical-solver-first (spec §5.3 / §6 boss_reviewers)

| Item | Verdict | Code |
|---|---|---|
| loop shape | CONFIRMED with count fix | `vertical_solver_first.py:37-72`: (0) if `advice != "No advice yet."` broadcast it as a Message from `"Evaluator"` to all; (1) `agents[0].astep(previous_plan, advice, task_description)` → plan; broadcast plan to **all** agents (solver included); (2) `for i in range(max_inner_turns)` (`:24` default 3; humaneval/gpt-4 uses the default, pythoncalculator sets 2, responsegen 3): all critics in parallel (`asyncio.gather`, `:45-49`); `nonempty_reviews = [r for r in reviews if not r.is_agree and r.content != ""]` (`:60-63`); if none → `break` (`:64-66`); else broadcast the disagreeing reviews to all (`:67`), solver revises (`:68`), broadcast new plan (`:70`). Return `[previous_plan]` (`:71-72`). ⇒ solver invocations = **1 + #rounds with a disagreement ≤ 1 + max_inner_turns = 4**, critics ≤ 3. The **last revision is never reviewed**. Spec T8 "never more than 3×" is WRONG for AgentVerse; either cap solver at 4 or state the deviation. |
| what a critic sees | CONFIRMED (via memory, not placeholders) | `critic.py:65-84`: system = `prepend_prompt_template` with `${preliminary_solution} ${advice} ${task_description} ${role_description} ${agent_name} ${all_roles} ${tool_descriptions}` safe-substituted; then **history = last `max_history` messages of its own memory** (`chat_history.py:69-107`; default `max_history=3` `critic.py:22`, configs set 5/10), every message rendered as `{"role":"assistant","content":"[sender]: content"}`; then user = `append_prompt_template`. Memory contains: Evaluator advice (if any), every plan broadcast, and every **disagreeing** review of every critic (broadcast to all, `:67`). So critics see the previous plan, the other critics' disagreements and the revised plans; they never see `Agree` messages. Note `preliminary_solution` is a `SolverMessage` object after the first step (`:42` rebinds `previous_plan`), harmless because no live template references it. `messages` are `assistant`-role even for others' text (`chat_history.py:102-107`). |
| agreeing critics silent | CONFIRMED | `output_parser.py:548-549`: Agree → `AgentCriticism(True, "")`; `critic.py:103-108` content `""`; not broadcast (`vertical_solver_first.py:62`). Also: a critic whose output fails to parse `max_retry` times yields content `""`, `is_agree=False` (`critic.py:100-108`) → excluded by `content != ""` → **counts as agreement**. |
| what the solver sees on revision | CONFIRMED | `solver.py:38-59`: prepend (`${former_solution} ${task_description} ${advice} ${role_description}` substitutable), history = last `max_history` (default 5, `solver.py:23`) memory messages = its own plans (`"[Planner]: …"`) + broadcast disagreeing reviews + advice, then append. `former_solution` is a Message object on revision; no live template uses it. |
| `Action: Agree/Disagree` parsing (`critic` parser = `CommonParser3`, `output_parser.py:539-561`) | CONFIRMED, details | `text = re.sub(r"\n+","\n", text.strip())`; `checks = text.split("\n")`; `checks[0]` must `startswith("Action:")` else `OutputParserError`; **`checks[0].strip(". ") == "Action: Agree"`** exact (so `Action: Agree.` ok, `Action:Agree` / `action: agree` / a leading `Thought:` line **fail**); `== "Action: Disagree"` → criticism = `re.compile(r"Action Input: ([\S\n ]+)").findall(text)[0].strip()` (everything after the first `Action Input: ` to end of text, newlines included); missing → default `"I think it is not correct. Please think carefully and improve it."`; any other first line → error → retry (`critic.py:86-98`). Spec's `startswith("Action: Disagree")` is looser — align. Other critic parsers in the repo (`mgsm-critic-agree` `[Agree]`/`[Disagree]` tokens, `responsegen-critic-2` `Decision:/Response:`) are **not** the one the spec's prompt targets. |
| memory persistence | CONFIRMED persists | `add_message_to_memory` appends (`chat_history.py:39-41`); reset only in `agent.reset()` (`critic.py:133`, `solver.py:117`), which `BasicEnvironment.reset` (`basic.py:141-144`) does **not** call. Memory persists across inner rounds and across outer turns. |
| how the plan is returned | CONFIRMED | `[previous_plan]` (`vertical_solver_first.py:72`) → `basic.py:66` `"\n".join(p.content)`; `content` = `parsed_response.return_values["output"]` (`solver.py:73-76`) = raw text for `dummy` parser (`output_parser.py:300-303`) or the **last** ```-fenced block for `humaneval-solver` (`:362` `re.findall(r"```.*?\n(.+?)```", text, re.DOTALL)[-1]`); `""` on total parse failure. `tasksolving.py:59-72` returns `previous_plan` as the answer. |
| brainstorming config = source of critic prompt | EXISTS but mismatched | `tasks/tasksolving/brainstorming/config.yaml:44-62` has the `Action: Agree` / `Action: Disagree` + `Action Input:` critic prompt with `${role_description}` (prepend and append) and `${task_description}` (prepend); parser `type: critic` (`:167`). **But** that config's decision maker is `type: brainstorming` with `max_inner_turns: 0` (`:108-110`, `brainstorming.py`): critics run **sequentially before** the solver, the solver is a **summarizer**, and all memories are wiped after each turn. The exact same critic prompt is used with `vertical-solver-first` in `tasks/tasksolving/pythoncalculator/config.yaml:37-64,106-108` (plus one line "Please control output code in 2048 tokens!"). Prefer pythoncalculator as the source, or keep brainstorming and say so. |
| humaneval/gpt-4 solver template | EXISTS, not generic | `humaneval/gpt-4/config.yaml:26-30`: prepend `"Can you complete the following code?\n```python \n${task_description} \n```"`; `:43-44` append `"You are ${role_description}. Provide a correct completion of the code. … Use ```python …"`; parser `humaneval-solver` (`:170`). `${former_solution}` and `${advice}` appear **only in commented-out YAML** (`:32-41`); the spec's placeholder list for `agentverse_solver.txt` is WRONG. A generic solver: `pythoncalculator/config.yaml:28-35` (`${task_description}` only; "Below is the chat history…" / "Now you are going to give a new solution, based upon your former solution and the critics' opinions"). |

### A.4 Prompt files (§7)

| File | Source path | Placeholders actually in the template | Spec says | Verdict |
|---|---|---|---|---|
| `autoagents_create_roles.txt` | `autoagents/actions/create_roles.py:9-59` PROMPT_TEMPLATE, `:61-95` FORMAT_EXAMPLE | `{context} {existing_roles} {history} {tools}`×3 `{format_example} {suggestions}`; literal `{{{{`/`}}}}` (→ `{{ }}` after one `.format`) | `{context} {existing_roles} {tools} {history} {suggestions}` | missing `{format_example}`; note the brace escaping if the file is rendered with `str.format` once (then the example shows `{{ … }}`) — copy verbatim and render once, as the code does |
| `autoagents_check_roles.txt` | `check_roles.py:9-62`, `:64-74` | `{question} {existing_roles} {selected_roles} {created_roles} {history} {tools}`×6 `{format_example}` | (§5.2) question, selected_roles, created_roles, tools, history | missing `{existing_roles}`, `{format_example}`; section `Suggestions` CONFIRMED |
| `autoagents_check_plans.txt` | `check_plans.py:8-44`, `:46-56` | `{context} {roles} {plan} {history} {format_example} {tools}` | context, roles, plan, tools, history | missing `{format_example}` |
| `autoagents_custom_action.txt` | `custom_action.py:18-58`, `:60-77` | `{role} {context}`×2 `{suggestions} {previous} {completed_steps} {tool}`×2 `{format_example}`; FORMAT_EXAMPLE's `[{tool}]` stays literal | `{role} {context} {suggestions} {previous} {completed_steps} {tool}` | missing `{format_example}`; sections Thought/Task/CurrentStep/Action/ActionInput CONFIRMED; built-ins Print/Write File/Final Output CONFIRMED (`:144`) |
| `agentverse_critic.txt` | `brainstorming/config.yaml:44-62` (or `pythoncalculator/config.yaml:37-64`) | prepend: `${role_description} ${task_description}`; append: `${role_description}` | `${role_description} ${task_description}` | CONFIRMED, but it is **two** templates (system prepend + user append) with the plan/reviews delivered as **chat history between them**, not via a placeholder — the spec's `render_prompt(user, previous=join(msgs))` never injects `msgs` (no placeholder) → critic would never see the plan. Add a `${chat_history}` placeholder or send history messages. |
| `agentverse_solver.txt` | `humaneval/gpt-4/config.yaml:26-30,43-44` | prepend: `${task_description}`; append: `${role_description}` | `${task_description} ${former_solution} ${advice} ${role_description}` | WRONG: `${former_solution}`/`${advice}` are commented out; template is code-specific. Use `pythoncalculator/config.yaml:28-35` (prepend `${task_description}`, append none) and add `${chat_history}` as above. |
| `language_expert.txt` | ours | — | — | NOT IN CODE (fine) |

---

## Part B — corrected pseudocode

Faithful lines cite the source; every departure is `# DEVIATION:`.

### B.1 Parsers

```python
import re, json

def parse_sections(text: str) -> dict[str, str]:
    """AutoAgents OutputParser.parse_blocks + parse_code (common.py:31-59, 103-131)."""
    out = {}
    for block in text.split("##"):                       # common.py:33  (also splits on '###')
        if block.strip() == "": continue
        title, body = block.split("\n", 1)               # common.py:43  (ValueError if a block has no newline)
        if title[-1] == ":": title = title[:-1]          # common.py:45-46
        body = body.strip()
        m = re.search(r'```.*?\s+(.*?)```', body, re.DOTALL)   # common.py:53 (lang="")
        if m: body = m.group(1)                          # first fenced block only, language tag dropped
        out[title.strip()] = body
    return out
    # A caller requiring keys K raises on missing (pydantic required fields → _repair_with_llm, action.py:69-75).

def parse_role_blobs(text: str) -> list[dict]:
    """environment._parser_roles (environment.py:60-73). NB: code runs it on the WHOLE planner output."""
    roles = []
    for blob in re.findall(r'{[\s\S]*?}', text):        # environment.py:62 — non-greedy: nested {} truncates
        d = json.loads(blob.strip())                     # environment.py:65 — raises on trailing comma / bad JSON
        if len(d.keys()) > 0: roles.append(d)            # environment.py:66-67
    return roles
    # DEVIATION: we call it on sections["Created Roles List"] only, and wrap json.loads in try/except → skip blob.

def parse_plan(text: str) -> list[str]:
    """environment._parser_plan (environment.py:75-84)."""
    plan_ctx = re.findall(r'## Execution Plan([\s\S]*?)##', text)[0]   # environment.py:77 — needs a following '##'
    steps = [v.split("\n")[0] for v in re.split(r"\n\d+\. ", plan_ctx)[1:]]   # environment.py:78
    steps.insert(0, '')                                  # environment.py:83 — sentinel eaten by Group._think pop(0)
    return steps
    # DEVIATION: we take sections["Execution Plan"] (no [0] lookup), drop the '' sentinel, and additionally split
    # each step into (roles, text) with  m = re.match(r'\s*\[(.*?)\]\s*:\s*(.*)', step);
    # roles = [r.strip() for r in m.group(1).split(',')]  — AutoAgents never does this (see run_flat matching).

def parse_critic(text: str) -> tuple[bool, str]:
    """AgentVerse CommonParser3 / 'critic' (output_parser.py:541-561). Returns (is_agree, criticism)."""
    text = re.sub(r"\n+", "\n", text.strip())            # :544
    first = text.split("\n")[0]                          # :545
    if not first.startswith("Action:"): raise OutputParserError(text)      # :546-547
    if first.strip(". ") == "Action: Agree":   return (True, "")           # :548-549  exact, case-sensitive
    if first.strip(". ") == "Action: Disagree":                            # :550
        m = re.compile(r"Action Input: ([\S\n ]+)").findall(text)          # :551
        crit = m[0].strip() if m else "I think it is not correct. Please think carefully and improve it."  # :552-557
        return (False, crit)
    raise OutputParserError(text)                        # :560-561
    # Caller (critic.py:86-108): retry max_retry times; on final failure content="" and is_agree=False,
    # which vertical_solver_first.py:62 then treats as silence (== agreement).
```

### B.2 `draft_team()` — AutoAgents Manager._act + Environment.publish_message

```python
def draft_team(task, llm, envelope, trace) -> Draft:
    ctx        = f"[Question/Task: {task.prompt}]"        # manager.py:32 str(important_memory); DEVIATION ok: pass task.prompt
    history    = ""                                       # manager.py:26 roles_plan
    sugg_roles = ""; sugg_plan = ""                       # manager.py:26 cumulative
    suggestions = ""                                      # manager.py:27 — what the planner sees (latest round only)
    consensus, rounds = False, 0
    last = None

    while not consensus and rounds < 3:                   # manager.py:27,30  num_steps = 3
        # --- state 0: planner (CreateRoles) ---
        raw = llm.chat(system=MANAGER_PREFIX,             # role.py:17 "You are a Manager, named Ethan, ..."
                       user=render(PROMPT.autoagents_create_roles,
                                   context=ctx, existing_roles="[]", tools=envelope.tool_catalog_string(),
                                   history=history, suggestions=suggestions,
                                   format_example=CREATE_ROLES_FORMAT_EXAMPLE))   # create_roles.py:128
        sec = require(parse_sections(raw), ["Selected Roles List","Created Roles List","Execution Plan",
                                            "RoleFeedback","PlanFeedback"])       # create_roles.py:97-103; on failure
                                                                                  # code: LLM repair + 1 retry (action.py:53-75)
        last = (raw, sec)
        history = pydantic_repr(sec)                      # manager.py:33 str(instruct_content); DEVIATION ok: use raw

        # --- state 1: roles observer (CheckRoles) --- always runs (manager.py:34 guard is dead)
        hist_roles = f"## Role Suggestions\n{sugg_roles}\n\n## Feedback\n{sec['RoleFeedback']}"   # manager.py:36
        q   = re.findall(r'## Question or Task:([\s\S]*?)##', raw)[0]         # check_roles.py:95 (colon required)
        cr  = re.findall(r'## Created Roles List:([\s\S]*?)##', raw)[0]       # :96
        sr_ = re.findall(r'## Selected Roles List:([\s\S]*?)##', raw)[0]      # :97
        # DEVIATION: use q=task.prompt, cr=sec['Created Roles List'], sr_=sec['Selected Roles List'] (no colon dependence)
        sr = require(parse_sections(llm.chat(MANAGER_PREFIX,
                 render(PROMPT.autoagents_check_roles, question=q, existing_roles="[]", selected_roles=sr_,
                        created_roles=cr, history=hist_roles, tools="None",             # check_roles.py:86 TOOLS='None'
                        format_example=CHECK_ROLES_FORMAT_EXAMPLE))), ["Suggestions"])["Suggestions"]
        sugg_roles += sr                                  # manager.py:38 (no separator)

        # --- state 2: plan observer (CheckPlans) ---
        hist_plan = f"## Plan Suggestions\n{sugg_roles}\n\n## Feedback\n{sec['PlanFeedback']}"   # manager.py:41 (BUG)
        hist_plan = f"## Plan Suggestions\n{sugg_plan}\n\n## Feedback\n{sec['PlanFeedback']}"    # DEVIATION: fixed
        roles_txt = sr_ if re.findall(r'{[\s\S]*?}', sr_) else ""             # check_plans.py:72-74
        roles_txt += cr                                                        # :75
        plan_txt  = re.findall(r'## Execution Plan:([\s\S]*?)##', raw)[-1]     # :76 ; DEVIATION: sec['Execution Plan']
        sp = require(parse_sections(llm.chat(MANAGER_PREFIX,
                 render(PROMPT.autoagents_check_plans, context=q, roles=roles_txt, plan=plan_txt,
                        history=hist_plan, tools="None", format_example=CHECK_PLANS_FORMAT_EXAMPLE))),
                     ["Suggestions"])["Suggestions"]
        sugg_plan += sp                                   # manager.py:43

        suggestions = f"## Role Suggestions\n{sr}\n\n## Plan Suggestions\n{sp}"   # manager.py:45 — latest round only
        if 'No Suggestions' in sugg_roles and 'No Suggestions' in sugg_plan:      # manager.py:47 — CUMULATIVE
            consensus = True
        # DEVIATION (stricter): if 'No Suggestions' in sr and 'No Suggestions' in sp: consensus = True
        rounds += 1

    # --- publish (manager.py:52-57 → environment.py:194-197): last draft, consensus or not ---
    raw, sec = last
    roles = parse_role_blobs(raw)                         # environment.py:196 — whole content
    steps = parse_plan(raw)                               # environment.py:195 — with '' sentinel
    # DEVIATION: roles = parse_role_blobs(sec["Created Roles List"]); steps = parse_plan(sec["Execution Plan"]) w/o sentinel

    # DEVIATION: deterministic post-checks (none exist in AutoAgents)
    for r in roles: r["tools"] = [t for t in r.get("tools", []) if t in envelope.allowed_tool_names]
    if not (2 <= len(roles) <= envelope.max_agents): raise DraftError
    if not any(len(r["tools"]) == 0 for r in roles): roles.append(LANGUAGE_EXPERT)
    names = {r["name"] for r in roles}
    plan = []
    for i, s in enumerate(steps):
        head = s.split(':')[0]                            # group.py:63
        who  = [n for n in names if n.replace('_',' ') in head]   # group.py:62-63 substring, case-sensitive, roster order
        if who: plan.append(PlanStep(index=i, agent_names=who, text=s))
    if not plan: raise DraftError
    return Draft(created_roles=[DraftedRole(**r) for r in roles], plan=plan,
                 rounds_used=rounds, consensus=consensus, role_feedback=sugg_roles, plan_feedback=sugg_plan)
```

### B.3 `run_flat()` — AutoAgents Group._think/_act + CustomAction.run

```python
def run_flat(team, task, llm, tools, trace) -> Answer:
    previous_msgs = [f"Question/Task: {task.prompt}"]     # important_memory: task (cause_by=Requirement) + every step output
    published = None
    for step in team.plan:                                # environment.run: while len(Group.steps) > 0 (environment.py:256)
        agents = step.agents                              # group.py:60-64 (see draft_team matching)
        # if agents == []: AutoAgents raises UnboundLocalError at group.py:104 — DEVIATION: skip step / fail typed
        previous = "[" + ", ".join(previous_msgs) + "]"   # group.py:76 str(list[Message]) → "[role: content, ...]"
        # DEVIATION (spec T7): previous = only the messages that arrived on incoming edges, not the full history
        completed_steps = ""                              # group.py:75 — shared by all agents of the step
        consensus = [0] * len(agents)                     # group.py:79
        it = 0
        response = None
        while len(agents) > sum(consensus) and it < 5:    # group.py:75,80  num_steps = 5
            if it > 5 - 2:                                # group.py:82 → fires only when it == 4 (5th iteration)
                completed_steps += '\n You should synthesize the responses of previous steps and provide the final feedback.'  # :83
            for i, agent in enumerate(agents):            # group.py:85 — every agent, even those already at consensus
                user = render(PROMPT.autoagents_custom_action,
                              role=agent.prompt_text,                 # custom_action.py:148 role_prompt (in USER msg)
                              context=step.text,                      # :146 — the STEP string, not the task
                              # DEVIATION: context=task.prompt
                              suggestions=agent.suggestions,          # :150
                              previous=previous,                      # :147
                              completed_steps=completed_steps,        # :151
                              tool=str(list(agent.tools) + ['Print', 'Write File', 'Final Output']),   # :144,149
                              # DEVIATION: drop 'Write File'
                              format_example=CUSTOM_ACTION_FORMAT_EXAMPLE)   # :152 — its "[{tool}]" stays literal
                raw = llm.chat(system=GROUP_PREFIX, user=user)        # group.py:33-35 → role.py:114,17: "You are a Group, named Alex, ..."
                                                                       # DEVIATION: system = agent.prompt.system (role prompt)
                sec = require(parse_sections(raw), ["CurrentStep", "Action", "ActionInput"])   # custom_action.py:79-83,155
                act, inp = sec["Action"], sec["ActionInput"]
                if 'Write File' in act:                               # :157 substring
                    resp = f"\n{inp}\n"                               # (+ save file, :196-206)
                elif act in agent.tools:                              # :207 exact membership → ALWAYS SearchAndSummarize (:208-211)
                    resp = tools.execute(act, inp)                    # DEVIATION: dispatch by name through ToolRegistry
                else:                                                 # 'Print', 'Final Output', anything else
                    resp = f"\n{inp}\n"                               # :213
                if 'Final Output' in act:                             # :215 substring
                    info = f"\n## Step\n{step.text}\n## Response\n{completed_steps}>>>> Final Output\n{resp}\n>>>>"   # :216
                    response = ("final", info, inp)
                    consensus[i] = 1                                  # group.py:93-96: FINAL mapping has no 'Action'
                else:
                    info = f"\n## Step\n{step.text}\n## Response\n{resp}\n## Action\n{sec['CurrentStep']}\n"   # :220
                    response = ("intermediate", info, inp)
                    completed_steps += f">{agent.class_name}_Action Substep:\n{sec['CurrentStep']}\n>Subresponse:\n{resp}\n"  # group.py:94
                # await asyncio.sleep(30)                             # group.py:98 — DEVIATION: dropped
            it += 1
        kind, info, inp = response                        # group.py:104-110: the LAST agent's LAST response, consensus or not
        published = info
        previous_msgs.append(f"user: {info}")             # Message role defaults to 'user' (group.py:105, schema.py:27)
    # AutoAgents has no final-answer object: Explorer.run returns environment.history (explorer.py:58).
    return Answer(text=published)                         # DEVIATION: answer = last step's ActionInput (inp) if kind == "final",
                                                          # else the last intermediate info, with error="max_turns"
```

### B.4 `run_boss_reviewers()` — AgentVerse VerticalSolverFirstDecisionMaker.astep

```python
def run_boss_reviewers(team, task, llm, trace, max_inner_turns=3) -> Answer:
    solver, critics = team.solver, team.critics           # vertical_solver_first.py:35-36 agents[0], agents[1:]
    memory = {a.id: [] for a in [solver, *critics]}       # ChatHistoryMemory per agent; persists for the whole run
    advice = "No advice yet."                             # tasksolving.py:63 — single outer turn ⇒ never anything else
    def broadcast(msgs):                                  # vertical_solver_first.py:74-76
        for a in [solver, *critics]: memory[a.id] += msgs

    def call(agent, prepend_kw, max_history):             # solver.py:38-59 / critic.py:65-91 + openai.py:436-446
        system = Template(agent.prepend).safe_substitute(**prepend_kw)
        hist   = [{"role": "assistant", "content": f"[{m.sender}]: {m.content}"}       # chat_history.py:102-107
                  for m in memory[agent.id][-max_history:]]                            # start_index = -max_history
        user   = Template(agent.append).safe_substitute(**prepend_kw)
        return llm.chat_messages([{"role":"system","content":system}, *hist, {"role":"user","content":user}])
        # DEVIATION (spec has single system+user): render hist into a ${chat_history} placeholder of the user prompt

    def solve():                                          # solver.py:30-80
        for _ in range(solver.max_retry):                 # config max_retry (1000 in configs); DEVIATION: 1 retry
            try:
                raw = call(solver, dict(task_description=task.prompt, role_description=solver.description,
                                        former_solution=plan_text, advice=advice), solver.max_history)   # default 5
                text = raw                                # parser 'dummy' (output_parser.py:300-303); humaneval-solver takes last ``` block (:362)
                break
            except Exception: continue
        else: text = ""                                   # solver.py:70-76
        return Message(sender=solver.name, content=text)

    def review(c):                                        # critic.py:55-109
        for _ in range(c.max_retry):
            try:
                raw = call(c, dict(task_description=task.prompt, role_description=c.description,
                                   advice=advice, preliminary_solution=plan_text), c.max_history)   # default 3
                agree, crit = parse_critic(raw); break
            except OutputParserError: continue
        else: agree, crit = False, ""                     # critic.py:100-108 → treated as silent below
        return CriticMessage(sender=c.name, content=crit, is_agree=agree)

    plan_text = "No solution yet."                        # basic.py:46 / tasksolving.py:64
    plan = solve()                                        # vertical_solver_first.py:41
    broadcast([plan]); plan_text = plan.content           # :42
    for i in range(max_inner_turns):                      # :44  (class default 3, :24)
        reviews = parallel(review(c) for c in critics)    # :45-49 asyncio.gather
        nonempty = [r for r in reviews if not r.is_agree and r.content != ""]   # :60-63
        if not nonempty: break                            # :64-66 "Consensus Reached!"
        broadcast(nonempty)                               # :67 — only disagreements, to everyone (solver + all critics)
        plan = solve()                                    # :68 — up to max_inner_turns revisions ⇒ solver calls ≤ 1 + 3 = 4
        broadcast([plan]); plan_text = plan.content       # :70
    # NB: the last revision (if made in round max_inner_turns-1) is never reviewed.
    return Answer(text=plan.content)                      # :71-72 → basic.py:66 → tasksolving.py:72
```

---

## Part C — corrections the spec needs

1. **§5.2 planner inputs.** `suggestions` passed to the planner is only the latest round's pair (`manager.py:45`), not the cumulative strings; `history` is `str(instruct_content)` (`:33`), not the raw text; `context` is `"[Question/Task: …]"` (`:32`). Add `{format_example}` to the placeholder list. State which of these are kept and which are deviations.
2. **§5.2 consensus test.** Code tests the cumulative strings (`manager.py:47`); the spec tests the current round. Keep the stricter rule but mark it `# DEVIATION`.
3. **§5.2 observers always run.** Drop any implication that observers are skipped; the `manager.py:34` guard is dead. Observer `tools` string is `'None'` in AutoAgents (`check_roles.py:86`, `check_plans.py:63`) while the planner gets the real catalog — decide (probably pass the catalog to both; mark DEVIATION).
4. **§5.2 observer inputs.** Observers receive regex-extracted raw sections that require a trailing colon in the heading (`check_roles.py:95-97`, `check_plans.py:72-77`), including the planner's echoed question. Spec should pass the parsed sections and `task.prompt` explicitly (DEVIATION), and list the missing placeholders `{existing_roles}` and `{format_example}`.
5. **§5.2 parsing happens once, on the whole output.** `_parser_roles` scans every `{…}` in the full planner text (`environment.py:62`) and `_parser_plan` returns a leading `''` sentinel (`:83`). The per-round `if not roles or not plan` path, the tool filter, the 2..5 size check, `ensure_summariser`, and step-role validation are all ours — label them. Note that `json.loads` failures are uncaught in AutoAgents.
6. **§5.2 / §6 role names in steps are matched by substring, case-sensitive, on the text before the first colon, in roster order (`group.py:61-64`).** Spec's `parse_plan` must either implement exactly that or explicitly define the bracket parser as a DEVIATION (recommended: bracket parser + exact name match).
7. **§6 `{context}` for workers is the current step string, not the task (`custom_action.py:124-128,146`).** `{role}` is in the *user* message; the system message is the Group prefix (`group.py:33-35`, `role.py:17`). Either follow or mark both as DEVIATION (`PromptRef(system=r.prompt)` is a deviation).
8. **§6 `previous` is the full history** (`str(important_memory)`: task + every earlier step's published message, `group.py:76`), not the previous edge's message. T7's per-edge context is a deliberate DEVIATION — say so.
9. **§6 hint fires at iteration index 4 (5th), once per step, before the agents run (`group.py:82-83`).** Spec's `if turn == 3` sits after the tool `continue` and so is skipped on tool turns; move it to the top of the loop as `if turn > 3`.
10. **§6 multi-agent steps.** AutoAgents runs all agents of a step round-robin with a shared `completed_steps`, re-invoking agents that already said Final Output until everyone has (`group.py:80-100`); the published message is the last agent's last response, even if intermediate (`:104-110`). Spec collapses this to sequential single-agent invocations — mark as DEVIATION and define what is published when `max_turns` is exhausted (AutoAgents: the last intermediate `info`).
11. **§6 tool dispatch.** `Action in self.tool` is exact membership but always calls SearchAndSummarize (`custom_action.py:207-211`); `'Write File'` and `'Final Output'` are substring checks (`:157,215`); `Print` is a no-op echo. Spec's `tools.execute(sec["Action"], …)` is the intended replacement — mark DEVIATION; decide whether `Final Output` detection is exact or substring.
12. **§6 Final Output content.** AutoAgents publishes `completed_steps + ">>>> Final Output\n…"` (`custom_action.py:216`) and has no answer object (`explorer.py:58`). Spec's `answer = ActionInput` is a DEVIATION.
13. **§5.3 flat `LoopPolicy(max_iterations=5, …)`** conflates AutoAgents' per-step inner cap (`group.py:75`, = `Budget.max_turns`) with per-episode invocations. Set flat `max_iterations` to the number of plan steps (or unbounded) and keep 5 only in `Budget.max_turns`.
14. **§6 boss_reviewers solver cap.** AgentVerse invokes the solver up to `1 + max_inner_turns = 4` times (`vertical_solver_first.py:41,68`) and never reviews the last revision. T8's "never more than 3×" and `LoopPolicy(max_iterations=3)` must change to 4 for the solver (critics 3), or be labelled a DEVIATION.
15. **§6 boss_reviewers join bug.** With `join="all"` and conditional `revise` edges, the solver waits for *every* critic's edge, but agreeing critics send nothing → solver is never re-invoked when only some critics disagree. Use `join="any"` for the solver (or mark filtered edges as arrived). Also define `all_agree` for critics not yet invoked in the round and for parse failures (AgentVerse: an unparseable critic is silent = agree, `vertical_solver_first.py:62`, `critic.py:100-108`).
16. **§6 `critic_disagrees` predicate.** AgentVerse: first non-empty line after `\n+`→`\n` collapse, `strip(". ") == "Action: Disagree"` exact; `Action Input: ` regex `([\S\n ]+)` to end of text; default criticism text if missing (`output_parser.py:544-557`). Replace `startswith` with this.
17. **§7 AgentVerse prompts are two templates (system prepend + user append) with the plan and disagreements delivered as chat-history messages between them** (`openai.py:436-446`, `chat_history.py:69-107`, last `max_history` messages, all rendered as `assistant` `"[sender]: content"`). The spec's `format="system+user"` with `previous=join(msgs)` never injects `msgs` because neither template has a placeholder. Add `${chat_history}` to the copied user template (DEVIATION) or make the interpreter emit real history messages.
18. **§7 `agentverse_solver.txt`.** `${former_solution}` and `${advice}` exist only in commented YAML in `humaneval/gpt-4/config.yaml:32-41`; the live template is code-specific (`:26-30,43-44`, parser `humaneval-solver`). Use `pythoncalculator/config.yaml:28-35` (also the config that actually pairs `vertical-solver-first` with the `critic` parser and the `Action: Agree/Disagree` prompt, `:37-64,106-108`), and fix T11's "verbatim" source accordingly.
19. **§7 `agentverse_critic.txt` provenance.** `brainstorming/config.yaml` uses decision maker `brainstorming` with `max_inner_turns: 0` (`:3,108-110`; `brainstorming.py`), not vertical-solver-first. The prompt text is fine; cite `pythoncalculator/config.yaml:37-64` or say the loop and the prompt come from different configs.
20. **§7 AutoAgents prompt files.** Add `{format_example}` to all four; note the `{{{{ … }}}}` escaping in `create_roles.py:37-43` and `check_roles.py:41-47` (verbatim copy + a single `str.format`-style render reproduces the code; a `${}`-style renderer would leave four braces). T11 must compare after the same single render, or store PROMPT_TEMPLATE and FORMAT_EXAMPLE as separate files.
21. **§8 fixtures / T4.** "observers complain twice, then No Suggestions → rounds_used = 3" is consistent only with the spec's current-round rule; under AutoAgents' cumulative rule a single early `No Suggestions` from one observer sticks. State which rule the fixture encodes.
22. **§5.2 system prompt for drafting calls.** AutoAgents sends the Manager prefix as the system message (`action.py:60`, `role.py:17`, `manager.py:17`). Spec should name the planner/observer `PromptRef.system` (verbatim prefix or `""`).
23. **§1 "No web search — AutoAgents' only real tool is SerpAPI".** Correct, and stronger: every drafted tool name routes to SerpAPI at run time (`custom_action.py:207-211`), so `tools` in a drafted role has no per-tool semantics in the original; the registry dispatch is new behaviour.
