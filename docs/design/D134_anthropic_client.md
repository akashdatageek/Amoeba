# D134 — native Claude client and refusal categories

Status: **built** (branch claude/protocol-v2), with the differences listed under "As built" at the end.

**Why.** All Claude calls went through Claude's OpenAI-compatible endpoint (`OpenAICompatibleClient`). That endpoint
ignores `response_format`, `strict`, `reasoning_effort` and `seed`, and answers a blocked call with an empty
`content_filter` reply that names no reason. The probe re-run (Oct 15) was blocked in planning. The cause is in the
prompts: 13 prompt files ask for a "## Thought" section, and Sonnet 5.5 refuses that as `reasoning_extraction`.
Nothing in the run could tell this refusal from a real safety refusal. D128 then retried every blocked reply once
with the same prompt, and the retry was blocked the same way every time.

## Design

1. **`AnthropicClient(LLMClient)`** (`amoeba/llm/anthropic_client.py`, the `anthropic` SDK). It has the same
   `chat_messages(messages, seed, max_tokens, tools=None)` as every other client, plus optional per-call keywords:
   - `schema` (a pydantic model): sent as `output_config.format` json_schema; the reply is validated into
     `ChatResponse.parsed`.
   - `effort`: low | medium | high | xhigh | max, sent as `output_config.effort`.
   - `thinking_display`: `summarized` sends `thinking: {type: adaptive, display: summarized}`. `omitted` sends
     nothing, and adaptive thinking stays on (Sonnet 5.5's default).
   - `cache_prefix`: puts `cache_control` on the system text and on the last tool.

   **Mapping.**
   - System messages become the top-level `system`.
   - An assistant message's `tool_calls` become `tool_use` blocks.
   - A `tool` message becomes a `tool_result` block in a user turn.
   - Consecutive turns of one role are merged.
   - OpenAI function specs become `{name, description, input_schema}`.
   - Tool calls come back in `ChatResponse.tool_calls`, with the input as a JSON string, as the OpenAI client
     returns it.

   **Never sent:** a temperature, a seed, a forced `tool_choice` (400 on Sonnet 5.5), a thinking budget.
2. **Schema converter** `claude_schema`: a pydantic JSON schema converted to Claude's subset.
   - Every object closed (`additionalProperties: false`).
   - Numeric, length and pattern bounds dropped, and `minItems` above 1.
   - `$ref` inlined; recursion raises.
   - At most 24 optional fields and 16 unions; more raises `SchemaTooComplex` before any call.
   - A free-form `dict` field also raises (structured outputs need named fields).
3. **New `ChatResponse` fields, all defaulted:** `parsed`, `thinking_summary`, `refusal_category`,
   `cache_read_tokens`, `cache_write_tokens`.
4. **Refusal.**
   - `stop_reason: refusal` becomes `finish_reason: "refusal"`, and `stop_details.category` becomes
     `refusal_category`.
   - `is_blocked` already lists `refusal`, so a refusal is still a blocked reply everywhere: the cache never stores
     it, there is no repair call, Box 4 cause `provider_blocked`.
5. **Retry policy by category**, replacing D128's identical retry in `TracedLLM`:
   - `reasoning_extraction`: no retry. A `prompt_asks_for_reasoning` event names the agent and the prompt files the
     call was rendered from (`prompt_sources`: each file's first literal line; files asking for "## Thought" come
     first). The step turn is unreadable (`REASONING_REFUSED_NOTE`), and `result.json` gets `reasoning_refusals`. The
     run summary prints a `!!` line per agent and prompt file.
   - Any other category, or a block with no category: no identical retry. In routed mode the router still sends the
     call to the next candidate model (router.py, D128). A reasoning refusal is not sent on, because it is the
     prompt's fault.
   - Box 4's `provider_blocked` evidence names the refusal categories when every blocked turn has one, else says
     "content filter, no category given". The signal carries `categories`.
6. **Response cache.** The new options stay out of `request_options`, so Gemma's and the OpenAI-compatible route's
   keys are unchanged and still hit (tested against the pre-D134 formula).
   - The schema name and the effort join the key only when set.
   - The Messages-API route adds `api: anthropic-messages`, so its replies are kept apart from the compat route's.
   - `thinking_display` and `cache_prefix` do not change the answer and stay out.
7. **Prompt-cache accounting.**
   - `input_tokens` is the whole prompt (fresh + cache read + cache write), and the trace records
     `amoeba.usage.cache_read_tokens` / `cache_write_tokens`.
   - `prices.yaml` and the registry price both carry `cache_read` 0.20 and `cache_write` 2.50 USD per 1M tokens
     for Sonnet 5.5 (Claude's pricing page: 0.1x and 1.25x the input price).
   - `limits.estimate` and the router's `ModelEntry.usd` price the cached parts apart.
   - Thinking tokens (`output_tokens_details.thinking_tokens`) are reported as `reasoning_tokens`, and
     `output_tokens` is the visible rest, so the bill (output + reasoning) is the API's output count.
8. **models.yaml.**
   - `provider: anthropic` (on a profile or a registry entry) selects `AnthropicClient` (`make_client`).
   - Profile `claude-sonnet` and registry entry `claude-sonnet-5-5` use it.
   - `claude-sonnet-compat` / `claude-sonnet-5-5-compat` keep the OpenAI-compatible route.
   - A profile is matched to the registry entry with its model and the same route.
9. **Mock.** `MockLLMClient(schema=...)` takes a scripted dict (or JSON text) and validates it into `parsed`. A
   scripted `ChatResponse` is returned as it is, for refusal tests.

## As built (Oct 16) — where the code differs from the request

- The OpenAI-compatible client also takes `schema`. It sends OpenAI's `response_format` json_schema and validates the
  reply. The endpoint is reported to ignore the field, and D135's model check shows whether it does; `parsed` stays
  None when it does.
- `effort`, `thinking_display` and `cache_prefix` are accepted and ignored by the OpenAI-compatible client and the
  mock. An unknown per-call option is a `TypeError` in every client and wrapper (`opts_kw`).
- The reasoning refusal skips the router's next-candidate fallback ("no retry" taken literally); other categories
  keep it.
- Not used: the server-side `fallbacks` parameter (beta). It would re-run a refused call on another model inside one
  request, which hides the category this decision exists to surface.

Tests: tests/test_anthropic_d134.py (request mapping with a stand-in SDK object, reply mapping, the schema converter on
Rubric / Task / AgentSpec, refusal mapping and retry policy, cache-key stability, thinking summary and cache tokens in
the trace, mock schema); tests/test_diagnosis_d128.py updated (no retry); tests/test_claude_profile.py (the two
routes).
