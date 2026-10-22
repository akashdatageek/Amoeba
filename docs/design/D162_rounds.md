# D162 — Box 4 saves every round

Status: **built** (branch claude/zen-fermi-mnaurm, Oct 22). It is stage 1 of `spec/BUILD_SPEC_BOX4_RSI.md`.

## Why
The lesson library (D163) learns from what each Box 4 edit did. The scoped round (D154) already knows this: both
edits, their quotes, both probes' cleared / kept / new signals, the pick. But it went only to the trace, to one
`box4_round` event and to the fix record, in shapes that differ between the scoped round and the single rung. One row
per round, in one shape, is what D163 reads.

## What
After each round, one row goes to `<run>/rounds.jsonl` and, as a `round` event, to the run's hash-chained
`events.jsonl` (`EvidenceLog.append`, checked by `scripts/verify_evidence.py`). The row holds:
- `task_id`, `niche` and `cause`. The niche is the profile's name, or `general`; it is recorded, never used to split.
- `mode` (`scoped` or `single`) and the stuck signals before the round.
- `edits`: each candidate with an op, its scope, params and `because` quote. The single rung's quote is its reason.
- `probes`: each probe's scope, op, params, status, limited, cleared, kept, new, tokens, turns and samples.
- `pick`, `pick_reason`, `base`, and the flags `complementary` / `shared_failure`.
- `step_status` (the step's status after the round, or `replanned`) and `outcome`.

The **single rung** (`--proposer single`, and a scoped round that falls back in sandbox mode) writes the same shape:
- one candidate;
- one probe, made from its re-run: the signals before and after, tokens and status;
- no probe for a plan edit (it is judged when its steps run) or when no valid edit came back.

When a run that had a round ends, `run_end` closes the record. It holds the task id, the run's `sim_score` (D161),
the judge hash and the status. It goes to `rounds.jsonl` and as a `run_end` event.

No model call is made here, and nothing about the run changes.

## As built (Oct 22)
- New `amoeba/adapt/rounds.py`: `round_row`, `write_round`, `read_rounds`, `close_rounds`, `niche_of`.
- `probe.finish` writes the scoped round's row. The existing `box4_round` event stays as it was.
- `PlanRunner._single_round` writes the single rung's row in each of its three endings (no edit, plan edit,
  re-run).
- `PlanRunner.rounds` holds the rows in memory.
- `run_one` calls `close_rounds` after the score is written.
- A new as-built box, `rounds`.

**Existing tests that changed: one, with your approval** (asked on Oct 22). `tests/test_proposer_d117.py
::test_grant_tool_after_the_pool_rung_was_skipped` checks the exact list of events in events.jsonl. It now
expects the new `round` event before `fix`.

## Tests
`tests/test_rounds_d162.py`:
- **a scoped round with an injected fault (`tool_error:1:30`) writes one row per round** that matches the trace's
  `box4_round` and the fix record: the pick, the edits with their quotes, and the probes' signals, tokens and
  samples. The `round` events in events.jsonl equal the rows, and the chain verifies;
- the single rung writes the same shape with one probe;
- no round means no file; `run_end` closes the record and the chain still verifies;
- `run_one` closes the record.
