# D139 — the model layer: what the audit asked for beyond D134

Status: **built** (branch claude/audit-fixes). The audit prompt's "D136: native Claude client" was mostly built
already by D134 (PR #42, merged). This decision adds only what D134 lacked.

## Why
Measured against the audit prompt, the D134 client was missing four things:
- optional fields were left optional in the schema sent to Claude;
- replies were validated as-is, so a provider null for an optional field, or a changed enum case, failed;
- prompt caching covered only the system text and tool list, not the step prompt's stable head;
- a block with a non-reasoning category had no second chance at all.

## What
1. `to_claude_schema` (alias of `claude_schema`): every property is required, and a property that was optional
   becomes nullable (`anyOf` with `{"type": "null"}`, not doubled when already nullable). The limits stay at 24
   optional fields and 16 unions; nullable wrappers count as optional fields, not as unions.
2. `validate_reply(model, data)` (llm/client.py), used by `parse_schema_reply`, the native client and step v2's
   Final_Output:
   - validates in code with the pydantic model, so a bound dropped from the provider schema is still enforced;
   - matches enum strings case-insensitively;
   - when a provider null fails validation, retries with the nulls dropped, so fields fall back to their defaults.
3. **Prompt caching.** With `cache_prefix`, after the tool list and the system text, the last user message is split
   at the first `CACHE_BREAKS` marker (`# Work done so far`). The head (task, role card, step, inputs) is a cached
   block; the per-turn rest follows it. The plan runner's native turns pass `cache_prefix=True` (other clients
   ignore it, and it is not part of the response-cache key).
4. **Compact retry hook.** `TracedLLM.chat_messages(..., compact=messages)`: a blocked reply whose category is not
   `reasoning_extraction` (including no category) is sent once more as the compact variant (`compact_retry`
   event). D141 builds the compact variants. A reasoning refusal is never retried.

## As built (Oct 16)
- **effort** accepts low | medium | high, plus xhigh and max, which the API also takes.
- **Gemma's structured calls** already go through Gemini's OpenAI-compatible `response_format` when `schema=` is
  given (D134's compat client). D135's model check found Gemma's schema mode unreadable, so its output mode is
  submit_tool, and D141's `ask()` uses that.
- **The role card** is cached as part of the user message's head, not moved into the system text: moving it would
  change the legacy prompts.

## Tests
tests/test_model_layer_d139.py covers: required and nullable fields; enum case and nulls in validation and in a
typed Final_Output; the cached head split; one compact retry, none for a reasoning refusal, none without a compact
variant.
