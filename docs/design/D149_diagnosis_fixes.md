# D149 — diagnosis fixes

Status: **built** (branch claude/run-gaps). These gaps were found in the fuel run 71d2f910.

## Why
- In 71d2f910 step 1, the gate refused `local:Bash` once in attempt 2 and once in attempt 3, both for
  `unsafe_command`. Box 4 still diagnosed missing_data and spent its fixes on more turns. A tool the helper holds
  that keeps being refused is the thing to fix first: until the call is rewritten, nothing else can be judged.
- BLOCKED lines written in other markdown (`*BLOCKED:*`, `` `BLOCKED:` ``) named no capability.

## What
1. **Repeated refusal decides the cause.**
   - Each step's meta carries `refusals`: the local-tool refusals of that step so far, across all its attempts,
     by tool and reason (`PlanRunner.count_refusals`, `stuck.refusal_counts`).
   - When one tool has been refused 2 or more times for the same reason, the watch adds the signal
     `repeated_refusal` (cause tool_error), with the evidence "local:Bash refused 2 times in this step for
     unsafe_command: rewrite the call (the refusal says how)".
   - This signal decides the cause whatever else is missing; it is the only deciding signal.
2. **BLOCKED in any markdown.** `unmark` also removes a marker right after the colon (`*BLOCKED:*`,
   `` `BLOCKED:` ``), so those lines name their capability like plain ones.

## As built (Oct 16)
- **The test you specified for the BLOCKED part already passed before this change.** `"**BLOCKED:** Census API
  key — x"` yields `"Census API key"`, which D128 fixed. Under your rule that part of the gap is not real for that
  form. The forms that did fail are `*BLOCKED:*` and `` `BLOCKED:` ``, and only those are fixed here.
- A refusal is counted from the tool call's result line, which every gate refusal starts with
  (`refused: local:<tool> — <reason>`).

## Tests (written first)
tests/test_diagnosis_d149.py.
- **Before the fix:**
  - the module could not import (`refusal_counts` did not exist);
  - replaying 71d2f910 step 1 attempt 3 gave cause missing_data;
  - `*BLOCKED:*` and `` `BLOCKED:` `` gave `[]`.
- **After the fix**, all 8 tests pass:
  - the replay of attempts 1–3 counts `{local:Bash, unsafe_command}: 2` and gives tool_error;
  - attempts 1–2 alone (1 refusal) still give missing_data;
  - the runner counts refusals across attempts.
