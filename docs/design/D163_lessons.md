# D163 — verdicts, the reflector and one lesson library

Status: **built** (branch claude/zen-fermi-mnaurm, Oct 22). It is stage 2 of `spec/BUILD_SPEC_BOX4_RSI.md`.
Following the user's call, it is general: **one library for every task**.

## Why
Box 4 forgot every round when its task ended. The next task stuck in the same way started from nothing. The rounds
are now recorded (D162). This decision turns them into counted evidence: which edit helped for which cause, how
often, in which niche. It also turns them into a short lesson a later task can be shown (D164) and the outer loop can
promote (D166).

## What
1. **Verdicts by plain code**, one per edit per round (`amoeba/adapt/lessons.py::verdict`). The rule used, in this
   order:
   - the edit was only tried combined with another edit (a D165 composed probe): **confounded**;
   - the probe ended `done`, or finished with limitation (a work-around): **helped**;
   - it cleared a signal *and* added a new one, so the signals disagree about the edit: **confounded**;
   - it cleared at least one signal and added none: **helped**;
   - it added a signal and cleared none: **hurt**;
   - nothing cleared, nothing new: **no_effect**.

   One probe is one sample (`samples: 1`). That is why D166 waits for repeats.
2. **One library** (`adapt.yaml lessons.library`, `data/lessons/`; `data/` is git-ignored like the tool library).
   - `index.jsonl` has one row per entry, keyed by **(cause, op, scope)**. Each row holds:
     - the counts (helped, hurt, no_effect, confounded), in total and **per niche** (`by_niche`);
     - the task ids and run ids;
     - the status (`unreviewed`, `approved`, `rejected`, `promoted`, `promotion_failed`);
     - the cue, the lesson and the confidence.
   - **The niche is recorded, never used to split** (the user's decision). D164 uses it only to put same-niche
     entries first and to hide an entry that hurt in this niche.
   - Each entry's folder holds:
     - `edit.json`: the op and the params that helped (the last 20);
     - `evidence.jsonl`: one line per verdict, with the run, task, niche, verdict and the probe's signals;
     - `EXPERIENCE.md`: the cue, the lesson, the counts and the latest evidence, for you to read.
   - **A repeat updates its entry**; it never adds a row. **Every verdict counts**, `hurt` included, even when no
     lesson is written.
   - **Safe for several writers.** Every change holds an exclusive `fcntl` lock on `<library>/.lock` (waiting up to
     `lock_timeout_s`) and replaces files atomically (temporary file and `os.replace`).
3. **The reflector** is one LLM call, made only when an edit of the round helped. It uses
   `prompts/reflector.txt`, written in our own words after Harness² Prompt 6.
   - **What it sees:** the step card, the round row (cause, signals, edits, probes, pick), and the run's tools and
     skills.
   - **What it does not see:** any score. The prompt also says that no score, rubric or answer key exists.
   - **What it returns:** `{cue, lesson, confidence}` or `NO_ENTRY`. A lesson is written for the helped edit that was
     picked (else the first helped one).
   - **Plain code refuses** a cue or lesson that:
     - is longer than `lessons.max_chars` (300);
     - uses denied wording (`limits.denylist`, the proposer's list);
     - contains a number or a proper noun from the task prompt (a capitalised word that does not start a sentence).

     A refused lesson is asked for once more, with the reasons, and then dropped.
   - **Its cost is counted.** The call is traced (`invoke_agent reflector`, box `lessons`). Its tokens count in the
     round's fix tokens and in the run's totals.
   - **It is skipped, and the skip logged** (`reflector_skipped` in the trace and events.jsonl), when any of these
     holds:
     - the run's token cap would not hold it;
     - the task's fix allowance (D151) would not hold it;
     - the step has used its share of the run cap.

     Any error in the library or the reflector is logged as a skip; it never fails the run.
4. **Your review.** `python -m scripts.lessons list|show|approve|reject` works like `scripts/tool_library.py`. Only
   an approved entry is ever shown to a task (D164).
5. **Switch.** `PlanOptions.lessons_write` (default off; the CLI flag comes with D164). With it off, nothing is
   written and no call is made.

## As built (Oct 22)
- New:
  - `amoeba/adapt/lessons.py` (`verdict`, `round_verdicts`, `key_of`, `lesson_problems`, `task_facts`,
    `LessonLibrary`, `learn_from_round`, `reflector_call`, `reflector_affordable`, `parse_reflection`);
  - `amoeba/config/prompts/reflector.txt`;
  - `scripts/lessons.py`.
- `adapt.yaml` gets a `lessons:` section: library, max_chars, reflector_max_tokens, lock_timeout_s, evidence_kept,
  max_entries, max_section_chars.
- `rounds.write_round` calls `learn_from_round` after each row.
- `result.json` `adaptation.lessons_learned` lists, per round, the verdicts counted and the lesson written or why it
  was skipped.
- The mock LLM learns the `reflector` kind.
- A new as-built box, `lessons`.

**Existing tests that changed: none.**

## Tests
`tests/test_lessons_d163.py`:
- the verdict rules;
- a lesson with a task number or name, denied wording or over the cap is refused, and the reply parsing works;
- the library counts every verdict and per niche, and a repeat updates the same entry;
- **two writer processes on one key lose no count** (50 of 50);
- **a hurt probe raises hurt without a lesson or a call**;
- **three runs with the same injected fault (`tool_error:1:30`) leave one entry with `helped: 3`** and a lesson;
  the other scope's edit has `no_effect: 3`; the reflector prompt says no score exists and lists the tools and
  skills;
- a refused lesson is asked once more, then dropped;
- `NO_ENTRY` keeps the counts;
- with writing off, nothing is written and no call is made;
- the reflector is skipped and logged when the cap would not hold it, and the run is unaffected;
- the CLI.
