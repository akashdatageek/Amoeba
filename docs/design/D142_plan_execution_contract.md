# D142 — the plan–execution contract

Status: **built** (branch claude/audit-fixes). This is the audit prompt's "D139", which it called the most important
logic fix.

## Why
Box 2 writes what "done" means for each step, but Box 3 never evaluated it. `done_when` fed only a format guess
(`step_checks`) and the prompts. So a step could promise "a 2-page Word memo with a cost table" and pass with a
5-page memo and no table, as long as the output text had two headings.

## What
1. **Typed checks on every step** (`DraftPlanStep.checks`, `PlanStep.checks`). Each is `{name, params, covers}`,
   taken from a fixed vocabulary that plain code can evaluate (`amoeba/task/contract.py` `VOCAB`):
   - files: `file_exists {kind, name?}`;
   - Word: `docx_pages_max {n}`, `docx_words_between {min, max}`, `docx_has_table {min_rows?}`;
   - Excel: `xlsx_rows_min {n, sheet?}`, `xlsx_columns {names}`, `xlsx_has_formulas`;
   - CSV: `csv_rows_min {n}`, `csv_columns {names}`;
   - images: `image_exists {kind: png|svg, min_px?}`;
   - the output text: `output_has_table {min_rows?}`, `output_has_list {min_items?}`, `output_mentions {terms}`;
   - sources and dates: `cites_every_figure` (the D33 provenance count), `figures_dated` (D110's undated figures);
   - `verdict_present` for verify steps;
   - `not_sent_fallback`: a file marked NOT SENT, plus a Limitations line that says so.

   Word pages are counted from explicit page breaks. Without them, pages are estimated at 500 words per page, and
   the detail says "estimated". `done_when` stays one sentence, for the reviewers.
2. **How a plan gets its checks.**
   - Under v2, `PlanOut`'s steps carry `checks`, and plan_create_v2 lists the vocabulary.
   - Under legacy, a step may carry an optional `checks:` line holding a JSON list. Unreadable JSON is kept as an
     `unparsed` check, so checks_valid reports it rather than dropping it. The legacy prompts are unchanged.
   - A step with no checks is judged on the checks its format markers imply (`derived_checks`), as before.
3. **Three new HARD quality checks** (task/quality.py), sent back to the planner through `gate_suggestions`:
   - `requirements_checked`: every requirement is covered by at least one step check;
   - `checks_valid`: every check is in the vocabulary, with well-formed parameters;
   - `checks_reachable`: no step has more than 6 checks, and a file check sits only on a step whose role has a
     file-writing tool (installed or requested).

   A plan with no checks at all gets n/a on all three.
4. **Box 3 runs a step's checks** after its Final Output (`PlanRunner.planned_checks`), on the output text and on the
   step's workspace files (the answer step sees every file). A result named `contract:<check>` joins the step's
   other checks:
   - a failure gets the D61 check-retry turn, then the step ends partial or incomplete;
   - it feeds Box 4's `checks` cause, with the check name as evidence.

   Results are kept in meta `contract_checks` and in the trace event `contract_checks`. The step's helpers see
   their checks in the step detail ("checked by plain code when you finish: ...").
5. **The final requirement check** (task/deliverables.py) has a stricter rule for "met".
   - A requirement is `met` only when every check covering it passed, and its key terms appear in the answer body
     above the Limitations section.
   - Terms found only under Limitations make it `reported_missing`.
   - The old measure stays as `status_legacy` on each requirement and as `met_legacy` in result.json's
     deliverables, so old and new runs can be compared.

## As built (Oct 16)
- A `reported_missing` requirement is unmet, but it does not count toward `no_deliverable`, and the refine turn
  is not asked about it, because the answer already says honestly that it is missing. (Departure: the prompt did
  not say how reported_missing counts for no_deliverable.)
- PlanOut now carries free-form check params, so it always goes as json_prompt (D141). Claude refused to compile
  its grammar anyway.
- The checks run in both protocols whenever a step has them.

## Tests
tests/test_contract_d142.py:
- validation of every parameter type;
- the legacy `checks:` line and an unparsed one;
- derived checks;
- PlanOut rendered into the legacy text and parsed back;
- every evaluator on real docx, xlsx, csv and png files;
- invalid checks and unreadable files fail without crashing;
- the three HARD checks and their gate lines;
- Box 3 runs the checks with the retry turn and records them, a failed check feeds Box 4's checks cause, and the
  step detail lists the checks;
- `met`, `reported_missing` and `met_legacy`.

tests/test_quality.py counts the three new n/a checks.
