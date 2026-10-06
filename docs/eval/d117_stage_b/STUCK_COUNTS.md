# D117 Stage B: stuck counts from stored runs

Made by `python -m scripts.stuck_report eval` (offline, no model calls) on Oct 6, 2026, over every stored run folder
with step records (`artifacts/step_*.json`): 618 plan runs, 2,145 step attempts. A step that was redone counts as two
attempts (`step_N.first.json`, then `step_N.json`). The same functions mark steps live with `--adapt on`
(`amoeba/adapt/stuck.py`).

A step attempt is **stuck** when it did not end `done` and at least one signal holds. One cause is picked per stuck
attempt, in the order of `diagnoser.causes` (capability, tool_error, checks, max_turns, …).

## Stuck attempts and the cause picked

| Run set | Runs | Runs with a stuck step | Step attempts | Not done | Stuck | capability | tool_error | checks | max_turns | claimed_file_missing | Attempts without tool-call records |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bench5 | 10 | 2 | 21 | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 0 |
| bench5b | 31 | 3 | 51 | 3 | 3 | 1 | 0 | 0 | 2 | 0 | 0 |
| bmv | 3 | 2 | 11 | 5 | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| loop | 466 | 52 | 1496 | 87 | 87 | 61 | 0 | 26 | 0 | 0 | 0 |
| pnw | 2 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| probe_hard | 4 | 3 | 26 | 15 | 10 | 9 | 1 | 0 | 0 | 0 | 0 |
| round1 | 10 | 8 | 54 | 30 | 30 | 29 | 0 | 1 | 0 | 0 | 54 |
| round2 | 10 | 8 | 54 | 27 | 27 | 27 | 0 | 0 | 0 | 0 | 54 |
| round2b | 10 | 8 | 56 | 25 | 25 | 25 | 0 | 0 | 0 | 0 | 56 |
| round3 | 10 | 6 | 52 | 24 | 24 | 24 | 0 | 0 | 0 | 0 | 52 |
| round4 | 62 | 36 | 317 | 134 | 134 | 131 | 0 | 3 | 0 | 0 | 163 |
| **total** | 618 | 128 | 2145 | 353 | 347 | 314 | 1 | 30 | 2 | 0 | 379 |

## Signals seen on stuck attempts (an attempt can show several)

| Run set | capability_unfilled | repeated_error | checks_after_retry | max_turns | no_file_change |
|---|---:|---:|---:|---:|---:|
| bench5 | 3 | 1 | 0 | 0 | 0 |
| bench5b | 1 | 0 | 0 | 2 | 0 |
| bmv | 4 | 0 | 2 | 0 | 0 |
| loop | 61 | 6 | 28 | 0 | 0 |
| pnw | 0 | 0 | 0 | 0 | 0 |
| probe_hard | 9 | 3 | 0 | 0 | 0 |
| round1 | 29 | 0 | 19 | 0 | 3 |
| round2 | 27 | 0 | 13 | 0 | 3 |
| round2b | 25 | 0 | 12 | 0 | 3 |
| round3 | 24 | 0 | 17 | 0 | 2 |
| round4 | 131 | 0 | 72 | 3 | 12 |
| **total** | 314 | 10 | 163 | 5 | 23 |

200 stuck attempts showed one signal, 126 two, 21 three.

## What the counts say

- **Capability is the cause of 314 of 347 stuck attempts (90%).** It comes first in the table order, and a step that
  lacked a tool usually also failed its checks (163 attempts show checks_after_retry, but checks is picked for only
  30). 104 of the 314 are second attempts: a rework without the missing tool stays stuck, as D61 (G6) predicted.
- **The lacked items are not all tools.** At least 20 capability-stuck attempts lacked only upstream data (BLOCKED
  lines such as "step 1 data" or "framework data table"); 125 more mix a tool name with a data gap. Stage C's
  "attach the missing tool" cannot fix a missing input; those need the upstream step re-run or the plan changed.
- **repeated_error is rare where it can be seen** (10 attempts, 1 picked as tool_error): 379 attempts (rounds 1–3 and
  round 4's r3b half) were stored before tool calls were recorded (D61), so the signal cannot fire there.
- **max_turns: 2 picked, 5 seen; no_file_change: 23 seen, never picked** (always together with a capability gap).
- **6 attempts ended not done with no signal**, all for a mislabelled citation (D74); the watch does not count that
  as stuck.
- The loop practice runs (466 runs, small calc tasks) are 75% of the runs but only 87 stuck attempts; the hard tasks
  (probe_hard, rounds 1–4, bmv) carry most of the stuck steps.

## Run it again

    python -m scripts.stuck_report eval [more roots] --json stuck_counts.json
