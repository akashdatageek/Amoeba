# D153 — plumbing found in the live runs

Status: **plan, waiting for approval** (branch claude/box4-scoped). This is the prompt's "D147".

**Numbering.** The prompt calls this D147. That number is already used on the unmerged branch claude/run-gaps
(PR #45): D147–D152 there are cut notes, the gate, diagnosis fixes, fix tries, fair budgets and two bugs. Two
decisions with one number would collide in the spec's §11 table. So this note is **D153**, and the scoped proposers
are **D154**. Say if you want different numbers.

**Base branch.** The prompt says "new branch from main". `main` stops at PR #40 (D131). The code and notes the
prompt asks me to build on (D136, D141, D143, D145, D146, protocol v2, the typed proposer call) exist only on
`claude/zen-fermi-mnaurm` (PRs #41–#44) and on PR #45. Built on `main`, none of this work could start. This branch
starts from claude/run-gaps (PR #45, D147–D152). **Decision for you:**
- (a) keep this base;
- (b) merge zen-fermi and #45 into main first, then branch from main;
- (c) branch from zen-fermi without #45. In that case A5 (below) has to be built differently.

Every item below was checked against the code on this branch. `PR` means `amoeba/interp/plan_runner.py`.

## Why
The live runs (Sonnet H2/H3/r1, the Box 4 probe, the fuel runs) showed small breaks in how things are wired, not in
what Amoeba decides:
- the protocol had to be picked by hand;
- a provider refusal still counts in the unreadable-reply tally;
- a period-terminated BLOCKED line lost its short name;
- a request for several roles is invisible to the stuck watch;
- team.yaml can name a model that was never used.

## What
Each item says: already fixed or not, the exact code I will change, and any conflict with the prompt.

### A1. Protocol default "auto" — not fixed
- **Today:**
  - `--protocol` has `choices=["legacy","v2"], default="legacy"` (`scripts/run_task.py:834`).
  - `run_one` sets `trace.protocol` from the option before drafting (`run_task.py:128`). Native tools are resolved
    later, after drafting (`resolve_native`, `run_task.py:585-597`, called at :269).
- **Change:**
  - add `auto` and make it the default (`run_task.py:834`).
  - A new `resolve_protocol(asked, llm)` next to `resolve_native` gives `v2` when the model's registry entry has
    `supports.tools: true`, else `legacy`. It uses the router's `can_use("tools")` (`amoeba/llm/router.py:410-418`);
    for a single client, it reads that model's registry entry.
  - It is called in `run_one` before line 128, so drafting, the steps and Box 4 all see the same answer.
  - `cli_plan_options` (`run_task.py:551-568`) passes the resolved value.
  - `protocol_used` (`run_task.py:373-379`) records `{asked: "auto", used, why}`.
  - legacy and v2 stay as explicit overrides.
- **Baselines:** unchanged. flat and boss_reviewers already always get legacy (`run_task.py:128`) and never read
  plan options (`runtime.py:241,372`). T7 holds.
- **Planning v2 (D143)** has no protocol switch of its own: it follows `trace.protocol`. It is left as it is, so under
  `auto` planning follows the same choice as the steps. Its separate `--planning-tier` (`run_task.py:838`) is left as
  it is.
- **Decision for you (not changed):**
  - Gemma's registry entry says `supports: {tools: false}` (`amoeba/config/models.yaml:97-114`). So `auto` gives
    legacy on Gemma.
  - My Oct 17 check called gemma-4-31b-it with one tool and got a correct tool call (`calc`, `17*23`). That is one
    call, not a model check.
  - `python -m scripts.model_check gemma-api` would settle it. Your call.
- **Test:** auto picks v2 for a tools model and legacy for a non-tools model; legacy and v2 override auto; the
  baselines stay legacy.

### A2. A refused reply is never a format slip — mostly fixed (D128, D134, D145); one gap
- **Already fixed:**
  - `is_blocked` (`amoeba/llm/cache.py:29-35`) is set before the D123 repair call, so a refused reply gets no repair
    call. Text path: `amoeba/interp/trace.py:351-366`. Native path: `PR:3526-3527`.
  - A blocked turn feeds only the signal `provider_blocked` (`amoeba/adapt/stuck.py:181-193`), not
    `unreadable_reply` (format) and not capability.
  - The end-to-end test `tests/test_ladder_d145.py:42` ("all replies refused") ends with cause provider_blocked.
- **Gap:**
  - A blocked turn is still stored in `meta["unreadable_turns"]` (with `blocked: true`, `PR:2384-2391`) and counted
    in the step's status line as "unreadable replies: N" (`PR:1725-1726`). That is the "counts as an unreadable
    turn" the prompt names.
  - **Change:** keep blocked turns in their own list `meta["blocked_turns"]`, and leave them out of
    `unreadable_turns` and of the "unreadable replies" count. Their line says "blocked replies: N (categories …)".
  - `step_signals` reads `blocked_turns` for provider_blocked, and still accepts the old field, so stored runs
    replay the same (`stuck.py:181-193`). Readers of `unreadable_turns` (`PR` watch, `fix_stuck` categories at
    `PR:2563`) are updated.
- **Also noted, not changed:** a refusal that carries some text is not treated as blocked (`is_blocked` needs an empty
  reply). The prompt asks for empty replies only.
- **Test:** a step whose replies are all refused has `blocked_turns`, an empty `unreadable_turns`, no repair call,
  and diagnosis provider_blocked, with neither format nor capability among its signals.

### A3. BLOCKED lines — three of four already right; one bug
Measured on this branch with `blocked_marks` (`PR:802-810`):

| Line | Recorded as lacked |
|---|---|
| `**BLOCKED:** Census API key. Every api.census.gov request needs a key, and I had none` | **wrong:** "Census API key. Every api.census.gov request needs a key" |
| `__BLOCKED:__ X` | X |
| `- **BLOCKED**: X` | X |
| `BLOCKED: X — reason` | X |

- **Change in the regex (`PR:805`):** a period followed by a space (a sentence end) also ends the name. A period
  inside a name ("api.census.gov", "v1.2") does not.
- **Change at `PR:808`:** the duplicate check compares lower case on both sides (today it compares a lower-case
  name with original-case names).
- **Test:** all four lines, the H2 line verbatim giving "Census API key".

### A4. The shell tool reaches the helper
- **(a) Already fixed by D127.**
  - `amoeba/capabilities/aliases.yaml:14-30` maps bash, shell, python interpreter, terminal and similar names to
    `code_execution`.
  - `amoeba/config/localtools.yaml:24-25` matches those to `local:Bash`, through `LocalToolbox.alias_hits`
    (`amoeba/localtools/toolbox.py:268-283`).
  - Checked: Bash, shell, python_interpreter, code_execution and terminal all reach local:Bash.
  - **Change:** nothing; I will add the five names as a regression test only.
- **(b) Partly fixed.**
  - D127 attaches a tool to every role a request names (`helpers_for`, `amoeba/pool/stock.py:212-219`).
  - But the request is stored with its raw `for_role` (`run_task.py:253`). Seven places then compare it exactly
    with one role name:
    - `stuck.py:228, 270, 273`
    - `PR:936` (contract needs), `PR:1123` (web tools), `PR:2457` (watch), `PR:2908` (marking a request filled)
    - `PR:3845` (re-plan check)
  - So an unfilled "A; B" request is never seen by the stuck watch.
  - **Change:** split it once, where the request list is stored (`run_task.py:253`, and the same for requests raised
    during the run at `PR` attach / watch). That means one entry per named role, using the same name matching as
    `helpers_for` (moved to a small shared function in `amoeba/pool/stock.py`). The seven readers then work
    unchanged.
- **(c) Already fixed by D127.**
  - The grant goes through `stock_toolbox(..., code_pick=True, exclude=…)`.
  - When the chosen candidate fails to connect, the next one shown is tried (`FALL_THROUGH`,
    `stock.py:39, 360-361, 413-418`; event `pool_fallthrough`), within the vetted shortlist.
  - **Change:** nothing.
- **(d) Already fixed by D61 P14 and D127.** At an equal score a local candidate goes first
  (`stock.py:303-309, 326-327`). **Change:** nothing.
- **Test:** the multi-role split is seen by the watch; a regression test for (a); (c) and (d) are covered by
  existing tests, which I will name in the as-built section.

### A5. Box 4's token budget follows the model — already fixed by D151, in a different form. Decision for you
- **Today (D151, on PR #45):**
  - The fixes' token allowance is `fix_tokens_per_attempt` (6) × the run's **average** step-attempt cost so far
    (`amoeba/adapt/fixes.py:47-52`, `PR:1290-1294`, `PR:2507-2508`).
  - It applies with or without `--max-tokens-per-run`.
  - `max_tokens_per_task` was removed.
  - D151 also gives each step a share of a run cap.
- **The prompt asks for:**
  - max(max_tokens_per_task, N × the **median** tokens of the steps run), N = 3;
  - only without a run cap.
- **Conflict:** D151 already made the budget follow the model, so building A5 as written would undo part of
  D151.
- **Options:**
  - (a) record A5 as already fixed by D151 and change nothing (my recommendation);
  - (b) switch D151's rule to the prompt's: bring back `max_tokens_per_task` as a floor, use the median and N = 3,
    and keep the per-step share for runs with a cap.
- **USD:** the USD limit is already the hard stop when a model has a price (`PR:2933-2936`, D145). Side note: on
  Gemma the price is `null` in prices.yaml but `0.0` in models.yaml, so the USD limit reports "not enforced". This
  is not changed.
- **Test (if b):** both cases (with and without a price).

### A6. team.yaml names the model actually used — partly fixed by D131
- **Today:** team.yaml is written once, before any step runs. The label is `planned_model(llm)`
  (`run_task.py:71-83, 255-259`). It is right for a single client. It is wrong when:
  - the router has several allowed models (it names the default);
  - roles or the D146 verifier use other models (RoleRouter is not matched);
  - a call fell back to another model;
  - a switch_model fix ran.
- **Change:**
  - after the run, rewrite each helper's `model` in team.yaml from the trace: the model the chat spans of that helper
    (`gen_ai.agent.id`) actually used (`gen_ai.response.model`).
  - When a helper used several models, the label lists them, the most-used first. A helper with no calls keeps the
    planned label.
  - The rewrite sits in `run_one` after the run (`run_task.py`, after the Interpreter returns), with a small
    function `used_models(trace)` beside `planned_model`.
- **Test:** a routed run where one helper's calls fell back to another model; team.yaml names the model used.

## As built
(Filled in after the build.)

## Tests
(Filled in after the build. Every new test runs offline with MockLLMClient.)
