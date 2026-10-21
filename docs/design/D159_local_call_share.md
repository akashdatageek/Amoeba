# D159 — local-tool calls scale with the plan

Status: **built** (branch claude/gemma-preflight, Oct 21).

## Why
A run could make at most 60 local-tool calls (Bash, Read, Write, …), whatever its plan. That number was set when
plans had about five steps (12 calls each). An 11-step plan that needs 10 calls per step was stopped at step 7. The
later steps were refused with "run_cap" even though no step had used more than its fair part. The opposite also
happened: one step could use all 60 calls, and the steps after it got none. D151 fixed both problems for tokens;
this does the same for local calls.

## What
1. **The run's allowance scales with the plan:** `calls_per_step × planned steps`.
   - With `calls_per_step: 12`, a 5-step plan gets 60, the same as before; an 11-step plan gets 132.
   - A re-plan that adds steps raises it. It never shrinks.
   - Without a plan (flat, boss_reviewers, the preflight) the run gets `calls_per_step × 5` = 60, as before.
   - `max_calls_per_run`, when set to a number, is a fixed cap instead. It is null by default.
2. **Each step gets a share.** When step n starts, its share is
   `step_share × (allowance − calls used) / steps not yet run (this one included)`.
   - A step that has used its share is refused with `step_share`. The refusal names the numbers and says the rest is
     kept for the steps not yet run, and the helper is told to finish with what it has or say what is missing.
   - A fix re-run of the step (Box 4) starts a fresh share from what is left, as D151 does.
3. **The per-step ceiling stays.** `max_calls_per_step: 20` still caps one step attempt, whatever its share.
4. **Recorded.** result.json `local_step_shares: {step: {share, left, not_run, factor}}`.

## The numbers
- **12 calls per step:** it is the old 60 / 5. A plan of the old size is treated exactly as before, so nothing
  that passed before is newly refused.
- **1.5:** this is D151's factor. A hard step may borrow half a share from the others, but no more.
- **Examples.** In an 11-step plan, step 1's share is 1.5 × 132 / 11 = 18. If every step uses 10 calls, the last
  step's share is 1.5 × 32 / 1 = 48, which the per-step ceiling then caps at 20. In a 4-step plan, step 1's share is
  1.5 × 48 / 4 = 18; if it uses all 18, step 2 gets 1.5 × 30 / 3 = 15.

## As built (Oct 21)
- `amoeba/config/localtools.yaml`: `calls_per_step: 12`, `step_share: 1.5`, `max_calls_per_run: null`.
- `LocalToolbox`:
  - `allowance()`;
  - `begin_step(step, trace, plan_steps=, not_run=)`;
  - the `step_share` refusal in `call()`;
  - `local_step_shares` from `finish()`.
- The plan runner passes the plan's size and the number of steps not yet run each time a step starts.
- `RunResult.local_step_shares`. `input_files` (D157) and this field are left out of result.json when empty, so
  Phase 1 records do not change.

**Existing tests that changed: one fake.** The stand-in toolbox in `tests/test_contract.py` now accepts the new
`begin_step` arguments. `test_output_and_call_caps` is unchanged: it still sets `max_calls_per_run: 3`, which now
works as an explicit fixed cap.

## Tests
`tests/test_local_share_d159.py`:
- the config has a share and no fixed run cap;
- **an 11-step plan making 110 calls is never refused** (the old cap stopped it at 60);
- a step over its share is refused with the numbers, and the next step has its own share;
- the per-step ceiling still holds;
- without a plan the allowance is the old 60;
- the plan runner passes the plan's size.
