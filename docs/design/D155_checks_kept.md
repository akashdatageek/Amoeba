# D155 — an edit never drops a check

Status: **built** (branch claude/box4-scoped, Oct 19). Your decision 7 on the D154 plan: fix the dropped checks in
**both** proposer modes, as their own decision, before D154. So `--proposer single` already has the fix.

## Why
While planning D154 I found three Box 4 edits that quietly dropped the checks a step must pass:
- **split_step.** The sub-steps were built with no checks (`_split_change`). After a split, the step's typed checks
  (Box 2's contract, D142) were gone.
- **replan_remaining.**
  - A re-planned step got only the checks the proposer happened to write on a `checks:` line.
  - Without one, the checks of the steps it replaced were lost.
  - With one, the proposer could write checks of its own choosing.
- **work_around.** It replaces the step's done_when. The keyword checks (D34) are drawn from the output and
  done_when lines, so a narrower done_when could quietly drop some of them.

All three let a "fix" pass a step by loosening what it had to pass. That breaks "LLM proposes, deterministic code
disposes": the model may change the work, never the bar the work is judged by.

## What
1. **Split.**
   - The last sub-step carries every typed check of the stuck step, plus the requirements those checks cover.
   - The last sub-step is the one the waiting steps read, and the one that hands over the step's result.
   - The earlier sub-steps are intermediate and get none: a file check on the first half of a split could never pass
     there.
2. **Re-plan.**
   - Every typed check of every step the re-plan replaces moves to one new step:
     - the replaced steps are the stuck step and the not-done steps it rewrites or drops;
     - the new step is the last one that covers what the check covers (or else the replaced step's requirements);
     - if no new step covers them, the last new work step.
   - A check already on that step is not added twice.
   - **A re-plan that writes a `checks:` line is refused.** The reason goes back to the proposer: "a re-plan may not
     write checks: plain code carries the replaced steps' checks to the new steps".
   - Box 2's HARD checks (D145) then run on the plan *with* the carried checks. So "every requirement checked" still
     holds after the edit.
3. **Work-around.**
   - It may still narrow the done_when the helpers are told.
   - The keyword checks keep reading the original done_when (`PlanRunner.check_view`).
   - The typed checks are never touched.
   - The watch's waived view (D124) never drops a citation check (`cites_every_figure`, `figures_dated`), even when
     its name mentions the waived file type.
4. **Records.** What moved is recorded on the fix: `checks_carried: [{check, from, to}]`, in result.json
   `adaptation.fixes`.

## As built (Oct 19)
- `PlanRunner.carry_checks(change, n, split)` is called in `_d_live` after a split or re-plan change is built and
  before Box 2's HARD checks.
- `PlanRunner.check_view(step, n)` with `done_when_kept` (set when a work_around replaces done_when) feeds both
  `step_checks` calls in `run_step`.
- `stuck.CITATION_CHECK` guards `waived_view`.
- **Not in scope:**
  - the contract of a step's *roles* (the D61 capability contract) is built from the roles, not from the step
    object, so a split or re-plan keeps it already;
  - re-plans made by the Action Observer (D63, `--replan on`) are not Box 4 edits and are left as they are.

**Existing tests that changed: none.**
- The existing split, re-plan and work-around tests (`tests/test_proposer_d117.py`) use plans whose steps have no
  typed checks, so there was nothing to carry.
- Box 2's HARD "every requirement checked" check applies only when a plan has typed checks.

## Tests
tests/test_checks_kept_d155.py, 6 tests:
- a split's last sub-step carries the stuck step's check and its requirement; the first sub-step has none;
  `checks_carried` names it;
- a re-plan carries step 1's check to the new step 1 and the dropped step 3's citation check to the new step 4,
  which covers its requirements;
- a re-plan that writes its own `checks:` line is refused, twice, so no fix;
- a work-around's narrowed done_when; the checks read the original (`check_view`);
- a work-around leaves the typed checks as they were;
- a waived capability never waives a citation check.

Full suite: 1019 passed, 9 skipped before; 1025 passed, 9 skipped after.
