# Plans before the Stage E full set

Two pieces of work the user asked to plan after the pilot and before the full set. Proposed D-numbers: D118 (skills in
prompts) and D119 (fault injection). Neither changes a default until the user approves it.

**Status (Oct 9).** D119 is built (offline tests only); D118 is still a plan.

## D118 — skills in prompts

**Why.** Skills are attached but rarely used. Of 56 skill attachments in 49 stored runs, a local:Bash call touched the
skill's folder in 5 (all xlsx); docx (8), pdf (7) and pptx (1) were never run. Today a helper's card carries the whole
SKILL.md body (up to `max_skill_chars`, 5,000 characters) as a data block plus "Full skill files are in …", the
Planner sees only "local skills for document formats: xlsx, docx, pptx, pdf", there is no way to look a skill up in
Box 3, and the step contract counts a local skill as used when any local call ran.

**1. A short skill block on each helper card.** Plain code writes, per attached skill:

    Skill xlsx — create and recalculate spreadsheets
    Path: /skills/xlsx (read-only in the sandbox; skills/xlsx/ in the workspace otherwise)
    Run:  python3 /skills/xlsx/scripts/recalc.py <file.xlsx> [timeout]
    More: local:Read /skills/xlsx/SKILL.md

- `Run` lines come from the skill itself: the first code block lines of SKILL.md that call a file under `scripts/`
  (matched by a regex on the folder's real file list), at most three; none found → "Run: (no script; read SKILL.md)".
- The full SKILL.md stays one `local:Read` away instead of 5,000 characters on every turn (fewer input tokens).
- The D71 note (LibreOffice missing → recalc.py will fail) stays, on the `Run` line it concerns.
- Code: `amoeba/localtools/skills.py` (`skill_card(entry, root) -> str`), used by `attach_skill` and the pool's
  `attach`; pool skills (text only, no files) keep a trimmed text block with no `Run` line.

**2. A skill shortlist for the Planner.** `toolbox_text` (Box 2) gains a section "Skills available for this task":
plain code ranks the vetted skill entries (pool index and local listing) against the task text with the existing
`rank` (shared words) and shows the best five: name, one line, and what to request (`{"name": "<skill>", "kind":
"skill"}`). The observers see the same list. Nothing is attached at Box 2; the toolbox step still decides.

**3. A `find_skill` tool in Box 3.** Given to every helper when the pool or local tools are on:

- `find_skill("<what you need>")` → up to five vetted skills (name, one line, path, Run line), ranked as above.
- `find_skill("use <name>")` → plain code attaches that skill to the calling helper (the short block joins its card
  from the next turn), within `max_per_helper`; logged as a `skill_found` trace event and in result.json
  `skills_attached` with `source: find_skill`.
- It never returns an entry the vetting refused (D60), and never runs anything.

**4. A stricter skill-used check.** For each skill on a step's helpers, the step contract counts it as used only when
a local:Bash call **that succeeded** ran a command containing the skill's path or the name of a file in its
`scripts/`, or the helper wrote "NOT NEEDED: <skill> — <why>". Otherwise: one refine turn naming it ("you were given
<skill> and never ran it: run <Run line> or write NOT NEEDED"), then `attached unused: <skill>` (status partial, as
for tools today, D61 G2) and the `unused_tool` stuck cause (allowed edits revoke_tool, add_role_rule).

**Tests (mock LLM).** The block from a real skill folder (xlsx: recalc.py found; pdf: scripts listed); a skill with no
scripts; the Planner's shortlist ranks a matching skill first and shows five at most; find_skill returns only vetted
entries and "use" attaches within the cap; the check passes on a Bash call running the script, fails on a Bash call
that does not touch the skill, passes on NOT NEEDED.

**Measure.** Re-run the stored-run count (skill attachments with a Bash call touching the skill folder: 5 of 56
today) on the Stage E full set, and the input tokens per step with the short block vs the full body.

## D119 — fault injection (test-only) — built Oct 9

Built as below, with these changes (spec row D119; README "Fault injection"): the capability fault keeps the tool in
the run's registry, so rung 2 grants it back (a pool-only shortlist entry could not be made the same way on every
task); max_turns gives the step 2 turns with no forced last turn (with 1 turn the forced last turn makes the helper
finish, so it would never run out of turns); the checks fault adds one hidden check (a markdown table with a Source
column) instead of a done_when line, which the format checks ignore when the output line has markers. The pair runner
does pass the flag, but only through its own `--inject-fault` and with the variable set for those runs only (user
request: three injected pairs in the pilot, `PLAN.md`). The real-model set below is still a plan.


**Why.** Stage E shows whether stuck steps recover, but not whether the watch names the right cause: the stored runs
have one tool_error and few max_turns. Injecting one known fault per cause gives a ground truth for the diagnosis
as well as for the recovery.

**The flag.** `--inject-fault <cause>:<step>[:<n>]`, repeatable, hidden from `--help`. run_task refuses it unless
`AMOEBA_TEST_FAULTS=1` is set in the environment, and the pair runner and batch scripts never pass it; result.json
records `faults` and the report marks such runs `injected`. A test asserts that the default is none and that the
flag is refused without the variable.

**The faults** (`amoeba/adapt/faults.py`, each a small wrapper at one point of the plan runner):

| Cause | Fault | Where | Expected diagnosis | Expected first fix |
|---|---|---|---|---|
| tool_error | a tool the step uses returns "error: <tool> failed: injected fault" for its first N calls (default 3), then works | the tool registry, for that step only | repeated_error → tool_error | more turns |
| capability | a tool the step needs is removed from its helpers and from the registry, but kept in the pool shortlist | PlanRunner before the step | capability_unfilled → capability | grant from the pool (rung 2) |
| missing_input (a) | an upstream output reaches the step cut to its first 200 characters (the artifact itself is whole) | inputs_text, first attempt only | missing_input, upstream named | add_dependency (passed in full) |
| missing_input (b) | the upstream artifact itself is cut to 200 characters after it ran | _save of the upstream step | missing_input, upstream named | rerun_upstream |
| max_turns | the step's max_turns is set to 1 | run_step | max_turns | more turns |
| checks | a stricter done_when ("a markdown table with a source column for every figure") the step's output check tests | the step's done_when before it runs | checks_after_retry → checks | more retry turns, then the proposer |

**What is reported per injection.** The injected cause and step; the stuck events on that step (diagnosed cause =
the first one; correct or not); false alarms (stuck events on other steps that the fault did not touch); the fixes
tried and their rungs; whether the step recovered (done), finished with a limitation, or the task stopped; the
adaptation's tokens. The summary is a confusion table (injected cause × diagnosed cause) and a recovery table
(cause × outcome × rung).

**Runs.** Mock-LLM tests first: each fault fires where it should and the watch's diagnosis on a scripted reply is the
expected one. Then, after approval, a real-model set: the six faults on two short tasks (r1-repo and m2-calc-g03),
one seed each, `--adapt on` only: 12 runs, roughly 1.2–1.8 M tokens and 3–4 hours sequential at the pilot's measured
rates, $0 at the current Gemma price (to be re-estimated from the pilot).
