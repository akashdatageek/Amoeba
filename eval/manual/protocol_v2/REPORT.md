# D134–D136 — native Claude client, model check, protocol v2 (Oct 16, 2026)

Branch `claude/protocol-v2`, from `claude/zen-fermi-mnaurm` at a902280. There is one commit per decision, plus a
box tag and the as-built rebuild:

| commit | what |
|---|---|
| bce5b5e | D134 native Claude client, refusal categories, no identical retry |
| 238410b | D136 protocol v2 (clean step protocol in native mode) |
| 7587a1d | D135 `scripts.model_check` |
| c5f9e93 | D136 box tag |
| aa0c3bc | as-built rebuild (7,527 file:line references, 0 bad) |

**Tests:** 803 passed and 9 skipped before; 832 passed and 9 skipped after.

New test files:
- tests/test_anthropic_d134.py (15 tests)
- tests/test_protocol_v2_d136.py (9 tests; one re-runs the 9 Box 4 test files in v2 mode)
- tests/test_model_check_d135.py (5 tests)

Everything is offline on the mock.

**Total live spend: about $0.20 of the $1.00 cap.** It is itemised at the end.

## 1. The A/B on the stored step-1 prompt (run d97f9e59)

The step-1 prompt of run d97f9e59 was rebuilt from its trace and sent 5 times to each arm, with max_tokens 4096.

- **(a)** claude-sonnet-compat with the legacy text protocol. This is the prompt exactly as the run sent it, with no
  tools.
- **(b)** claude-sonnet native (Messages API) with `--protocol v2`. This is the stored prompt's sections up to `# Tools`,
  then plan_step_v2's `# Tools` and `# How to act` sections with the same tool list, the same unavailable and
  local-tool lines and the same contract line. Plain code's wording (`v2_text`) is applied, and the 7 tools are typed.

The prompt is in `ab_prompt_v2.txt` and the per-call results are in `ab_results.json`.

| arm | blocked | proper tool calls | first call | input / output tokens per call |
|---|---|---|---|---|
| (a) compat + legacy | **5 of 5** (`content_filter`, 0 output tokens, no category) | 0 | — | 4,089 / 0 |
| (b) native + v2 | **0 of 5** | **5 of 5** (arguments pass plain code's check) | `fetch_url` every time; the step's first instruction is to fetch the EIA page | 5,533 / ~150 |

**Success criterion met:** (b) had 0 blocked replies and 5 proper tool calls.

The v2 prompt is 1,444 tokens longer than (a), for two reasons. Tool definitions are counted as input on the
Messages API. The Final_Output schema documents its fields.

## 2. Model check tables (`python -m scripts.model_check <profile>`)

Each probe uses the real prompt builder on a toy task (a van's weekly fuel cost). A gate stops each pipeline right
after its own call. The step turn uses `--protocol v2`. The full results are under `model_checks/` (also written to
data/model_checks/, which is gitignored).

### claude-sonnet (native, Messages API) — spent $0.0443

| probe | status | category | ms | in | out | USD |
|---|---|---|---|---|---|---|
| reading (Box 1) | **blocked** | **reasoning_extraction** | 1383 | 428 | 0 | 0.0009 |
| planner (d19, one round) | ok | | 8339 | 1446 | 1309 | 0.0160 |
| observer (check roles) | ok | | 5210 | 1998 | 643 | 0.0104 |
| step, native tools (v2) | ok — `calc` call | | 1449 | 2336 | 121 | 0.0059 |
| fix proposer | ok | | 1945 | 753 | 170 | 0.0032 |
| pool pick | ok | | 1811 | 309 | 136 | 0.0020 |
| output mode: schema | ok | | 2744 | 405 | 89 | 0.0017 |
| output mode: submit_tool | ok | | 1550 | 592 | 163 | 0.0028 |
| output mode: json_prompt | ok | | 1347 | 269 | 93 | 0.0015 |

- The check fails, as designed: `FAIL: reading was refused as reasoning_extraction — the prompt asks for written-out
  reasoning (prompt file: interpret.txt)`.
- Result: `supports.tools = true`, `supports.output_mode = schema`.

### claude-sonnet-compat (OpenAI-compatible endpoint) — spent $0.0444

| probe | status | category | ms | in | out | USD |
|---|---|---|---|---|---|---|
| reading | **blocked** | (none given) | 1602 | 428 | 0 | 0.0009 |
| planner | ok | | 8721 | 1446 | 1319 | 0.0161 |
| observer | ok | | 4653 | 1984 | 580 | 0.0098 |
| step, native tools (v2) | ok — `calc` call | | 1385 | 2336 | 121 | 0.0059 |
| fix proposer | ok | | 2023 | 753 | 187 | 0.0034 |
| pool pick | ok | | 2065 | 309 | 186 | 0.0025 |
| output mode: schema | ok | | 1837 | 405 | 89 | 0.0017 |
| output mode: submit_tool | ok | | 1514 | 592 | 163 | 0.0028 |
| output mode: json_prompt | ok | | 1790 | 269 | 91 | 0.0014 |

- The same block as the native route, but with no category: the reply is the opaque `content_filter` that D134
  replaces. The check does not fail on it, because no category means it cannot be named.
- Result: `supports.tools = true`, `supports.output_mode = schema`.

### gemma-api (gemma-4-31b through the Gemini API) — free tier, $0

| probe | status | ms | in | out |
|---|---|---|---|---|
| reading | ok | 15121 | 332 | 501 |
| planner | ok | 30594 | 951 | 1079 |
| observer | ok | 21412 | 1075 | 745 |
| step, native tools (v2) | ok — `calc` call | 7101 | 1511 | 228 |
| fix proposer | ok | 64874 | 534 | 2329 |
| pool pick | ok | 8074 | 206 | 278 |
| output mode: schema | **unreadable** | 2518 | 63 | 74 |
| output mode: submit_tool | ok | 12518 | 201 | 430 |
| output mode: json_prompt | ok | 9484 | 187 | 318 |

- No 429 this time, so gemma-openrouter was not needed. `OPENROUTER_API_KEY` is not set in this container.
- Result: `supports.tools = true`, `supports.output_mode = submit_tool`.

**`--write`:** applied to the two Claude entries. Their supports gained `output_mode: schema`, plus `checked_at:
2026-10-16`. It was **not** applied to Gemma; see 4.3.

## 3. Blocked calls by category, over all live calls of this session

| route | calls | blocked | categories |
|---|---|---|---|
| native (Messages API) | 1 smoke + 9 model check + 5 A/B = 15 | 1 | reasoning_extraction ×1 (interpret.txt) |
| compat | 9 model check + 1 verification + 5 A/B = 15 | 6 | none given (content_filter ×6: the interpret probe and all 5 legacy A/B calls) |
| gemma-api | 9 | 0 | — |

## 4. Where the request did not match the code or the service, and what I did instead

1. **"The OpenAI-compatible endpoint ignores response_format."** On Oct 16 it honoured a json_schema
   `response_format`. The compat `schema` probe validated. One extra call ($0.0017) returned exactly the schema's
   field names (`weekly_cost_eur`, `working`, `unit`), which the prompt never mentioned. The compat client therefore
   sends `response_format` when `schema=` is given, and `parsed` reports whether it was honoured. I did not re-test
   `strict`, `reasoning_effort` or `seed`.
2. **"Sonnet 5.5 refuses '## Thought'."** This held for `interpret.txt` on both routes. It did not hold for the d19
   planner (`autoagents_create_roles_format.txt`) or the observer (`autoagents_check_roles_format.txt`). Both carry
   `## Thought`, and both were answered on both routes in this one sample each. Earlier in the probe (Oct 15), 2 of 3
   fresh plans were blocked. So the refusal depends on the prompt and is not certain for every `## Thought` file.
   Planning v2 (the next prompt) should still remove it everywhere.
3. **Native tools on Gemma.** Native tool calling works on gemma-4-31b through Gemini's OpenAI layer: the step and
   submit_tool probes passed. Its registry entry says `supports.tools: false` ("no native tool calling is used").
   Writing `true` would switch every Gemma run to native tools through `--native-tools auto`, so I left it for you to
   decide. Gemma's `schema` mode does not work there.
4. **`provider: anthropic` was already in the registry entry for claude-sonnet-5-5, but nothing read the field.** It
   now selects the client. Profiles gained a `provider` key, and a profile is matched to the registry entry with the
   same model and route. Without this, the native and compat routes, which share one model id, would collide. The
   compat registry entry is `claude-sonnet-5-5-compat`.
5. **Thinking tokens.** On the Messages API `output_tokens` already includes thinking, while Amoeba bills output +
   reasoning. AnthropicClient therefore reports thinking as `reasoning_tokens` and the visible rest as
   `output_tokens`, so the bill equals the API's count.
6. **Line references.**
   - `cache.py:29` is `BLOCKED_FINISH`; `is_blocked` is at :33.
   - `parse_verdict_block` is at plan_runner.py:674, not :671.
   - The others matched within a few lines: client.py:77, cache.py:77-85, trace.py:237-245, plan_runner.py:278 /
     :2891 / :2905 / :3022, stuck.py:181-199, disputes.py:139, router.py:364.
7. **"The existing Box 4 tests must pass in both modes."** They do. The 9 files (D117 stuck / fixes / proposer / stage
   E, D124, D125, D128, D129, D133) are re-run by a test with every PlanOptions in native v2 mode. One stub needed a
   change, in tests/test_failed_step_d133.py: "step 2 never writes a readable reply" returned the text "nothing
   readable here". That is a valid step output in native mode, where text without a call is the output, so the stub
   now returns an empty reply. No Box 4 code changed.
8. **Additions the request did not list** (each recorded in the design notes' "As built"):
   - `Final_Output.not_needed[]`: D61's contract reads NOT NEEDED lines, and without it a v2 helper could not decline
     a tool.
   - `Print{note}`.
   - The summariser has no v2 file, so in v2 its `# Format` is replaced and its wording is fixed by `v2_text`. The
     answer's Limitations section is asked for as "a markdown section headed Limitations".
   - `Final_Output.status` is recorded, but plain code still decides the step status.
   - A reasoning refusal does not go to the router's next candidate.
9. **Not used:** the server-side `fallbacks` parameter (beta). It re-runs a refused call on another model inside one
   request, which would hide the refusal category that D134 exists to surface.

## 5. Live spend

| item | USD |
|---|---|
| native smoke call (D134) | 0.0001 |
| model_check claude-sonnet | 0.0443 |
| model_check claude-sonnet-compat | 0.0444 |
| compat response_format verification | 0.0017 |
| model_check gemma-api | 0 (free tier) |
| A/B 5 × 2 | 0.1038 |
| **Claude total** | **0.1943** |
| as-built box text (gemini-3.1-flash-lite, 2 rebuilds, ~80k tokens in) | ≈ 0.01 or less (Gemini key) |

## 6. Not started (next prompt)

- Planning v2: Box 1 and Box 2 schemas, and removing `## Thought` from interpret.txt and the d19 / d24 drafting
  prompts.
- Switching `--protocol`'s default to v2.
