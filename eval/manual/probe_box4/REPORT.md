# Box 4 probe: one fuel-surcharge task, Sonnet adapt on vs off

**Code:** branch `claude/zen-fermi-mnaurm` at `3ed22afb600e205b987248ac64f8f74b44bf3960` (D127–D131 in: 50e1954, ff3906d, 7f77083, 85ff37d, 1e41d32). Offline suite before the runs: 792 passed, 9 skipped. No Amoeba code was changed.
**Task:** `tasks/probe_box4.jsonl`, id `probe-b4-fuel`, prompt word for word as given. No hints, no `--clarify`, no context files.
**Date:** 15 October 2026.

## The headline

**Claude's content filter blocked most of the Sonnet calls.** Runs `d97f9e59`, `e981a833` and `206c61a7` had 57%, 72% and 74% of all their calls blocked (77% of run 2's step calls). Every blocked call was `finish_reason: content_filter` with 0 output tokens. That is far above the 30% line. The filter, not the six built-in difficulties, decided every Sonnet run. Box 4 never saw C1–C6.

**Gemma did not run.** Google's API answered 429 RESOURCE_EXHAUSTED ("check quota") to the first Box 1 call (`eb1aab56`). The run gave up after 5 retries. On your instruction, run 3 was redone with Sonnet.

## What changed from the plan

| Planned | What ran | Why |
|---|---|---|
| Run 3: Gemma, adapt on, fresh plan | `eb1aab56`: Gemma, stopped at call 1 by a quota 429 | Gemma API quota. Not fixed (your rule). |
| (replacement) | `2f0f0679`: Sonnet, adapt on, fresh plan. Died in drafting. | The filter blocked Box 1 (the call and its retry) and the planner (the call and its retry, cut off after 1,066 and 1,639 output tokens). The draft had no sections. |
| (replacement) | `206c61a7`: Sonnet, adapt on, run 1's plan (`--drafts-from`) | Your choice after `2f0f0679` failed. It is a second adapt-on sample on the exact plan run 2 used. |
| Run 4: fault injection | Not run | `capability:auto` arms step 1 (the first work step with tools). Step 1 was blocked on every adapt-on attempt. Box 4 ranks `provider_blocked` first, so the fault could not be reached. |

Keys came from the session's chmod-600 env file, loaded into each run's environment, never printed or passed as flags. Local tools ran in-process with `AMOEBA_SANDBOX=1`. One aborted start of the Gemma run (killed after 1 trace line so it could be relaunched detached) is not counted. The toy runs that the as-built hook made (`c3e6d9fa`, `1ab27e92`, `1b5e1ad9`, `c0af746f`) are not part of this probe.

## Commands

Base (as given):

    AMOEBA_SANDBOX=1 python -m scripts.run_task --tasks tasks/probe_box4.jsonl --topology plan \
      --llm openai --draft-prompts d24 --web-tools --plan-search on --pool \
      --local-tools on --local-tools-mode inprocess --replan off --ask-assumed off \
      --max-tokens-per-run 1500000 --planner-max-tokens 32768 --observer-max-tokens 16384

- `d97f9e59` (run 1): base + `--profile claude-sonnet --adapt on`
- `e981a833` (run 2): base + `--profile claude-sonnet --adapt off --drafts-from runs/d97f9e59-1df8-43df-bafa-90f6fd33324d`
- `eb1aab56` (run 3, Gemma): base + `--profile gemma-api --adapt on`
- `2f0f0679` (run 3, Sonnet): base + `--profile claude-sonnet --adapt on`
- `206c61a7` (run 3b): base + `--profile claude-sonnet --adapt on --drafts-from runs/d97f9e59-1df8-43df-bafa-90f6fd33324d`

`--drafts-from` with a single run folder loads that run's `plan.json` (there is no `draft.json`). The `plan.json` sha256 is the same in `d97f9e59`, `e981a833` and `206c61a7`: `3a802b3e…8578`. The step lists are identical (11 steps).

## C1–C3 checks before run 1 (2 lookups)

- **C1 holds.** EIA's weekly diesel table covers the U.S., the PADDs and sub-PADDs, and California. Indiana is not listed.
- **C2 holds.** The full history is offered only as an XLS file ("full history XLS").
- **C3 holds.** ATRI's 2026 edition (2025 data) is reported in the press release and the trade press: $2.336 per mile in total, $1.854 per mile without fuel, so fuel is about $0.482 per mile (about 21%).

## Results, one row per run

| Run | Model / arm | Outcome | Steps | Files | Tokens | LLM calls | Blocked calls | Cost | Wall | Evidence chain |
|---|---|---|---|---|---|---|---|---|---|---|
| `d97f9e59` | Sonnet, adapt on | stuck at step 1 (`provider_blocked`) | 1 of 11 reached, 0 done | none | 313,626 | 46 | 26 (57%) | $1.19 | 8.6 min | intact, 5 rows |
| `e981a833` | Sonnet, adapt off, run 1's plan | stopped at the 1.5M token limit; steps 10–11 not run | 9 of 11 reached: 5 partial, 4 incomplete, 0 done | none | 1,508,680 | 140 | 101 (72%; 77% of step calls) | $3.43 | 9.6 min | intact, 0 rows (adapt off) |
| `eb1aab56` | Gemma, adapt on | infra_error, quota 429 | none | none | 0 | 1 | none | — | 2.8 min | — |
| `2f0f0679` | Sonnet, adapt on, fresh plan | agent_error in drafting (no plan) | none | none | 11,861 | 5 | 4 (80%) | $0.05 | 0.5 min | — |
| `206c61a7` | Sonnet, adapt on, run 1's plan | stuck at step 1 (`provider_blocked`) | 1 of 11 reached, 0 done | none | 117,253 | 35 | 26 (74%) | $0.23 | 1.2 min | intact, 5 rows |

**Sonnet total: $4.90.** `team.yaml` names `claude-sonnet-5-5` for every helper (D131 works). Blocked calls still pay for their input: they took 35% of run 1's tokens (about $0.22) and 64% of run 2's (about $1.92).

## The step-1 prompt

The blocked prompt is the ordinary step prompt: the task, the working reading, the role card and the tool list (saved from the trace of `d97f9e59`). Nothing in it looks like it should trip a filter. In run 1 the same task passed Box 1, the planner, the observers and the pool picker. In `2f0f0679` Box 1 and the planner were blocked. The filter is not deterministic from our side.

## Grading Box 4

Only two stuck episodes happened with adapt on. Both are the same step on the same plan.

| Run | Step | Signals | Cause Box 4 named | C# | Expected cause | Diagnosis | Rungs tried | Recovered? | Fix tokens |
|---|---|---|---|---|---|---|---|---|---|
| `d97f9e59` | 1 | provider_blocked, max_turns, capability_unfilled | provider_blocked | none | provider_blocked (8 of 8 turns blocked) | right | 1: `set_run_option:max_turns` 5→8; D: refused (no edit allowed for provider_blocked) | no: still 8 of 8 turns blocked | 68,828 ($0.14) |
| `206c61a7` | 1 | provider_blocked, max_turns, capability_unfilled | provider_blocked | none | provider_blocked (8 of 8 turns blocked) | right | 1: `set_run_option:max_turns` 5→8; D: refused | no: same | 68,828 ($0.14) |

Counts: right 2, partly 0, wrong 0. Recovered 0 of 2. No run reached rung 2, W or D with an edit. None of C1–C6 reached Box 4.

**What Box 4 would have said in run 2.** This is offline, from `python -m scripts.stuck_report` on `e981a833`. Box 4 was off and nothing acted on it.
- Steps 1, 2, 3: `provider_blocked`. That is right.
- Steps 3 (second try), 4, 5, 6, 7, 8: `capability`. That is wrong. The helpers wrote "BLOCKED: Bash", but every one of them held `local:Bash` (see finding 2). The real cause in steps 5–8 was the missing price table from steps 2–3. The expected cause was missing_input (C6) or missing_data. The `missing_data` signal fired 6 times, but `capability` outranked it.

### The specific checks

- **Did a "lacked" data item become a tool request or a pool grant?** No. There were no requests raised during any run. Every MISSING DATA line stayed a data line. For example, `e981a833` step 5: "MISSING DATA: the 52 weekly EIA diesel prices … step 3 returned status "incomplete" with no content". D127's data/tool split held. One odd lacked item did appear: `local`, taken from "BLOCKED: local:Write". It reached the answer's Limitations as "BLOCKED: local".
- **Did the pool grant anything that runs code or sends files outside the container?** No. All 17 attachments are local and in-process: `local:Bash`, `local:Read`, `local:Write`, `local:Edit`, and the `xlsx` and `docx` skills. `local:Bash` runs code only inside this container. The 19 `local_tool_refused` events are the server's own tool list (Agent, CronCreate, WebFetch, …) being filtered at start-up, not helper calls.
- **Did `--cite-arithmetic` let the surcharge and fleet-cost figures pass?** Not testable. No run computed a surcharge or a fleet cost, because no step ever had the price table. On the ATRI figures in `e981a833`:
  - Step 4's "$0.482 ÷ $2.336 × 100 = … 20.63%" passed.
  - Step 8's "0.482 ÷ 2.336 = 0.2063 … 20.63%" was flagged ("'20.63%' not in S2"). The written result (0.2063) and the claim (20.63%) differ by the ×100 the line never wrote.
- **Did any step finish with a stated limitation?** No step finished "with a stated limitation" (the work-around status). The only limitations are in run 2's final answer, added by plain code. For example: "BLOCKED: code_execution (the team had no such capability; added by plain code)" and "NOT USED: local tools (local:Bash, local:Write) (given to the team for step 1, 2, 9 but never used; added by plain code)".

## Adapt on vs off (same plan)

| | adapt on (`d97f9e59`) | adapt on (`206c61a7`) | adapt off (`e981a833`) |
|---|---|---|---|
| Steps reached | 1 | 1 | 9 (10 had started when the token limit hit) |
| Done / partial / incomplete | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 5 / 4 |
| xlsx | none | none | none |
| png | none | none | none |
| docx | none | none | none |
| Final answer | none (stopped at step 1) | none | assembled by code from steps 1–9 |
| Tokens | 313,626 | 117,253 | 1,508,680 |
| Cost | $1.19 | $0.23 | $3.43 |
| Wall | 8.6 min | 1.2 min | 9.6 min |

What Box 4 bought here: nothing in output, but it saved tokens.
- With adapt on, Box 4 ended the task at step 1 after one rung-1 fix, at 8–21% of the off arm's tokens.
- With adapt off, the runner went past the empty steps 1–3 and spent 1.5M tokens. It produced partial text but no file.
- Off made more text only because it did not stop.
- In `e981a833` step 4 the ATRI figures came from search excerpts and the press release, with the gaps listed. That is a good C3 outcome, and it needed no Box 4.

These are one off run and two on runs, on a provider that blocked 57–77% of calls. This is indicative only. It says nothing about whether Box 4 helps when the model answers.

## What D127–D131 should have prevented, and did not

1. **The Bash request is never cleared once `local:Bash` is granted (D127).**
   - Every helper asked for "Bash". The pool marked it filled, and `team.yaml` gives every helper `local:Bash`. But `missing_tools` still lists "Bash" (and "Edit") for every helper.
   - So each step prompt says both "Tool Bash is unavailable this run; proceed without it or answer BLOCKED: Bash" and "You may use local:Bash" (`d97f9e59`, step 1).
   - In `e981a833` the helpers chose the first line. Steps 5, 6 and 7 wrote "BLOCKED: Bash" and never called `local:Bash`. Step 4 did the fuel-share sum by hand, saying "no calculation tool was available", although it held `calc`.
   - The same leftover "Bash" raises `capability_unfilled` on every step. That is why the offline diagnosis of run 2 says `capability` where the truth is missing input.
2. **The D131 citation relabel broke a correct citation.**
   - In `e981a833` step 4 the fuel row cited [S5] for "48.2 cents ($0.482)". [S5] does contain 48.2.
   - The relabel matched "$0.482" in [S1] and moved the whole line to [S1].
   - The citation check then flagged "step 4 cites S1 for '48.2', which S1 does not contain; it is in S5". One claim on a line was fixed by breaking another.
3. **`provider_blocked` has no rung that can work.**
   - Its only allowed edit is more turns. More turns on a filter that blocks every turn cost 68,828 tokens twice and changed nothing.
   - D128's retry-once rule also doubles every blocked call: 26 blocked calls per stuck step, all billed for input.
   - Routing could not help either: the `claude-sonnet` profile leaves one candidate, so there was no other model to fall back to.

## Recommended changes

These are from the discussion after the runs. No code was changed in this session.

### 1. Tools: let the helper find and use them (replaces the issue-2 fix)

The model already chooses its tool every turn. What broke this run is the code around that choice:
- Box 2 guesses each role's tools at planning time and writes them as names.
- The pool searches on the helper's behalf.
- Code keeps a wish list and crosses items off by exact name.
- Leftover wishes reach the helper as orders: "Tool Bash is unavailable … answer BLOCKED: Bash".
- A contract (D61) makes the helper use or declare every item.

In `e981a833` that text overruled a tool the helper held (`local:Bash`), and no file was built.

Recommended design, the same pattern as LangChain-style agents and Claude Code's tool search:
1. **An always-visible core.** Every helper sees `web_search`, `fetch_url`, `calc`, `local:Bash`, `local:Write` and `local:Read`, each with a short description. The helper picks per turn.
2. **`find_tool("what I need")` for everything else.**
   - The helper calls it at the moment of need, inside the step.
   - Code searches the pool (the hundreds of skills and MCP tools); the model may rerank the hits.
   - Code vets each candidate and attaches it, and the helper uses it on the next turn. No stuck step and no Box 4 needed.
3. **No wish-list bookkeeping.**
   - Box 2's tool names become hints only: they warm the search and never become prompt orders.
   - No "X is unavailable" lines. A tool is unavailable only when a helper calls one that does not exist, and then the error says so.
4. **Using a tool is not forced.** Drop the D61 use-or-declare contract for tools. A "BLOCKED: <tool>" claim is checked by code against a call that really failed, not demanded in advance.
5. **Code still decides safety.** The sandbox, the allow-list, vetting of tools that run code outside the container, send files out or need credentials, run limits, and the log of every call. This is "LLM proposes, code disposes" in its proper place: the model picks, and code guards and executes.
6. **Box 4 reads facts.** Its `capability` cause comes from failed tool calls and failed `find_tool` searches, not from a stale list.
7. **Later: native tool calling.** Use the model service's tool-calling API in place of the `## Action / ## ActionInput` text sections. The choice becomes structured, and the "unreadable reply" failures go away.

### 2. A failed step blocks only the steps that depend on it

Today there are two outcomes:
- Adapt off: the dependents run on empty input. In `e981a833`, steps 5–8 spent about 1M tokens with no price table.
- Adapt on: the whole task stops. In `d97f9e59` that also killed step 4 (ATRI), which does not depend on steps 1–3.

Recommended: mark only the dependents of a failed step as blocked, keep running the independent steps, and assemble the answer from what finished.

### 3. A real fix for `provider_blocked`

Today its only fix is more turns, and every blocked call is retried as it stands, so it is billed twice.

Recommended:
- Drop the identical retry.
- Give the cause real fixes: re-send the step with reworded instructions (the tool-use block shortened), and fall back to another model when the profile allows one.
- Run a cheap A/B first, about 20 calls and $0.05–0.10: the saved step-1 prompt with and without the `local:Bash` paragraph. That tells us whether the refusals come from how we word tool use or from the provider.

### 4. Smaller

- **The D131 relabel** must not move a line's tag when another claim on that line is only in the old source.
- **The citation check** should accept "a ÷ b = c%" without a written ×100.

## Anything new

- **The filter is the main blocker for Claude on this endpoint.** The October runs had it at 36–38% of calls; this task has it at 57–80%. Planning calls are sometimes blocked (`2f0f0679`) and sometimes not (`d97f9e59`, on the same task).
- **C1 was settled before planning.** Box 1 marked the Indiana reading as an assumption with PADD 2 as the alternative. Box 2 wrote step 1 as "check whether Indiana is listed; if not, use Midwest (PADD 2), series EMD_EPD2D_PTE_R20_DPG". So C1 would not have been a Box 4 episode even without the filter.
- **The answer that runs when the token limit is hit worked as designed.** `e981a833` stopped cleanly at 1,508,680 tokens and assembled an answer from steps 1–9, with the reading line first and code-added limitations.
- **The adapt-off arm writes no `events.jsonl` rows.** Its hash chain is trivially intact.

## Files

Run folders (copied whole): `d97f9e59-…`, `e981a833-…`, `eb1aab56-…`, `2f0f0679-…`, `206c61a7-…`. Each has `result.json`, `trace.jsonl` and `plan.json`; the adapt-on runs also have `adapt_report.md` and `events.jsonl`.
