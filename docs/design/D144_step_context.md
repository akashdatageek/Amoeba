# D144 — context handling in steps (both protocols)

Status: **built** (branch claude/audit-fixes). This is the audit prompt's "D141".

## Why
Every turn of a step resent the whole transcript: each tool result in full (a fetched page can be 20,000
characters), each local:Write with its whole file content, and Print's input twice (once as the input, once as
its echo). Long steps grew quadratically in tokens, and the useful recent turns were buried.

## What
1. **Long tool results go to a file.**
   - A result over 2,000 characters is written to `workspace/tool_results/step<n>_<k>.txt`, or to the run folder
     when local tools are off.
   - The transcript keeps the first 800 and the last 400 characters, plus a line naming the file and how much was
     cut. With local:Read the helper can open the whole file.
   - The shown path is relative, so a resumed run (D73) sends the same prompt and hits the cache.
   - The step's own record (`w.tool_results`, used by provenance and the verifier) keeps the full result.
2. **local:Write inputs are summarised** in the transcript as the path, the size and the first 300 characters
   (`write_summary`).
3. **Compaction, by plain code** (`_Work.view`): a turn sees the current turn and the last 2 turns in full. Each
   older turn is one line: who, the action, its input (first 120 characters), and ok/error with the first 160
   characters of the result (`one_line`). Notes plain code adds (refine, revision) are never shortened. There is no
   LLM summary.
4. **Print and unknown actions** whose result is only the echo of their input appear once.
5. **Counted per step**: meta `context` = {chars_sent, chars_saved} (the transcript characters sent, and those saved
   by compaction). The event `tool_result_spilled` records each file.
6. With the native Claude client, the stable prompt prefix is cached (D136, D139: `cache_prefix`).

## As built (Oct 16)
- The step transcript is now a list of blocks (`_Work.blocks`), each with its full and one-line form;
  `_Work.completed` is the full text.
- Steps stay sequential. Running a wave's independent steps in parallel is later work.
- Long tool *inputs* other than local:Write are not cut (the prompt asked only for results and Write inputs).

## Tests
tests/test_context_d144.py:
- one_line and write_summary;
- compaction keeps the last 2 turns in full, and notes stay;
- in a plan run, a 3,000-character result is cut in the transcript, saved whole to its file, and shown as one
  line three turns later;
- Print appears once;
- the counts are recorded.

tests/test_resume_d73.py still passes, so the spilled path keeps resumed prompts identical.
