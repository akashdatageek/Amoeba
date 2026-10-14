# Box 4 on the same three complex tasks with Gemma 4 31B, compared with Claude Sonnet 5.5

Oct 13, 2026 · model `gemma-4-31b-it` (profile `gemma-api`, free tier) · code `9aa8782` (current `main`). This is the
same command and flags as the Sonnet runs (`eval/manual/sonnet/REPORT.md`); only the profile differs. The flags:
`--topology plan --draft-prompts d24 --web-tools --plan-search on --adapt on --pool --local-tools on
--local-tools-mode inprocess --replan off --ask-assumed off --max-tokens-per-run 1500000 --planner-max-tokens 32768
--observer-max-tokens 16384`. One run per task, one at a time.

## Result in short

| Task | Gemma outcome | Steps past | Stuck / fixes | Tokens | Wall | Sonnet outcome (same task) |
|---|---|---|---|---|---|---|
| H3 EV trucks | **stopped by Box 4 at step 2 of 5** (capability; limit 3 fixes per step) | 1 | 3 / 3 | 235,238 | 84.7 min | stopped at step 3 of 7 |
| H2 real income | **stopped by Box 4 at step 1 of 4** (capability; limit 3 fixes per step) | 0 | 3 / 3 | 219,634 | 33.5 min | stopped at step 3 of 5 |
| r1 GitHub chain | **stopped by Box 4 at step 5 of 6** (capability: send_email; limit 3 fixes per step) | **4** | 6 / 6 | 568,731 | 99.1 min | stopped at step 1 of 6 |

- **No task finished, on either model.** Gemma's r1 got furthest of all eight runs. It made the spreadsheet, the chart
  and a 2-page Word report (`framework_report.docx`, the first `.docx` in any run). It stopped only at "send the email",
  for which no tool exists.
- **The first Box 4 rescue in any run.** On Gemma's r1, step 1 was stuck three times. The fix proposer's `work_around`
  ("Use web_search to identify the top 5 multi-agent frameworks and extract their star counts and latest release
  dates from their GitHub repository pages") let the run go on. It was recorded as **finished with limitation**:
  "Data was collected via web search instead of the GitHub API". This is the D124 change working.
- **Gemma had 0 blocked calls in 140.** There was no `content_filter` and no unreadable reply. On Sonnet, 47 of 145
  calls were blocked. The blocking is Claude's endpoint, not Amoeba.
- **Finish mode never switched on.** The largest run used 568,731 of the 1,500,000-token cap.
- **Cost:** $0, on the free tier. The "$" line in the run log is my script pricing the tokens at Claude's rates; ignore it.

## Box by box

### Box 1 and Box 2 (reading and planning)
- **Box 1:** every run read the task and the planning search said `not_needed`. On r1 Gemma wrote: "I read
  'spreadsheet' as Microsoft Excel; if you meant Google Sheets or CSV file, the answer below may not apply."
- **Box 2 rounds:** H3 took 3 rounds (no consensus), H2 2 (consensus) and r1 3.
- **Planner reply length per round:** H3 3,435 / 3,913 / 3,942; H2 3,015 / 3,055; r1 3,856 / 4,016 / 4,324 output
  tokens, each with about 900–6,200 tokens of hidden reasoning. That is about a quarter of Sonnet's 13–19k per round.
- **A slow planner call on H3.** The round-2 call took 26.5 minutes (`latency_ms` 1,587,959). With the 32,768 limit,
  Gemma can think much longer per call; rounds 1 and 3 took about 2 minutes each.

### Box 3 (the steps)
**H3** (plan: Data Gathering → Financial Modeling → Audit → Memo (.docx) → Final Delivery):
- **Step 1: partial** (mislabelled citations: `'180,000' not in S6`).
- **Step 2, the TCO model: partial, four tries.** The TCO Analyst's `calc` calls failed with "invalid syntax". It wrote
  `calculations.py` but had no Python to run it. Its status: "lacked: Charging Infrastructure, Maintenance Cost".

**H2** (plan: Data Gathering for all three variables over 9 years → Calculation and Visualization → Data Verification
by the same researcher → Final Assembly):
- **Step 1 ran three times and never ended:** "lacked: BLS Search, Excel File Reading, US Nominal Income", then
  "lacked: IN Nominal Income, US Nominal Income".
- It made 7 local tool calls and no files.

**r1** (plan: Data Extraction → Spreadsheet and Chart → Report Drafting → Quality Verification → Final Delivery (email)
→ Final Assembly):

| Step | Result |
|---|---|
| 1 | partial, then finished with limitation (the work-around: web search instead of the API) |
| 2 | **done:** `framework_stats.xlsx` (38,625 bytes) and `chart.png` (39,756 bytes) |
| 3 | partial (`'59,059' not in S26`): `framework_report.docx` (72,039 bytes), 805 words, the chart embedded, no data table. It opens "Executive Report: Top 5 Open-Source Multi-Agent AI Frameworks". |
| 4 | **done** |
| 5 | stuck: "lacked: send_email" |
| 6 | not run |

### Box 4 (the focus)

**Every stuck event:**

| Run | Step | Cause | Evidence (shortened) | Cause matches the evidence? |
|---|---|---|---|---|
| H3 | 2 (×3) | capability | "TCO Analyst: calc failed twice in a row with the same error: error: invalid syntax"; "lacked: Charging Infrastructure, Maintenance Cost"; "requested capability python_interpreter for TCO Analyst: unfilled (connect_failed)" | **Partly.** Python was really missing: the toolbox step gave the request to an internet MCP whose connection failed, not to `local:Bash`. "Charging Infrastructure" and "Maintenance Cost" are data items, not tools; plain code took them for capabilities. |
| H2 | 1 (×3) | capability | "lacked: BLS Search, Excel File Reading, US Nominal Income"; "requested capability BLS Search … unfilled (connect_failed)" | **Mostly no.** The researcher had the web tools. What it lacked was data ("US Nominal Income", "IN Nominal Income"), and plain code read those as missing tools. |
| r1 | 1 (×3) | capability | "lacked: fetch_url" | **Yes.** `fetch_url` failed on the GitHub API (the proposer: "fetch_url tool is failing with a WebToolError"). |
| r1 | 5 (×3) | capability | "lacked: send_email"; then "lacked: email body, send_email"; then "lacked: Delivery Lead email body, send_email"; "requested capability send_email … unfilled (pick_none)" | **Yes** for send_email (no email tool exists). "email body" is noise. |

**Every fix:**

| Run | Step | Try | Rung | Edit | Result | Tokens |
|---|---|---|---|---|---|---|
| H3 | 2 | 1 | pool (2) | grant: Charging Infrastructure, Maintenance Cost, python_interpreter | failed: still stuck | 16,621 |
| H3 | 2 | – | tool writer (W) | – | skipped: "no offline library for Charging Infrastructure, Maintenance Cost, python_interpreter" | 0 |
| H3 | 2 | 2 | pool (2) | the same items, `local:Bash` excluded (already given) | failed: "nothing to attach" | 0 |
| H3 | 2 | 3 | proposer (D) | grant_tool `web_search` to the TCO Analyst ("lacking specific data for Charging Infrastructure and Maintenance Costs and is hallucinating citations") | failed: still stuck → stop | 53,258 |
| H2 | 1 | 1 | pool (2) | grant: BLS Search, Excel File Reading, US Nominal Income | failed: still stuck | 56,650 |
| H2 | 1 | 2 | pool (2) | grant: BLS Search, IN/US Nominal Income | failed: "nothing to attach" | 0 |
| H2 | 1 | 3 | proposer (D) | split_step (e.g. "Gather US Nominal Income"); reason: "failed by attempting to use unavailable Python libraries in Bash and requesting non-existent specialized tools" | applied; the first sub-step was stuck again and inherited the 3-fix limit → stop | 6,270 |
| r1 | 1 | 1 | pool (2) | grant fetch_url | failed: still stuck | 25,039 |
| r1 | 1 | 2 | proposer (D) | grant `local:Bash` ("to use curl") | failed: still stuck | 28,273 |
| r1 | 1 | 3 | proposer (D) | **work_around**: web search instead of the API | **finished with limitation**, and the run went on | 25,215 |
| r1 | 5 | 1 | pool (2) | grant send_email | failed: still stuck | 21,369 |
| r1 | 5 | 2 | pool (2) | grant "email body", send_email | failed: still stuck | 36,078 |
| r1 | 5 | 3 | pool (2) | grant "Delivery Lead email body", send_email | failed: "nothing to attach" → stop | 0 |

**Two new findings in the fixes:**
- **On r1 step 5, all three fixes were pool grants.** Each time the helper's "lacked" line added a new word ("email
  body", then "Delivery Lead email body"), so every grant looked like a new fix (D124 compares the items). The three
  grants used up the per-step limit before the proposer could offer the `work_around` that rescued step 1. A "NOT
  SENT" file would have let step 6 run.
- **Several proposer replies were cut at their reply limit:** 2,048 / 4,096 tokens on H3 and H2. Gemma thinks before it
  answers.

**Adaptations by kind (Gemma, 3 runs):**

| Kind | Tried | Recovered a step | Finished with limitation |
|---|---|---|---|
| pool grant (rung 2) | 8 | 0 | 0 |
| tool writer (rung W) | 0 (skipped 6×: no offline library) | – | – |
| proposer grant_tool | 2 | 0 | 0 |
| proposer split_step | 1 | 0 | 0 |
| proposer work_around | 1 | 0 | **1** (r1 step 1) |
| **all** | **12** | **0** | **1** |

**Adaptation tokens vs the run:** H3 69,879 of 235,238 (30%); H2 62,920 of 219,634 (29%); r1 135,974 of 568,731 (24%).

### Doc skills and local tools
| Run | Skills attached | Local calls | Files | Refusals |
|---|---|---|---|---|
| H3 | docx → Document Specialist | 1 | `calculations.py` | – |
| H2 | xlsx → Economic Data Researcher | 7 | none | – |
| r1 | xlsx → Data Analyst; docx → Technical Writer; pptx and discernment-nudge → Automation Engineer (granted in Box 4's email tries) | 15 | `framework_stats.xlsx`, `chart.png`, `framework_report.docx`, `generate_report.py` | 2 `unsafe_command` ("path outside the workspace: /workspace/sources/" and "/workspace") |

### Box 5
- **Model:** all calls went to `gemma-4-31b-it`.
- **Rate limits:** 16 rate-limit waits on H3, 3 on H2 and 7 on r1, all recovered (the free tier allows 15 requests per
  minute).

## Gemma vs Sonnet on the same tasks

| | Gemma 4 31B | Claude Sonnet 5.5 |
|---|---|---|
| Steps past, H3 / H2 / r1 | 1 / 0 / **4** | **2 / 2** / 0 |
| Files made | r1: xlsx, png, **docx**; H3: a script | H2: csv, png, script; H3: a script |
| Box 4 rescues | **1** (work-around, r1 step 1) | 0 |
| Blocked calls | **0 of 140** | 47 of 145 |
| Seconds per call (wall / calls) | 134 / 63 / 85 | 19 / 12 / 17 |
| Planner output per round | 3.0–4.3k | 13–19k |
| Cost | $0 | $5.23 (+ $0.94 for a failed first attempt) |

**How each model fails.** Gemma fails in its "lacked" lines: it lists data as missing tools, and grants then fail on
internet tools that cannot connect. Sonnet fails on blocked calls, and on its own very demanding done_when conditions.

## Planning: which model plans best, and which plan could finish

**Sonnet writes the better plan on all three tasks:**
- **Independent research steps.** On H3, incentives and cost data are separate steps that can run side by side, and the
  incentives step must check the 45W credit at the source. On H2, there are separate Census and BLS researchers.
- **Independent verification with correction loops.** Gemma's H2 has the same researcher check its own data.
- **Correct scope.** Gemma's H2 asks for "all 9 years"; the task needs 2015 and 2023.
- **Honest fallbacks for things no tool can do.** Sonnet's r1 email step: "or the NOT SENT fallback file exists and is
  stated explicitly". Gemma's: "Email is successfully dispatched", which is impossible.

**Gemma's simpler plans moved further on r1**, for two reasons:
- **Its step goals are reachable.** "5 frameworks with API-verified stars and dates", against Sonnet's 5 repos + 5
  logged candidates + a call budget in one step of 5 turns.
- **Every capability request names exactly one role**, so all four r1 roles got `local:Bash`. Sonnet's
  `python_interpreter` request named two roles in one field and was dropped.

**As predicted before the run ended,** Gemma's r1 stopped at the email step. Its done_when could not be met, and it
had no fallback.

**The plan most likely to finish** is Sonnet's structure with three changes, all prompt or check changes (not made):
1. **Every done_when must be reachable** within the step's turns: no exact-string demands, and no two-source agreement
   on every value.
2. **Every capability no tool covers gets a written fallback**, as Sonnet did for email but not for the Census key.
3. **Each capability request names exactly one role.** The plan observers could enforce all three.

## What went wrong, in order of weight (Gemma)
1. **Data read as missing tools.** "US Nominal Income", "Charging Infrastructure" and "email body" in a "lacked" line
   become capability requests and pool grants (H2, H3, r1 step 5).
2. **Python requests went to internet MCPs that fail to connect** (`connect_failed`), not to `local:Bash` (H3, H2).
3. **Grant variants used up the per-step limit** before the proposer's work-around could run (r1 step 5).
4. **A split step inherits its parent's fix count** (H2), as on Sonnet's H3.
5. **Proposer replies were cut at 2,048 / 4,096 tokens** (Gemma's hidden reasoning).

## Notes
- Local tools ran in-process in this container (`AMOEBA_SANDBOX=1`); there were 2 gate refusals on r1.
- No code was changed during the runs.

Key scan of `eval/manual/gemma/` (420 files, 13.0 MB; key patterns and the three real key values): clean.
