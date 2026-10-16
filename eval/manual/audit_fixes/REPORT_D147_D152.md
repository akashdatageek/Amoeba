# D147–D152: the six gaps from run 71d2f910, and the rerun

Branch `claude/run-gaps`, made from the code run 71d2f910 used (PR #44). There is one commit per decision, each
with its tests written first and a design note in `docs/design/`.

**Rerun 4b51a368 (Oct 16).**
- Same command and flags as 71d2f910: `--protocol v2`, plain `claude-sonnet` profile, `--max-tokens-per-run
  1500000`, `--max-usd-per-run 4`, adapt on. No plan or prompt edits.
- Code at commit 4baa74d.
- The run folder is `live/4b51a368-328e-4f35-95d1-3bd5889f2c72`.

## Tests: before and after each fix

| D | What it changes | Before the fix | After |
|---|---|---|---|
| D147 | Every cut says where the whole copy is. A cut page names its saved `sources/S#_….txt` file and says "open it with local:Read". A table excerpt shows its first rows, matching rows, last rows and its path. | 3 of 4 tests failed (no saved path; no last row) | 4 pass |
| D148 | The gate judges what a command does, not its text. A path counts as unsafe only if it resolves outside the workspace, after any `cd`. Each refusal names the exact part that matched and how to rewrite it. | 7 of 9 failed (`cd sources && python3 -c "open('../x.csv','w')"` was refused) | 9 pass |
| D149 | A held tool refused 2 or more times in one step for the same reason makes the cause tool_error. BLOCKED lines in any markdown name their capability. | the module could not import; the replay of 71d2f910 step 1 attempt 3 gave missing_data | 8 pass (the replay gives tool_error) |
| D150 | A fix kind that failed on a step is never tried again on it. After one failed code fix, the fix proposer is next. | the fixes were max_turns, max_turns, then the proposer | 2 pass |
| D151 | The fix allowance is 6 × the average step-attempt cost. With a run cap, each step may spend 1.5 × (cap − used) / steps not yet run; at its share it stops retrying (kept_going) and the later steps still run. | no scaling allowance (KeyError); the cap stopped the run during step 1's fixes | 2 pass |
| D152 | The cut note is not checked as cited text. The reply room follows each role group's largest reply (×1.5, at most ×2). | all 4 failed | 4 pass |

- **D149:** the exact `**BLOCKED:**` test that was asked for already passed before (D128 fixed it). That form of the
  gap is not real; only the `*BLOCKED:*` and `` `BLOCKED:` `` forms were.
- Full offline suite: 1008 passed, 9 skipped.
- Toy runs: flat mean score 1.000, 4,802.6 tokens, 6.35 calls; boss_reviewers 1.000, 3,756.7 tokens, 6.00 calls.

## The rerun, step by step
The planner made an 11-step plan this time; 71d2f910 had 8. Steps 1, 2 and 3 have no dependencies and ran first:
1. the inputs register;
2. the EIA prices (step 1 in 71d2f910);
3. ATRI (step 2 in 71d2f910).

| Step | Status | Tokens | What each fix did |
|---|---|---|---|
| 1 Inputs and assumptions register | **done**, first attempt | 146k | – |
| 2 52 weeks of EIA Midwest diesel prices | partial (`figures_dated`: one web figure without a date) | 189k | One max_turns fix (101k), which failed. Then **D151**: the step had used 188,994 tokens, over its share of 172,969, so it stopped retrying and was marked kept_going with that reason. |
| 3 Latest ATRI marginal cost per mile | partial (a mislabelled citation: the ATRI report's title quoted against S29; 0.481 against S36) | 143k | One max_turns fix (77k). After it the step was no longer stuck, only partial, so no further fix applied. |
| 4 Formula workbook | partial (`domain_xlsx_formulas`: Inputs!B16 = 2.336 typed in, not a formula) | 249k | None. **D151**: the first attempt alone was over the step's share of 154,047, so kept_going. |
| 5 Stats and band table in Python | partial (the report title quoted against S29) | 215k | None. **D151**: over its share of 122,753, so kept_going. |
| 6 Price and surcharge chart | partial (`image_exists`) | 208k | None. The run had reached 85% of the cap, so finish mode skipped fixes. |
| 7 Verify | started; stopped by the run cap during the step | 183k | – |
| 8–11 Memo content, Word memo, verify memo, final answer | not run | – | – |

The run stopped at the 1.5M token cap (billed 1,532,330). The answer was assembled by code from steps 1–6.

## The questions
- **Did the EIA step read the saved page by itself?** **Yes.**
  - The EIA step (step 2 here; step 1 in 71d2f910) was shown the D147 note "the whole page is in
    sources/S10_Weekly_Midwest_No_2_Diesel_Retail_Prices.txt". S10 is this run's counterpart of S4 in the last run;
    source numbers are given per run.
  - It then opened the file itself, about ten times, with `local:Bash` (`cd sources; grep … S10*.txt`, `sed`, a
    Python parser). It wrote `eia_prices.csv` from it: 52 distinct weeks, 2025-09-29 to 2026-09-21, series
    EMD_EPD2D_PTE_R20_DPG.
  - Nobody pointed it there; the note did.
- **Did the ATRI step find the ATRI total in its saved sources?** **Yes.**
  - It read S29, S30, S36 and S28 from `sources/` with `grep`.
  - It found the total, **$2.336 per mile**, in S29, and the fuel part, **48.2 cents** ($0.482), in S36.
  - The assembled answer gives both figures, 2.336 and 0.482.
  - The step stayed partial for two reasons. It quoted the full report title against S29, a press release that
    words the title differently. It also cited 0.481 (a derived figure) to S36. Both are real citation-check
    findings, not the D152 bug.
- **Blocked calls:** **0 of 47** local calls were refused. In 71d2f910, the gate refused 4 local:Bash calls (`..` and
  `/tmp/x` text).
- **Replies cut at the length limit:** **0.** In 71d2f910 there was 1. D152 raised the reply room on 53 calls; most
  went just above 8,192 (to 8,291).
- **Cost:** **$3.11.** The $4 limit was never close.
- **Where the tokens went** (1,494,968 total, 91 calls):
  - drafting and planning: 201k;
  - steps 1–7: 1.33M, in first attempts of 143k–249k each;
  - fixes: 178k (step 2: 101k, step 3: 77k).
  - Input is 92% of the tokens (1,379,776 in; 731k of it read from the prompt cache). Each helper turn re-sends the
    step's context, up to 55k tokens per turn, over 6–11 turns.

## Compared with 71d2f910

| | 71d2f910 (before) | 4b51a368 (after D147–D152) |
|---|---|---|
| Plan steps | 8 | 11 |
| Steps run | 5 (1–5); 6–8 not run | 6 (1–6) + step 7 stopped part-way; 8–11 not run |
| Steps done | 0 | 1 (step 1) |
| EIA step | partial after 4 attempts (3 fixes: max_turns 9, max_turns 12, check_retry_turns 3) | partial after 1 fix, then stopped at its share (D151) |
| EIA step read the saved page by itself | no (S4 not opened; history rows from 1996–97 only) | yes: S10, about 10 times; 52 weeks parsed |
| ATRI total found | no (cut at "$2.") | yes: $2.336 (S29), fuel 48.2¢ (S36) |
| Fixes | 3 on step 1, then the allowance was used up | 2 (steps 2 and 3); steps 4 and 5 stopped at their share |
| Gate refusals | 4 | 0 |
| Cut-marker citation finding | 1 ("971 characters cut") | 0 |
| Replies cut at the length limit | 1 | 0 |
| LLM calls | 102 | 91 |
| Tokens | 1,487,356 | 1,494,968 |
| Cost | $3.30 | $3.11 |
| Why it ended | token cap, before step 6 | token cap, during step 7 |

## What this run shows
- **D147 (cut notes)** worked: both research steps found their figures in the saved copies.
- **D148 (gate):** no false refusals.
- **D152 (two bugs):** no cut replies and no cut-marker finding.
- **D151 (shares)** worked as designed: a failing step stopped retrying at its share, and the run went on.
- **The deliverables were still not reached.** A share caps retries; it cannot make a first attempt cheaper. Here the
  first attempts alone cost 143k–249k tokens each. Eleven steps at about 200k each are more than the 1.3M left after
  planning, so the memo steps (8–11) did not run. The next lever is the cost of one attempt: the context re-sent on
  every turn. That is not part of this change.
- **D149 and D150 were not exercised** in this run. No tool was refused twice, and no step reached a second fix: the
  share or finish mode came first.
