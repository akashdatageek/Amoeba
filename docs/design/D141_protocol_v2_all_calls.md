# D141 — protocol v2 for every call

Status: **built** (branch claude/audit-fixes). This is the audit prompt's "D138". D136 (PR #42) made the step
protocol typed. This decision does the same for every other model call.

Protocol v2 is a user-approved deviation from the CLAUDE.md rule to copy AutoAgents/AgentVerse prompts word for word
(user decision, Oct 15 2026). Legacy prompts are kept unchanged under --protocol legacy.

## Why
Under `--protocol v2` only the step turns were typed. Every other call still sent a legacy prompt that asked for
written sections and was parsed by regex:
- Box 1: the task reading, the family and the plan search;
- Box 2: the planner and both observers;
- Box 3: the critique, the replan, the summary and the pool pick;
- Box 4: the proposer and the tool writer.

Some of those prompts ask for a written-out thought, which Claude refuses (`reasoning_extraction`, D134). A
regex-parsed section also fails silently when the model drifts from the format.

## What
1. **Reply models** (`amoeba/task/schemas.py`). There is one pydantic model per call kind: ReadingOut, FamilyOut,
   PlanSearchOut, PlanOut, ReviewOut (with typed IssueOut), CritiqueOut, ReplanOut, PoolPickOut and ToolWriterOut.
   D136's StepFinal and ResolveOut and D117's FixReply are reused. No model has a thought, reasoning or
   chain-of-thought field. Each has an optional `rationale` of at most two sentences, which goes to the trace only
   (`ask_rationale`).
2. **`ask()`** (`amoeba/llm/ask.py`). One structured call goes out in the output mode the model passed in the model
   check (models.yaml `supports.output_mode`):
   - `schema`: the provider enforces the schema;
   - `submit_tool`: a `submit_<kind>` tool, offered but never forced;
   - `json_prompt`: the schema is shown in the prompt.

   Every mode validates the reply in code (`validate_reply`). An invalid reply gets one repair call that quotes the
   exact validation error. A second invalid reply, or a blocked one, raises `Unreadable`. A schema Claude cannot
   take (FixReply's free-form params) goes as json_prompt.
3. **v2 prompt files**, each headed `# source: ours — DEVIATION D141`: interpret_v2, plan_create_v2,
   plan_review_team_v2, plan_review_plan_v2, plan_critique_v2, plan_replan_v2, plan_summarise_v2, pool_pick_v2 and
   tool_writer_v2. They keep the legacy prompts' content (rules, inputs, decisions) and drop the sections to write.
   No v2 prompt names Action, ActionInput, a Final Output section, a heading to write, or asks the model to show or
   explain its reasoning (tested).
4. **Each call site renders its typed reply into the text its legacy reader parses** (`to_legacy`, `plan_markdown`,
   `review_text`). The code after each call is the same in both protocols, as D136 does for Final_Output. The run's
   protocol is carried on its TraceWriter (`trace.protocol`, read by `protocol_of`), so Box 1 and Box 2 see it
   without a signature change.
5. **Compact variant.** `compact_step_prompt` trims the role card to Name, Goal and Outputs, and the rule blocks to
   the contract line. Under v2, a native step turn passes it to TracedLLM as `compact=`. A reply blocked for any
   reason other than a reasoning request is sent once more as the compact variant (D139's `compact_retry`).
6. **Unreadable replies fail safe.**
   - A reading gives no entities.
   - A review counts as REVISE, never as approval.
   - A pool pick picks nothing.
   - The planner fails the draft, as a missing section does.
   - The proposer stops; ask() has already made the repair call, so no second repair is made.

## As built (Oct 16)
- Under v2, drafting always uses the d24 prompts' content (D19 has no v2 form).
- family_classify, plan_search and fix_proposer were already plain JSON prompts with no sections or reasoning
  request. They are sent unchanged, through `ask()`.
- The baseline topologies (flat, boss_reviewers) keep their legacy prompts. They are the papers' baselines.
- `AMOEBA_TEST_PROTOCOL=v2` (tests/conftest.py) runs the Box 3 and Box 4 tests under v2. Box 1 and Box 2 stay
  legacy there, because those tests script legacy section text. A legacy tool-writer reply is adapted to
  ToolWriterOut.
- The `Action` word ban skips "Action Observer", which is a role name.

## Tests
tests/test_protocol_v2_all_d141.py:
- the word ban on every *_v2 prompt;
- no thought field in any schema;
- the rationale cut to two sentences;
- `ask()` in all three modes, the repair call, Unreadable, and a blocked reply;
- read_task, family, pool pick and draft_team under v2;
- the critique, replan and tool-writer renderings;
- legacy drafting unchanged;
- the compact variant and the compact retry.

tests/test_model_check_d135.py checks that the v2 probes use the typed builders. tests/test_protocol_v2_d136.py runs
the Box 4 tests under v2, and they pass.
