# Audit fixes (Oct 15 audit, D134–D143 in the prompt; D137–D146 here)

Branch `claude/audit-fixes`, from `claude/zen-fermi-mnaurm` after PR #42 merged. There is one commit per decision,
each with its own tests and a design note `docs/design/D1xx_*.md`. Each decision's commit is followed by an as-built
rebuild commit. Not merged.

**Numbering.** The prompt's D134–D136 were already taken by the merged PR #42, so the prompt's decisions are
renumbered: its D134 → D137, D135 → D138, …, D143 → D146. Its D136 (the model client) and D137 (the model check) were
mostly built by PR #42; D139 and D140 add only what was missing.

**The offline suite before every commit** (`python -m pytest -q`), passed and skipped:

| after | passed | skipped |
|---|---|---|
| base (7b7f5a1) | 832 | 9 |
| D137 | 846 | 9 |
| D138 | 855 | 9 |
| D139 | 859 | 9 |
| D140 | 859 | 9 |
| D141 | 884 | 9 |
| D141 live findings | 887 | 9 |
| D142 | 944 | 9 |
| D143 | 962 | 9 |
| D144 | 965 | 9 |
| D145 | 974 | 9 |
| D146 | 978 | 9 |
| Phase G | 979 | 9 |

The toy runs still work:
- `--toy --seed 0 --n 20 --topology flat`: mean score 1.000, 4,802.6 tokens and 6.35 LLM calls per run.
- `--topology boss_reviewers`: mean score 1.000, 3,756.7 tokens and 6.00 calls.

## One row per decision

| prompt | here | commit | what | tests |
|---|---|---|---|---|
| D134 security | **D137** | a1e7fbc | - Pool servers that run remote code are refused unless `--allow-remote-exec` is given (event `pool_refused_remote_exec`).<br>- http_get refuses non-public addresses ("refused: address not public") and re-checks every redirect, at most 3.<br>- The niche gate exempts `local:` and `made:` tools. | test_security_d137 |
| D135 Box 3 bugs | **D138** | ef5fb29 | B1–B10 in both protocols:<br>- a skipped step has no provenance;<br>- a rework keeps the earlier output;<br>- no output → no text (`no_final_output`, `last_message`);<br>- an answer-like text with no call;<br>- file findings only for file writers;<br>- stale marks after a dispute;<br>- an unreadable review counts as REVISE;<br>- real rechecks only;<br>- the full input as a file for the verifier;<br>- `failed_step` defaults to dependents. | test_box3_bugs_d138 |
| D136 model client (gaps) | **D139** | 4842120 | - Claude schemas: every field required, optional ones nullable.<br>- Replies validated in code (enums matched in any case, a null falls back to the default).<br>- A cached step head.<br>- The compact-retry hook in TracedLLM. | test_model_layer_d139 |
| D137 model check (gaps) | **D140** | 3b7de29 | - The plan observer probe.<br>- A Final_Output probe (second step turn).<br>- The repair call quotes the validation error. | test_model_check_d135 |
| D138 protocol v2 everywhere | **D141** | 63a0668, 4c40f03 | - `ask()` in three output modes, with one repair call.<br>- Typed reply models (no thought field) and v2 prompt files.<br>- `to_legacy`, so each reader is unchanged.<br>- A compact step-prompt variant.<br>- Live fixes: a schema Claude will not compile goes as json_prompt; the model-check gate. | test_protocol_v2_all_d141 |
| D139 plan–execution contract | **D142** | d7c4cc9 | - Typed step checks from a fixed vocabulary (17 checks).<br>- HARD checks requirements_checked, checks_valid, checks_reachable.<br>- Box 3 runs the checks (meta `contract_checks`); a failure feeds Box 4.<br>- `met` needs every covering check passed and the key terms above Limitations; `reported_missing`; `met_legacy`. | test_contract_d142 |
| D140 planning v2 | **D143** | 837833b | - Planning tier light / standard / full / auto.<br>- Only blocking issues go back; the plan diff is recorded.<br>- The best draft is published (`published_round`).<br>- A reading revision under code's rules, with its opening line (`reading_revised`). | test_planning_d143 |
| D141 step context | **D144** | 4edca90 | - Results over 2,000 characters go to `tool_results/` (first 800 + last 400 kept).<br>- Write inputs are summarised.<br>- The last 2 turns in full, older turns one line each.<br>- An echo is shown once.<br>- `chars_sent` / `chars_saved` per step. | test_context_d144 |
| D142 Box 4 ladder | **D145** | 3885ed7 | - provider_blocked: compact prompt → another model → stop naming the categories.<br>- No re-granting of a held tool (tool_error); capability only from evidence; requests per step.<br>- replan_remaining keeps independent steps and must pass the HARD checks; same_method sees the stuck step.<br>- rerun_upstream at depth 1; proposer key per step.<br>- USD-unknown warning; `kept_going`; max_input_chars for a capped input; a make_tool note.<br>- max_turns cap 12, plan helpers 6 turns. | test_ladder_d145 |
| D143 measurement | **D146** | e79a892 | - Stuck rows with all signals and `ground_truth: null`; `scripts.grade_episodes`.<br>- A profile `verifier`, and profile `claude-sonnet+gemma-verify`.<br>- `verifier_independence` per verify step in result.json.<br>- A clean sources folder for the own-result loop.<br>- The hash chain is documented as self-consistent only. | test_measurement_d146 |
| Phase G | — | d263aff | An offline end-to-end mock run of the fuel plan under v2. | test_e2e_fuel_v2 |

The required sentence is in spec §11 (D141's row) and in the Phase-2 spec: "Protocol v2 is a user-approved deviation
from the CLAUDE.md rule to copy AutoAgents/AgentVerse prompts word for word (user decision, Oct 15 2026). Legacy
prompts are kept unchanged under --protocol legacy." `--protocol` still defaults to `legacy`.

## Model check (live, protocol v2)

Files: `eval/manual/audit_fixes/model_check/`.

| probe | claude-sonnet | claude-sonnet-compat | gemma-api |
|---|---|---|---|
| reading | ok | ok | ok |
| planner | ok (json_prompt after Claude refused to compile PlanOut's grammar) | ok (same) | ok |
| observer | ok | ok | ok |
| plan observer | ok | ok | ok |
| step (native tools) | ok: a calc call | ok: a calc call | ok: a calc call |
| Final_Output | ok: typed fields | ok: typed fields | **unreadable**: ended with text, no Final_Output call |
| fix proposer | ok | ok | **unreadable** after the repair call |
| pool pick | ok | ok | ok (valid after one repair call) |
| output mode: schema | ok | ok | **unreadable** |
| output mode: submit_tool | ok | ok | ok |
| output mode: json_prompt | ok | ok | ok |
| cost | $0.0827 | $0.0854 | free tier |

- Neither Claude route had a blocked reply or a reasoning refusal.
- The model check would record Gemma as `supports.output_mode: submit_tool` (`--write` was not used, so models.yaml
  is unchanged).
- The first run found two bugs, both fixed in D141 (commit 4c40f03): PlanOut is too big for Claude's constrained
  grammar (400 "compiled grammar is too large"), and the probe's gate blocked the json_prompt retry.

## A/B (live)

The d97f9e59 step-1 prompt, sent 5 times per arm. Files: `eval/manual/audit_fixes/ab/`.

| arm | blocked | proper tool calls |
|---|---|---|
| (a) claude-sonnet-compat, legacy | **5 of 5** (content_filter) | 0 |
| (b) claude-sonnet native, v2 | **0 of 5** | **5 of 5** (fetch_url; arguments pass check_args) |

**The target is met** (0 blocked, 5 proper calls for b), so the work went on past Phase C.

## Live spend

| what | USD |
|---|---|
| model_check claude-sonnet ×3 (the first two hit the bugs above) | 0.0272 + 0.0235 + 0.0827 |
| model_check claude-sonnet-compat ×3 | 0.0294 + 0.0293 + 0.0854 |
| a schema-compile probe (400, no output) | ~0.0005 |
| A/B 5×2 | 0.1057 |
| model_check gemma-api ×3 | 0 (free tier) |
| **total** | **$0.38 of the $1.50 allowed** |

Not counted above: the as-built page's box-text check (`tools/arch_update.py`) ran on `gemini-3.1-flash-lite`, about
190k input tokens over the eight rebuilds. That model has no price in prices.yaml; it uses the free-tier Gemini key.

Keys came only from the environment (a chmod-600 file, loaded with `set -a`). They were never printed, written or
passed as flags. The key scan was run on the staged files before the commit that added `eval/manual/audit_fixes/`:
clean.

## Departures

1. **Renumbering**: D134–D143 → D137–D146 (D134–D136 were taken by merged PR #42), and the prompt's D136 and D137
   were mostly done there already.
2. **The v2 prompt headers** name D141 (`# source: ours — DEVIATION D141`), not D138. The D136 files keep their D136
   header.
3. **family_classify, plan_search and fix_proposer** keep their legacy prompt files under v2: they were already plain
   JSON prompts with no sections and no reasoning request. They go through `ask()`.
4. **The flat and boss_reviewers baselines** keep the legacy protocol and AutoAgents' 5 turns. Only plan teams get
   6 turns (set in `instantiate`, not in the schema default). This keeps T7 and the papers' baselines unchanged.
5. **The compact retry** covers step prompts only, not tool descriptions.
6. **SSRF guard**: an unresolvable host is allowed only through the proxy, and DNS rebinding between the check and the
   fetch is not closed.
7. **The `AMOEBA_TEST_PROTOCOL=v2` conftest hook** covers Boxes 3–4. Box 1–2 tests script legacy section text, so
   those boxes stay legacy there.
8. **PlanOut goes as json_prompt** for every model. Its check params are a free-form dict, and Claude refuses to
   compile its grammar anyway.
9. **`reported_missing`** counts as unmet, but not toward `no_deliverable`, and the refine turn is not asked about it.
   The prompt did not say.
10. **The tier's requirement count** is estimated before planning from the task's deliverable verbs. Web need is a
    keyword test. Box 1's reading adds nothing to these counts.
11. **Reading revision (a)** checks that a [P#] the planner was shown is cited. Whether the page really shows the
    reading's data does not exist is left to the plan observer's approval (b).
12. **Light tier**: there is no observer, so (b) does not apply there.
13. **Long tool inputs** other than local:Write are not cut (D144 asked for results and Write inputs only).
14. **`switch_model`** works only with a ModelRouter in fixed mode that has other allowed models. In routed mode a
    blocked call already falls back per call. With a single client, rung (b) offers nothing.
15. **A provider_blocked step that nothing recovers stops the task even under D133**: the prompt's rung (c) says stop.
16. **The `verifier` profile** applies under `--routing role`. Under `routed` the router's verifier_independence
    policy decides, and `fixed` drops per-role models. The reviewers group it covers also includes D51's critique
    reviewers.
17. **Model families** are read from model names.

## Proposed live runs (not run; for your approval)

Estimates come from the earlier runs' token counts at Sonnet's price ($2 input, $10 output per M):
- probe_box4 d97f9e59: $1.19 (stuck at step 1);
- probe_box4 e981a833: $3.43 (adapt off, stopped at the 1.5M cap);
- Sonnet B H3: $2.43, H2: $2.08, r1: $0.72.

v2 should cost less per useful call (no blocked calls, compaction). `--max-tokens-per-run 1500000` caps any one
run near $3.5.

Base (from the probe):

    BASE="AMOEBA_SANDBOX=1 python -m scripts.run_task --topology plan --llm openai --draft-prompts d24 --web-tools \
      --plan-search on --pool --local-tools on --local-tools-mode inprocess --replan off --ask-assumed off \
      --max-tokens-per-run 1500000 --planner-max-tokens 32768 --observer-max-tokens 16384 --protocol v2 \
      --native-tools on --deliverable-check on"

| # | run | command | estimate |
|---|---|---|---|
| 2a | fuel task, Sonnet, v2, adapt on | `$BASE --tasks tasks/probe_box4.jsonl --profile claude-sonnet --adapt on` | ~$2.5 (cap ~$3.5) |
| 2b | the same plan, adapt off | `$BASE --tasks tasks/probe_box4.jsonl --profile claude-sonnet --adapt off --drafts-from runs/<2a run id>` | ~$2.0 (cap ~$3.5) |
| 3a | fuel task, Gemma, adapt on | `$BASE --tasks tasks/probe_box4.jsonl --profile gemma-api --adapt on` (on a 429: `--profile gemma-openrouter`) | $0 (free tier; quota risk) |
| 3b | the same plan, adapt off | `$BASE --tasks tasks/probe_box4.jsonl --profile gemma-api --adapt off --drafts-from runs/<3a run id>` | $0 |
| 4 | H3, H2, r1 legacy vs v2, Sonnet | for T in h3 h2 r1: `$BASE --tasks eval/manual/sonnet/tasks/$T.jsonl --profile claude-sonnet --adapt on --protocol legacy`, then the same with `--protocol v2` (one-task files, the same ones Sonnet B used; `--protocol` given last overrides BASE) | legacy ≈ $5.2 (from Sonnet B), v2 ≈ $4–5; together ~$10 |
| opt | verifier independence | 2a with `--profile claude-sonnet+gemma-verify --routing role` | ~$2.5 |

**Total for runs 2–4: about $14.5**, or ~$17 with the optional run. The model_check tables (run 1) are above.

## What the prompt missed (or left open)

- **Claude's constrained output has a grammar size limit.** A schema as big as PlanOut is refused with a 400, not a
  bad reply, so "schema mode" needs a fallback. Now built.
- **The plan topology routes through the ModelRouter by default** (`--routing routed`), so a profile-level `verifier`
  only acts under `--routing role`. Deciding which mode the live runs use matters for D146's comparison.
- **Gemma ends a v2 step with text** instead of a Final_Output call. The plan runner's text fallback still reads it,
  but the fix proposer and schema mode are unreadable on Gemma. Its model check row would set `output_mode:
  submit_tool`.
- **Box 1's tier signals**: the prompt asks for a tier "from Box 1's reading", but the reading has no requirement
  count. A cheap pre-planning count from the task text stands in.
- **`stop_when_exhausted` vs D133**: the setting only meant anything with `--failed-step run`. It is kept and
  documented rather than removed.
- **No parallel waves**: steps stay sequential (noted as later work in D144).
