# Part 2, Step 4: the Stage 1 runs

Each `tasks/stage1_dev.jsonl` task ran once, one at a time, in the runner container. Profile claude-sonnet+gemma-verify,
the Part 2 flags (`probes/flags.sh`), `--max-usd-per-run 6`, `--seed 0`, `--lessons off`, `--lessons-write on`, one
shared library (`/out/lessons`, snapshot in `lessons_after_step4/`). Scores come from today's frozen judge
(`eval/stage1/rescore.py`): two judge bugs were found and fixed during this step, and every run was re-scored with the
fixed judge. No team run was repeated for that. Table: `python eval/stage1/report.py eval/stage1/step4`.

| # | category | task | score (parts) | status | stuck steps / fixes | honest stop | cost | min | calls |
|---|---|---|---|---|---|---|---|---|---|
| 1 | research | probe-h2-income | 0.425 (answer_key 0.4, files 0.5) | no_deliverable | 1, 2, 5 / 5 | yes: "no ACS number was filled from memory" | $3.74 | 41 | 185 |
| 2 | exact | probe-h1-freight | **1.0** (answer_key 1.0, files 1.0) | partial* | - / 0 | n/a | $0.65 | 14 | 28 |
| 3 | files | probe-b4-fuel | **0.0** | stalled | 1 / 4 | no (stopped) | $2.25 | 19 | 92 |
| 4 | software | wordfreq-cli | **1.0** (12/12 hidden tests) | partial* | 2, 7 / 4 | n/a | $2.86 | 35 | 121 |
| 5 | chain | clickstream-pipeline | 0.714 (rubric) | partial* | 2 / 2 | n/a | $5.95 | 66 | 173 |
| 6 | decision | db-choice | 0.143 (rubric) | infra_error (Gemma 429) | 1, 2 / 5 | yes, about the steps that did not run | $5.97 | 66 | 193 |
| 7 | missing capability | soil-gateway-missing | **1.0** (rubric) | no_deliverable* | 1, 2 / 5 | **yes**, with scripts and a draft order | $2.52 | 27 | 101 |
| 8 | drone | drone-field-a | **1.0** (answer_key 1.0, files 1.0) | partial* | 3 / 1 | n/a | $0.82 | 13 | 45 |

\* The status reflects Amoeba's own checks, not the score. "partial" comes mostly from the D74 citation check's false
positives (task inputs, counts and timestamps such as '0:47' flagged as uncited figures) and from tool output shown
cut off. For task 7, the live-data requirements can never be met from here.

Mean score 0.66 over the 8 tasks. Spend **$31.12 of $50**: $24.75 on the eight scored runs plus $6.37 on attempts
killed by three container restarts (`step4/aborted/`: H1 $0.006, clickstream $0.55, db-choice $5.81, and a first
start at $0.003).

## Box 4 rounds (from rounds.jsonl)
Every round had two scoped edits (inv and dom). A control was run whenever lesson writing was on.
- **No round picked a winner.** No probe recovered its step, and in each round both probes stayed `partial`. Only
  the fuel run picked an edit (a dom work_around that cleared the capability signal); the step still ended partial.
- Controls: 6 measured, 5 skipped. Two skips are the db-choice re-run, where lesson writing was off. Three are
  because "the allowance holds only 1–2 probes: the edits come first".
- Verdicts in the library after Step 4: helped 1, hurt 3, no_effect 6, confounded 1, uncontrolled 6.
- Verdicts: see the library snapshot. One lesson was written, `capability__work_around__dom__L1`
  (unreviewed). It came from db-choice's first attempt, the one killed by a restart.

## db-choice: two attempts
The first attempt was killed by a container restart at $5.81. It had already written three verdicts and lesson L1 to
the library. The re-run (scored above) ran with `--lessons-write off`, so the task counts once in the library. The
score comes from the re-run; the library evidence comes from the first attempt. A rollback by replay was not exact:
the evidence rows do not keep the edit parameters that edit.json collects. A copy of the library at that moment is
kept outside the repository.

## Judge-access audit
Each run's trace and workspace were searched for the judge folders (`*_keys`, `*_hidden`). All eight runs are clean.
The team's in-process Bash could read the image's repository, so this check after the run is what guards the keys.

## Failures, sorted
| kind | where | what |
|---|---|---|
| tool/setting | H2 | the Census API now needs a key (none configured), and data.census.gov renders with JavaScript; the ACS brief PDFs that hold the figures were never found |
| tool/setting | judge (fixed) | rubric grader's 1,024-token room cut Gemma off before its SCORE line, so every rubric scored 0 (90f03af); the parser took the first SCORE line, so db-choice got 1.0 for a 1/7 reply (11a6519) |
| tool/setting | db-choice | Gemma's free tier answered 429 "exceeded your current quota"; the run ended as infra_error instead of the verifier falling back to Sonnet |
| tool/setting | all | container restarts (three in five hours) killed runs in progress |
| Amoeba's logic | fuel | a step with usable output (52 weeks of PADD 2 prices) stayed partial on small check failures; Box 4 retried it until the D122 stall stop (60 calls with no progress), and the other nine steps never ran |
| Amoeba's logic | all | the D74 citation check flags task inputs, counts and timestamps as uncited figures, so most steps end partial and Box 4 spends on them |
| Amoeba's logic | wordfreq, H2 | tool output shown cut off is read as missing data, though the full output is saved in tool_results/ |
| model reasoning | clickstream | the runbook was written to a file, but its on-call steps were not in the answer (rubric point 6) |
| model reasoning | H2 | the team searched the API and data.census.gov over and over instead of looking for the published briefs |
