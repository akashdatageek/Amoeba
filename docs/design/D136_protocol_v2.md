# D136 — a clean step protocol in native mode (`--protocol v2`)

Status: **built** (branch claude/protocol-v2; default `legacy`, switching the default is a later decision), with the
differences listed under "As built" at the end.

**User decision (Oct 16).** Protocol v2 is a deliberate, user-approved deviation from the CLAUDE.md rule that prompt
text is copied verbatim from the source repos. The verbatim prompts and T11 stay untouched; `--protocol legacy` keeps
them in force. Recorded in spec §11 (BUILD_SPEC_PHASE1.md, row D136) and in BUILD_SPEC_PHASE2.md ("Deviations of
Phase 2").

**Why.** D132 strips the `# Format` section in native mode. But the step prompts still said "name it under Action and
give its input under ActionInput", "put the whole step output in ActionInput", "choose Final Output", and the
unreadable-turn note asked for `## Thought` headings even in native mode. Every tool took one untyped `input`
argument. Claude refuses a prompt that asks for written-out reasoning (`reasoning_extraction`, D134). It also answers a
text tool protocol with an empty content_filter reply (D132).

## Design

1. **v2 prompt files**: `plan_step_v2.txt`, `plan_resolve_v2.txt`, `plan_verify_own_v2.txt`, each headed
   `# source: ours — DEVIATION D136`.
   - They keep every instruction of the legacy file (facts and sources, the research rules).
   - The `# Tools` section speaks of tool calls, and a final `# How to act` section replaces `# Format`.
   - Plain code's notes (contract line, last turn) go right above `# How to act`.
   - The notes plain code adds (verify, rework, retry, refine, contract, missing input, made tool, work-around, the
     local and pool tool texts, the summariser's prompt) are worded for v2 by `v2_text`.
   - `plan_step_system.txt` needed no change.
2. **The word ban** (`step_protocol.banned_words`). No native-mode prompt may mention:
   - Action, ActionInput or CurrentStep;
   - "Final Output" (the section; the tool is `Final_Output`);
   - `## Thought`;
   - a quoted `##` heading to write, a `# Format` section, or "must use exactly these sections".

   The `##` headings of data a prompt shows (an input step's output, a disputed figure) are not instructions. A test
   renders every v2 prompt with every note and checks.
3. **Typed tool arguments** (`TYPED`): `web_search{query}`, `fetch_url{url}`, `calc{expr}`, `local:Bash{command}`,
   `local:Read{path}`, `local:Write{path, content}`, `find_tool{need}`, `Print{note}`.
   - A pool tool with one MCP tool uses its MCP input schema; anything else takes one `input` string.
   - Plain code checks every call (`check_args`: required, unknown, type). A bad call is not run; its result names the
     schema and gives an example (`bad_call_text`, worded like D131's repeated-error hint), with a
     `tool_args_rejected` event.
   - Checked arguments become the input string the tool's runner already takes (`typed_input`).
4. **Typed `Final_Output`** (`FinalOutput`: `status` done|partial|blocked, `output`, `blocked[]`, `missing_data[]`,
   `missing_input[]`, `not_needed[]`, `verdict` PASS|FAIL|null, `issues[]`).
   - `final_text` renders it into the same marker text the legacy readers parse: Verdict first, the output, one
     BLOCKED / NOT NEEDED / MISSING DATA / MISSING INPUT line per item, the Issues last.
   - So `meta.blocked`, `missing_data`, `missing_inputs`, `not_needed` (adapt/stuck.py) and the verify reader are
     fed unchanged.
   - A typed verdict also goes straight into `meta.verdict / issues` (`typed_verdicts`), so a word "issues" inside the
     output cannot shift them.
   - **Box 4 needs no change.** Its nine test files pass in both modes (a test re-runs them with every PlanOptions in
     native v2 mode, via `AMOEBA_TEST_PROTOCOL=v2` in tests/conftest.py).
   - Text markers stay a fallback: a reply with text and no call is the step output as before, and a `Final_Output`
     with the old single `input` is read as text.
5. **The resolver** (`ResolverOutput`: `figures[{n, value, evidence, verdict}]`). `resolver_text` writes the blocks
   `parse_resolution` reads; `settle()` is unchanged.
6. **Fallback.** `--protocol v2` without native tool calling runs the steps in legacy. A `protocol_fallback` event is
   recorded, `result.json` gets `protocol: {asked, used, why}`, and the run summary prints a line.
7. **Native-mode notes.** `UNREADABLE_NOTE_V2` and `PROVIDER_BLOCKED_NOTE_V2` ask for a tool call or `Final_Output`,
   never headings.

## As built (Oct 16) — where the code differs from the request

- `FinalOutput` has one more list, `not_needed[]`. D61's step contract reads NOT NEEDED lines, so without it a v2
  helper could not decline a tool it was given.
- `Print` takes `{note}` (not listed in the request).
- `FinalOutput.status` is recorded (`final_output_typed` event) but plain code still sets the step status from its
  checks and markers. It is the helper's own word, and LLM proposes, code disposes.
- The summariser keeps `plan_summarise.txt`, which has no v2 file (none was asked for). In v2 its `# Format` section is
  replaced by `HOW_TO_ACT_TEXT` and its protocol lines are reworded by `v2_text`. The answer's Limitations section is
  asked for as "a markdown section headed Limitations" instead of a quoted `## Limitations`.
- tests/test_failed_step_d133.py: the stub for "step 2 never writes a readable reply" now returns an empty reply. Its
  old text ("nothing readable here") is a valid step output in native mode, where text without a call is the output.

Tests: tests/test_protocol_v2_d136.py (word ban, a v2 run's prompts and tool specs, typed arguments good and bad, a bad
call not run, Final_Output → markers = the marker parser, the typed output reaching the step meta as markers do, the
resolver's typed figures settling like their text, the fallback, the Box 4 tests in v2 mode).
