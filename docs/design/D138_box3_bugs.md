# D138 — Box 3 correctness bugs (audit Phase B, B1–B10)

Status: **built** (branch claude/audit-fixes). The audit prompt numbers this decision D135; it is renumbered
because PR #42 used D134–D136. Applies in both protocols.

## Why
The Oct 15 audit of a9022801 found bugs in the plan runner that lose finished work, pass a search query on as a
step's output, crash after D133 skips a step, or count unreadable or meaningless replies as success.

## What
| # | Bug | Fix |
|---|---|---|
| B1 | `skip_step` saved meta with no `provenance`; `all_inputs_text` and `evidence_text` read `meta["provenance"]` and crashed | skip_step writes `EMPTY_PROVENANCE` (check_provenance's keys, all empty); both readers use `.get` with that default |
| B2 | `refine` and `critique` cleared `w.done`; a rework that gave no Final Output left the step with its last message | one `rework()` keeps the earlier Final Output and restores it (and its partials) when the rework ends without a new one; `rework_no_output` in the step meta and the trace |
| B3 | `_text` fell back to the last message (D44) when nobody wrote a Final Output | no Final Output and no partial means no output (""); meta `no_final_output: true` and `last_message` (for the report and Box 4 only); D133's `no_output` then skips dependents |
| B4 | in native mode any text reply ended the step | text without a tool call is the output only on the last turn or when it is clearly an answer (`answer_like`: more than 400 characters, or a markdown table or heading); otherwise it is a "no action" turn and the helper is told: "Call one of your tools, or call Final_Output with the step's output." (`native_text_no_action`) |
| B5 | the answer step, which holds no tools, was told to "Make them" (missing files) | `final_findings(fc, can_make_files)`: a step with no file-writing tool (local Write/Bash/Edit or a made tool) is told "List each missing file under Limitations as not made." |
| B6 | a figure the dispute resolver corrected did not reach steps that had already used it | after `replace_figure`, `mark_stale(corrected producers, verify step)`; D39's re-run applies |
| B7 | an unreadable review counted as AGREE | one repair call ("Your Verdict section must say AGREE or REVISE.", or chat_sections' own repair for a missing section), then REVISE with the issue "reviewer reply unreadable"; never an approval |
| B8 | find_tool (and failed calls) counted as re-checking calls for D65 | `rechecks(w.calls)`: only successful calls of tools that read or compute data (not find_tool, not Print) |
| B9 | a verifier saw inputs cut to max_input_chars while disputes compared the full texts | for a verify step, a capped input's full text is written to `inputs/step_<d>.md` in the workspace and the prompt names the path |
| B10 | `--failed-step`: library default "run", CLI default "dependents" | the library default is "dependents" too; the tests that check the stop-the-task behaviour of "run" now set it explicitly |

## As built (Oct 16)
- **B3** replaces D44's fallback; tests/test_plan_runner.py's D44 test was rewritten. The answer assembled by code
  and Box 4's evidence still see `last_message`.
- **B6** uses the existing D39 machinery: with `--rerun-stale` the consumers re-run once; without it they are only
  marked stale.
- **B7**: a reply with no Verdict section at all already had a repair call inside `chat_sections`, so no second one
  is made.
- **B9** applies only when the run has a local workspace (local tools); without one, the prompt is as before.
- **B10**: 9 tests across test_fixes_d117, test_proposer_d117, test_run_guard_d122, test_stuck_d117,
  test_unreadable_d123 and test_plan_runner set `failed_step="run"`, because they test the stop-the-task path.
- The "evidence block gets the full source list" part of B9 needed no change: `evidence_text` already lists every
  source the step fetched.

## Tests
tests/test_box3_bugs_d138.py (one per item: B1, B2, B3, B4, B5, B6, B8, B9, B10); B7 in tests/test_collab.py; B3
also in tests/test_plan_runner.py.
