# D143 — planning v2 (Box 1 and Box 2)

Status: **built** (branch claude/audit-fixes). This is the audit prompt's "D140". Everything here is on under
`--protocol v2`. Under legacy the drafting loop is unchanged: `--planning-tier auto` is `full`, the last draft is
published, and the observers' full suggestions go back. An explicit `--planning-tier` applies in both protocols.

## Why
- The drafting loop published the **last** round's draft, even when an earlier round was better.
- The observers' full suggestions, minor ones included, went back to the planner, which then rewrote the plan around
  nits.
- Every task got the same three rounds and both observers, however simple it was.
- The planner could never correct Box 1's reading, even when the planning search showed that the reading's data did
  not exist: the prompt said "plan on it exactly" and observer rule 10 forced a revision.

## What
1. **Planning tier** (`amoeba/task/planning.py` `resolve_tier`), decided by code from the task:
   - **light**: at most 3 requirements (the task's deliverable phrases), no web research, no files to deliver. One
     round: the planner and the code checks.
   - **full**: 7 or more requirements, or web research plus 2 or more files, or any outside action (send, post,
     pay). Up to 3 rounds, both observers.
   - **standard**: everything else. Up to 2 rounds, the plan observer only.

   `--planning-tier light|standard|full|auto` overrides it (default auto). The tier and its signals go into the
   trace (`planning_tier`), the Draft, and result.json (`planning_tier`).
2. **Typed issues; only blocking ones go back.**
   - The reviewers answer with ReviewOut {verdict, issues [{severity, step?, requirement?, problem, fix}]}.
   - Code sends the planner only the blocking issues, plus the failed HARD checks (the existing gate).
   - Minor issues are kept in the round's record only.
   - The planner gets its previous PlanOut as JSON plus those issues, and returns a full PlanOut. Code diffs it
     against the previous one (`plan_diff`: requirements and steps added, removed or changed), kept in the round's
     `plan_diff`.
3. **The best draft is published, not the last.** Each round is scored by:
   - the number of failed HARD checks (computed every round under v2);
   - then the number of blocking review issues (an unreadable review counts as one);
   - then the round number (the later round wins a tie).

   The best round's draft is published. `published_round` and `published_score` go on the Draft and into
   result.json, with the trace event `draft_published`. Consensus still means both observers approved and the gate
   passed.
4. **The planner may revise the reading, under code control.**
   - PlanOut has an optional `reading_revision` {entity, from_reading, to_reading, reason, evidence}.
   - Code (`check_revision`) accepts it only if both hold:
     - (a) to_reading is one of Box 1's alternatives for that entity, or the evidence cites a plan-search source
       [P#] the planner was shown;
     - (b) the plan observer approved that round, when a plan observer ran.
   - If accepted (`apply_revision`):
     - the working reading changes (settled `revised`, and the old reading becomes an alternative);
     - run_task re-renders the task note;
     - the opening line says: "I read X as <to> because <reason>; <from> is not available." enforce_opening adds it.
   - result.json records it in `reading_revised`. A refused revision leaves the reading as it was and logs
     `reading_revision_refused`.
   - plan_create_v2 says when a revision may be proposed.
   - Observer rule 10 in plan_review_plan_v2: a plan that reads an entity differently without a reading_revision
     must be revised. With one, the observer judges its evidence. The plan observer is shown the revision.
5. **Box 1 under v2** (ReadingOut) and **the planning search** (PlanSearchOut) were already built in D141.

## As built (Oct 16)
- The requirement count used for the tier is estimated before planning, from the task's deliverable verbs
  (`quality.deliverable_phrases`), because the planner has not written requirements yet. Web need is a keyword test
  on the task. Departure: the prompt said "from the task and Box 1's reading"; the reading adds nothing to these
  counts.
- (a)'s "[P#] source that shows the original reading's data does not exist" is checked as "a [P#] the planner was
  shown is cited". Whether the page really shows that is judged by the plan observer (b), not by code.
- A light-tier task has no observer, so (b) does not apply there.

## Tests
tests/test_planning_d143.py:
- the tier rules, legacy auto = full, an explicit tier, and the CLI flag;
- light runs the planner alone, and standard runs the planner and the plan observer;
- the score order;
- the best round published (round 1 of 3), with only blocking issues and the previous PlanOut sent back, and minor
  issues recorded;
- plan_diff;
- the eight revision rules;
- an accepted revision changes the reading, the task note and the opening line;
- a refused revision leaves the reading.

The D141 drafting tests and the model-check planner probe ask for `full`, so that both observers run.
