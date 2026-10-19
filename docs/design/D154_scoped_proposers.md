# D154 — two scoped fix proposers, probed and picked by plain code

Status: **plan, waiting for approval** (branch claude/box4-scoped). This is the prompt's "D148". The reason for the
new number and the base branch is given at the top of `docs/design/D153_plumbing.md`.

Source idea: Harness² (arXiv 2610.14224), at the level of one task only. Nothing carries over between tasks: no
library, no recipes, no outer loop.

`PR` means `amoeba/interp/plan_runner.py`.

## Why
- Today Box 4's last rung makes **one** fix-proposer call, which yields **one** edit. Then:
  1. the step re-runs;
  2. the step's checks and contract decide.
- When the edit is wrong, the try is spent, and the edit **stays applied** for every later try. Rules, tools,
  helpers, done_when and run options all persist; there is no rollback today.
- One proposer mixes two kinds of fix:
  - how the team works: procedure, tool use, turns;
  - what an expert would know: content, sources, what "done" means.
- The live runs (Sonnet H2/H3/r1, the Box 4 probe, the fuel runs) mostly got edits of the first kind when the problem
  was of the second, or the other way round.

## What
The gate stays: a step counts as recovered only when its own checks and contract say so. What is added:
- two proposers, each scoped;
- each proposal is tried (a probe) from the same starting state;
- plain code compares the signals and picks one, then undoes everything the loser did.

The new logic lives in a new module, `amoeba/adapt/probe.py`. plan_runner calls it, so plan_runner does not grow
further.

### The round in one picture
```
 stuck step (signals S0)
        │
        ▼
 ┌──────────── snapshot (team, step, options, counters, faults, files) ───────────┐
 │                                                                                  │
 ▼                                                                                  ▼
 INV proposer: how the team works                              DOM proposer: what an expert would know
 (rule, tool, tool guidance, watch rule, split)                (rule, helper, work-around, re-plan)
 │  plain-code checks + "because" quote                        │  plain-code checks + "because" quote
 ▼                                                              ▼
 probe INV: apply, re-run step, signals S1, then undo          probe DOM: apply, re-run step, signals S2, then undo
 └──────────────────────────────┬───────────────────────────────────┘
                                ▼
       plain code picks: done > finished with limitation > most cleared / fewest new
                                ▼
           the winner's state is put back; the loser stays undone
```

### B1. Two scoped proposers — new
- **Prompts:**
  - `amoeba/config/prompts/fix_proposer_inv.txt` and `fix_proposer_dom.txt`. Each is `fix_proposer.txt` plus one
    scope section, and each says that the other scope belongs to a parallel proposer and must not be covered.
  - Today there is one proposer prompt for both protocols. The typed (v2) call sends the same rendered text as JSON
    with the `FixOut` schema (`PR:3273, 3280-3291`; `amoeba/task/schemas.py:23`). So "the same scope text in the typed
    call" comes for free: both protocols render the scoped file.
- **Scope edits:**
  - INV: add_role_rule, grant_tool, add_tool_guidance, add_watch_rule, split_step.
  - DOM: add_role_rule, add_helper_role, work_around, replan_remaining.
  - Each scope is offered its edits ∩ the `allowed` list `propose_fix` builds today, after its existing filters
    (`PR:3055-3065`). An empty set means that scope is not called.
- **"because":**
  - a new field on the reply (`FixReply`, `amoeba/adapt/proposer.py:166-170`), at most 200 characters.
  - Plain code refuses the edit unless the quote occurs in the evidence and last-attempt text the proposer was shown
    (whitespace and case folded). That text is kept from `_proposer_call` (`PR:3247-3276`).
  - In single mode the field is optional and not checked, so single mode stays exactly as today.
- **Checks and retry:**
  - both replies pass `fix_problems` (`proposer.py:201-239`) and `_d_live` (`PR:3150-3186`), with today's single
    retry. The typed-mode rule at `PR:3080-3084` is kept.
  - A proposer that fails twice gives no candidate.
- **Switches:**
  - `adapt.yaml proposer.scoped: true`.
  - CLI `--proposer scoped|single`, default scoped (`scripts/run_task.py`, beside `--adapt`), passed as
    `PlanOptions.proposer`.
  - `single` runs today's `propose_fix` unchanged.
- **Code:**
  - `PR.propose_fix` (`PR:3051`) becomes a dispatcher: `single` goes to today's body, renamed `_propose_single`;
    `scoped` goes to `probe.scoped_round(self, n, wave, d)`.
  - `_proposer_call` gains a `scope` argument that picks the prompt file and the edit subset.

### B2. Probe, compare, pick — new (`amoeba/adapt/probe.py`)
**Snapshot.** Taken once before the probes, by `Snapshot.take(runner, n)`. Restored with `snap.restore()`.
- The step's agents: tools, missing_tools, constraints. `add_role_rule` edits the shared role card (`PR:3115-3117`),
  so it is copied in full.
- Added helpers: `self.agents`, `cfg.agents`, `steps[n].agent_ids` (`PR:3122-3127`, `PR:4058-4073`).
- `steps[n].done_when`, `step_opts[n]`, `waived[n]`, `provided[n]`, `helpers_added`.
- `artifacts[n]` and its meta, and the step attempt files.
- `fix_keys` additions, `proposer_gave_up`, `workarounds`.
- Per-step tool guidance and watch rules (B3).

**Files.**
- In in-process mode (`--local-tools-mode inprocess`, the mode the live runs used): a copy of the workspace, except
  the read-only parts the gate protects: `sources/`, `skills/`, `made_tools/` (`amoeba/localtools/gate.py:131-132`).
- After each probe, files the probe added are deleted and files it changed are put back.
- **Open point, to settle during the build:**
  - in sandbox mode (OpenShell) the workspace lives in the sandbox. I will restore files through the toolbox's own
    file calls.
  - If that cannot restore them reliably, the scoped round falls back to single for that run, with a logged reason.
    It will never run on half-restored files.

**Faults (D119).**
- Today a `tool_error` fault fires on the first n tool calls *in total*, across attempts (`faults.py:169-179`), and a
  capability fault is cleared only by the code-fix grant (`faults.py:204-209`). So without care, the second probe
  would face a weaker fault than the first.
- **Change:** `Faults.snapshot()` / `restore()` of each fault's `fired`, `cleared` and `hidden` state. Each probe
  starts from the fault state of the stuck attempt.
- **Also noted:** the proposer's grant_tool does not call `faults.granted` (`PR:3118-3121`), while the code fix does
  (`PR:2722`). I will make both behave the same.

**Probes.**
- Run one after the other: same model, inputs and options.
- Each probe keeps its attempt as `step_N.probe-inv.json/.md` and `step_N.probe-dom.json/.md`, beside keep_try's
  `step_N.tryK` files (`PR:2884-2890`).

**Signal diff.**
- After each probe, `step_signals()` (`stuck.py:155`) is computed on the probe's meta.
- It is compared with the stuck attempt's signals: cleared, kept, new. Status, tokens and turns are recorded too.

**Pick** (plain code, `probe.pick`):
1. A candidate whose step ends `done`. On a tie: fewer new signals, then fewer tokens.
2. A work_around that finished with limitation, only if no candidate is done.
3. Otherwise none recovered. The base for the next rung is the candidate with the most cleared and the fewest new
   signals, or the original state if neither cleared anything.

**Winner and loser.**
- The loser stays undone.
- The winner: its post-probe state is put back (a second snapshot is taken after each probe). The step is **not run a
  third time**.
  - The prompt says "re-apply only the winner's edit". Re-applying and re-running would cost a third run and could
    end differently. Restoring the probed state gives exactly the result that was judged.
  - Say if you want a re-run instead.
- No LLM composer, and the two edits are never merged.
- When the two probes cleared different signals: `complementary: true`.

**Plan-changing edits.**
- split_step and replan_remaining change the plan graph and are not probed.
- The other scope is probed first. The plan edit is applied, today's way (`PR:3106-3113`), only if that probe did not
  recover the step.

**Budget.**
- A scoped round counts as **one** try toward max_fixes_per_step / max_fixes_per_substep / max_fixes_per_task: one
  `fixes` record with `rung: "D"` and a `candidates` list.
- Tokens and USD count per probe, against the existing caps in `fix_stuck` (`PR:2500-2521`): D151's allowance, the
  step share and the USD limit.
- If only one probe fits the remaining budget, the scope is picked by cause: INV for tool_error, format, max_turns
  and claimed_file_missing; DOM otherwise.

**Question for you.** As written, both probes run even when the first ends `done`, so the tie-breaks can apply. Short-
circuiting after a `done` first probe would halve the cost of an easy round, but the comparison would be lost. I'll
build it as written unless you say otherwise.

### B3. Two new edits — new
Both go into `D_OPS`, `SHAPES` and `PARAMS` (`proposer.py:39-112`) and into adapt.yaml `allowed_edits`. The size,
denylist and rollback rules apply to both.

**add_tool_guidance** `{"tool": <a tool the step's helpers hold>, "text": ≤300 characters}`
- Allowed for tool_error, claimed_file_missing, missing_data and capability.
- It adds one line for that tool in the step's tool section:
  - text protocol: an extra line in the tools block of `plan_step.txt` / `plan_step_v2.txt`, through the slot that
    holds the unavailable and pool notes today (`PR:3386-3392`);
  - native protocols (legacy native and v2): appended to that tool's description in `native_specs`
    (`PR:3455-3468`), within its 600-character cut.

**add_watch_rule** `{"after_calls": 5–40, "unless": "file_written" | "tool_called:<name>", "text": ≤300 characters}`
- Allowed for max_turns, format, claimed_file_missing and checks.
- **Where it acts:** at the one place every tool result enters the turn history, for every protocol: `PR._loop`
  (`PR:2400-2408`).
- After the step has made `after_calls` tool calls without the condition, plain code appends the text once to the
  next tool result.
  - `file_written`: the local toolbox credited a new or changed file to this step (`toolbox.py:516-524`).
  - `tool_called:<name>`: that tool appears among the step's calls.
- It never blocks a call and never ends the step.

### B4. Design rules, each with a test
- **No check edits.**
  - No proposer op edits a check, the contract or a checker script today. But three of them drop checks as a side
    effect:
    - split_step builds its sub-steps with no checks (`PR:3222-3225`);
    - a replan_remaining step written without a `checks:` line loses its D142 checks (`PR:3976-3980`);
    - a work_around's narrower done_when changes the keyword checks drawn from done_when (`PR:737`).
  - **Change, by plain code:**
    - the last sub-step of a split inherits the stuck step's checks;
    - a re-planned step that replaces the stuck step keeps its checks, and a proposer reply that writes a `checks:`
      line is refused;
    - keyword checks keep using the original done_when.
  - **This changes today's split, re-plan and work_around behaviour in single mode too.** Say if you want it limited
    to scoped mode.
- `samples: 1` on every probe record. Nothing reads one probe as proof that an edit works in general.
- **`shared_failure: <signal>`** when both candidates fail with the same new signal.

### B5. Logging for the ablation — logging only, no learning
- **Records:**
  - one `events.jsonl` row per Box 4 round (`log_event`, `PR:2961-2963`; hash chain unchanged), plus result.json
    `adaptation.rounds`;
  - each row holds the stuck signals, each candidate (scope, op, params, because, refusals), each probe (diff,
    status, tokens, turns, files changed) and the pick with its reason.
- **`scripts/stuck_report.py`** gains a per-scope summary: candidates, probes, recoveries, signals cleared, tokens.
  It is read from stored result.json files.
- **`--fix-pick code|llm`** (default code):
  - `llm` is one call with a new prompt, `fix_picker.txt`. It sees only the task, the step's card and the two probe
    outputs labelled A and B, and picks one.
  - The checks still run on the result. The pick and the checks' verdict are both recorded.
  - It is for experiments only.

### Diagram, as-built page, docs
- New code is tagged `# box: proposer` or `# box: fixes`.
- `amoeba/adapt/probe.py` is named in the Box 4 proposer card's Files in `diagram/amoeba_phase1.html`; the stuck,
  fixes and plan-step cards are updated too.
- README's Box 4 section and spec §17 get the round in plain words and the sketch above.
- `python tools/arch_update.py` runs at the end, with no unassigned code.

### Tests (offline, mock)
- Everything the prompt lists.
- **Re-run of the Box 4 test set** (the D136 list in `tests/test_protocol_v2_d136.py:176-188`) under single and
  scoped × legacy and v2. A conftest switch `AMOEBA_TEST_PROPOSER` works the same way as `AMOEBA_TEST_PROTOCOL`
  (`tests/conftest.py:64-90`).
  - Under single every test must pass unchanged.
  - Under scoped, tests that count proposer calls or assert the exact list of fixes differ by design: a round makes
    two calls and logs one record with candidates.
  - I will list each such test and give it a scoped expectation. None will be skipped.
- I will also add the Box 4 files missing from the D136 list: test_ladder_d145, test_fix_tries_d150,
  test_faults_d119, test_budgets_d151 and test_diagnosis_d149.

## As built
(Filled in after the build.)

## Tests
(Filled in after the build.)
