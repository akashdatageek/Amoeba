# Adaptation report

## Step 2 — cause missing_data

**Fixes tried:**
1. set_run_option:max_turns (rung 1, on step 2, {"max_turns": 9}): failed: still stuck (missing_data: missing data: Full text of SQLite WAL page — only part of S1 seen; WAL side-file behaviour marked [unverified]) — 97,861 tokens
2. scoped_round (rung D, on step 2): failed: none recovered: the candidate that cleared most signals (fewest new) is the base (base: inv add_role_rule) — 145,443 tokens

**Not tried:**
- set_run_option:max_turns

**Steps built on an upstream output from before its re-run:**
- none

Adaptation used 243,304 tokens ($0.4467).
