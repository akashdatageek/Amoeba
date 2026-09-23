# Box 2: why the drafts are shallow, and the prompt upgrade (proposed D24)

This is based on `2026-09-23_complex_transcript.md` (task `db-choice`, gemini-3.1-flash-lite, 3 attempts × 3 rounds)
and the prompts that are actually sent at commit `1d913f5` (the `_d19` versions plus `MANAGER_PREFIX`).

---

## 1. What the transcript shows

| # | Observation | Evidence |
|---|---|---|
| 1 | **No capability requests in 27 Planner replies**, even though the task plainly needs a web search tool ("gather *current* benchmarks and pricing") and a place to run databases ("*prototype and test* a schema in both databases"). | Every `## Capability Requests` is `None`. The Plan Observer even writes "the existing `calc` and `echo` tools are sufficient". |
| 2 | **Requirements are quietly weakened to fit the tools.** "Prototype and test" becomes "dry-run latency calculations". "Gather benchmark results" becomes "Research industry benchmarks" with no tool that can research anything. In attempts 1–2, no one is assigned the benchmark research at all. | Attempt 3, step 2. Attempts 1–2, steps 1–3. |
| 3 | **`echo` is handed out as a filler tool**, including to the Language Expert, which the prompt says must have none. | All three attempts. |
| 4 | **Roles are thin**: a one-line description and a one-sentence "prompt". A role has no inputs, outputs, skills, method, finish criteria or constraints. | For example, Cloud Financial Analyst: `"Calculate monthly costs for 10TB…"`. |
| 5 | **Plans are one line per specialist**, 4–5 steps, run in order. There are no sub-tasks, no parallel work, no review or check step (until an Observer asks for one), and no decision points. | Every final plan. |
| 6 | **The writer is given the real content.** The "Language Expert" is asked to *create* the 90-day migration plan and the risk table, which is specialist work. | Final step in all attempts. |
| 7 | **The numbers are never worked out up front.** Attempt 2 writes "15TB" when 50 × 200 GB = 10 TB, and nothing catches it. | Attempt 2, final plan, steps 1–2. |
| 8 | **Consensus is never reached (0 of 3), and the check itself is broken.** In attempt 1, round 2, the Agent Observer lists 4 suggestions and then writes "No Suggestions." The substring check (`draft.py:146`) counts that as approval. | Attempt 1, round 2. |
| 9 | **The Observers only patch.** Each round adds one fix (a link between steps, a review step, a note on tenant isolation). Nobody steps back and asks whether this is how an experienced lead would run the project. | All rounds. |
| 10 | **The context the task gives is ignored until late.** "12-person startup" (limited people, which drives operating burden) only appears in attempt 3, round 3, through an Observer. | Attempt 3. |

## 2. Why: what in the prompts causes each problem

| Problem | Where it comes from in the prompts that are sent |
|---|---|
| Plans bent to fit our tools (1, 2, 3) | Planner: "tools (**prefer existing tools** from {tools}…)" and "**Prefer existing tools** {tools}". Both Observers repeat "Prefer existing tools". The tool list is the only concrete capability the prompt mentions, so the model plans around it. Nothing says "plan the ideal first, then match it to what exists". |
| Thin roles (4) | The example role blob has only `name, description, tools, suggestions, prompt`, with placeholders like "ROLE PROMPT". The model copies the shape it's shown. And even if it wrote more, `DraftedRole` is `extra="ignore"`, so any extra field would be thrown away. |
| Shallow plans (5) | "Provide a **concise** execution plan". The format example shows `1. [ROLE 1, ROLE2]: STEP 1`, one line each. Also, `parse_plan` keeps only the first line of each step (`split("\n")[0]`), so any detail on later lines is lost. |
| No planning expertise (9, 10) | The system message is `MANAGER_PREFIX`: "You are a Manager, named Ethan … the constraint is ." (the constraint is empty). The Planner prompt opens with "manager and **expert prompt engineer**". It's framed as writing prompts, not as running a project. There are no steps for writing down requirements, assumptions, risks or checks. |
| No "skills" (4) | The word only appears in the Capability Request line. There's no field for what know-how each role must bring (for example "cost modelling", "GDPR Article 44 transfer analysis"). |
| Writer doing specialist work (6) | "Always add one language expert role (no tools) to summarize" plus "End with the language expert synthesis step". Nothing says the specialists must produce the content and the writer only puts it together. |
| Arithmetic not checked (7) | No step asks for the numbers the task gives and what follows from them. |
| Broken consensus (8) | The Observers' format ends in free-text `## Suggestions`, and code looks for the substring "No Suggestions". |
| Observers only patch (9) | "Use History … do not repeat suggestions" plus a free-form list of suggestions. There's no checklist of what a good plan needs. |

Two code limits also block depth, whatever the prompts say:
- `max_tokens = 2048` (`llm/client.py:42`). The current Planner reply is already long. A detailed draft would be cut off, and a cut-off draft fails to parse.
- `DraftedRole(extra="ignore")` and `parse_plan` (first line only) throw away the new detail.

---

## 3. Proposed prompts (ours, deviation D24)

Keep the verbatim AutoAgents prompts and the `_d19` versions as they are. Add new prompt files, marked "ours",
selected with `--draft-prompts d24`, so that D19 and D24 can be compared on the same tasks. **Write them with
`${placeholder}` syntax.** `render()` then uses `string.Template`, so the JSON examples below need no doubled braces.

### 3.1 Planner system message (replaces `MANAGER_PREFIX` for the Planner only)

```
You are a principal engineer and delivery lead with 15+ years of experience running cross-functional
projects. You plan work the way an experienced lead would before staffing it: you pin down the real
objective and every deliverable, work out the numbers, surface assumptions and risks, decide who is
needed and what each person must know and produce, and build in checks. You plan for what the task
actually requires, not for whatever tools happen to be installed.
```

### 3.2 Planner prompt (`d24_create_team.txt`)

```
# Task
${context}

# Existing expert roles (reuse if they fit)
${existing_roles}

# Installed tools (for mapping only — do NOT let this list limit the plan)
${tools}

# History (your previous draft)
${history}

# Reviewer suggestions (latest round)
${suggestions}

# How to plan
Work in this order and write each section.

1. Requirements. List every deliverable and requirement stated or clearly implied by the task, one per
   line with an id (R1, R2, ...). Keep the task's own verbs: "gather current", "prototype and test",
   "estimate", "deliver". Never weaken a requirement (e.g. "test" must stay "test", not "estimate").
2. Givens and derived numbers. List the numbers in the task and anything that follows from them
   (show the arithmetic). List assumptions you must make, each marked as an assumption.
3. Ideal capabilities. Before choosing roles, decide what abilities the work needs, as if any reasonable
   tool or skill were available. A TOOL is something that acts or fetches (web search, code execution,
   a database sandbox, a file reader). A SKILL is know-how or a method (cost modelling, schema design,
   GDPR transfer analysis, risk assessment).
4. Roles. Create the smallest team of well-defined specialists (at most ${max_agents} including the
   final writer) that covers every requirement. A role is well defined only if it has ALL of these fields:
   {
     "name": "Cloud Cost Analyst",
     "seniority": "senior",
     "description": "who they are and why they are on this team (2-3 sentences)",
     "goal": "the single outcome this role is accountable for",
     "responsibilities": ["...", "..."],
     "skills": ["managed-database pricing models", "TCO modelling", "..."],
     "tools": ["the tools this role ideally needs, installed or not"],
     "inputs": ["what it receives and from which step"],
     "outputs": [{"artifact": "cost table", "format": "markdown table: provider x db x monthly USD"}],
     "success_criteria": ["how we know the output is good enough"],
     "constraints": ["limits from the task, e.g. 12-person team, EU residency"],
     "covers": ["R2", "R3"],
     "is_summariser": false,
     "prompt": "the full working prompt for this specialist: persona, method step by step, what to
                check, and the exact output format. Write it as a senior practitioner would brief a peer."
   }
   Do not give a role a tool only to fill the field; an empty list is fine. Specialists produce the
   content (analysis, tables, plans); exactly one role has "is_summariser": true and only assembles and
   edits their outputs into the final deliverable — it creates no new analysis and has no tools.
5. Capability requests. For every tool or skill in step 3 that is not installed, add one request.
   Requesting is expected and costs nothing now; hiding a need is a planning error.
6. Execution plan. Numbered steps. Each step's FIRST line must be "N. [Role A, Role B]: short title".
   Under it, indented lines:
     covers: R ids
     depends_on: step numbers (or none) — steps with no dependency between them may run in parallel
     do: what exactly happens, as sub-steps
     output: artifact + format
     done_when: the check that ends the step
   Include at least one verification step where a different role checks numbers, sources or the
   prototype results before the final step. The final step is the summariser assembling the deliverable.
7. Risks and decision points. The main risks to the plan and where a decision must be made
   (for example "if residency rules out region X, re-run step 3").

# Output format (write every section, in this order, each starting with '## ')
${format_example}

# Rules
- Every requirement id must appear in at least one step's "covers" and one role's "covers".
- Do not ask the user questions; state assumptions instead.
- If a reviewer suggestion is wrong, say why under RoleFeedback/PlanFeedback instead of applying it.
```

### 3.3 Planner format (`d24_create_team_format.txt`)

~~~
## Thought
your reasoning in 3-6 sentences

## Requirements:
R1: ...
R2: ...

## Givens and Assumptions:
- given: ...
- derived: ... (show arithmetic)
- assumption: ...

## Selected Roles List:
```
None, or existing role JSON blobs
```

## Created Roles List:
```
ROLE JSON BLOB 1,
ROLE JSON BLOB 2
```

## Execution Plan:
1. [Role A]: title
   covers: R1, R2
   depends_on: none
   do: ...
   output: ...
   done_when: ...
2. [Role B, Role C]: title
   ...

## Capability Requests:
```
REQUEST JSON BLOB 1   (or None only if every ability in step 3 is installed)
```

## Risks and Decisions:
- ...

## RoleFeedback
...

## PlanFeedback
...
~~~

### 3.4 Agent Observer (its own system message, `d24_review_team.txt`)

System: `You are a staffing reviewer who has built and run many expert teams. You judge whether each role is
well defined and whether together they can deliver every requirement. You are independent of the planner.`

```
# Task
${question}

# Planner's requirements, givens and roles
${requirements}
${created_roles}
${selected_roles}

# Capability requests
${capability_requests}

# Installed tools (for reference only)
${tools}

# History
${history}

# Check each point and report only real problems
1. Coverage: does every requirement id have a role that covers it? List uncovered ids.
2. Definition: does every role have goal, skills, inputs, outputs with format, success_criteria and a
   full working prompt a specialist could act on? Name roles that are thin.
3. Skills: are the skills specific and sufficient for the requirements they cover?
4. Capabilities: does any requirement need an ability no installed tool provides (fetching current data,
   running code, testing in a real system)? If it is not requested, tell the planner to ADD a
   capability request. Never say installed tools are "sufficient" for a requirement they cannot perform,
   and never accept a requirement that was weakened to fit the tools.
5. Summariser: exactly one, no tools, and it creates no new analysis.
6. Size: no duplicate roles, at most ${max_agents}, none without a covered requirement.

# Output format
## Thought
...
## Suggestions
1. ... (or None)
## Verdict
APPROVE or REVISE
```

### 3.5 Plan Observer (its own system message, `d24_review_plan.txt`)

System: `You are a senior delivery reviewer. You judge whether this plan is how an experienced lead would run
the project: complete, ordered correctly, checkable and realistic.`

```
# Task
${context}

# Requirements, givens and assumptions
${requirements}

# Roles
${roles}

# Execution plan
${plan}

# Risks and decisions
${risks}

# Capability requests
${capability_requests}

# History
${history}

# Check each point and report only real problems
1. Coverage: every requirement id appears in a step's "covers"; no requirement weakened (compare verbs).
2. Numbers: the derived figures are correct (recompute them) and used by the steps that need them.
3. Dependencies: depends_on is correct; independent steps are marked parallel; no step uses an input
   that no earlier step produces.
4. Depth: every step has do / output / done_when specific enough to execute and check.
5. Verification: at least one step where a different role checks numbers, sources or test results.
6. Context: constraints in the task (team size, budget, region, deadline) shape the plan.
7. Risks and decision points are real and linked to steps.
8. Capabilities: each step can actually be done with installed tools or a requested capability.

# Output format
## Thought
...
## Suggestions
1. ... (or None)
## Verdict
APPROVE or REVISE
```

---

## 4. Code changes needed so the detail isn't lost

1. **Schema.** Add the new fields to `DraftedRole` (`seniority, goal, responsibilities, skills, inputs, outputs,
   success_criteria, constraints, covers`) and to `DraftPlanStep` (`covers, depends_on, do, output, done_when`).
   Add `Draft.requirements, givens, risks`. Keep `extra="ignore"` for anything else.
2. **Parsers.** Add a `parse_plan_d24` that keeps the indented lines under each step. Its first line stays
   `N. [roles]: title`, so name matching doesn't change. Use `parse_json_objects` (brace-balanced) for role blobs.
3. **Consensus.** For D24 prompts, consensus = both replies have `## Verdict` exactly `APPROVE`. Record the
   verdict and the number of suggestions separately. Also fix the substring bug for D19: an Observer reply that has
   any numbered suggestion is not "No Suggestions".
4. **Deterministic checks after drafting** (the "code disposes" part). Write them to `result.json` and the trace:
   - every requirement is covered by at least one step and one role, and the uncovered ones are listed
   - every `depends_on` points to an earlier step, and there are no cycles
   - every role has non-empty `goal, skills, outputs, success_criteria, prompt`
   - exactly one summariser, with no tools, and it owns only the last step
   - no tool assigned that isn't registered or requested
   - the plan has at least one verification step (a step whose roles differ from the roles of the steps it depends on)
   Failures are recorded (`draft_quality` block) and **don't reject the draft** at first. The first job is to measure.
5. **Box 3 gets the detail.** `with_unavailable()` and the worker prompt should include the role's `goal`, `skills`,
   `outputs` (format), `success_criteria` and the step's `do / done_when`. Otherwise the depth never reaches the helpers.
6. **Token limit.** Allow a per-call `max_tokens`, with 8192 for the Planner and 2048 for the Observers. Raise a
   trace flag when `finish_reason == "length"`.
7. **Separate system messages.** Planner and Observers each get the system message above instead of the shared
   "Manager Ethan" one.

## 5. How to test it

- Run `eval_draft` on the complex tasks (db-choice and the others) with `--draft-prompts d19` and `d24`, 3 repeats
  each, first on gemini-3.1-flash-lite, then on gemini-3.5-flash.
- Compare: requirements covered, % of roles fully defined, capability requests per task (expect ≥ 2 for db-choice:
  web search, database sandbox or code execution), verification step present, derived numbers correct, consensus
  rate, rounds, tokens.
- Read one D24 transcript by eye before trusting the numbers.
- Record it in `docs/real_runs/<date>_d19_vs_d24.md`. The comparison is itself a result worth reporting: how much
  of a drafting failure comes from the AutoAgents prompts rather than from the model.
