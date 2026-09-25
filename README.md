# Amoeba

A research system  in which a team of AI helpers is drafted per task and, in later
phases, reshapes itself under plain-code control. Motto: **first make it, then make it better.** Principle
everywhere: **LLM proposes, deterministic code disposes.**

**Phase 1** (this repo) builds three boxes only:

```
Task  ──▶  Plan a new team  ──▶  Team runs the task
           (AutoAgents drafting:   flat (AutoAgents) or
            planner + 2 observers,  boss + reviewers (AgentVerse)
            ≤3 rounds, then plain   ≤5 turns/step · ≤3 review rounds
            code builds the team)   every LLM call traced
```

No memory, monitor, gate or cost handling yet. Token counts are recorded in the trace, never enforced.

## Quick start

```bash
./clone_sources.sh                       # read-only clones the prompts are copied from (AutoAgents MIT, AgentVerse Apache-2.0)
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
python -m scripts.extract_prompts        # byte-exact prompt files → amoeba/config/prompts/
pytest -q                                # T1–T11, all offline

python -m scripts.run_task --toy --seed 0 --n 20 --topology flat
python -m scripts.run_task --toy --seed 0 --n 20 --topology boss_reviewers
python -m scripts.run_task "Reverse the string 'adaptive' then uppercase it" --topology flat
# real model, any OpenAI-compatible endpoint:
python -m scripts.run_task --toy --n 5 --llm openai --base-url http://localhost:8000/v1 --model qwen2.5
```

Without `--llm openai` a scripted stand-in model (`amoeba/llm/toy_mock.py`) answers, so everything runs with no
key. Each run writes `runs/<run_id>/{team.yaml, plan.json, trace.jsonl, capability_requests.json, result.json}` and the CLI prints mean
score, tokens and LLM calls.

## Box 3 plan runner and web tools (D31–D32)

```bash
python -m scripts.run_task --tasks tasks/draft_eval_complex.jsonl --llm openai --draft-prompts d24 --topology plan
python -m scripts.run_task --tasks tasks/draft_eval_complex.jsonl --llm openai --draft-prompts d24 --topology plan --web-tools
python -m scripts.smoke_web "Amazon RDS for PostgreSQL storage price per GB-month"   # one real call per web tool
```

`--web-tools` gives the plan runner `web_search` and `fetch_url` through Tavily. The key is read from the
environment variable **`TAVILY_API_KEY`** (never from a file). In the Claude Code cloud environment, add the domain
**`api.tavily.com`** to the environment's network allowlist (cloud environment menu → Edit → Network access); search
and page extraction both go through that one domain, so no other site needs to be reachable.

## Box 3 stocks its toolbox from the tool/skill pool (D56)

```bash
python -m amoeba pool refresh        # or `amoeba pool refresh`: MCP Registry servers + anthropics/skills → data/pool/
python -m amoeba pool status         # what the cache holds
python -m scripts.run_task --tasks tasks/draft_eval_complex.jsonl --llm openai --draft-prompts d24 --topology plan
python -m scripts.run_task ... --no-pool                 # the step off (e.g. to replay an older --llm-cache)
```

Before the runner is chosen, every capability request Box 2 recorded is matched against the cached pool by keywords
(plain code, the top 5), one short AI call (role group `pool`, default the workers' model) picks one candidate or
NONE, and plain code vets and attaches it. A tool needs an HTTPS remote, a source repository, a pinned version, no key
or its key in the environment variable named in `amoeba/config/pool.yaml` (`auth_env`), and a description unchanged
since the refresh and since it was first attached (`data/pool/pins.json`). It becomes `pool:<name>` for the asking
helper only and runs through `ToolRegistry.execute` with the MCP Python SDK, capped like web_search, every result an
[S#] source. A skill must be instruction-only and at most 5,000 characters; its SKILL.md text goes on the helper's
role card. Pool text only ever reaches a prompt inside marked POOL DATA blocks. Each request's outcome (status,
pool_id, candidates, reason) is in capability_requests.json; result.json has a `pool` summary. Without a cache the
run logs `pool_unavailable` and runs as before. Refreshing needs `registry.modelcontextprotocol.io`, `api.github.com`
and `raw.githubusercontent.com` (set `GITHUB_TOKEN` for a higher GitHub rate limit); a run needs only the hosts of the
servers it attaches.

## Cost controls (D45–D48)

```bash
# reuse the Box 2 drafts an eval_draft run already paid for (repeat k = --draft-pick k); no drafting calls
python -m scripts.run_task --tasks tasks/draft_eval_complex.jsonl --llm openai --topology plan \
    --drafts-from runs/draft_eval/cmp2-gemini-3.1-flash-lite-d24 --draft-pick 0 \
    --llm-cache runs/cache --llm-cache-mode record --llm-cache-namespace rep0 \
    --max-tokens-per-run 200000 --min-seconds-between-calls 1
```

- `--drafts-from DIR --draft-pick K`: reuse saved drafts (an eval_draft folder or a runs folder); result.json names
  the `draft_source`.
- `--llm-cache DIR --llm-cache-mode record|replay|off [--llm-cache-namespace NAME]`: every model reply and web result
  is stored; `replay` never calls anything (a miss ends the run with `error="cache_miss"`).
- `--max-tokens-per-run N`, `--max-calls-per-run N`: the run stops cleanly with `error="budget"`; what ran is saved.
  Every run prints its billed tokens and an estimated cost from `amoeba/config/prices.yaml` (fill in the prices;
  a model without one gets tokens only).
- HTTP 429/503 are retried up to `--max-rate-retries` (5) with exponential waits or the server's Retry-After;
  `--min-seconds-between-calls` spaces calls out for free tiers.

## Model profiles and Gemma 4 (D49, D54)

With `--llm openai` the model is chosen by a **profile** in `amoeba/config/models.yaml`. The default profile is
**`gemma-api`**. Without `--llm openai` (the default, and in every test) the offline stand-in model answers.

| profile | endpoint | model | settings |
|---|---|---|---|
| `gemma-api` (default) | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemma-4-31b-it` | merge_system, reasoning_effort low; key in `GEMINI_API_KEY` |
| `gemma-openrouter` | `https://openrouter.ai/api/v1` | `google/gemma-4-31b-it:free` | merge_system; key in `OPENROUTER_API_KEY` |
| `gemini-flash-lite` | Gemini API | `gemini-3.1-flash-lite` | as in the 2026-09-24 baseline; key in `GEMINI_API_KEY` |
| `gemini-flash` | Gemini API | `gemini-3.5-flash` | as in the 2026-09-24 baseline; key in `GEMINI_API_KEY` |

To switch, pass `--profile NAME` to `run_task` or `eval_draft`, or change `default:` in the file:

```bash
export GEMINI_API_KEY=<your Gemini API key>        # never commit it; AMOEBA_API_KEY, when set, is used first
python -m scripts.list_models --profile gemma-api   # check the model names this endpoint really offers
python -m scripts.run_task --tasks tasks/draft_eval_complex.jsonl --llm openai --profile gemma-api \
    --draft-prompts d24 --topology plan --max-calls-per-run 60
python -m scripts.run_task ... --llm openai --profile gemini-flash-lite
```

**Model names must be checked against the provider.** Model names in the file are what the provider called its
models when the file was written. Providers rename and retire them, so run `scripts/list_models.py` first; it
marks the profile's models with `*` and names any it cannot find. OpenRouter ids carry the provider prefix and a
`:free` suffix for the free variant.

A profile can set:
- `base_url` and `model`;
- `api_key_env`: the variable that holds the key;
- `merge_system`: Gemma takes no system message on some endpoints, so the system text goes into the user message;
- `reasoning_effort`: `off | low | medium | high`, sent only when set;
- `max_tokens`: the reply limit of calls that set none;
- `roles`: a `model` and `max_tokens` per role group. The groups are `planner`, `observers` (both Box 2 checkers),
  `workers`, `reviewers` (boss_reviewers critics, the plan runner's verify steps and critique reviews) and
  `summariser`.

What overrides the profile:
- `--base-url` / `--model` flags, then `AMOEBA_BASE_URL` / `AMOEBA_MODEL`, replace the profile's endpoint and
  default model. Per-role models still apply.
- `--merge-system` / `--no-merge-system` and `--reasoning-effort` (`unset` sends nothing) replace the profile's
  settings.
- `--planner-max-tokens` / `--observer-max-tokens` replace the profile's per-role limits.

Every trace line carries `amoeba.profile`. Each AI line holds `gen_ai.request.model` (asked for) and
`gen_ai.response.model` (the exact name the API returned). result.json has `profile` and `models`
(`requested` per role group, `returned`).

**Free tiers may use your prompts and replies to improve their products** (Google's free Gemini API tier and many
free OpenRouter models say so in their terms). Do not send anything confidential through a free tier; use a paid
key for private data.

## The as-built page keeps itself up to date (D55)

`docs/arch/phase1.html` is rebuilt from the code by `python tools/arch_update.py`. That script does nothing when no input
changed. After `git config core.hooksPath tools/hooks` it runs after every commit, and the Claude Code Stop hook
(`.claude/settings.json`) runs it when Claude Code stops. Code joins a box with a `# box: <id>` line above its def or
class. Box text is re-checked by a cheap model (`arch-text` profile) only for boxes whose extracted facts changed, and
the tokens are logged in `docs/arch/text_log.jsonl`. Numbers in the text come from the code. Set `ARCH_TEXT_LLM=off` to
never call a model; changed boxes are then marked stale.

## Layout

```
amoeba/
  llm/client.py            OpenAICompatibleClient, MockLLMClient
  llm/toy_mock.py          scripted stand-in model for the toy tasks
  llm/profiles.py          D54: model profiles (config/models.yaml), per-role routing
  config/schema.py         TeamConfig, AgentSpec, Edge, PlanStep, Limits, PromptRef
  config/validate.py       V1 V3 V5 V6 V7 V8
  config/io.py             load_yaml, dump_yaml, config_hash
  config/prompts/          verbatim prompt files (one source-header line each) + render()
  task/models.py           Task, Episode, Draft, RunResult, ...
  task/source.py           ToyTaskSource — 3 families with known answers
  task/evaluate.py         exact-match scoring (no AI judge in Phase 1)
  task/parsers.py          parse_sections, parse_role_blobs, parse_plan, parse_critic (regexes from the sources)
  task/draft.py            BOX 2: draft_team()
  task/instantiate.py      Draft → TeamConfig (flat | boss_reviewers)
  interp/runtime.py        BOX 3: Interpreter.run() → run_flat / run_boss_reviewers
  interp/trace.py          TraceWriter (JSONL, OpenTelemetry GenAI names), TracedLLM
  tools/registry.py        echo, calc
  safety/envelope.py       allowed_tools per role, max_agents
  pool/                    D56: index (refresh), match, stock (pick, vet, attach), mcp (pool tools)
  cli.py                   D56: `amoeba pool refresh` / `python -m amoeba pool refresh`
scripts/run_task.py        CLI
scripts/list_models.py     D54: the models an endpoint offers (check a profile's names)
scripts/extract_prompts.py copies the prompts out of repos/
tests/                     T1–T11 with fixtures
spec/                      BUILD_SPEC_PHASE1.md (the spec), VERIFICATION_PHASE1.md, full spec for reference
repo_notes/                what the source repos actually do
diagram/                   living architecture page (drill-down boxes, hover cards, change requests)
```

## Read in this order

1. `CLAUDE.md` — rules for anyone (human or agent) changing this repo.
2. `spec/BUILD_SPEC_PHASE1.md` — §13 is the build instruction; §11 lists deliberate deviations from the papers.
3. `spec/VERIFICATION_PHASE1.md` — pseudocode with `file:line` citations into the source repos.
4. `diagram/amoeba_phase1.html` — open it in a browser; `diagram/CLAUDE_CODE_EDIT_LOOP.md` explains the edit loop.

## Phase 1 results (offline stand-in model, seed 0, n = 20)

| topology | mean score | mean tokens | mean LLM calls |
|---|---|---|---|
| flat | 1.000 | 4046.0 | 5.35 |
| boss_reviewers | 1.000 | 3112.7 | 5.00 |

Tokens are the mock's estimate (`len(text) // 4`). The score is 1.0 because the stand-in is well-behaved by
construction — it verifies the pipeline does not lose the answer, not model quality.

## Where the code departs from the spec

- `AgentSpec.role_prompt` holds the drafted role prompt (rendered into `{role}` of the worker's user message).
- `agentverse_solver_append` is stored verbatim; the deviation (dropping "Write the code step by step.") is
  applied at load time as `seed:agentverse_solver_append_generic`.
- `tests/fixtures/manager_output_real.txt` is hand-composed in AutoAgents' output format, not a captured run.
- Draft post-checks: a role blob without a `name` is skipped; duplicate names keep the first.

Everything else — the caps 3/5/3, the `No Suggestions` / `Final Output` sentinels, the observer history strings,
the 5th-iteration hint, the shared scratchpad, chat-history delivery of plans and reviews, silent-agree, solver ≤ 4
calls — follows the source code, with every deliberate departure marked `DEVIATION` in the code and spec §11.

## Licences of copied text

Prompt text in `amoeba/config/prompts/` is copied verbatim from AutoAgents (MIT) and AgentVerse (Apache-2.0);
each file's first line names the source path and lines. Nothing is copied from EvoMAS (CC BY-NC).
