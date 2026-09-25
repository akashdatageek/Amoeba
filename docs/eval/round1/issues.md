# Observer round 1 — issues (baseline, no pool)

Severity: **high** = wrong or dishonest answer · **medium** = wasted cost or weaker answer · **low** = cosmetic.
Every root cause is a **hypothesis** unless it says 'confirmed'. No fixes are proposed beyond one line of direction.
Evidence paths are inside this PR (`eval/round1/runs/<task>__<run_id>/`).

Ranked by impact (details below): I2, I9, I8, I10, I3, then I12, I4, I13, I15, I11, I14.

## Box 1

### I1 — The task intake check reads few deliverables and cuts some badly (low)

- **Tasks:** r1-fx-email, r1-route, r1-full-chain, r1-deck
- **Evidence:**
  - `eval/round1/runs/r1-fx-email__544fb5fa-13e0-401f-873c-4d1a1f62b8bd/plan.json → quality.checks.task_coverage.phrases` — ["test @example"]
  - `eval/round1/runs/r1-route__54ab8b83-35c2-4acf-80da-dd48c0606ae9/plan.json → quality.checks.task_coverage.phrases` — "estimate the fuel cost at 6" (cut at the decimal point of 6.5)
  - `eval/round1/runs/r1-deck__fa0b5ab9-477d-4e11-8c4f-5aa174472975/plan.json → quality.checks.task_coverage.phrases` — ["delivered"]
- **Likely root cause (hypothesis):** amoeba/task/quality.py DELIVERABLE_VERBS / deliverable_phrases: only 8 verbs (run, convert, email, make, save, write, list, read are not among them), and a phrase ends at any '.' — inside an email address or a decimal too. All 10 runs pass the check, so it says nothing about these tasks.
- **What would confirm it:** Call task_coverage on the ten prompts: 'run it', 'email the result', 'save it as a PNG' produce no phrase.
- **Possible direction:** Widen the verb list and end phrases at sentence punctuation only.

## Box 2

### I2 — Box 2 is never told web_search / fetch_url exist, and Box 3 grants them only to an exact alias (medium)

- **Tasks:** r1-weather, r1-pdf-read, r1-fx-email, r1-repo, r1-full-chain
- **Evidence:**
  - `eval/round1/runs/r1-weather__aea4d8ec-df0c-4a9f-b902-d47177f826d3/trace.jsonl, first planner chat, gen_ai.input.messages` — "# Installed tools … tool: calc … tool: echo" — no web_search, no fetch_url
  - `eval/round1/runs/r1-weather__aea4d8ec-df0c-4a9f-b902-d47177f826d3/capability_requests.json` — weather_search (tool), canonical weather_search, mapped false
  - `eval/round1/runs/r1-route__54ab8b83-35c2-4acf-80da-dd48c0606ae9/trace.jsonl` — the only capability_mapped event of the round (request named web_search)
  - `eval/round1/runs/r1-fx-email__544fb5fa-13e0-401f-873c-4d1a1f62b8bd/artifacts/step_1.md` — BLOCKED currency_api — no rate, although web_search was registered
  - `eval/round1/runs/r1-full-chain__a3ddb368-882b-4d8d-bea6-513cef4c5845/capability_requests.json` — github_api_tool … no web_search request; nothing was found
- **Likely root cause (hypothesis):** Hypothesis: scripts/run_task.py:378 builds the Envelope that Box 2 sees from default_registry() (echo, calc) — D32 keeps the web tools out of Box 2 on purpose; amoeba/interp/plan_runner.py:355 grant_web_tools hands web_search/fetch_url only to a role whose request normalises to web_search via aliases.yaml. Any other name for a data source (weather_search, currency_api, pdf_reader, github_*) leaves the registered web tools unused.
- **What would confirm it:** Replay r1-weather with an alias weather_search → web_search (or with the web tools in the Envelope) and see whether step 1 searches and cites.
- **Possible direction:** Let Box 2 see the tools Box 3 will have, and grant by what a request needs, not by its exact name.

### I3 — No capability is ever requested as a skill (0 of 23 requests) (medium)

- **Tasks:** r1-xlsx, r1-deck, r1-full-chain
- **Evidence:**
  - `eval/round1/runs/r1-xlsx__0f9da92a-7749-43a1-af04-883bf9364dc3/capability_requests.json` — excel_generator, kind tool
  - `eval/round1/runs/r1-deck__fa0b5ab9-477d-4e11-8c4f-5aa174472975/capability_requests.json` — presentation-generator, kind tool; no brand-style request
  - `eval/round1/runs/r1-full-chain__a3ddb368-882b-4d8d-bea6-513cef4c5845/capability_requests.json` — spreadsheet_tool, word_doc_tool, chart_tool — all kind tool
- **Likely root cause (hypothesis):** Hypothesis: amoeba/config/prompts/d24_create_team.txt:29-30 defines a TOOL as something that 'acts or fetches' and a SKILL as 'know-how or a method (cost modelling, schema design…)'; producing an .xlsx / .pptx / .docx reads as acting, so it becomes a tool. Consequence for round 2: amoeba/pool/match.py rank() only compares entries of the request's kind, so anthropics/skills entries can never be candidates.
- **What would confirm it:** Count kinds over more drafts; draft r1-xlsx once with a skill example in the prompt and see the kind change.
- **Possible direction:** Say in the Planner prompt that a document format or a house style is a skill, or let the pool match across kinds.

### I4 — The Plan Observer does not know which tools are installed and asks for calc to be requested (medium)

- **Tasks:** r1-weather, r1-fx-email
- **Evidence:**
  - `eval/round1/runs/r1-weather__aea4d8ec-df0c-4a9f-b902-d47177f826d3/plan.json → rounds[0].plan_observer` — "Add `calc` to Capability requests … so the Data Analyst has the necessary tool"
  - `eval/round1/runs/r1-weather__aea4d8ec-df0c-4a9f-b902-d47177f826d3/plan.json → rounds[1].plan_observer` — "The `calc` tool must be formally requested in the Capability requests section"
  - `eval/round1/runs/r1-fx-email__544fb5fa-13e0-401f-873c-4d1a1f62b8bd/plan.json → rounds[0].plan_observer` — "Add `calc` to Capability Requests"
  - `eval/round1/runs/r1-weather__aea4d8ec-df0c-4a9f-b902-d47177f826d3/result.json` — 3 draft rounds, 18 calls, 67,686 billed tokens (median run: 12 calls, 44k)
- **Likely root cause (hypothesis):** Confirmed in the trace: the plan_observer prompt has no 'Installed tools' section, while amoeba/config/prompts/d24_review_plan.txt:33 asks it whether 'each step can actually be done with installed tools or a requested capability'. amoeba/task/draft.py:247-249 renders d24_review_plan without the tool list (the agent observer's d24_review_team.txt:13 has it).
- **What would confirm it:** Already seen: no 'Installed tools' string in any plan_observer prompt of the round.
- **Possible direction:** Give the Plan Observer the same installed-tools list the Agent Observer gets.

### I5 — The Planner leaves needed capabilities out, or turns a company-specific input into an assumption (medium)

- **Tasks:** r1-deck, r1-full-chain
- **Evidence:**
  - `eval/round1/runs/r1-deck__fa0b5ab9-477d-4e11-8c4f-5aa174472975/plan.json → givens` — "assumption: The 'company brand style' implies a professional corporate template with specific color palettes and font standards."
  - `eval/round1/runs/r1-deck__fa0b5ab9-477d-4e11-8c4f-5aa174472975/capability_requests.json` — only presentation-generator; no chart, file writing or brand style
  - `eval/round1/runs/r1-full-chain__a3ddb368-882b-4d8d-bea6-513cef4c5845/capability_requests.json` — no web_search and no code runner requested
- **Likely root cause (hypothesis):** Hypothesis: d24_create_team.txt asks for 'ideal capabilities' but also to settle ambiguity by assumption (D53); a brand guide the team cannot know is treated as an ambiguity to assume rather than an input to request or an Open Question. The observers' checklists do not ask 'what must come from the user?'.
- **What would confirm it:** Check whether any draft in the round lists an Open Question or a request for the brand guide (none does).
- **Possible direction:** Anything only the user or the company can supply becomes a request or an Open Question, never an assumption.

### I6 — Failed draft checks change nothing without the quality gate (low)

- **Tasks:** r1-deck
- **Evidence:**
  - `eval/round1/runs/r1-deck__fa0b5ab9-477d-4e11-8c4f-5aa174472975/plan.json → quality.failed_checks` — ["summariser", "independent_verification"] with both observers APPROVE
- **Likely root cause (hypothesis):** By design (D24/D28): draft_quality is recorded only unless --quality-gate, which this round's settings do not set. The deck plan has the Delivery Lead verify and then summarise its own work, and no real verify step.
- **What would confirm it:** result.json draft_quality of r1-deck.
- **Possible direction:** Decide whether the observer rounds should use --quality-gate (it would change the settings between rounds).

### I7 — 16 of 18 request names are not in the alias list (low)

- **Tasks:** all
- **Evidence:**
  - `eval/round1/runs/r1-chart__4eace600-ecae-4ca6-a1e0-f799b71e7413/capability_requests.json` — code_interpreter → canonical code_interpreter, mapped false (python_interpreter maps to code_execution)
- **Likely root cause (hypothesis):** amoeba/capabilities/aliases.yaml has no entries for these names (full list in capabilities.md). It matters wherever code relies on the standard name: web tool granting (I2), blocked-capability counts, reports.
- **What would confirm it:** result.json unmapped_capabilities of each run.
- **Possible direction:** Grow aliases.yaml from capabilities.md.

## Box 3

### I8 — A helper without its tool can finish 'done' from memory, with no BLOCKED line (high)

- **Tasks:** r1-route, r1-deck, r1-fx-email, r1-code-run
- **Evidence:**
  - `eval/round1/runs/r1-route__54ab8b83-35c2-4acf-80da-dd48c0606ae9/artifacts/step_1.json` — status done; the Logistics Specialist lacked route_engine; distances 185/175/185 [unverified]
  - `eval/round1/runs/r1-deck__fa0b5ab9-477d-4e11-8c4f-5aa174472975/artifacts/step_2.md:5-10` — "Deep Navy (#002060) … Segoe UI … Company Logo (Top Right)" — the designer lacked presentation-generator; status done
- **Likely root cause (hypothesis):** Hypothesis: amoeba/interp/plan_runner.py:501-513 (run_step) derives the status only from BLOCKED actions and BLOCKED marks in the text; the helper's missing_tools and the step's open capability requests are not consulted, so a step whose helper simply writes an answer anyway is 'done'.
- **What would confirm it:** Compare each step's roles' missing_tools with its status: 9 'done' steps have a helper with a missing tool; in 4 the step needed that tool — r1-route 1 (routing), r1-deck 2 (slides), r1-fx-email 3 (email: 'Not sent', no BLOCKED), r1-code-run 2 (verify without the interpreter, I16).
- **Possible direction:** A step whose helper lacks a requested capability cannot be 'done' without saying what it did instead.

### I9 — Invented facts reach the answer, softened only by [unverified] (high)

- **Tasks:** r1-pdf-read, r1-deck, r1-route
- **Evidence:**
  - `eval/round1/runs/r1-pdf-read__cc2ed6f7-957f-45ff-ad2e-c3aef0770cdd/result.json → answer, lines 1-2` — "Agent Designer (Page 4 [unverified])" — the paper's drafting-stage agents are Planner, Agent Observer, Plan Observer; the PDF was never read
  - `eval/round1/runs/r1-pdf-read__cc2ed6f7-957f-45ff-ad2e-c3aef0770cdd/result.json → summary_check` — answer_unverified ['4'] — seen by code, not acted on
  - `eval/round1/runs/r1-deck__fa0b5ab9-477d-4e11-8c4f-5aa174472975/result.json → answer` — invented brand colours, fonts and logo placement
- **Likely root cause (hypothesis):** Hypothesis: D33 treats [unverified] as an honest label, and amoeba/config/prompts/plan_step.txt:20 invites figures 'from your own knowledge' tagged [unverified] — even when the requirement itself (R4 'page number where each is described') can only be met by the capability that was BLOCKED.
- **What would confirm it:** In each run, list requirements whose covering step is partial/blocked yet whose figures appear in the answer as [unverified] (r1-pdf-read R4).
- **Possible direction:** A requirement whose capability was blocked is reported as not met, never answered from memory.

### I10 — [S#] is used for step numbers, and made-up citations stay in the final answer (high)

- **Tasks:** r1-chart
- **Evidence:**
  - `eval/round1/runs/r1-chart__4eace600-ecae-4ca6-a1e0-f799b71e7413/artifacts/step_3.md:7` — "Total Revenues from Step 2: 22200 [S2], 16800 [S2] …"
  - `eval/round1/runs/r1-chart__4eace600-ecae-4ca6-a1e0-f799b71e7413/artifacts/step_4.md:6-9` — "Lane A: 22,200 [S1]" … — no source S1 exists in this run
  - `eval/round1/runs/r1-chart__4eace600-ecae-4ca6-a1e0-f799b71e7413/artifacts/step_4.json → provenance` — hallucinated_citations ['S1'], yet the answer keeps it
- **Likely root cause (hypothesis):** Hypothesis: the source ids S1, S2 … read like step numbers ('Step 2' → [S2]); provenance (amoeba/interp/provenance.py check_provenance) detects the unseen id but nothing removes it, and the summariser's step is not refined for it.
- **What would confirm it:** Search every answer of the round for [S#] with no sources in the run: only r1-chart; 2 hallucinated ids.
- **Possible direction:** Strip or flag an unseen [S#] in the answer by code, and name sources so they cannot be read as steps.

### I11 — Provenance tagging corrupts code and spreadsheet formulas (medium)

- **Tasks:** r1-code-run, r1-xlsx
- **Evidence:**
  - `eval/round1/runs/r1-code-run__7242d0c0-bf30-4861-b5c6-f3d6fa055444/artifacts/step_1.md:8` — "if n < 0: # 0 [unverified]" (also in the final answer)
  - `eval/round1/runs/r1-xlsx__0f9da92a-7749-43a1-af04-883bf9364dc3/artifacts/step_1.md:22-23` — "=SUM(B2 [unverified]:B5 [unverified])"
  - `eval/round1/runs/r1-xlsx__0f9da92a-7749-43a1-af04-883bf9364dc3/artifacts/step_1.md:5` — "**1 [unverified]. Column Definitions**"
- **Likely root cause (hypothesis):** Hypothesis: amoeba/interp/provenance.py:34 _line_numbers counts every number, including those inside code fences, cell references and bold list numbers (LIST_MARKER at :22 only matches a plain '1. '); the D50 refine turn (--self-refine on-issues) then asks the helper to tag them, and it does.
- **What would confirm it:** Run check_provenance on those lines: they come back as untagged figures.
- **Possible direction:** Leave code blocks, formulas, cell references and list numbering out of the figure count.

### I12 — The summariser drops work that was done when a later step fails (medium)

- **Tasks:** r1-xlsx, r1-fx-email, r1-repo
- **Evidence:**
  - `eval/round1/runs/r1-xlsx__0f9da92a-7749-43a1-af04-883bf9364dc3/artifacts/step_1.md` — full table with lane totals 22,200 / 16,800 / 28,400 / 12,400 and formulas
  - `eval/round1/runs/r1-xlsx__0f9da92a-7749-43a1-af04-883bf9364dc3/result.json → answer` — "Verification Status: Failed … R1/R2/R3: Not met" — no totals, no 79,800, no 1,855.81
- **Likely root cause (hypothesis):** Hypothesis: amoeba/config/prompts/plan_summarise.txt asks the summariser to assemble the deliverable from the step outputs; after a verify FAIL it writes a status memo instead, and nothing checks that the figures already produced upstream reach the answer.
- **What would confirm it:** Compare each step's numbers (figure_ledger) with the answer's figures: r1-xlsx loses all of step 1's.
- **Possible direction:** The answer carries every usable artifact produced upstream, next to what is missing.

### I13 — BLOCKED names turn sentences, step numbers and missing inputs into 'capabilities' (medium)

- **Tasks:** r1-weather, r1-xlsx, r1-repo, r1-full-chain
- **Evidence:**
  - `eval/round1/runs/r1-full-chain__a3ddb368-882b-4d8d-bea6-513cef4c5845/result.json → blocked_capabilities` — keys 'Step 1', 'Step 2', 'Step 1 (OS Intelligence Analyst) — No framework data provided.'
  - `eval/round1/runs/r1-weather__aea4d8ec-df0c-4a9f-b902-d47177f826d3/result.json → answer` — four appended BLOCKED lines for two gaps, one of them 'weather_data' (an input, not a tool)
  - `eval/round1/runs/r1-full-chain__a3ddb368-882b-4d8d-bea6-513cef4c5845/result.json → answer` — "BLOCKED: Step 1 (OS Intelligence Analyst) — No framework data provided. (the team had no such capability; added by plain code)"
- **Likely root cause (hypothesis):** Hypothesis: amoeba/interp/runtime.py:200 (_dispatch) keeps everything after 'BLOCKED:' up to the line end, including '— reason'; helpers also answer BLOCKED when an upstream input is missing; plan_runner.py:763/776 (blocked_capabilities / enforce_limitations) then key on that raw text.
- **What would confirm it:** result.json blocked_capabilities of the four runs.
- **Possible direction:** Cut the name at the first dash and record 'input missing' apart from 'capability missing'.

### I14 — Verify FAIL triggers rework that cannot help when the producer lacks a tool (medium)

- **Tasks:** r1-weather, r1-pdf-read, r1-xlsx, r1-fx-email, r1-repo, r1-full-chain
- **Evidence:**
  - `eval/round1/runs/r1-full-chain__a3ddb368-882b-4d8d-bea6-513cef4c5845/trace.jsonl` — 3 rework events, 2 stale, 1 reverify — every reworked step blocked again
  - `eval/round1/runs/r1-xlsx__0f9da92a-7749-43a1-af04-883bf9364dc3/trace.jsonl` — rework of step 2 (BLOCKED excel_generator) → blocked again
- **Likely root cause (hypothesis):** Hypothesis: amoeba/interp/plan_runner.py:808 rework_producers re-runs every checked producer on FAIL without looking at why it failed; a missing capability does not change between attempts.
- **What would confirm it:** Sum the calls of reworked steps in the six runs (tokens spent with no change of status).
- **Possible direction:** Skip rework when the producer's only problem is a blocked capability.

### I15 — Limitations miss gaps that no helper wrote as BLOCKED (medium)

- **Tasks:** r1-fx-email, r1-route, r1-deck
- **Evidence:**
  - `eval/round1/runs/r1-fx-email__544fb5fa-13e0-401f-873c-4d1a1f62b8bd/result.json → answer` — Limitations name currency_api only; email_service missing was never said
  - `eval/round1/runs/r1-route__54ab8b83-35c2-4acf-80da-dd48c0606ae9/result.json → answer` — route_engine not named; only 'distances … are [unverified]'
  - `eval/round1/runs/r1-deck__fa0b5ab9-477d-4e11-8c4f-5aa174472975/result.json → answer` — no pptx, chart or brand-guide gap named
- **Likely root cause (hypothesis):** Hypothesis: amoeba/interp/plan_runner.py:763 blocked_capabilities comes only from BLOCKED actions and marks; the run's unfilled capability requests (capability_requests.json) are not used by enforce_limitations.
- **What would confirm it:** Diff capability_requests.json against each answer's Limitations.
- **Possible direction:** Every unfilled capability request appears in Limitations, whatever the helpers wrote.

### I16 — A verify step passes without the capability it needed (low)

- **Tasks:** r1-code-run
- **Evidence:**
  - `eval/round1/runs/r1-code-run__7242d0c0-bf30-4861-b5c6-f3d6fa055444/artifacts/step_2.md` — "Verdict: PASS … verified against the known mathematical value" — QA lacked python_interpreter
- **Likely root cause (hypothesis):** Same mechanism as I8 for verify steps: nothing ties a verdict to the verifier's missing tools.
- **What would confirm it:** Verify steps whose role has missing_tools: only this one passed.
- **Possible direction:** A verifier without its tool says what it could not check.

### I17 — calc is under-used (low)

- **Tasks:** r1-code-run, r1-fx-email
- **Evidence:**
  - `eval/round1/runs/r1-code-run__7242d0c0-bf30-4861-b5c6-f3d6fa055444/trace.jsonl` — no execute_tool span: F50 was not checked (calc can evaluate Binet's formula)
- **Likely root cause (hypothesis):** Hypothesis: helpers use calc for products and sums, not to cross-check a value they 'know'.
- **What would confirm it:** Tool calls per run in facts/*.json (calc: 0, 0, 0, 1, 4, 0, 1, 0, 1, 0).
- **Possible direction:** Low priority.

## Cross-cutting

### I18 — Cost is invisible in the run records (low)

- **Tasks:** all
- **Evidence:**
  - `eval/round1/runs/r1-code-run__7242d0c0-bf30-4861-b5c6-f3d6fa055444/result.json → usage.cost_usd` — null — prices.yaml has no price for gemma-4-31b-it
  - `eval/round1/runs/r1-weather__aea4d8ec-df0c-4a9f-b902-d47177f826d3/result.json → usage` — reasoning 24,517 of 67,686 billed tokens
- **Likely root cause (hypothesis):** amoeba/config/prices.yaml leaves Gemma null; reasoning tokens are 38% of the round's billed tokens (171,251 of 453,133) and runs took 5–16.5 minutes each.
- **What would confirm it:** Sum usage over facts/*.json.
- **Possible direction:** Fill in a Gemma price (even $0 for the Gemini API) so cost appears per run.

### I19 — The environment can change a run without anyone noticing (low)

- **Tasks:** all
- **Evidence:**
  - `eval/round1/runs/r1-code-run__7242d0c0-bf30-4861-b5c6-f3d6fa055444/result.json → models.returned` — gemma-4-31b-it — only because old AMOEBA_* variables were unset first
  - `eval/round1/runs/r1-code-run__7242d0c0-bf30-4861-b5c6-f3d6fa055444/result.json` — unrelated: the D55 Stop hook spent 22,670 arch-text tokens during the round (docs/arch/text_log.jsonl)
- **Likely root cause (hypothesis):** D54 precedence (AMOEBA_* > profile) is intended but silent; the Stop hook calls a model whenever box facts change.
- **What would confirm it:** docs/arch/text_log.jsonl entry of 2026-09-25T19:32Z.
- **Possible direction:** Print the effective model, endpoint and key source at the start of every run.
