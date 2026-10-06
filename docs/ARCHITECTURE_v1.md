# Amoeba v1.0: architecture in plain language

Amoeba drafts a team of AI helpers for each task and runs it step by step. Since D117 it adapts only within a single
task, when a step gets stuck; nothing carries over between tasks (the offline learning loop is removed). One rule
holds throughout: **the AI proposes, plain code decides.**

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

- **Family.** A free-text task gets a task family (D101); it is recorded only.
- **Interpretation.** The key names and terms are listed with their possible readings (D77). Plain code then picks a
  working reading or marks one as an assumption. With `--interactive`, the user is asked one question instead.
- **Standards.** The standards in the user's context file are shown here.
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
`done_when`. Two Observers then check the roles and the plan, for up to a fixed number of rounds. The niche profile's
done clauses are added to the answer step.

**Who decides.** AI drafts and reviews. Code validates the plan graph, applies the profile's clauses, and keeps the
toolbox to the allowed tools.

**Reads.** The task with its interpretation, the toolbox (only the tools the profile allows), the user's standards,
the Environment section.

**Writes.** `plan.json`, `team.yaml`, `capability_requests.json`.

**Flags.** `--draft-prompts d24`, `--quality-gate`, `--drafts-from` (reuse a saved
draft), `--niche`.

## Box 3: The team runs the task

**What it does.** The plan runner executes the steps in waves over `depends_on`. Each helper works in turns:
thought, action, tool call. Tools include `calc`, web search and fetch, pool tools, and local tools in the sandbox.

After every step, plain code checks the output:

- format and inputs;
- the step contract (did the helper use the tools it needed, D61);
- provenance of figures and sources (D33, D66);
- citations (D74), leaving out a calculation's result shown on the line, powers and year ranges (D104);
- the niche profile's domain checks (D102);
- for a step that made a workbook, that totals and derived cells are formulas (D113).

A failed check earns one retry turn. A verify step first works out its own answer without seeing the outputs it
checks, then compares (D90). Plain code pairs that blind answer's figures with the worker's by label; every
disagreement goes to a resolver, one fresh call that settles each figure by the source text or a re-run in the
sandbox and writes value, evidence and verdict. Code checks the evidence; a settled value replaces the wrong one, and
an unresolved one keeps the step from PASS and goes into the answer's Limitations (D109). The Action Observer may re-plan mid-run (D63); a step it
adds for a failed one must change the method (a different tool, source type or a split query), else the re-plan is
rejected (D108). The summariser writes the final answer. Then plain code runs one final-answer requirement check: each Box 2
requirement against the final answer, each promised file against the workspace, and a date on every web-sourced
figure. Missing items earn one refine turn; what is still missing goes into Limitations, and the run ends
`no_deliverable` when a core deliverable is missing (D105 + D110).

Research steps get help from plain code (D106): a packed search is split (one per place, year or quoted query), the
top three results of each are read (official domains first), and data files a page links (.csv, .xlsx, .json) are
downloaded and parsed into tables. With local tools on, every page and table read is saved read-only under the
workspace's `sources/`, so analysts in the sandbox can compute from them (D107).

At the end, plain code sets the run's `status` in result.json: `ok`, `agent_error`, `infra_error` (the model service
or the network failed; never a score, D111) or `no_deliverable` (a core deliverable missing from the final answer,
D105). `requirement_status` records each requirement as checked on the final answer.

**Who decides.** AI helpers act. Code runs the graph, runs every check, refuses tools outside the profile (logged as
`niche_refused`), and records step status (done / partial / incomplete / blocked).

**Reads.** `plan.json`, the tool registry, the local sandbox, the pool.

**Writes.** `trace.jsonl` (every model and tool call, each tagged with its as-built box), `step_<n>.json`,
`result.json` (answer, score, tokens, USD, routing, flags).

**Flags.** `--topology plan`, `--step-contract on|off`, `--verify-first`, `--replan`, `--self-refine`, `--collab`,
`--max-turns`, `--check-retry-turns`, `--web-tools`, `--pool`, `--local-tools on` (+ `--local-tools-mode`),
`--disable-tools`, `--max-tokens-per-run`, `--max-calls-per-run`. Probe fixes, each `on|off` and on by default for
the plan runner: `--disputes` (D109), `--deliverable-check` (D105), `--research` (D106), `--workspace-sources` (D107),
`--replan-method` (D108), `--dated-figures` (D110), `--cite-arithmetic` (D104), `--xlsx-formulas` (D113).

## Box 4: Adapt within the task (D117)

**What it does.** The offline learning loop of v1.0 (task streams, Experimenter, Gate, Monitor, Diagnoser, Architect,
recipe store, retention replays, pruning, user-memory proposals, ledger) is removed. Adaptation now happens inside a
single task: when a Box 3 step gets stuck, the planned team is changed from that run's own logs, results and errors, so
the task can still finish. Nothing carries over between tasks. Built in stages: (A) the removal; (B) a stuck watch and
diagnosis in plain code; (C) code fixes, cheapest first; (D) a small fix-proposer agent for when the code fixes fail;
(E) a comparison with `--adapt on` and `off`.

**Kept for it.**

- the step contract's causes (capability, checks, max_turns, unused_tool, claimed_file_missing), which become stuck
  signals;
- the cause → allowed-edit table (`amoeba/config/adapt.yaml`);
- the single-edit JSON format and its checks (`amoeba/adapt/architect.py`) with the edit menu, the transforms and
  V1–V6 (`amoeba/adapt/recipe.py`);
- the hash-chained event log and the evidence branch (`amoeba/adapt/evidence.py`, below).

**Stage B: the stuck watch (built).** After each step attempt, with `--adapt on` (the command-line default),
`PlanRunner.watch` reads what the step recorded and looks for five signals (`amoeba/adapt/stuck.py`):

| Signal | When | Cause |
|---|---|---|
| repeated_error | two failed tool calls in a row, same tool, same error once digits are masked | tool_error |
| checks_after_retry | a check still fails at the end of the step (after its retry turn) | checks |
| max_turns | the helpers ran out of turns before a Final Output | max_turns |
| capability_unfilled | a capability was BLOCKED or not declared, or a request for one of the step's roles stayed unfilled | capability |
| no_file_change | the step owes a file and its files did not change across the refine turn or between attempts | claimed_file_missing |

A step is STUCK when it did not end `done` and a signal holds. One cause is picked by the order of
`diagnoser.causes`, with that cause's allowed edits and at most eight evidence lines. The event is written to
`step_N.json` (`stuck`), the trace (`stuck`), `result.json` (`stuck`) and the run's hash-chained `events.jsonl`.
`scripts/stuck_report.py` runs the same functions over stored run folders.

A sixth cause, **missing_input** (Stage C), separates data an earlier step should have given from a missing tool:
a lacked item with no tool word that names a step, an input, output, data or files, another step's role, or most of
an earlier step's planned output (`classify_lacked`). It comes first in the table order, so a step that lacked both
is fixed for the input, then re-checked. Checks that fail only because the helpers ran out of turns count as
max_turns.

**Stage C: code fixes (built).** `PlanRunner.fix_stuck` runs after each step of the wave loop. It asks
`amoeba/adapt/fixes.py` for the fixes of the cause, cheapest first, keeps those the table allows and that were not
tried in this task, applies the first, keeps the replaced attempt as `step_N.tryK.*`, re-runs only the stuck step
and re-checks it (success: the step ends `done`):

1. missing_input: an upstream step that is done and holds the item (60% of its own words) is added to depends_on,
   or passed in full when it already is a dependency; otherwise that upstream step is re-run once with the item
   added to its done_when, then the stuck step. That re-run is the only time a completed step is redone; steps that
   used its old output stay as they are and are listed.
2. Rung 1: more turns (tool_error, max_turns); more retry turns, then a larger input when one was shortened (checks).
3. Rung 2 (capability): a lacked tool the registry has is granted; otherwise the toolbox step runs again for it
   with `code_pick` — the first vetted candidate of the shortlist not given before, no AI pick. Without the pool and
   local tools the rung is skipped: "capability fix unavailable: pool off".

Limits (`adapt` in adapt.yaml): 3 fixes per step, 8 per task, a token cap (200,000) and a dollar cap ($1, when the
model has a price) on the fix attempts, checked before each fix. When the step is still stuck and nothing is left,
the task stops: `adapt_report.md` (also the run's answer) lists the stuck step, the cause, the evidence, each fix and
why it failed, and the rungs not tried; the run status is `stuck`. Every fix is a trace event and an `events.jsonl`
row; `result.json` `adaptation` sums them up.

**Who decides.** Code. No AI in Stages A–C.

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
3. **Choice.** A preference set for the role (D98, built, off), else the role's default, else the cheapest model of the role's
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

## The user context file (D77, D99)

`--context user.yaml` holds who is asking (location, organisation, role) and `standards:`, lasting preferences the
user wrote. Box 1 and Box 2 read it. No run and no agent writes it; it sits outside every workspace and the sandbox
mounts none of it. (D117 removed recipe memory and the loop's proposals of standards.)

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

The skills the pool picks are read-only under `/opt/skills/<name>/` in the sandbox image; a helper reads them with
`local:Read` and runs their scripts with `local:Bash` (D103). Fetched pages and data tables arrive read-only under
`sources/` (D107). A Python program sent to `local:Bash` runs with `python3` (D112).

Files are copied back to `runs/<id>/workspace/` after each call. The sandbox is destroyed at the end of the run. The
harness gate refuses, before the sandbox even sees them:

- network commands;
- paths outside the workspace;
- writes to MCP configs, hooks, settings, skills and the `sources/` inputs.

**Who decides.** Code (the gate in `amoeba/localtools/gate.py`, the sandbox policy in
`amoeba/config/localtools.yaml`). The policy lives outside the agent.

**Writes.** Every allow and deny decision goes into the run's trace, and from there into `events.jsonl`
(`tool_decisions`).

**Flags.** `--local-tools on|off`; `--local-tools-mode sandbox|inprocess` (sandbox is the default; inprocess only on
request, and only with `AMOEBA_SANDBOX=1`); `localtools.yaml` `bash_python` (D112).

On a dropped connection the model client reads the proxy fresh from the file `AMOEBA_PROXY_FILE` names, and
reconnects if it moved (D111). Running on a persistent machine: `docs/RUNNING_ON_A_VM.md`.

## Evidence (D95)

**What it does.** Events go into one append-only `events.jsonl`, written only by the harness (D117: for in-task
adaptation, every stuck step, diagnosis and fix). Each row
carries the SHA-256 of the row before it and of the run folders it names, so the log forms a hash chain. Finished
runs are key-scanned. Runs and new rows are then shipped as normal, fast-forward commits to the GitHub `evidence`
branch, at most one commit every 10 minutes. Each commit message carries the chain head. Agents never get git
credentials.

**Who decides.** Code.

**Reads / writes.** `events.jsonl`; the `evidence` branch.

**Flags.** `python -m scripts.verify_evidence` (local copy) or `--branch evidence` (GitHub's history).
