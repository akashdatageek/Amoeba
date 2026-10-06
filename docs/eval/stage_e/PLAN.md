# D117 Stage E: --adapt off vs on — plan and cost estimate (not run)

## Design

- **Arms**: the same command, only `--adapt off|on` differs. Shared flags: `--topology plan`, the `gemma-api` model
  (gemma-4-31b-it, as before), pool on, `--local-tools on`, `--web-tools` (as in the probe runs), `--ask-assumed off`
  (background runs cannot answer questions; D116 would otherwise stop at Box 1).
- **Pairs**: same task, same seed. The off arm drafts (Boxes 1–2); the on arm reuses that run's `plan.json`
  (`--drafts-from <off runs folder>`), and both use one `--picks-file`, so the team, the plan, the interpretation and
  the pool picks are identical and the arms differ only in Box 3. Box 3 sampling stays noisy (Gemma's API does not
  promise a fixed seed): hence 3 seeds.
- **Pilot**: H1–H3 × 2 arms × seed 0 (6 runs); report the cost per run; ask before the full set. The pilot counts as
  seed 0 of H1–H3 in the full set, and as the H1–H3 rerun still open (task #78).
- **Full set**: 13 tasks × 3 seeds × 2 arms = 78 runs (72 after the pilot).

## Tasks (H1–H3 plus 10 previously stuck)

| Task | Cause it was stuck on (stored runs) | Rubric | Source |
|---|---|---|---|
| probe-h1-freight | none in 1 run | no | tasks/probe_hard.jsonl |
| probe-h2-income | capability (2 per run) | no | tasks/probe_hard.jsonl |
| probe-h3-ev-trucks | capability; the only stored tool_error | no | tasks/probe_hard.jsonl |
| r1-full-chain | missing_input 50, capability 26 (11 runs) | no | tasks/observer_round1.jsonl |
| r1-weather | missing_input 12 | no | tasks/observer_round1.jsonl |
| r1-repo | capability 43 (pool on) | no | tasks/observer_round1.jsonl |
| r1-pdf-read | capability 38 (pool on) | no | tasks/observer_round1.jsonl |
| r1-fx-email | capability 26 (pool on) | no | tasks/observer_round1.jsonl |
| r1-xlsx | max_turns 3, capability 17 | no | tasks/observer_round1.jsonl |
| bench5-xlsx | max_turns 2 | yes | tasks/bench5.jsonl |
| m2-calc-g09 | checks 6 (only cause) | yes | stream_m2 (removed in D117 A; restored from git into tasks/stage_e.jsonl) |
| m2-calc-g03 | checks 4 (only cause) | yes | as above |
| m2-calc-g05 | repeated_error signal 6× (tool_error candidate), capability 30 | yes | as above |

Caveats: only one tool_error was ever picked in stored runs, so tool_error rests on H3 and g05. The checks tasks were
stuck only with the pool off (5 of 21 and 3 of 21 runs), so with 3 seeds they may not get stuck at all. The r1 tasks
were last run in round 4 with older code.

## Report per arm (scripts/stage_e_report.py, to be written before the pilot)

- outcome per run: **done** (status ok, no step left stuck, no work-around) / **done with limitation** (an answer,
  but a work-around or a step left not done) / **stuck-stopped** (on arm: status `stuck`) / **failed** (agent_error,
  infra_error, no_deliverable, needs_clarification). The off arm's stuck steps are counted offline with the same
  watch (`scripts/stuck_report.py`), since `--adapt off` does not watch.
- stuck steps by cause; recovered steps by rung (code: add_dependency, rerun_upstream, more turns, retry turns,
  larger input, grant from the pool; proposer: each edit type); work-arounds counted apart ("finished with
  limitation").
- rubric score where the task has one (bench5-xlsx, m2-calc-*).
- extra tokens and $ from adaptation (`result.json` `adaptation.tokens` / `cost_usd`), and each arm's totals.
- 3 recovered steps per arm picked at random (seeded), each with its trace lines (`stuck`, `fix_try`, `proposer_reply`,
  `fix_done`, the re-run's `step_done` and checks) and the step's text before and after, to check the recovery is real
  and not only the contract passing.

## Cost estimate (from stored traces)

Tokens are billed tokens (input + output + Gemma's hidden reasoning). Per task: the stored runs' Box 2 and Box 3
tokens; the off arm = Box 2 + Box 3; the on arm = Box 3 (the draft is reused) + adaptation. Adaptation per stuck step:
typical 2 step re-runs + 1 proposer call (~6,000 tokens); high 3 re-runs + 3 proposer calls with a retry each; capped
at 200,000 tokens per task (adapt.yaml). Stuck steps per run: the stored average for that task. Runs from round 4 and
bench5b (older code, saved drafts) are scaled ×1.5 and given 35,000 Box 2 tokens.

| Task | off arm | on arm (typical) | on arm (high) | off min | on min | stuck / run |
|---|---:|---:|---:|---:|---:|---:|
| probe-h1-freight | 156,246 | 108,436 | 225,763 | 31 | 31 | 0.00 |
| probe-h2-income | 204,806 | 270,968 | 367,963 | 35 | 51 | 2.00 |
| probe-h3-ev-trucks | 303,098 | 433,488 | 433,488 | 63 | 116 | 4.00 |
| r1-full-chain | 112,042 | 248,310 | 277,042 | 15 | 47 | 8.00 |
| r1-weather | 172,008 | 137,008 | 250,074 | 34 | 34 | 0.00 |
| r1-repo | 64,150 | 107,732 | 229,150 | 7 | 24 | 5.00 |
| r1-pdf-read | 121,804 | 249,690 | 286,804 | 17 | 50 | 4.00 |
| r1-fx-email | 128,848 | 176,234 | 271,427 | 22 | 42 | 2.00 |
| r1-xlsx | 164,643 | 211,725 | 288,766 | 27 | 44 | 1.33 |
| bench5-xlsx | 132,490 | 144,820 | 186,484 | 18 | 27 | 0.67 |
| m2-calc-g09 | 130,781 | 112,102 | 129,057 | 31 | 38 | 0.29 |
| m2-calc-g03 | 95,339 | 92,496 | 103,082 | 22 | 25 | 0.19 |
| m2-calc-g05 | 128,596 | 211,835 | 305,441 | 33 | 60 | 1.67 |

| | Runs | Tokens (typical) | Tokens (high) | Wall time, sequential | $ |
|---|---:|---:|---:|---:|---:|
| Pilot (H1–H3 × 2 arms × 1 seed) | 6 | 1.48 M | 1.69 M | ~5.5 h (~3 h with the 3 tasks in parallel) | $0.00 |
| Full set (13 × 3 × 2) | 78 | 13.3 M | 15.8 M | ~47 h (~16 h with 3 in parallel) | $0.00 |
| Full set after the pilot | 72 | 11.8 M | 14.1 M | | $0.00 |

- **$**: Gemma runs through the Gemini API (Google AI Studio key) with no price in `amoeba/config/prices.yaml`
  (`gemma-4-31b-it: {input: null, output: null}`), and the probe report billed $0.00. At another rate the cost is
  tokens × rate (e.g. 13.3 M tokens at $X per million = 13.3·X dollars).
- **Adaptation's own share** (typical): about 0.29 M tokens in the pilot (H2 ~86 k, H3 ~200 k at the cap) and about
  3.1 M over the full set.
- **Other quotas**: web searches go to Tavily — the stored H runs used 0 (H1), 16 (H2) and 8 and 3 (H3's two runs) searches and fetches; the full
  set may use a few hundred. The API's request rate limit may stretch the wall time.
- **Uncertainty**: the stuck rates come from older runs and fixes since then (D105–D116) change them; one stored run
  each for H1 and H2. The pilot's measured cost per run replaces these figures before the full set is asked for.
