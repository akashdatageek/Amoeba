# D151 — budgets scale with the model and are shared fairly

Status: **built** (branch claude/run-gaps). These gaps were found in the fuel run 71d2f910.

## Why
- **The allowance did not fit the model.** All fixes of one task could use 200,000 tokens, or a quarter of the
  run cap when that was larger. That number was set for a small model. In 71d2f910, one step attempt on Sonnet cost
  69k–147k tokens, so the allowance came to about three re-runs, and it was the same whatever the model.
- **One step took the budget from the others.** In 71d2f910, step 1 used 457k of the 1.27M tokens left after
  planning: its first attempt plus three fixes. Steps 2–5 got no fixes (the adaptation allowance was spent). Steps
  6–8 never ran, because the run cap was reached.

## What
1. **The fix allowance is a multiple of the run's average step-attempt cost so far.**
   - `adapt.fix_tokens_per_attempt: 6` in adapt.yaml replaces `max_tokens_per_task` and `tokens_share_of_run_cap`.
   - The average is the billed tokens since the plan run started, divided by the step attempts saved so far.
   - It is recomputed before each fix.
   - A model that reads or thinks three times as much gets three times the room.
   - **Why 6:** a fix re-runs the step, and a re-run with more turns or a longer input costs about 1.5–2 first
     attempts (in 71d2f910: 107k, 128k and 144k after a 69k first attempt), plus a proposer call. Six attempts' worth
     is room for about three fixes, which is the per-step limit.
   - When no attempt cost has been measured yet (an attempt that billed nothing), the token check is skipped. The
     other limits (fixes per step and per task, $) still apply.
2. **Each step gets a share of the run cap.**
   - This applies only with `--max-tokens-per-run`.
   - When step n starts, its share is `run_guard.step_share` (1.5) × (cap − used) / (steps not yet run, this one
     included).
   - Everything spent while step n is the current step counts toward its share: attempts, fixes, the proposer, and
     rework of its producers.
   - Before each fix, and before a verifier's rework, code checks the share. A step that has reached it stops
     retrying, and the run goes on.
   - Such a step is recorded in `adaptation.kept_going` with the reason, for example "limit: step 1 used 7,644 tokens,
     its share of the run cap (6,297 = 1.5 x 16,792 tokens left / 4 steps not yet run); the rest is kept for the
     steps not yet run".
   - This holds whatever `--failed-step` says, because the point is that the later steps run.
   - **Why 1.5:** a hard step may borrow half a share from the others, but no more. The check comes before a retry,
     so a step can go over by at most one attempt.
3. `adaptation.token_allowance` and `adaptation.step_shares` record both numbers in result.json.

In 71d2f910 this would have meant the following. Step 1's share would have been 1.5 × 1.27M / 8 = 238k. Its first
fix ran at 69k spent; the second was allowed at 179k; at 310k it would have stopped. That leaves about 150k more for
steps 2–8.

## Tests (written first)
tests/test_budgets_d151.py.
- **Before the fix:**
  - The 3× model test raised `KeyError: 'token_allowance'`: there was no allowance that scaled; it was the fixed
    200,000 for both models.
  - The share test failed: the run cap stopped the run (`budget_stop`) while step 1 was being fixed, and steps 2–4
    never ran.
- **After the fix**, both tests pass:
  - the heavy model's allowance is 3.0× the light one's;
  - step 1 is kept_going with the share reason, steps 1–4 all run, and there is no budget_stop.
- D129's allowance test was rewritten for the new rule. Two tests that set `max_tokens_per_task` now set
  `fix_tokens_per_attempt`.
- Full suite: 1004 passed, 9 skipped.
