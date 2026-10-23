# Part 2 report: the first live tests (Stage 1)

Runner container (`scripts/vm/`), profile claude-sonnet+gemma-verify, protocol v2, plan topology, d24 drafts, web
tools, plan search on, adapt on, proposer scoped, pool on, local tools in-process. Run stop `--max-usd-per-run`, 5 M
token runaway guard. Scores come from the frozen judge as of `11a6519` (every run re-scored with it; no team run
repeated). Costs are at Sonnet 5.5 list prices with prompt-cache reads and writes priced apart; Gemma is free.
Per-step details: `STEP2_PROBES.md`, `STEP4_RUNS.md`; tables: `python eval/stage1/report.py eval/stage1/step4` (and
`step5`).

**Spend: $54.86 of $98 in caps.** Step 2 $6.70 of $8, Step 4 $31.12 of $50 ($6.37 of it on runs killed by
container restarts), Step 5 $17.04 of $40. No lesson approved, `scripts.promote` not run.

## The table

| run | category | task | score (parts) | req. met | stuck steps | Box 4 rounds: edits → probe status (signals cleared/new); control; pick | honest stop | cost | min | calls |
|---|---|---|---|---|---|---|---|---|---|---|
| S4-1 | research | probe-h2-income | 0.425 (key 0.4, files 0.5) | 3/13 | 1, 2, 5 | s1 capability: inv add_tool_guidance → partial (0/0), dom work_around → partial (0/0); control partial; none | yes | $3.74 | 41 | 185 |
| S4-2 | exact | probe-h1-freight | **1.0** (key 1.0, files 1.0) | 6/6 | – | – | n/a | $0.65 | 14 | 28 |
| S4-3 | files | probe-b4-fuel | **0.0** | 0/– | 1 | s1 capability ×3: dom work_around → partial (−1/0), picked; inv add_tool_guidance → partial (0/+1) twice; controls partial, partial, skipped (allowance) | no: stall stop | $2.25 | 19 | 92 |
| S4-4 | software | wordfreq-cli | **1.0** (12/12 hidden tests) | 12/12 | 2, 7 | s2 missing_data ×2: inv add_role_rule → partial (0/+2), dom work_around → partial (0/+1); control partial, then skipped (allowance); none | n/a | $2.86 | 35 | 121 |
| S4-5 | chain | clickstream-pipeline | 0.714 (rubric) | 13/14 | 2 | s2 missing_data: inv add_role_rule → partial (0/+1), dom work_around → partial (0/+1); control partial; none | n/a | $5.95 | 66 | 173 |
| S4-6 | decision | db-choice (re-run†) | 0.143 (rubric) | –/– | 1, 2 | s1, s2 missing_data: dom work_around → partial; no control (lesson writing off in the re-run); none | yes, about the steps that did not run | $5.97 | 66 | 193 |
| S4-7 | missing capability | soil-gateway-missing | **1.0** (rubric) | 3/8 | 1, 2 | s1 capability: inv add_tool_guidance → partial (−1/+1), dom work_around → partial (−1/+2); control partial; none. s2: skipped (allowance) | **yes**, with scripts and a draft order | $2.52 | 27 | 101 |
| S4-8 | drone | drone-field-a | **1.0** (key 1.0, files 1.0) | 8/8 | 3 | – | n/a | $0.82 | 13 | 45 |
| S5-1 | research + tool_error | probe-h2-income s1 | 0.475 (key 0.3, files 1.0) | 4/13 | 1, 2, 3, 7, 9 | s1 capability: inv add_tool_guidance → partial (−2/+1) **hurt**, dom work_around → partial (−2/0) **helped** → lesson L2; control partial; none | yes | $4.08 | 40 | 182 |
| S5-2 | research + tool_error | probe-h2-income s2 | **0.925** (key 0.9, files 1.0) | 3/13 | 1, 2, 5 | s1 capability: both edits → partial, no effect; control partial; none | yes | $3.36 | 44 | 149 |
| S5-3 | files + capability | probe-b4-fuel s1 | **0.0** | 0/– | 1 | s1 missing_data: dom add_role_rule → partial (0/0), no effect; control partial; inv picked | no: stall stop | $2.23 | 19 | 94 |
| S5-4 | files + capability | probe-b4-fuel s2 | 0.8 (files 1.0, key 0.6) | 5/13 | 1, 2, 3 | s1 capability ×2: no-edit round, then both edits → partial, no effect; s2: skipped (allowance) | yes | $5.78 | 58 | 190 |
| S5-5 | drone + missing_input | drone-field-a s1 | **1.0** | 8/9 | – | – (the fault fired once; the step never got stuck) | n/a | $0.71 | 19 | 40 |
| S5-6 | drone + missing_input | drone-field-a s2 | **1.0** | 8/8 | 2 | – (one code fix) | n/a | $0.88 | 13 | 51 |

† db-choice's first attempt was killed by a container restart at $5.81, after it had written three verdicts and lesson
L1 to the library. The scored re-run ran with `--lessons-write off`, so the task counts once in the library.

Means: Step 4 **0.66** over 8 tasks; Step 5 **0.70** over 6 runs. Box 4 recovered no stuck step in any round: every
probe ended `partial`. In Step 5 the first diagnosis on the faulty step matched the injected cause in 2 of the 5
runs where that step got stuck (fuel s2 capability, drone s2 missing_input). The other three read the task's own,
real gap first: Census access (both H2 runs) and missing data (fuel s1).

The judge-access audit is clean on all 14 runs: no trace and no workspace file names `*_keys` or `*_hidden`.

## The library after Step 5 (`lessons_after_step5/`, nothing approved)

| entry | kind | all verdicts (h / hurt / none / conf) | controlled (h / hurt / none / conf) | uncontrolled | tasks |
|---|---|---|---|---|---|
| capability · work_around · dom | family | 3 / 0 / 6 / 2 | 2 / 1 / 3 / 1 | 4 | H2, fuel, db-choice, soil |
| → L1 "use a work_around at domain scope … record every item not found as an explicit gap" | lesson, unreviewed | – | 0 / 0 / 0 / 0 | helped 1 | db-choice (killed attempt) |
| → L2 (same advice, reworded) | lesson, unreviewed | – | **1** / 0 / 0 / 0 | 0 | H2 (S5-1) |
| capability · add_tool_guidance · inv | family | 0 / 3 / 3 / 2 | 0 / 1 / 5 / 0 | 2 | H2, fuel, db-choice, soil |
| missing_data · add_role_rule · dom | family | 0 / 0 / 1 / 0 | 0 / 0 / 1 / 0 | 0 | fuel |
| missing_data · add_role_rule · inv | family | 0 / 2 / 0 / 0 | 0 / 1 / 1 / 0 | 0 | wordfreq, clickstream |
| missing_data · work_around · dom | family | 0 / 3 / 0 / 0 | 0 / 1 / 1 / 0 | 1 | wordfreq, clickstream |

In plain words: the only edit with any controlled "helped" is a domain-scope work_around for a missing capability:
name the gap, use what is available, state the limit. It has 2 controlled helps against 1 controlled hurt, over four
tasks. Both lessons say the same thing. L2 has one controlled help; L1 has none (its one help had no control).
Tool guidance from the "how the team works" scope never helped (1 controlled hurt, 5 no effect). Both missing_data
edits hurt more often than they helped. One more helped verdict (fuel, S4-3) got no lesson: the reflector's text was
refused twice for naming facts of the task.

## Every failure, sorted

**Tool or setting**
- **Census access.** The Census API now needs a key, and none is configured; data.census.gov renders with JavaScript.
  This sank H2 in S4-1 and S5-1. In S5-2 the team found the ACS brief PDFs and scored 0.925.
- **Gemma's free tier as verifier.** At 15 requests a minute, Gemma goes into cooldown, and the router falls back to
  Sonnet for those calls (clickstream: 30 of 42 verifier calls). One fallback marks the whole verify step
  `same_model`, so no run in Steps 4–5 has a verify step counted as independent. db-choice also got a 429 "exceeded
  your current quota", and the run ended as infra_error instead of falling back. Fix options: a paid Gemma tier, or a
  verifier from another family with higher limits.
- **Container restarts.** Three in five hours killed runs in progress ($6.37). The VM guide's advice holds: long
  batches belong on a VM.
- Fixed during Part 2, each with a test written first:
  - the runner's CA for git, curl and Node (dc8dc32);
  - the USD cap now ends Box 4 rather than the run (7aa4c0f);
  - Gemma priced in prices.yaml (d02bcf8);
  - a call that never ran costs nothing (2a63ed5);
  - the D146 verifier is honoured under the router (4d2f794);
  - a task's inputs are not delivered work (582b3d0);
  - the rubric grader's reply room and retry (90f03af), and the last SCORE line is its verdict (11a6519). Before
    these two, rubric tasks scored 0, or 1.0 by mistake.

**Amoeba's logic**
- **The fuel stall (S4-3, S5-3).** Step 1 has usable output (52 weeks of PADD 2 prices), but small check failures
  keep it `partial` (an undated figure, a missing table, an unconfirmed latest week). Box 4 retries it until the D122
  stall stop (60 calls with no progress), and the nine later steps never run. It happened in 2 of 3 fuel runs. The
  third (S5-4) got through and scored 0.8.
- **Citation false positives.** The D74 citation check flags task inputs, counts and timestamps ('4,7,9', '0:47',
  '33') as uncited figures. That makes most steps `partial`, and Box 4 spends on them. Step 2's exact, chain and
  decision probes ended partial with correct work, as did 4 of the 5 Step 4 runs that scored 0.714 or more.
- **Cut-off output read as missing data.** Tool output shown cut off is read as missing data, though the full output
  is in tool_results/. wordfreq spent four Box 4 fixes on this.
- **Budget burned on unsuppliable capabilities.** Box 4 keeps spending on a capability nothing can supply (the Step 2
  missing-capability and research probes ran out of budget before an answer). With $6 the soil task got there.
- **Probe allowance.** Five rounds skipped their control, or their only probe, because "the allowance holds only 0–2
  probes". In those rounds every verdict is uncontrolled.
- **Statuses disagree with scores.** The run status (`partial`, `no_deliverable`) disagrees with the score in 9 of 14
  runs. It reflects Amoeba's own checks, not the result.

**The model's reasoning**
- clickstream: the runbook was written to a file, but its on-call steps were never put in the answer (rubric point 6).
- H2 (S4-1, S5-1): the team retried the API and data.census.gov instead of looking for the published briefs; S5-2 did
  look and nearly aced it.
- db-choice: no schema prototype was run before the cap and the quota stop. A 15-step plan for a $6 run is too wide.

## Not done, on purpose
No lesson is approved. `scripts.promote` was not run. The replay set (`tasks/stage1_replay.jsonl`) was never run. The
draft PR is not merged.
