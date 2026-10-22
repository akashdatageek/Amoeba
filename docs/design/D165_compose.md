# D165 — compose two complementary edits

Status: **built** (branch claude/zen-fermi-mnaurm, Oct 22). It is stage 4 of `spec/BUILD_SPEC_BOX4_RSI.md`.
**Off by default** (`adapt.yaml compose.enabled: false`).

## Why
D154's round tries two edits, one per scope, and keeps at most one of them. Sometimes each edit fixes a different
part of what is wrong: the INV edit clears one stuck signal, the DOM edit clears another, and neither alone lets the
step finish. `round_flags` already marks this case `complementary`, but the code then picked one edit and left the
other part broken.

## What
A third probe runs only when all of these hold:
- the two probes were **complementary** (each cleared a signal, and the cleared sets differ);
- **neither probe recovered the step** (none ended done or finished with limitation; otherwise there is nothing to
  gain);
- **neither edit changes the plan graph** (`split_step` and `replan_remaining` are never composed);
- **one more probe fits** the fixes' token allowance and the step's share of a run cap, each probe estimated at one
  average step attempt (D151);
- `compose.enabled` is true.

The third probe:
- restores the round's starting snapshot, applies both edits, re-runs the step once, measures cleared / kept / new
  signals, and undoes everything, like any probe;
- is recorded with scope `compose`, its files kept as `step_N.probe-compose.*`, and with `composed_of` naming both
  edits.

**Keep rule (plain code):** the composed state is kept when it ends done, or when it clears more signals than either
probe alone and adds no new one. Otherwise today's pick stands, with the base for the next rung as before.

**Records and cost.**
- A kept composed state becomes the step's current attempt, and the fix record has kind `compose`. A work-around
  inside it is listed with the work-arounds.
- The third probe's tokens count toward the round's fix tokens and dollars. No proposer is called again.
- D163 judges each edit by its own probe, and the composed probe is `confounded` for both edits.
- The round row (D162) shows all three probes and the `complementary` flag.

## As built (Oct 22)
- `amoeba/adapt/probe.py`: `compose_config`, `composable`, `keep_composed`, `third_affordable`,
  `compose_probe`, plus a shared `measure` that `probe` now uses too (same output as before).
- In `scoped_round`, `round_flags` is now computed on the two scoped probes.
- `adapt.yaml compose:` section.
- A new as-built box, `compose`.

**Departure from the prompt's "done when".** The prompt's example was two injected faults (`tool_error` + `checks`)
on one step. The fault injector cannot make two faults that one edit each clears, so the test scripts a step that
lacks two things, one per edit. It reads that step's own BLOCKED items as its stuck signals: a test seam on how
signals are read only. Applying, re-running, measuring and undoing are the real code.

**Existing tests that changed: none.**

## Tests
`tests/test_compose_d165.py`:
- compose is off by default;
- **complementary edits are composed and kept**: the round row has `complementary` and the three probes inv, dom
  and compose; the composed probe ends done, both rules are on the role card, the fix is `compose` and `recovered`,
  no extra proposer call is made, and the library counts each edit as helped once and confounded once;
- with compose off, the round is as before;
- the keep rule;
- plan edits are never composed.
