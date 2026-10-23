# Adaptation report

## Step 1 — cause capability

**Fixes tried:**
1. grant_tool (rung 2, on step 1, {"items": ["Census API access", "data.census.gov table fetch"], "exclude": []}): failed: still stuck (capability: check contract:cites_every_figure still fails after the retry turn: 2 figure(s) without a source tag; check contract:figures_dated still fails after the retry turn: 1 web figure(s) without a date) — 63,127 tokens
2. scoped_round (rung D, on step 1): failed: none recovered and neither cleared a signal: the original state is kept — 199,495 tokens
3. set_run_option:max_turns (rung 1, on step 1, {"max_turns": 9}): failed: still stuck (capability: check contract:cites_every_figure still fails after the retry turn: 2 figure(s) without a source tag; check contract:figures_dated still fails after the retry turn: 1 web figure(s) without a date) — 80,136 tokens

**Not tried:**
- grant_tool
- tool writer: no offline library for Census API access, data.census.gov table fetch
- tool writer: no offline library for Census API access, data.census.gov table fetch, Census API access

## Step 2 — cause missing_data

**Fixes tried:**
1. set_run_option:max_turns (rung 1, on step 2, {"max_turns": 9}): failed: not stuck but partial (mislabelled citation: '0:06' not in S44) — 43,298 tokens

## Step 3 — cause missing_input

**Fixes tried:**
- none

## Step 4 — cause missing_input

**Fixes tried:**
- none

## Step 5 — cause missing_input

**Fixes tried:**
1. rerun_upstream (rung input, on step 1, {"then": 5, "add_done_when": "ACS B19013 1-year values for Indiana and United States, 2015 and 2023, with release year"}): failed: still stuck (missing_input: missing input: data.census.gov table rendering (from step 1); missing input: B19013 ACS 1-year values for Indiana and the United States, 2015 and 2023 — step 1 delivered none (from step 1, 2)) — 302,639 tokens

## Step 6 — cause missing_input

**Fixes tried:**
- none

## Step 7 — cause missing_input

**Fixes tried:**
- none

## Step 8 — cause missing_input

**Fixes tried:**
- none

**Kept going (no fix recovered the step; only its dependents were skipped):**
- step 1: capability — limit: 3 fixes per step
- step 3: missing_input — limit: adaptation tokens 386,056 of 355,496
- step 5: missing_input — limit: adaptation tokens 688,695 of 554,198
- step 4: missing_input — limit: adaptation tokens 688,695 of 541,857
- step 6: missing_input — limit: adaptation tokens 688,695 of 567,940
- step 7: missing_input — limit: adaptation tokens 688,695 of 600,479
- step 8: missing_input — limit: adaptation tokens 688,695 of 585,585

**Steps built on an upstream output from before its re-run:**
- step 3 used step 1's earlier output (not redone)

Adaptation used 688,695 tokens ($1.1715).
