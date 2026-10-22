# Adaptation report

## Step 1 — cause missing_data, tool_error

**Fixes tried:**
1. set_run_option:max_turns (rung 1, on step 1, {"max_turns": 9}): failed: still stuck (missing_data: missing data: Full URL and exact title of the April 26, 2021 apportionment press release — saved copy of the page gave only a truncated URL; missing data: Header text of the resident-population column) — 63,544 tokens
2. scoped_round (rung D, on step 1): failed: none recovered and neither cleared a signal: the original state is kept — 170,353 tokens
3. scoped_round (rung D, on step 1): failed: none recovered and neither cleared a signal: the original state is kept — 132,302 tokens

**Not tried:**
- set_run_option:max_turns

## Step 2 — cause missing_data

**Fixes tried:**
- none

## Step 3 — cause checks

**Fixes tried:**
- none

**Kept going (no fix recovered the step; only its dependents were skipped):**
- step 1: missing_data — limit: 3 fixes per step
- step 2: missing_data — limit: adaptation tokens 366,199 of 352,882
- step 3: checks — limit: adaptation tokens 366,199 of 308,772

**Limits:** a model of this run has no price in prices.yaml, so the adaptation's USD limit could not be computed; only its token limit was enforced.

**Steps built on an upstream output from before its re-run:**
- none

Adaptation used 366,199 tokens.
