# Amoeba v1.0: architecture in plain language

Amoeba drafts a team of AI helpers for each task, runs the team, and learns from practice which team "recipe" works
for each kind of task. One rule holds throughout: **the AI proposes, plain code decides.**

Each part below covers four things:

- **What it does.**
- **Who decides.** Either AI (a model call) or code (plain, deterministic Python).
- **Reads / writes.** Its inputs and outputs.
- **Flag.** How to switch it or tune it.

Defaults are for Amoeba (`--topology plan`). The two baselines (`flat`, `boss_reviewers`) stay as they were: every
new v1 feature is off for them.

The as-built page (`docs/arch/phase1.html`, generated from the code) shows every part with file:line links.

---

## Box 1: Task (reading the task)

**What it does.** Box 1 reads the task before any planning:

- **Family.** A free-text task gets a task family (D101), so it can start from that family's recipe.
- **Interpretation.** The key names and terms are listed with their possible readings (D77). Plain code then picks a
  working reading or marks one as an assumption. With `--interactive`, the user is asked one question instead.
- **Standards.** The user's approved standards (D99) are shown here.
- **Environment.** So is the niche profile's Environment section (D102).

**Who decides.**

- *Family:* code first, using keyword rules in `amoeba/config/families.yaml`. Only when no rule decides, one AI call
  (router role `family_classifier`) picks from the list or "new", and code checks the answer.
- *Interpretation:* one AI call lists the readings; code picks one using a fixed confidence gap.

**Reads.** The task, `families.yaml`, the user context file (`--context`), the niche profile.

**Writes.** `result.json` fields `family` and `interpretation`; trace events `task_family` and `task_interpretation`.
An assumed reading is stated at the top of the answer, added by code.

**Flags.** `--family-classify auto|on|off` (auto = on for plan), `--interpret on|off`, `--context user.yaml`,
`--interactive`, `--niche`.

## Box 2: Plan a new team

**What it does.** A Planner drafts the team: roles, each role's tools, and a plan of steps with `depends_on` and
`done_when`. Two Observers then check the roles and the plan, for up to a fixed number of rounds. After that, code
applies the family's recipe:

- planner rules ("lessons") go into the Planner's and Observers' prompts;
- transforms are applied to the final draft (an added verify step, tighter done clauses, tools granted or revoked,
  role rules);
- run options are set.

The niche profile's done clauses are added to the answer step.

**Who decides.** AI drafts and reviews. Code validates the plan graph, applies the recipe and the profile's clauses,
and keeps the toolbox to the allowed tools.

**Reads.** The task with its interpretation, the toolbox (only the tools the profile allows), the recipe, the user's
approved standards, the Environment section.

**Writes.** `draft.json` (Box 2's own draft), `plan.json` (after transforms), `team.yaml`, `capability_requests.json`.

**Flags.** `--draft-prompts d24`, `--quality-gate`, `--recipes` / `--recipes-from`, `--drafts-from` (reuse a saved
draft), `--niche`.

## Box 3: The team runs the task

**What it does.** The plan runner executes the steps in waves over `depends_on`. Each helper works in turns:
thought, action, tool call. Tools include `calc`, web search and fetch, pool tools, and local tools in the sandbox.

After every step, plain code checks the output:

- format and inputs;
- the step contract (did the helper use the tools it needed, D61);
- provenance of figures and sources (D33, D66);
- citations (D74);
- the niche profile's domain checks (D102).

A failed check earns one retry turn. A verify step first works out its own answer without seeing the outputs it
checks, then compares (D90). The Action Observer may re-plan mid-run (D63). The summariser writes the final answer.

**Who decides.** AI helpers act. Code runs the graph, runs every check, refuses tools outside the profile (logged as
`niche_refused`), and records step status (done / partial / incomplete / blocked).

**Reads.** `plan.json`, the tool registry, the local sandbox, the pool.

**Writes.** `trace.jsonl` (every model and tool call, each tagged with its as-built box), `step_<n>.json`,
`result.json` (answer, score, tokens, USD, routing, flags).

**Flags.** `--topology plan`, `--step-contract on|off`, `--verify-first`, `--replan`, `--self-refine`, `--collab`,
`--max-turns`, `--check-retry-turns`, `--web-tools`, `--pool`, `--local-tools on` (+ `--local-tools-mode`),
`--disable-tools`, `--max-tokens-per-run`, `--max-calls-per-run`.

## Box 4: Monitor

**What it does.** Watches the practice runs of each family. It raises an alarm when a family's recent scores fall
below its reference (a *score* alarm), or when one cause or failed rubric item rises (a *cause* alarm). Every 12
practice tasks of a family, it also replays the old (pre-shift) gate tasks with the current recipe, and raises a
*retention* alarm if they got worse beyond noise (D100).

**Who decides.** Code (fixed window, reference and thresholds).

**Reads.** Practice records (score and failed rubric item names only). For retention, the replay scores.

**Writes.** `alarm` and `retention` events in `events.jsonl`; `retention.jsonl`; `loop_state.json`.

**Flags.** `adapt.yaml` `monitor:`; `--retention-every N` (default 12, 0 = off).

## Box 5: Diagnoser

**What it does.** Turns an alarm into a cause, with evidence quoted from the run files. It also states which recipe
edits may answer that cause (the cause → edit table). Only causes observed in the runs can be chosen; causes a model
only claimed are reported separately (D93). A retention alarm is diagnosed from scores alone.

**Who decides.** Code.

**Reads.** The window's run folders (`step_<n>.json`, `result.json`).

**Writes.** `diagnoses/o<order>-<family>.json`; `diagnosis` events.

**Flags.** `--diagnoser tier0|none` (`none` = alarm only, every edit allowed; for the ablation).

## Box 6: Architect

**What it does.** Proposes one recipe edit for the diagnosis, from the allowed menu. The menu covers planner rules,
transforms, run options, and (D98, off by default) a model preference. Each proposal comes with a rationale and a
predicted gain.

**Who decides.** AI proposes; code validates the edit against the menu and checks V1–V6, with one retry. This is the
only AI call inside the adaptation loop.

**Reads.** The diagnosis, the current recipe, the family's failed hypotheses, practice examples (never held-out
tasks).

**Writes.** `architect/<hypothesis>.json` and its trace; `hypothesis` rows in the ledger.

**Flags.** `--allow-model-edits` (D98, off).

## Box 7: Experimenter

**What it does.** Measures a proposed edit. It replays the family's gate tasks with recipe A (current) and recipe B
(current + edit), same seeds, several repeats. The same machinery runs:

- the noise calibration (A against A);
- the retention replays;
- the prunes (recipe minus one line, D100).

**Who decides.** Code (the runs themselves use the team, i.e. AI).

**Reads.** The gate set (held-out tasks: never shown to Box 6), the arm-A cache.

**Writes.** `experiments/<id>/` (`experiment.json`, `pairs.jsonl`, run folders).

**Flags.** `scripts/run_experiment.py --repeats --parallel`; `adapt.yaml` `experiment:`.

## Box 8: Gate

**What it does.** Accepts or rejects an edit using fixed rules (Gate v3):

1. the edit passes validation and the leakage screen;
2. the gain beats the noise floor, by a permutation test, within the family's fixed hypothesis quota;
3. no held-out leak;
4. the cost is justified, in USD when prices exist, else in tokens;
5. no honesty or error regression.

It also judges prunes: a line is removed when removing it loses nothing beyond noise and saves cost. It runs the
rollback watch after an accept.

**Who decides.** Code.

**Reads.** The experiment's pairs, the calibration, the ledger.

**Writes.** `decision` rows in `ledger.jsonl` (prunes carry `prune: true`); `decision` and `prune` events.

**Flags.** `adapt.yaml` `gate:` (version, alpha, cost ratio, dwell, cooldown); `--prune end|off`;
`scripts/prune_recipe.py`; `--check` (the single pre-registered check).

## Box 9: Memory (recipe store)

**What it does.** Keeps each family's recipe versions. Only a Gate accept writes a new version, and a rollback
reverts it. Every recipe line carries its provenance: the hypothesis that added it, the date, and the Gate row that
accepted it (D99). A new stream can start from another stream's store.

**Who decides.** Code; only the Gate writes.

**Reads / writes.** `recipes/index.json`, `recipes/<family>/v<N>.yaml`, `recipes/experience.jsonl`.

**Flags.** `--recipes`, `--recipes-from`.

## The loop driver

Runs the stream's practice tasks in order, each with its family's current recipe, and calls Boxes 4–9 in turn. At
the end of a stream it prunes each recipe. Everything it does is saved to disk, so a crash resumes where it stopped.
Code only.

**Writes.** `summary.json` and `REPORT.md`.

**Flags.** `scripts/run_loop.py --stream --parallel --parallel-until --repeats`.

---

## Model router (D97)

**What it does.** Chooses the model for every model call in Boxes 1–9. Each call states:

- its role (interpreter, planner, agent_observer, plan_observer, worker, verifier, action_observer, summariser,
  architect, pool_picker, family_classifier);
- its step;
- its size (estimated prompt tokens and reply limit);
- the features it needs (JSON, tools, vision);
- its data class (normal or sensitive).

The decision runs in a fixed order:

1. **Candidates.** Registry models that are allowed (niche profile ∩ `--allowed-models`) and available (key present,
   not cooling down after a 429, not failing).
2. **Hard filters, never relaxed.** Context window, features, sensitive data → local models only, cost within the
   run's USD cap, and verifier independence when set to `required`.
3. **Choice.** The recipe's preference for the role, else the role's default, else the cheapest model of the role's
   size tier. Under `preferred`, the verifier gets a different model family when one exists; otherwise
   `verifier_same_family: no alternative` is logged.
4. **No candidate.** The call fails as `no_model`, recorded like a missing capability.

A token bucket per model, shared by all processes, keeps calls within each model's per-minute limits.

**Who decides.** Code; no AI takes part in the decision.

**Reads.** `amoeba/config/models.yaml` (`registry`, `routing`). Today the registry holds Gemma 4 31B only. Adding a
model is a registry entry, with no code change.

**Writes.** `route` / `no_model` trace events; `routing` rows in `events.jsonl`; `result.json` `routing`, with calls,
tokens and USD per model.

**Flags.** `--routing fixed|role|routed` (routed for Amoeba; fixed for the baselines and the Paper 1 benchmark),
`--allowed-models`, `--max-usd-per-run`; `verifier_independence: required|preferred|off` in `models.yaml` or the
niche profile.

## Memory: three kinds (D99)

| Kind | What | Written by | Read by |
|---|---|---|---|
| Recipe memory | the recipe store (Box 9), every line with provenance | the Gate only | Boxes 2–3 (recipe), Box 6 |
| User memory | `standards:` in the user context file (`--context`) | the user only, via `scripts/approve_memory.py` (logged in `events.jsonl`) | Box 1, Box 2 |
| Event memory | the evidence log `events.jsonl` (below) | the harness only, append-only | people and verification scripts; never fed raw into prompts |

**Who decides.** For user memory, the loop may only **propose** a standard. It does so when the same feedback item
fails in at least 3 practice runs across at least 2 families, and the proposal goes to `memory_proposals.jsonl`. The
user approves it or not. Nothing an agent writes reaches any memory: the files sit outside every run's workspace, and
the sandbox mounts none of them.

## Niche profiles (D102)

**What it does.** One file per environment, `profiles/<niche>.yaml`, covering:

- allowed tools and the local-sandbox limits;
- allowed models and the verifier-independence setting;
- domain rules and vocabulary;
- what "done" means (default done clauses);
- which domain checks run (`amoeba/checks/<name>.py`);
- safety limits (USD, tokens and calls per run; outside actions).

The prompts stay generic: one "Environment" section in Box 1's and Box 2's prompts asks the team to assess the
environment first and plan only with what is allowed.

**Who decides.** A person writes the profile; code enforces it. Box 3 refuses any tool outside the profile and logs
the refusal. The router refuses any model outside it. The domain checks earn a retry turn when they fail.

**Ships.** `general` (exactly today's behaviour: no section, no limit, no check) and `calc` (every final figure must
be reproducible by calc from the task's numbers).

**Flag.** `--niche <name>` (default `general`).

## Local-tool sandbox (D96)

**What it does.** With `--local-tools on`, Claude Code's tools (Bash, Read, Write, Edit, Glob, Grep, skills) run in
a fresh NVIDIA OpenShell sandbox for each run:

- no network;
- Landlock, so only the sandbox workspace is writable, and skills are read-only;
- no secrets;
- one CPU, 1 GiB of memory, 300 s per command, one hour per run (a niche profile can change these).

Files are copied back to `runs/<id>/workspace/` after each call. The sandbox is destroyed at the end of the run. The
harness gate refuses, before the sandbox even sees them:

- network commands;
- paths outside the workspace;
- writes to MCP configs, hooks, settings and skills.

**Who decides.** Code (the gate in `amoeba/localtools/gate.py`, the sandbox policy in
`amoeba/config/localtools.yaml`). The policy lives outside the agent.

**Writes.** Every allow and deny decision goes into the run's trace, and from there into `events.jsonl`
(`tool_decisions`).

**Flags.** `--local-tools on|off`; `--local-tools-mode sandbox|inprocess` (sandbox is the default; inprocess only on
request, and only with `AMOEBA_SANDBOX=1`).

## Evidence (D95)

**What it does.** Every loop event goes into one append-only `events.jsonl`, written only by the harness. Each row
carries the SHA-256 of the row before it and of the run folders it names, so the log forms a hash chain. Finished
runs are key-scanned. Runs and new rows are then shipped as normal, fast-forward commits to the GitHub `evidence`
branch, at most one commit every 10 minutes. Each commit message carries the chain head. Agents never get git
credentials.

**Who decides.** Code.

**Reads / writes.** `eval/loop/<stream>/events.jsonl`; the `evidence` branch.

**Flags.** `--no-ship`; `python -m scripts.verify_evidence --stream <s>` (local copy) or `--branch evidence`
(GitHub's history).
