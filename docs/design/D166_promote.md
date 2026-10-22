# D166 — the outer loop: a proven lesson becomes a general setting

Status: **built** (branch claude/zen-fermi-mnaurm, Oct 22). It is stage 5 of `spec/BUILD_SPEC_BOX4_RSI.md`.
**General**, by the user's decision: no niche is chosen, and the loop changes settings that apply to every task.

## Why
A lesson in the library (D163) helps only when a task is shown it (D164). When the same edit keeps helping on
different tasks and never hurts, it should become part of how Amoeba works, so every task gets it without a lookup.
But a change to Amoeba could also make things worse. So it is tested first on tasks the library never learned from,
with everything else held fixed and the judge frozen (D161). And it is applied only by you.

## What
`python -m scripts.promote --replay <tasks> [--entry ID] [--seeds N] [--lessons-dir DIR] -- <run_task flags>`. It is
run by hand and never during a task.

1. **Trigger (plain code, `candidates`).** An entry qualifies when it is `approved`, has a lesson, helped
   `promote.min_helped` (3) times on `promote.min_tasks` (2) different tasks, and has hurt 0 in every niche. An
   entry already `promoted` or `promotion_failed` is not tried again. `--list` shows the candidates.
2. **The proposal: one LLM call.** It uses `prompts/promote.txt`, written in our own words. The call is traced to
   `promotions/<name>.trace.jsonl`, and its tokens and dollars go to the report.
   - The proposer sees the lesson, its counts, today's settings and the tools that exist. The prompt says that no
     score, rubric or answer key exists.
   - It returns one change, or `NO_CHANGE`. **The change surface is general and is only `amoeba/config/adapt.yaml`:**
     - `reorder_allowed_edits`: the cause's list in `diagnoser.allowed_edits`, reordered;
     - `planner_rule`: a line in `promoted.planner_rules`, shown to the Planner and both observers under
       "Rules learned from earlier tasks";
     - `tool_guidance`: one line for one tool in `promoted.tool_guidance`, shown to every helper that holds the tool.
       A step's own D154 guidance still wins.
   - The `promoted` lists start empty, so today's runs do not change.
3. **Plain code's checks before any run (`change_problems`).** It refuses:
   - any other kind or an extra key;
   - any target file but adapt.yaml: Python, prompts, `frozen.yaml` or a file it lists (each named in the reason);
   - a text over `promote.max_text_chars` (300) or with denied wording;
   - an unknown tool;
   - an order that is not exactly today's edits reordered.

   The change is written into the text of a **temporary copy** (`promotions/configs/<name>.yaml`), keeping every
   comment. The live file is never written. The judge hash must be the same before and after.
4. **The test reuses `scripts/stage_e.py`**, with a new `--arms config` pair: `current` (today's adapt.yaml) and
   `changed` (the copy, through `AMOEBA_ADAPT_CONFIG`, which `adapt_config()` now honours).
   - Only the `set: replay` tasks run, never the stream set.
   - The changed arm reuses the current arm's draft (`--drafts-from`), and both share one `--picks-file`.
   - Each task runs on `promote.seeds` (3) seeds; the seed is also the sim seed.
   - **Both arms run with `--lessons-write off`**, so the test cannot change the library it is testing. Reading
     (`--lessons`) comes from the pass-through flags and is the same in both arms.
   - Every run must carry the same judge hash, and it must be today's (`same_judge`); otherwise the test is refused.
5. **Accept rule (plain code, `accept`).**
   - The mean sim-score delta (changed − current, over every task and seed) is above 0.
   - No task's mean score drops by more than `promote.max_task_drop` (0.05).
   - The step-contract pass rate does not fall. That rate is the share of steps whose D61 contract passed, read from
     each run's `artifacts/step_N.json`.
6. **Output.**
   - `promotions/<date>_<entry>.md` says the decision, the lesson, the change and a per-task table, in plain words.
     Next to it are a `.json` record and a `.patch` (a unified diff of adapt.yaml).
   - The entry's status becomes `promoted` (accepted) or `promotion_failed` (rejected). A refused proposal leaves it
     unchanged, because it was never tested. **A lesson is never deleted.**
   - A `promotion` row goes to `promotions/events.jsonl` (hash-chained).
7. **You apply it.** `--apply <report>` writes the accepted change to adapt.yaml, but only while that file is still
   the one the report was made from (its sha256). Otherwise it refuses and asks you to promote again.

## Departures and limits
- **The edit surface is general, not a niche profile** (the user's decision). The prompt's `profiles/<niche>.yaml`
  rules became `promoted.planner_rules`, and its tool-guidance lines became `promoted.tool_guidance`.
- **Only the stand-in scorer exists**, so a real gain needs a real scorer (D161's slot). On the mock, both arms
  score the same, and the loop correctly rejects ("the mean score delta is +0.0000").
- **The prompt asked for `--sim-seed` to be kept the same in both arms.** It is: both arms run on the same `--seed`,
  and the sim seed defaults to it.

## As built (Oct 22)
- New:
  - `scripts/promote.py` (`candidates`, `change_problems`, `apply_change_text`, `replay_ids`, `stage_e_runner`,
    `contract_rate`, `summarise`, `accept`, `promote`, `report_text`, `apply_report`, `main`);
  - `amoeba/config/prompts/promote.txt`.
- `adapt.yaml` gets `promoted:` (empty) and `promote:` sections.
- `amoeba/adapt/config.py`: `config_path()` honours `AMOEBA_ADAPT_CONFIG`.
- `PlanRunner.guidance(n)` puts the promoted tool guidance under the step's own.
- `run_one` shows `promoted.planner_rules` to Box 2.
- `scripts/stage_e.py`: `CONFIG_ARMS`, `--arms config`, `--config-b`, and the changed arm's environment.
- The mock LLM learns the `promoter` kind.
- A new as-built box, `promote`.

**Existing tests that changed: none.**

## Tests
`tests/test_promote_d166.py`:
- the plain-code trigger;
- the config can be a temporary copy, and today's `promoted` is empty;
- the change surface checks: a frozen file, code, a prompt, frozen.yaml, an unknown kind or tool, denied wording, a
  long text, a bad reorder and an extra key are all refused;
- the change is written to text, keeping comments and changing nothing else;
- **a change that helps is accepted but not applied**: the report, patch and events row are written, the live file
  is unchanged, `--apply` writes it, and a second `--apply` on the changed file is refused;
- **a change that hurts one task is rejected** (`promotion_failed`, the lesson kept);
- a lower contract pass rate is rejected;
- **a proposal touching a frozen file is refused before any run**;
- runs judged differently are refused;
- only the replay set runs;
- promoted settings reach the Planner and the helpers;
- stage_e's config arm pair;
- **the real pair runner on the mock** runs only the replay tasks, and rejects a change that changes nothing.
