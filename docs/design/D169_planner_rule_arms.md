# D169 — planner-rule changes are tested with real planning

Status: **built** (branch claude/zen-fermi-mnaurm, Oct 22). This fixes a review finding on D166 (main @ 9f1fb29).

## Why
D166's config arms ran the changed arm on the current arm's saved plan (`--drafts-from`). run_task adds
`promoted.planner_rules` to the Planner's and the observers' prompts only when it drafts (`saved_draft is None`). So
in a `planner_rule` promotion, the changed arm's Planner was never called. The rule was never seen, the two arms ran
the same plan, and the test could only ever measure noise.

## What
1. **`scripts/promote.py::arm_mode`** decides how the arms run:
   - **`planner_rule`: fresh plans.** Both arms plan for themselves (`stage_e --fresh-plans`, which leaves
     `--drafts-from` out). They run on `promote.planner_seeds` seeds per replay task (default 5). Planning varies
     between runs, so one seed would compare two random drafts.
   - **`tool_guidance` and `reorder_allowed_edits`: shared draft,** as before, on `promote.seeds` seeds (default 3).
     These act after planning, so the arms run one draft and differ only where the change acts.
2. **What stays the same.** The pick file, the sim seeds, `--lessons-write off` and the one-judge check are unchanged
   in both modes.
3. **The report** names the mode and the reason. The `.json` record carries it as `test_mode {mode, seeds, why}`.
4. **A rule that cannot reach the Planner is refused before any run.**
   - Only the d24 drafting prompts have the `{lessons}` slot that carries the rules. The d19 prompts copy AutoAgents
     verbatim and have none.
   - So a `planner_rule` test without `--draft-prompts d24` among the pass-through flags is refused, with that
     reason, and the entry's status is not changed.
5. **`stage_e --fresh-plans`** is also available by hand.

## Cost
A planner-rule test runs 2 arms × 5 seeds × the replay tasks, each with its own planning (3 calls a round). The
other kinds run 2 × 3 per task, as before.

## Tests (tests/test_planner_rule_arms_d169.py, red on 9f1fb29)
- **A real promotion.** It goes through the real pair runner with `run_task --llm mock --draft-prompts d24`. In the
  changed arm's trace the Planner's prompt holds the rule; in the current arm's it does not. Both arms planned. The
  report says "fresh plans".
- **The defaults.** With no seeds given, a planner rule gets 5 seeds and `fresh_plans`, and a tool_guidance change
  gets 3 seeds and the shared draft. A planner rule without the d24 prompts is refused before any run.
- **The flag.** `arm_command(..., fresh_plans=True)` has no `--drafts-from`.
