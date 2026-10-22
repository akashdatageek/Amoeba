# D168 — "helped" is measured against a control

Status: **built** (branch claude/zen-fermi-mnaurm, Oct 22). This fixes a review finding on D154/D163 (main @ 9f1fb29).
It is general.

## Why
A probe re-runs the stuck step with one edit. A re-run alone can clear a signal or finish the step by chance: a
flaky tool call, a different sample, a transient error. D163 called every such probe "helped", so "helped" was
over-counted. The library, and D166's trigger on top of it, read that count.

## What
1. **The control probe** (`amoeba/adapt/probe.py::control_probe`) runs in a scoped round that has at least one
   probeable edit.
   - **How it runs.** It starts from the same snapshot as the edits' probes, faults included. It applies no edit,
     re-runs the step once, is measured like any probe, and is undone.
   - **What is kept.** Its attempt is kept as `step_N.probe-control.*`, and it is recorded as `control` in the round
     row (D162).
   - **It never wins the pick.** It is not in `probes`, so `pick`, `round_flags` and compose never see it.
   - **It counts as a probe for budgets.** Its tokens are in the round's fix tokens. Before the round,
     `probe_room` (the allowance divided by the average attempt, D151) must hold the edits' probes plus one. When it
     cannot, the edits come first, the control is skipped, and the round records why (`control_skipped`).
2. **When it runs** is set by `adapt.yaml probe.control`:
   - `auto` (the default): always with `--lessons-write on`, otherwise off;
   - `always`;
   - `sampled`: a seeded draw per (task, step, try) below `probe.control_rate`, default 0.5;
   - `off`.

   The single rung (D117 D) never runs one.
3. **The controlled verdict** (`lessons.py::controlled_verdict`):
   - a composed probe (D165): **confounded**, as before;
   - the edit ends done (or finished with limitation) and the control did not: **helped**;
   - both end done: **no_effect** (the control did as well);
   - the control ends done and the edit did not: **hurt**;
   - otherwise compare the signals with the control's. The edit cleared at least one the control did not clear and
     added none the control did not add: **helped**. It did both: **confounded**. It only added: **hurt**. Neither:
     **no_effect**.

   Without a control, the verdict is **`uncontrolled`**. The rule without a control is kept as `raw`.
4. **What the library keeps** (with D167):
   - **A family** counts the raw verdict, as today, for reports. It keeps the controlled verdicts apart
     (`controlled`) and counts the ones without a control (`uncontrolled`).
   - **A lesson's `counts`** hold controlled verdicts only. Its uses without a control go to `uncontrolled`, by their
     raw verdict.
   - **Readers.** Retrieval (D164) and promotion (D166) read `counts` only, so **promotion ignores uncontrolled
     counts**.
5. **The reflector** is asked when an edit helped against the control. Without a control, it is asked when the raw
   rule says helped, and that lesson's first sample is then uncontrolled.

## Cost
With `--lessons-write on` (the default when adapt is on), a scoped round runs one more re-run of the stuck step.
That costs about one average step attempt per round. The allowance check keeps it from crowding out an edit.

## Tests (tests/test_control_d168.py, red on 9f1fb29)
- A step that clears on a plain re-run: the control ends done, both edits end done, and both verdicts are no_effect.
  No lesson is written.
- A control that ends done while both edits fail is undone: the pick is none and the step is not done after the
  round. Both edits are judged hurt.
- The control's tokens are in the round's tokens. With room for only two probes, the control is skipped with the
  reason, and the verdicts are uncontrolled.
- The setting: auto is off without writing, and off, always and sampled behave as described.
- The verdict rules. A lesson used only without a control has `counts.helped` 0, and promotion finds no candidate.

## Existing tests changed
- `tests/test_lessons_d163.py::row` now carries a control (stuck, nothing cleared) by default, so the helpers of
  D163, D164, D166 and D167 build controlled verdicts. Their expected numbers are unchanged.
