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

## Running with Gemma 4 (D49)

Gemma models take no system message on some endpoints, so use `--merge-system` (the system text goes to the top of
the user message). `--reasoning-effort off|low|medium|high` is sent only when you set it; leave it out if the
endpoint rejects it. The model name below is a placeholder: check the exact id in the provider's model list.

Through the **Gemini API** (key from Google AI Studio; in the cloud environment, allow
`generativelanguage.googleapis.com`):

```bash
export AMOEBA_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
export AMOEBA_API_KEY=<your Gemini API key>
python -m scripts.run_task --tasks tasks/draft_eval_complex.jsonl --llm openai --model gemma-4-31b-it \
    --merge-system --draft-prompts d24 --topology plan --max-calls-per-run 60
```

Through **OpenRouter** (key from openrouter.ai; allow `openrouter.ai`; OpenRouter model ids carry the provider
prefix, e.g. `google/gemma-4-31b-it`, and a `:free` suffix for the free variant where one exists):

```bash
export AMOEBA_BASE_URL=https://openrouter.ai/api/v1
export AMOEBA_API_KEY=<your OpenRouter key>
python -m scripts.run_task --tasks tasks/draft_eval_complex.jsonl --llm openai --model google/gemma-4-31b-it \
    --merge-system --draft-prompts d24 --topology plan --min-seconds-between-calls 4
```

**Free tiers may use your prompts and replies to improve their products** (Google's free Gemini API tier and many
free OpenRouter models say so in their terms). Do not send anything confidential through a free tier; use a paid
key for private data.

## Layout

```
amoeba/
  llm/client.py            OpenAICompatibleClient, MockLLMClient
  llm/toy_mock.py          scripted stand-in model for the toy tasks
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
scripts/run_task.py        CLI
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
