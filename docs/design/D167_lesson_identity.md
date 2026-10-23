# D167 — a lesson's counts are about that lesson

Status: **built** (branch claude/zen-fermi-mnaurm, Oct 22). This fixes a review finding on D163/D164/D166 (main @
9f1fb29). It is general and names no task or niche.

## Why
Up to D166, the library had one entry per **(cause, op, scope)**. Two things went wrong:
- **The counts mixed different edits.** Three different rules that each helped once added up to "helped 3".
- **The shown text was only the latest.** `add_lesson` replaced an entry's text and kept its status. An approved
  entry could therefore show text the user never approved.

D166's trigger ("helped ≥ 3 on ≥ 2 tasks") read those mixed counts. A lesson could be promoted on evidence that was
never about it.

## What
1. **Families and lessons.**
   - **Families.** (cause, op, scope) is now a **family**, stored in `index.jsonl`. It counts every verdict, as
     today, in total and per niche. These counts are **for reports only**.
   - **Lessons.** Each lesson the reflector writes is **its own entry**, stored in `lessons.jsonl`. Its id is
     `<family>__L<k>`. It has its own text, cue, confidence, status, counts, per-niche counts, task ids and run ids.
     It also has its own folder with `evidence.jsonl` and `EXPERIENCE.md`.
   - **Families have no status.** Only a lesson is approved, rejected or promoted.
2. **A lesson's text never changes.**
   - New text in the same family is a **new lesson**, `unreviewed`.
   - The same text again is the same lesson. It is returned unchanged, and nothing is counted for it.
3. **A lesson gains evidence only when it is used.**
   - **First sample.** The round that wrote it: the reflector's helped verdict.
   - **Showing the id.** When Box 4 shows lessons (D164), each line carries the lesson's id in brackets. The section
     says that an edit following one of them adds `"from_lesson": "<id>"`. The section exists only when lessons are
     shown, so with `--lessons off` the prompt stays byte-identical.
   - **Checking a citation.** Plain code checks it in `probe.py::lesson_cite_problems`. The id must have been shown to
     this run's Box 4 for this cause, and the lesson's op and scope must be the edit's op and scope. A refusal is
     handled like any other: it is shown to the proposer, which is asked once more.
   - **Counting.** The probe's verdict counts for that lesson (`LessonLibrary.record_use`). A composed probe (D165)
     carries each part's citation.
   - **Record.** `result.json lessons.used` now lists the cited lessons as `{id, step, status}`. Before, it listed
     shown lessons whose fix ended done.
4. **Readers.**
   - **Retrieval (D164)** returns lessons, never families: approved, helped > hurt, never hurt in this niche, and the
     cause for Box 4.
   - **Promotion (D166)** reads lesson counts and sets a lesson's status. It never reads family counts.
   - **The CLI.** `scripts.lessons list` prints each family and its lessons. `approve` and `reject` take a lesson id;
     a family id is refused.
5. **Migration.**
   - When a pre-D167 library is opened, every row is turned into a family. Its `status`, `cue`, `lesson`,
     `confidence` and `lesson_run` move out.
   - A written lesson moves into its family as one lesson, `unreviewed`. Its counts start at 0, because the old counts
     were the family's. The old status is kept as `migrated_from_status`, for the record only.
   - The library is git-ignored and none had been written, so nothing in the repository changes.

## Tests (tests/test_lesson_identity_d167.py, red on 9f1fb29)
- Three runs whose reflector wrote three different rules give three lessons, each helped 1, and a family helped 3.
- An approved lesson keeps its text and status when new text is written. The new text is a new, unreviewed lesson,
  and the same text is the same lesson.
- A `from_lesson` naming a lesson that was not shown, or a lesson of another op, is refused and the proposer is asked
  again.
- A shown lesson that is not cited gains nothing. A cited one gains the probe's verdict, and `used` names it.
- An old library is migrated: the lesson moves into its family, unreviewed, and the family keeps its counts.

## Existing tests changed (the behaviour they pinned is the one this decision replaces)
- **`test_lessons_d163.py`**: the family has no status and no lesson text. The same text from three runs is one lesson
  counted once (nobody cited it). The CLI refuses a family id.
- **`test_lessons_read_d164.py`**: the seed helper writes a lesson and counts its uses through `record_use`. A
  proposer that does not cite the shown lesson leaves `used` empty, and the shown section carries the id.
- **`test_promote_d166.py`**: the seed helper builds the lesson's own counts the same way.
