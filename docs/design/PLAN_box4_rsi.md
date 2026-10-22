# Plan: Box 4 lessons and the outer loop (D161–D166)

Status: **plan, not built.** This is the plan for `claude_code_prompt_box4_rsi.md`, changed so the library is
general, not split by niche. Crop is only the first test bed for the outer loop. Stages 4–5 wait until the simulator
and the crop tasks are chosen.

## What changed from the prompt
1. **One shared library, not one per niche.**
   - Entries are keyed by `(cause, op, scope)`, which is already free of task facts.
   - Each entry also keeps the niches it was seen in, with helped/hurt counts per niche, so a lesson that helps in
     one niche and hurts in another is visible.
   - The folder is `data/lessons/`, with no niche level.
2. **Retrieval prefers the run's own niche but does not stop at it.** An approved lesson is shown when:
   - its overall helped > hurt;
   - and its hurt count in this run's niche is 0;
   - and, for Box 4, the cause matches.

   Lessons seen in the same niche come first, then the general ones, the most-helped first, within the N-entries and
   M-characters caps.
3. **Promotion targets general settings by default.**
   - The default edit surface is the order of a cause's list in `adapt.yaml allowed_edits`, which affects all tasks.
   - `profiles/<niche>.yaml` rules, `done_when` and tool-guidance lines can be edited only when `--niche <name>` is
     given.
   - The trigger counts tasks across niches, but requires `hurt == 0` in every niche.
4. **The scorer is pluggable per task.**
   - `SimScorer` is an interface, chosen by a field in the task's JSONL.
   - The stand-in scorer (it reads a number from the task) is the only one for now. A crop simulator becomes one more
     scorer when you choose it.
   - Box 4 never reads a score; its verdicts use the step's own signals.
5. **The frozen-judge hash is general.** It covers checks, quality, evaluate, the scorers and the baseline result
   files, for every run in every niche.
6. **The crop frame is reduced to fixtures.**
   - `profiles/crop.yaml` is a placeholder marked `TODO(Mehar)`, not limited to small local models.
   - `tasks/crop_example.jsonl` has two placeholder tasks with `set: stream | replay`.
   - Both serve as the outer loop's first test bed only.
   - A second, general replay set (`tasks/general_replay.jsonl`, toy-sized tasks) is added, so promotion can be
     tested without crop.

## The stages

**D161, the frozen judge and the scorer slot (general).**
- `amoeba/config/frozen.yaml` lists the judge files. At run start, `sha256_text`/`manifest` from `evidence.py` hash
  them, and the hash is written to `result.json`.
- `amoeba/eval/sim_score.py`: the `SimScorer` interface, the stand-in scorer, and picking a scorer per task. It writes
  `sim_score.json` with the score, the baseline score on the same seed, the delta, the seed and the judge hash.
- Placeholder crop profile and tasks, plus the general replay set.
- **Done when:** the same seed gives the same score twice, and a changed frozen file changes the hash and makes a
  comparison refuse.

**D162, Box 4 saves every round (no behaviour change).**
- One row per round goes to `<run>/rounds.jsonl` and to `events.jsonl` (event `round`). It holds:
  - the task id, the niche and the cause;
  - each edit with its scope and quote;
  - each probe's status, the cleared/kept/new signals and its tokens;
  - the pick and why it was made;
  - the step's final status.
- A closing `run_end` row carries the run's `sim_score` when there is one.
- The single-proposer rung is recorded in the same format, with one probe.

**D163, verdicts, the reflector and the library.**
- `amoeba/adapt/lessons.py` holds the plain-code verdicts:
  - `helped`: the probe ended done, or it cleared at least one signal and added none;
  - `hurt`: it added a signal and cleared none;
  - `no_effect`: it cleared nothing and added nothing;
  - `confounded`: the edit was only tested together with another edit, or the signals and the final status disagree.
- The reflector is one LLM call (`prompts/reflector.txt`), made only when an edit helped. It sees the round rows and
  the step card, never a score, and returns `{cue, lesson, confidence}` or `NO_ENTRY`.
- Plain code refuses a lesson that is over the character cap, uses denylisted wording, or contains a number or proper
  noun from the task. A refused lesson is asked for once more, then dropped.
- The library lives in `data/lessons/`:
  - `index.jsonl` is keyed by `(cause, op, scope)` and holds per-niche counts, the task ids and a status
    (unreviewed, approved, rejected, promoted or promotion_failed);
  - each entry has `edit.json` and `EXPERIENCE.md`.
  - Writes take a file lock and replace files atomically. Every verdict updates the counts.
- The CLI is `python -m scripts.lessons list|show|approve|reject`.
- **Done when:** three runs with the same injected fault leave one entry with helped 3, and a hurt probe raises the
  hurt count without adding a lesson.

**D164, Box 2 and Box 4 read the library.**
- Retrieval follows point 2 above.
- Box 4: a section "What helped before for this cause" is added to the INV, DOM and single proposer prompts. The quote
  rule stays: an edit must still quote this run's evidence.
- Box 2: the lessons go under "Lessons from earlier tasks" in the Environment text. The Planner prompt files do not
  change.
- Flags:
  - `--lessons on|off` (reading, default off);
  - `--lessons-write on|off` (default on with `--adapt on`);
  - a `replay` task always runs with writing off.
  - `result.json` lists the lessons shown and whether a matching fix ended done.
- **Done when:** with reading on, a matching prompt shows the lesson. With it off, the prompts are byte-identical to
  today.

**D165, compose two edits. Held until you say go.**
- A third probe applies both edits together, only when `round_flags` says they are complementary and the budget
  allows. Plan edits are never composed. It is behind `compose.enabled: false`.

**D166, promotion, run by hand. Held until the simulator and tasks are chosen.**
- `python -m scripts.promote --replay <tasks> [--niche <name>]`. It never runs during a task.
- The trigger: the entry is approved, helped at least 3 times, comes from at least 2 tasks, and has hurt 0 in every
  niche.
- One LLM call proposes a change, within the surface in point 3 above.
- Plain code refuses any change to code, prompts or frozen files, and checks the judge hash before and after.
- The test reuses `scripts/stage_e.py`:
  - it runs the replay set only, in two arms (current setup and with the change);
  - it uses 3 seeds per task, the same drafts and picks, and lesson writing off;
  - the change goes into a temporary copy of the config, never the live one.
- The change is accepted only if:
  - the mean score delta is above 0;
  - no task drops more than the set margin;
  - the step-contract pass rate does not fall.
- It writes a report and a patch, and never applies them; you apply the change with `--apply <report>`.

## Rules (unchanged from the prompt)
- Everything new is off by default, and a test proves that a run with the flags off is unchanged.
- All numbers live in `adapt.yaml` (`lessons:`, `compose:` and `promote:`).
- Tests run offline. There are no real model runs without asking.
- New prompts are in our own words and list the run's tools and skills.
- The housekeeping applies: box tags, BOXES, cards, a design note per decision, and the as-built page.

## Open before starting
- The spec `spec/BUILD_SPEC_BOX4_RSI.md` was not attached. Until it is, this plan stands in for it.
- The base branch: build on `claude/box4-scoped`, which now holds D153–D160, or merge PR #46 into `main` first.
