# Adaptation report

## Step 2 — cause missing_data, tool_error

**Fixes tried:**
1. set_run_option:max_turns (rung 1, on step 2, {"max_turns": 9}): failed: still stuck (missing_data: missing data: Exact number of tests in test_wordfreq.py and whether all of E01–E33 are covered — the count was cut from the displayed output of the tool r; missing data: Verbatim middle of main() in t) — 88,272 tokens
2. scoped_round (rung D, on step 2): failed: none recovered and neither cleared a signal: the original state is kept — 295,292 tokens
3. work_around (rung D, on step 2, {"capability": "Exact test count and E01\u2013E33 coverage from the cut-off tool output", "method": "Output the full wordfreq.py as written from the spec. Report only the four smoke runs actually seen (sample, missing file, -n 0, empty file). Leave the test count and E01\u2013E33 coverage to the tes): failed: none recovered and neither cleared a signal: the original state is kept — 91,310 tokens

**Not tried:**
- set_run_option:max_turns

## Step 3 — cause missing_data

**Fixes tried:**
- none

## Step 4 — cause missing_data

**Fixes tried:**
- none

## Step 7 — cause missing_input

**Fixes tried:**
1. rerun_upstream (rung input, on step 2, {"then": 7, "add_done_when": "Complete test_wordfreq.py source; Verbatim wordfreq.py"}): failed: still stuck (missing_input: missing input: Complete verbatim wordfreq.py — Step 2 (from step 2, 3, 4, 6); missing input: Complete verbatim test_wordfreq.py — Step 3 (from step 2, 3, 4, 6)) — 139,541 tokens

**Kept going (no fix recovered the step; only its dependents were skipped):**
- step 2: missing_data — limit: 3 fixes per step
- step 3: missing_data — limit: adaptation tokens 474,874 of 460,083
- step 4: missing_data — limit: adaptation tokens 474,874 of 421,344
- step 7: missing_input — limit: adaptation tokens 614,415 of 518,328

**Steps built on an upstream output from before its re-run:**
- step 4 used step 2's earlier output (not redone)
- step 5 used step 2's earlier output (not redone)

Adaptation used 614,415 tokens ($1.2760).
