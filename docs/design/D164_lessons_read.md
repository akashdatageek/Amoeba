# D164 — Box 2 and Box 4 read the library

Status: **built** (branch claude/zen-fermi-mnaurm, Oct 22). It is stage 3 of `spec/BUILD_SPEC_BOX4_RSI.md`.

## Why
A library nobody reads changes nothing. A later task whose step gets stuck in the same way should see what helped
before, and the Planner should see it before planning. Reading must also be a switch, so its effect can be measured
(the paper's "without library" row), and it must never let a lesson weaken a check.

## What
1. **Retrieval is plain code** (`amoeba/adapt/retrieval.py::retrieve`), with no embeddings. An entry is shown when:
   - it is `approved` (your decision) and has a lesson;
   - it helped more often than it hurt, over every niche;
   - **it never hurt in this run's niche**;
   - for Box 4 only, its cause is the stuck step's cause. Box 2 takes any cause.

   Entries seen in this run's niche come first, then the most-helped. There are at most `lessons.max_entries` (5)
   entries and `lessons.max_section_chars` (1,500) characters. The niche is still never used to split the library;
   it only orders the entries and hides one that hurt here.
2. **Box 4.** `fix_proposer.txt`, `fix_proposer_inv.txt` and `fix_proposer_dom.txt` get a `${lessons}` slot right
   after the fixes already tried.
   - It is filled with "# What helped before for this cause": each lesson's op, scope, helped and hurt counts, and
     the lesson.
   - The section says it is a hint only. Plain code still refuses an edit whose `because` does not quote this run's
     evidence, and every other check stands.
   - **With reading off the slot is empty, so the prompts are byte-identical to before.**
3. **Box 2.** The Planner and both observers get "# Lessons from earlier tasks" through the drafting prompts'
   existing `{lessons}` slot (D82; D102's environment text uses it too). The Planner prompt files do not change.
   - The general niche has no Environment section, which is why the slot is used.
   - The legacy d19 drafting prompts have no slot, so they show no lessons.
   - A reused draft (`--drafts-from`) is not re-planned, so it shows none.
4. **Flags**, on `run_task` and on `stage_e` (for both arms):
   - `--lessons on|off`: reading, default off;
   - `--lessons-write on|off`: D163's counting and reflector, default on with `--adapt on`;
   - `--lessons-dir DIR`: the library folder, `run_task` only.

   Reading and writing are separate switches, so a replay run can read without writing. **A task with
   `set: replay` never writes**: run_one forces writing off and records `off (replay task)`.
5. **What was shown and used.** `result.json` gets a `lessons` field with:
   - `read` and `write`;
   - `shown`: the ids shown to Box 2 and Box 4;
   - `used`: each shown lesson whose edit (same cause, op and scope) ended `done` in a round.

   `adaptation.lessons` holds Box 4's part. D166 reads `used` to see whether lessons get used.

## As built (Oct 22)
- New `amoeba/adapt/retrieval.py` (`retrieve`, `box4_section`, `box2_section`).
- `PlanRunner.box4_lessons` fills the slot. An unreadable library gives an empty section and a trace event, never a
  failed fix.
- `rounds.write_round` records the lessons used.
- `run_one` handles the Box 2 section, the replay rule and the `lessons` record (`RunResult.lessons`, left out when
  None).
- `cli_plan_options` sets the defaults, and `stage_e.arm_command` passes the flags to both arms.
- A new as-built box, `lessons_read`.

**Existing tests that changed: none.**

## Tests
`tests/test_lessons_read_d164.py`:
- retrieval rules: approved only, the cause for Box 4, any cause for Box 2, hidden when it hurt in this niche,
  helped must exceed hurt;
- same-niche first, then most-helped, within the caps;
- **with reading off the proposer prompts do not change** (the slot renders to nothing, and the text after it is the
  old text);
- **with reading on, a matching proposer prompt shows the lesson**, and `adaptation.lessons` names it as shown and
  used; writing off leaves the library unchanged;
- the flags and their defaults;
- **a replay task never writes**, while the Planner and both observers see the lessons;
- stage_e passes the flags to both arms.
