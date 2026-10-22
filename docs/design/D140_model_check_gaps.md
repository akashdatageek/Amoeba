# D140 — the model check: what the audit asked for beyond D135

Status: **built** (branch claude/audit-fixes). The audit prompt's "D137: model smoke check" was built by D135
(PR #42, merged). This decision adds only the probes and the repair wording D135 lacked.

## Why
The audit prompt asks for three things D135 did not have:
- a probe of the plan observer, where D135 probed only the agent observer;
- a separate Final_Output probe;
- a json_prompt repair call that quotes the exact validation error.

## What
1. **Both observers.** The planner probe lets the planner, the agent observer and the plan observer each through
   once (`draft_team`, one round). The table gets rows `planner`, `observer` and `plan observer`.
2. **The step probe has two turns.** The first should be a tool call (`step (native tools)`). The second should end
   the step (`Final_Output`), and is ok when it is a Final_Output call whose typed fields pass plain code's check
   (`step_protocol.check_args`) under v2, or any Final_Output call under legacy.
3. **The json_prompt repair** quotes the exact reason the first reply failed (`validation_error`: pydantic's first
   errors, or the JSON error).

## As built (Oct 16)
- The live re-run of the model check on the three profiles is part of D141's live step. It uses the v2 builders, so
  it shows whether the reasoning refusals are gone.

## Tests
tests/test_model_check_d135.py, updated: 11 probe rows; the second step turn's typed Final_Output; the repair
quoting the error.
