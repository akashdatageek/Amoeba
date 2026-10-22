# D170 — the accept rule needs more than "average went up"

Status: **built** (branch claude/zen-fermi-mnaurm, Oct 22). This fixes a review finding on D166 (main @ 9f1fb29).

## Why
D166 accepted a change when the mean sim-score delta was above 0, no task dropped more than 0.05, and the contract
rate did not fall. On a few replay tasks with three seeds, run-to-run noise alone can push the mean above 0. Three
pairs won by a hair and two lost was an "accept".

## What
1. **Paired comparison.** `summarise` pairs the two arms' runs of the same task and seed, which already share the
   picks, the sim seed and the judge. For each pair it keeps current, changed and delta (`pair_rows`). It counts
   **wins** (delta > 1e-9), **losses** (delta < -1e-9) and **ties**.
2. **The accept rule** (`scripts/promote.py::accept`). All four must hold:
   - the mean paired delta is **at least `promote.min_delta`** (default 0.05);
   - no task's mean drops by more than `promote.max_task_drop` (today's rule);
   - the changed arm **wins more than twice as many pairs as it loses** (ties count for neither);
   - the step-contract pass rate does not fall (today's rule).

   The first rule that fails is the reason given.
3. **The report** has a table of every pair (task, seed, current, changed, delta). It also gives the wins, losses and
   ties, and the mean delta.

## Tests (tests/test_paired_accept_d170.py, red on 9f1fb29)
- **Wins by a hair are rejected.** Three pairs win by 0.01, two lose by 0.005 and one ties (mean +0.0033, which today
  accepted). It is now rejected. The report lists all six pairs and "3 wins, 2 losses, 1 tie".
- **A clear win is accepted.** Six pairs each win by 0.2: accepted, 6 wins, mean delta 0.2.
- **The rule alone.** A mean below 0.05 is rejected. 4 wins against 2 losses is rejected, and 5 against 2 is accepted.
  The default `min_delta` is 0.05.

The D166 tests are unchanged. Their reasons still come out, because the per-task drop is checked before the
win/loss rule.
