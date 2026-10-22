# D152 — the two bugs found in run 71d2f910

Status: **built** (branch claude/run-gaps).

## 1. The cut note was checked as cited source text
- **What happened.** Step 1 of 71d2f910 wrote, honestly: `The printed output was cut off ("971 characters cut")
  [S24].` The citation check (D74) read the quoted phrase as a claim taken from S24. It did not find the phrase there
  and reported a mislabelled citation: `'971 characters cut' not in S24`. A step that names a cut is not making a
  claim about the source; the words are Amoeba's own note.
- **Fix.** `citecheck.CUT_NOTE` matches the cut note of D144/D147 (`… [N characters cut; the whole … is in …; open it
  with local:Read] …`), bracketed or quoted, with one nested bracket. It is blanked out before the claims of a stretch
  are picked. Its numbers ("1,203") are no longer read as figures. Everything else in the stretch is still checked.

## 2. A step reply hit the length limit
- **Why it happened.** In step 3, the helper wrote a whole Python script as the input of one `local:Bash` call
  (a heredoc).
  - The reply needed 5,222 visible tokens and 2,970 thinking tokens: exactly the 8,192-token room.
  - Thinking shares that room with the visible reply (D27).
  - The cut reply was thrown away and asked again with twice the room (D27). The second reply went through, and the
    command ran in full; the 1,616 characters in the trace are only the trace's preview. So nothing half-written
    ran, but one 8,192-token reply was paid for and discarded.
  - **The run had a warning.** An earlier reply of the same role group (workers, row 310) had already used 7,404 of
    the 8,192 tokens (90%). In the whole run, five helper replies used more than 5,900 tokens. Writing a file in one
    tool call is a normal way for a helper to work, so the fixed room was too small for this kind of work on this
    model.
- **Fix (general, not one number raised).** `TracedLLM` keeps the largest reply (visible + thinking tokens) each
  role group has needed in the run.
  - A call's room becomes `room_for(asked, peak)` = max(asked, 1.5 × peak), and never more than 2 × asked (the room
    D27's retry would give anyway).
  - So a group that came close to its room gets more on its next call, and a group that never came close keeps the
    room the caller asked for.
  - The room is a cap, not a price: a larger one costs nothing unless the reply uses it. A cut reply costs the whole
    reply twice.
  - The trace records `amoeba.room_raised_from` on a call whose room was raised.
  - In 71d2f910, the call at row 627 would have had 11,106 tokens of room, and the 8,192-token reply would not have
    been cut.

## Tests (written first)
tests/test_two_bugs_d152.py.
- **Before the fix**, all 4 failed:
  - the quoted cut note was reported as `'971 characters cut' not in S24`;
  - the bracketed note gave `['1,203', '4.40']` instead of `['4.40']`;
  - the second call of a group that had used 7,404 tokens got 8,192 again, was cut and retried
    (rooms `[8192, 8192, 16384]`);
  - the room was not capped, and not kept per group.
- **After the fix**, all 4 pass. Full suite: 1008 passed, 9 skipped.
