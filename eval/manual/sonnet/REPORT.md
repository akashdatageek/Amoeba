# Box 4 on three complex tasks with Claude Sonnet 5.5

Oct 13, 2026 · model `claude-sonnet-5-5` (profile `claude-sonnet`, D126) · code `8e91f38` (runs 1–3; the failed first
attempt ran on `8752f98`). Command as asked: `--topology plan --draft-prompts d24 --web-tools --plan-search on --adapt on
--pool --local-tools on --local-tools-mode inprocess --replan off --ask-assumed off --max-tokens-per-run 1500000`, plus
`--planner-max-tokens 32768 --observer-max-tokens 16384` (added after the first attempt, see below). One run per task,
one at a time.

## Result in short

| Run | Task | Outcome | Stuck events | Fixes tried | Billed tokens | Cost | Wall |
|---|---|---|---|---|---|---|---|
| (0) | H3 EV trucks, first attempt | Box 2 failed: planner replies cut at the 8,192/16,384 reply limit | 0 | 0 | 189,008 | $0.94 | 7.3 min |
| 1 | H3 EV trucks | **stopped by Box 4** at step 3 of 7 (capability; limit 3 fixes per step) | 3 | 3 | 702,185 | $2.43 | 19.6 min |
| 2 | H2 real income IN vs US | **stopped by Box 4** at step 3 of 5 (format; adaptation token limit) | 2 | 1 | 695,653 | $2.08 | 11.6 min |
| 3 | r1 GitHub frameworks chain | **stopped by Box 4** at step 1 of 6 (capability; nothing left to try) | 1 | 2 | 163,437 | $0.72 | 6.4 min |
| | **Total** | | **6** | **6** | | **$6.17** | |

- **No stuck step recovered** and none finished with a limitation. All three tasks stopped. Each run still returned an
  answer: Box 4's stop report followed by the finished steps under "# Partial answer" (D123). That is 27,492 characters
  for H3, 12,705 for H2 and 7,632 for r1.
- **Finish mode (D122) never switched on.** The largest run used 702,185 of the 1,500,000-token cap (47%; finish mode
  starts at 85%). No fix was skipped for the cap, so every fix Box 4 could try, it tried.
- **The main finding is not about Box 4's logic.** 47 of the 145 model calls in runs 1–3 came back empty, with
  `finish_reason: content_filter`. Amoeba reads an empty reply as a reply that "could not be read" (D123). Most of the
  stuck turns in H3 and H2 were these blocked calls. Box 4 diagnosed "capability" and "format", and it has no fix for a
  provider that blocks the call. See Box 4 below.

**Model label.** All calls in runs 1–3 went to `claude-sonnet-5-5`: `result.json` `usage.model` and
`models.requested`, and the trace's `gen_ai.request.model` and `gen_ai.response.model`. The first attempt (0) was
written before the label fix (`8e91f38`), so its `result.json` still says `gemma-4-31b`. Its trace shows all 10 calls
went to `claude-sonnet-5-5`; I left the file as written. `team.yaml` in every run lists `model: gemma-4-31b` per
helper. That field is the configured default, not what the router called, and it is still wrong (not fixed yet).

## Box by box

### Box 1 (task reading) and the planning search
All three runs read the task, wrote the reading at the top of the answer, and the planning search decided `not_needed`.
- **H3:** "I read 'federal and Indiana incentives that actually apply to a purchase in 2026' as Federal 45W commercial clean
  vehicle credit (up to $40,000 for over 14,000 lb), which may have expired for vehicles acquired after Sept 30, 2025,
  plus any Indiana state or utility programs". Plan search: "The readings already flag the uncertain 45W status, and the
  plan only needs a step to verify it, which the team can do with its own web tools". Sonnet raised the 45W expiry at
  the reading stage. Gemma caught it only in the audit, in H3 run 2.
- **H2:** "I read 'U.S. Census Bureau survey estimates for income' as American Community Survey (ACS) 1-year estimates,
  table B19013 median household income".
- **r1:** plan search: "The GitHub REST API (stars via repos endpoint, releases/latest) is well known and the readings
  fix the terms".

### Box 2 (planning)
| Run | Rounds | Consensus | Roles | Steps |
|---|---|---|---|---|
| (0) H3 | 1 (failed) | – | – | – |
| 1 H3 | 3 | yes | Incentives and Tax Policy Researcher · Fleet Cost Data Researcher · TCO Modeller and Fleet Feasibility Analyst · Cost Model Verifier · Memo Editor and Document Assembler | 7, including a conditional correction loop (steps 5–6) and the .docx memo (step 7) |
| 2 H2 | 3 | no | Census Income Data Researcher · BLS Price Index Researcher · Quantitative Analyst and Chart Builder · Independent Verification Auditor · Final Report Writer | 5 |
| 3 r1 | 2 | yes | GitHub Data Researcher · Data and Visualization Analyst · Technical Report Author and Delivery Specialist · Data QA Reviewer · Delivery Summariser | 6, including "Send the report by email" (step 5) |

**First attempt (0).** The planner's replies were cut at the reply limit (`finish: length`) in 5 of 6 calls: 8,192 on
the first try and 16,384 on the automatic retry. The run ended with `planner: missing sections ['Risks and Decisions',
'RoleFeedback', 'PlanFeedback']`. With `--planner-max-tokens 32768` every planner reply finished by itself.

**Planner reply length per round (output tokens), Sonnet vs Gemma on the same task:**

| Task | Sonnet: round 1 / 2 / 3 | Gemma: round 1 / 2 / 3 (visible + hidden reasoning) | Gemma run |
|---|---|---|---|
| H3 | 14,805 / 17,931 / 18,564 | 3,258 (+1,054) / 3,678 (+1,788), after one call cut at 8,189 hidden / 3,668 (+0) | `eval/manual/h3/fe375170` |
| H2 | 13,243 / 13,708 / 14,134, after one call blocked at 1,869 (`content_filter`) | 3,592 (+1,080), 1 round | `amoeba-probe/eval/probe_hard/runs/2da6434b` |
| r1 | 14,436 / 15,392 | 3,324 (+675) / 3,716 (+864) | `eval/round1/runs/r1-full-chain__a3ddb368` |

Sonnet's plans are about 4–5× Gemma's visible output, and about 3× Gemma's visible plus hidden output.

**Does the long plan drive the cost?** Mostly inside Box 2, and much less in later steps:
- Box 2 and the toolbox step cost $0.96 of $2.43 on H3 (39%), $0.85 of $2.08 on H2 (41%) and $0.55 of $0.72 on r1 (77%).
- The planner's own output alone is 51,300 tokens ($0.51, 21%) on H3, 42,954 ($0.43, 21%) on H2 and 29,828 ($0.30,
  42%) on r1. The two observers re-read each plan every round, with inputs of 10,800–18,900 tokens per call.
- In Box 3 a helper's prompt carries its own step's card and inputs, not the whole plan (`plan_runner._turn`). The
  average helper input on H3 was 9,963 tokens with Sonnet vs 8,755 with Gemma (run 4): +14%.
- In Box 3 the bigger cost drivers were the turn history and upstream outputs that each turn re-sends, and the blocked
  calls (next point).

So a shorter-plan prompt would cut Box 2 (roughly 20–40% of these runs). It would barely change the per-step cost.

### Box 3 (the steps)
**H3 (run 1):**
- **Steps 1 and 2: partial** (mislabelled citations), with real data. Step 2 says: "Input sheet for the 7-year TCO:
  Indiana, 20 Class 8 regional tractors, 60,000 mi/truck/yr". Flags: `'4051' not in S14`, `'$100,000' not in S14`.
- **Step 3 (TCO model): incomplete.** Status: "lacked: Bash; checks failed: format_table, conclusion; not declared by the
  helper: Bash; unreadable replies: 3". Its last output is one calc expression: `340000*1.12 + 420000*1.5/0.9*0.1393 +
  0.12*420000 + 10*165000/20`. The modeller wrote `tco_model.py` but could not run it. The file's own header says
  "NOTE: written in a run where Bash was unavailable; script NOT executed."
- **Steps 4–7 did not run.**

**H2 (run 2):**
- **Step 1: partial, and it says itself: "NOT COMPLETE. No estimate or margin of error was retrieved."** The Census data
  API answered "Missing Key: A valid key must be included with each data API request". The run has no Census key.
- **Step 2: partial.** "STATUS: done_when NOT met … 2023 = 304.702 is confirmed only by secondary sources."
- **Step 3: incomplete (max_turns; unreadable replies)**, yet it produced real files: `build.py`, `mi_income_indiana_us.csv`,
  `plotted_values.json` and `real_median_household_income.png` (92,769 bytes).
- **Steps 4–5 did not run.**
- Box 4 never saw the missing income figures. Step 1 did write "**BLOCKED:** Census API key. Every api.census.gov
  request needs a key, and I had none". Plain code recorded nothing as lacked (`blocked: []`), most likely because of
  the bold markdown around "BLOCKED:", so no stuck signal fired on step 1.

**r1 (run 3):** step 1 is partial: "STATUS: INCOMPLETE … Only 1 of the 5 required repos has API-sourced data". It
fetched `api.github.com/repos/microsoft/autogen` and its `releases/latest` with `fetch_url` (ok). `…/rate_limit`
failed. Its BLOCKED lines say: "BLOCKED: github_api_fetch — the tool is unavailable this run. I used fetch_url on
api.github.com URLs instead, and those worked" and "BLOCKED: turn budget — candidate collection … were not run".

### Box 4 (the focus)

**Every stuck event:**

| Run | Step | Attempt | Cause | Signals | Evidence (shortened) | Cause matches the evidence? |
|---|---|---|---|---|---|---|
| H3 | 3 | 1 | capability | checks_after_retry, unreadable_reply, capability_unfilled | "check format_table still fails …"; "turn 2/4/5: reply not readable"; "lacked: Bash"; "requested capability Bash … unfilled (pick_none)" | **Partly.** Bash was really missing (see "Why the modeller had no Bash"). But 24 of the modeller's 30 calls came back empty with `content_filter`; that, not the missing Bash, is what used up its turns. Box 4 has no cause for it. |
| H3 | 3 | 2 | capability | same | turns 1/3/4/5 not readable; "lacked: Bash" | Partly, as above |
| H3 | 3 | 3 | capability | same | turns 3/5 not readable; "lacked: Bash"; request "unfilled (connect_failed)" | Partly, as above (this is the split's first sub-step, see fix 3) |
| H2 | 3 | 1 | format | unreadable_reply, max_turns | "Quantitative Analyst and Chart Builder, turn 4: reply not readable — … missing sections ['CurrentStep', 'Action', 'ActionInput']"; "turns used: 5" | **No.** 18 of the analyst's 26 calls were empty `content_filter` replies, not format slips. A role rule or more turns cannot fix a blocked call. |
| H2 | 3 | 2 | format | unreadable_reply, max_turns | turns 6/7/8 not readable; "turns used: 8" | No, as above |
| r1 | 1 | 1 | capability | capability_unfilled | "lacked: github_api_fetch, rate-limit check, turn budget"; "requested capability github_api_fetch … unfilled (pick_none)" | **Partly.** No GitHub API tool exists, but `fetch_url` reached the API (2 of 3 calls ok). The step ran out of turns after 1 of 5 repos; its own line says "turn budget". More turns was the fitting fix, and it was never tried: a step with lacked items is "partial", so the max_turns signal does not fire. |

**Every fix:**

| Run | Step | Try | Rung | Edit | Applied or refused, and why | Result | Tokens |
|---|---|---|---|---|---|---|---|
| H3 | 3 | 1 | pool (rung 2) | `grant_tool` items `["Bash"]` | applied; the code pick chose `io.github.MichielDeRuiter/sandboxapi-mcp` (score 1, same as `local:Bash`), whose connection failed | failed: "the pool shortlist had nothing to attach for Bash (no candidate passed the checks)" | 0 |
| H3 | 3 | – | tool writer (rung W) | – | skipped: "tool writer: no offline library for Bash" (correct: Bash is not a file type) | – | 0 |
| H3 | 3 | 2 | proposer (rung D) | `work_around`: "Use the calc fallback the step allows. Compute every total, $/mile, break-even and charging window with calc" | applied (the proposer's reason: "This removes the Bash need and asks for a markdown table and a written conclusion") | failed: still stuck; no markdown table | 109,294 |
| H3 | 3 | 3 | proposer (rung D) | `split_step` into three sub-steps, the first: "Compute per-truck 7-yr totals with calc and present them as a markdown table" | applied | the first sub-step was stuck again at 19:02:05 and the task stopped: "limit: 3 fixes per step". The sub-step kept number 3, so it inherited the three fixes already counted. | 9,866 |
| H2 | 3 | 1 | code (rung 1) | `set_run_option:max_turns` 5 → 8 | applied | failed: still stuck (format); the next fix was refused: "limit: adaptation tokens 270,099 of 200,000" | 270,099 |
| r1 | 1 | 1 | pool (rung 2) | `grant_tool` items `["github_api_fetch", "rate-limit check", "turn budget"]` | applied | failed: "the pool shortlist had nothing to attach" | 0 |
| r1 | 1 | – | tool writer (rung W) | – | skipped: "no offline library for github_api_fetch" (correct: it needs the network) | – | 0 |
| r1 | 1 | 2 | proposer (rung D) | `work_around`, twice | **refused by plain code both times**: "size: method: 495 characters > 300", then "wording: method: denied wording ['skip']" | failed: "fix proposer: no valid edit in two replies"; nothing left, the task stopped | 6,559 |

**Outcome per stuck step:** H3 step 3 stopped the task. H2 step 3 stopped the task. r1 step 1 stopped the task. None
recovered and none finished with a limitation.

**Adaptations by kind across the three runs:**

| Kind | Tried | Applied | Recovered a step | Refused by plain code | Skipped |
|---|---|---|---|---|---|
| code: more turns (rung 1) | 1 | 1 | 0 | 0 | 0 |
| pool grant (rung 2) | 2 | 2 | 0 | 0 | 0 |
| tool writer (rung W, D125) | 0 | 0 | 0 | 0 | 3 (no offline library: Bash ×2, github_api_fetch) |
| fix proposer (rung D) | 3 calls → 2 edits applied (work_around, split_step), 1 with no valid edit | 2 | 0 | 2 replies (r1) | 0 |
| **all** | **6** | **5** | **0** | | |

**Cost of adaptation vs the whole run** (Box 4's own count: the fixes, the proposer calls and the re-runs they cause):

| Run | Adaptation tokens | Adaptation $ | Run $ | Share |
|---|---|---|---|---|
| H3 | 119,160 | $0.30 | $2.43 | 12% |
| H2 | 270,099 | $0.61 | $2.08 | 29% |
| r1 | 6,559 | $0.03 | $0.72 | 4% |

One "more turns" fix on H2 used more than Box 4's whole allowance per task (`adapt.max_tokens_per_task: 200,000`).
That allowance was set for Gemma, where the same fix costs far less. With Sonnet's long contexts, one re-run of a step
can use it all.

**What Box 4 could not see: blocked calls.** In runs 1–3, 47 of the 145 calls returned an empty reply with
`finish_reason: content_filter`. That is 24 of 30 for H3's TCO Modeller, 18 of 26 for H2's Quantitative Analyst, plus
one planner call (H2), 3 researcher calls (H2) and 1 (r1).
- **Cost:** the API reported 558,058 input tokens for them, about **$1.12 of the $6.17**.
- **How Amoeba handled them:** each blocked reply got D123's repair call, which was often blocked too. The turn was then
  counted as an "unreadable reply". Box 4's watch saw those as `unreadable_reply` (cause `format`) or as a step that
  never finished.
- **What triggers it is not known.** I compared the blocked prompts with the allowed ones. Every term I checked
  appears in both ("sandbox", "Bash", "BLOCKED", "API key", "Missing Key"). The same kind of prompt is blocked one time
  and passes the next.

**Why the H3 modeller had no Bash** (three gaps that add up; all are in the trace):
1. Box 2 requested `python_interpreter` for "TCO Modeller and Fleet Feasibility Analyst; Cost Model Verifier", two roles
   in one field. The toolbox step matched no helper to that string (`no_helper`), so the request was dropped.
2. The modeller's own request for `Bash` found only internet tools at score 2, and the AI pick chose none
   (`pick_none`). `local:Bash` was not among the candidates: its description ("run Python code or a shell command …")
   never says "bash". Read and Write were matched to their local tools.
3. Box 4's rung-2 grant listed `local:Bash` (score 1) next to an internet sandbox MCP (score 1). It took the internet
   one first, whose connection failed, and did not try the next candidate.

In H2 the analyst did get `local:Bash` at the toolbox step and used it 7 times.

### Doc skills and local tools
| Run | Skills attached | Local tool calls | Files created | Refusals |
|---|---|---|---|---|
| H3 | docx → Memo Editor and Document Assembler (its step 7 never ran) | 1 (`local:Write` of `tco_model.py`) | `tco_model.py` (2,599 bytes, never executed) | none |
| H2 | none | 7 `local:Bash`: read the fetched sources, wrote and ran `build.py`. One run failed on a `%` in a chart label and the helper fixed it with `sed`. | `build.py`, `mi_income_indiana_us.csv`, `plotted_values.json`, `real_median_household_income.png` | 1: `unsafe_command`, "path outside the workspace: /parameter" |
| r1 | xlsx → Data and Visualization Analyst, Data QA Reviewer; docx → Technical Report Author, Data QA Reviewer | 0 (stopped at step 1) | none | none |

No `.docx` was produced in any run: every memo or report step comes after the step where the task stopped.

### Box 5 (around every box)
- **Model:** all calls went to `claude-sonnet-5-5`. The router's only candidate was that model (the profile limits it,
  D126). No fallbacks.
- **Temperature:** not sent, as set.
- **No rate-limit waits.**

## Compared with Gemma

| | Sonnet 5.5 (these runs) | Gemma 4 31B |
|---|---|---|
| H3 outcome | stopped by Box 4 at step 3 of 7 | run 4 (`eval/manual/h3/d9d4ebc3`): stopped by Box 4 at step 4 of 5 (capability: no .docx tool), after the audit's rework of steps 1–3 |
| H3 stuck events | 3 (all step 3) | 5 (run 4) |
| H3 wall / live calls | 19.6 min / 61 → **19 s per call** | 70.7 min / 42 → **101 s per call** |
| H3 cost | $2.43 (+ $0.94 failed first attempt) | $0 (free tier) |
| H2 | stopped by Box 4 at step 3 of 5; 11.6 min, 12 s per call | older run (before Box 4 and local tools): all steps ran, 35 min, 55 s per call |
| r1 | stopped by Box 4 at step 1 of 6; 6.4 min, 17 s per call | older runs (round 1 / round 3, before Box 4): all steps ran, 10.8–14.7 min, 34–44 s per call |

**Speed.** Sonnet answers 3–5× faster per call. Its runs are still not short, because it writes much more: plans of
15–19k tokens, and step outputs of 5–10k characters.

**Stuck counts are only comparable on H3.** The H2 and r1 Gemma runs predate Box 4 (D117), so "0 stuck" there means
"no watch", not "no problem".

## What went wrong, in order of weight
1. **Blocked calls (`content_filter`).** 32% of the calls in runs 1–3 came back empty, concentrated in the two modelling
   roles. They cost about $1.12 and used up the turns of the two steps that got stuck. Amoeba treats an empty filtered
   reply as an unreadable one and makes a repair call, and Box 4 diagnoses it as format or capability.
2. **Bash never reached the H3 modeller** (three matching gaps, above). With Bash it would have run its own
   `tco_model.py`.
3. **Box 4's limits fit Gemma, not Sonnet.** One more-turns fix used 270,099 tokens and exhausted the 200,000-token
   allowance (H2). A split step inherits its parent's fix count, so the first sub-step was stopped before any fix (H3).
4. **The proposer's work-around was refused twice by plain code** (r1): once for length (495 > 300 characters), once for
   the word "skip". The more-turns fix that fitted r1 was never offered, because a partial step does not raise
   `max_turns`.
5. **A BLOCKED line went unseen** (H2): step 1 wrote "**BLOCKED:** Census API key", in bold, and plain code recorded
   nothing as lacked, so no signal fired and step 3 worked from missing inputs.
6. **Labels.** `team.yaml` still names `gemma-4-31b` per helper (the configured default). `result.json` was fixed in
   `8e91f38`; the failed first attempt predates the fix.

## Notes
- **In-process local tools.** As asked, local tools ran in this container (`AMOEBA_SANDBOX=1`), not in a sandbox.
  Commands go through Amoeba's gate (one refusal, above). The helpers' environment carries no keys, but code they write
  could read files elsewhere on this machine.
- **No code was changed during the runs.** The fixes for points 1–6 are not made; they are listed for your decision.
- **Spend:** $6.17 of $20 ($0.94 of it the failed first attempt). The $15 stop-and-ask line was never reached.

Key scan of `eval/manual/sonnet/` (283 files, 12.7 MB; key patterns and the three real key values): clean.
