# D150 — fixes don't waste their tries

Status: **built** (branch claude/run-gaps). This gap was found in the fuel run 71d2f910.

## Why
- In 71d2f910, step 1 used its three fix tries like this: max_turns 9, then max_turns 12, then check_retry_turns 3.
  All three failed.
- The second max_turns try had a new value, so its fix key was new, and the "never the same fix twice" rule did not
  stop it. Yet more turns had already failed to help, so giving still more turns repeated a kind of fix that had
  already failed.
- The fix proposer reads the evidence and can change the step itself. It was only reached after every code fix had
  been used up, and by then the step's tries were gone.

## What
In `PlanRunner.fix_stuck`:
1. **A kind that failed is not tried again on that step.** Before picking a code fix, code collects the kinds of the
   step's failed fixes (for example `set_run_option:max_turns`) and skips any candidate of the same kind, whatever
   its value. Each skip is logged once as `fix_skipped` with the note "<kind> already failed on step <n>; not tried
   again".
2. **After a failed code fix, the proposer goes next.** When one code fix (rung 1–3) has failed on the step and the
   proposer has not been asked yet for this step, the next try is the fix proposer (rung D).
3. **If the proposer has nothing**, meaning no edit is allowed or there is no valid reply, the loop goes back to
   code fixes of kinds not yet tried. If none are left, it stops as before.

The model still decides the edit. Code only decides the order of the tries and what is never repeated. The limits
(fixes per step, per task, tokens, $) are unchanged.

## Tests (written first)
tests/test_fix_tries_d150.py: step 1 stalls on calc until max_turns, and the proposer replies with no edit.
- **Before the fix**, both tests failed. Step 1's fixes were
  `[(set_run_option:max_turns, 1), (set_run_option:max_turns, 1), (fix_proposer, D)]`: the same kind was tried twice
  and the proposer came last.
- **After the fix**, both tests pass. The proposer call comes right after the first failed max_turns fix, and no
  failed kind repeats.
- Full suite: 1002 passed, 9 skipped.
