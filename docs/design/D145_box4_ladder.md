# D145 — the Box 4 ladder

Status: **built** (branch claude/audit-fixes). This is the audit prompt's "D142". It applies in both protocols (Box 4
runs with `--adapt on`).

## Why
The audit found Box 4's rungs doing the wrong thing in several places:
- a provider-blocked step got more turns, which cannot help;
- a tool the helper already held was "granted" again and counted as a fix;
- a BLOCKED line about a held tool was diagnosed as a missing capability;
- replan_remaining dropped independent unrun steps and skipped Box 2's checks;
- the proposer's same edit on another step counted as already tried;
- a failed upstream re-run was never fixed itself;
- a model with no price silently disabled the USD limit;
- under D133 a step no fix recovered was reported as "stopped";
- the missing_input row named a fix that was never generated;
- make_tool failed silently with local tools off.

## What
0. **Defaults.**
   - adapt.yaml `run_options.max_turns {min 3, max 12}` (was max 8).
   - Plan helpers get 6 turns (`PLAN_MAX_TURNS`, was 5).
   - `more_turns` stays 3, so two "more turns" fixes fit per step.
1. **provider_blocked rungs** (adapt.yaml `provider_blocked: [compact_prompt, switch_model]`):
   - (a) `compact_prompt`: the step re-runs with the compact prompt variant (`compact_step_prompt`: the role card
     cut to Name, Goal and Outputs, and the rule blocks to their contract line).
   - (b) `switch_model`: re-run the step on another candidate model, when the run's router (fixed mode) has other
     allowed models. In routed mode a blocked call already falls back per call.
   - (c) when nothing is left, the task stops (even under D133), and the report names the refusal categories.
   - More turns are no longer a provider_blocked fix.
2. **A held tool is never granted again.**
   - The grant drops items the step's helpers hold. If all of them are held, there is no grant, with the note
     "tool held but failed, not granted again".
   - The watch turns a lacked line about a held tool (D132's `held_tool`) into the signal `held_tool_failed`
     (cause tool_error), with the evidence "tool held but failed: <tool> — <last error>".
   - A tool that a capability fault (D119) took away is not counted as held.
3. **Capability only from evidence.**
   - A bare BLOCKED line about a held tool is never a capability.
   - `open_requests` applies the same held_tool rule.
   - Capability requests raised during the run carry their step (`CapabilityRequest.step`). They count only for
     that step, not for every later step of the same role.
4. **replan_remaining** (Box 4's proposer edit):
   - Only the stuck step and the unrun steps built on it, directly or through others, may be dropped. Independent
     unrun steps stay.
   - The plan as it would be after the edit must pass Box 2's HARD checks (`replan_hard_problems`): every
     requirement covered, plus D142's requirements_checked, checks_valid and checks_reachable. Any failure is sent
     back to the proposer as a refusal reason.
   - D108's same_method also sees the stuck step's own method (it is out of the finished steps while being checked).
5. **rerun_upstream at depth 1**: if the re-run upstream step is itself stuck, `fix_stuck` runs on it once, within
   the same task limits (`fix_depth`).
6. **The proposer's edit key includes the step number**, so the same rule on a different step is not "already
   tried".
7. **Limits and outcomes.**
   - When a model has no price, the USD limit cannot be computed. The event `adapt_usd_unknown` is logged once,
     only the token limit is enforced, and the adapt report and run summary say so (`usd_limit_enforced: false`).
   - Under D133, a step no fix recovered is reported as `kept_going` (adapt_summary `kept_going`, with its own
     report section), not `stopped`.
   - `stop_when_exhausted` now applies only with `--failed-step run`. `false` means "never stop".
8. **The missing_input row's `set_run_option:max_input_chars`** is now generated when the step's input was cut.
   This was the second option the prompt offered, and it is under 20 lines.
9. **make_tool with local tools off**: the run summary prints "make_tool not run: tool writer: no code runner (local
   tools are off)" (adapt_summary `make_tool_unavailable`).

## As built (Oct 16)
- The flat and boss_reviewers baselines keep AutoAgents' 5 turns (the schema default). Only plan teams get 6, set in
  `instantiate`. Departure: the prompt said "schema default max_turns 6"; changing the schema would alter the papers'
  baselines (T7).
- `switch_model` needs a ModelRouter in fixed mode with other allowed models. With a single client (the claude-sonnet
  profile) rung (b) offers nothing, and the step goes to (c).

## Tests
tests/test_ladder_d145.py:
- the defaults;
- a blocked step recovered by the compact prompt;
- a step still blocked stops and names its categories;
- a held tool is tool_error, and a grant drops it;
- a request for a held tool is not open;
- the proposer key per step;
- max_input_chars for a capped input;
- replan_remaining drops only the dependents and its HARD checks refuse an uncovered requirement;
- the summary lines.

Updated: test_diagnosis_d128, test_ladder_d129, test_faults_d119, test_fixes_d117 and test_plan_runner (6 turns).
