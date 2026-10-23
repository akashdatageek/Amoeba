# Part 2, Step 2: one small probe per category

Runner container (`scripts/vm/run.sh`, image built from this branch), profile claude-sonnet+gemma-verify, protocol v2,
plan topology, d24 drafts, web tools, plan search on, adapt on, proposer scoped, pool on (`/out/pool`), local tools
in-process; `--max-usd-per-run 1`, `--max-tokens-per-run 5000000`; lessons off (probes do not learn). Flags:
`probes/flags.sh`, `probes/probe.sh`; prompts: `probes/probes.jsonl`. Costs at Sonnet 5.5 list prices with prompt-cache
reads and writes priced apart (`probes/probe_costs.txt`); Gemma is free.

| probe | result | status | cost | calls | what failed, and its kind |
|---|---|---|---|---|---|
| research | **fail** | no_deliverable | $0.93 | 69 | Step 1 found Indiana's 2020 count (6,785,528) but chased a day-level publication date for 11 turns and through four Box 4 fixes; the $1 cap then left no model for the check and the answer steps. *Amoeba's logic* (the date requirement and Box 4 keep a missing_data step alive past what the budget allows) and *setting*: no price for Gemma turned Box 4's own USD limit off (fixed, d02bcf8) |
| exact | pass | partial | $0.31 | 17 | correct (makespan 11, all 8 assignments). "partial" only from the D74 citation check flagging task inputs and labels ('4,7,9', '1,2', '3') as figures missing from S3: *Amoeba's logic* (false positive) |
| files, 1st | **fail** | crash | $0.92 | 53 | the $1 cap was reached inside a Box 4 proposer call and NoModelAvailable killed the run (no result.json): *tool/setting* (fixed, 7aa4c0f) |
| files, re-run | pass | ok | $0.93 | 68 | prices.xlsx with live `=B*C` and `=SUM` formulas, totals.png; verify steps on Gemma after the routing fix |
| software | pass | ok | $0.44 | 31 | slug.py + 10 pytest cases, run (10 passed) and re-run by the reviewer |
| chain | pass | partial | $0.50 | 28 | correct (3 duplicates, 17 rows, distinct users per country); "partial" from the same citation false positive ('0:00' of a timestamp): *Amoeba's logic* |
| decision | pass | partial | $0.89 | 48 | SQLite, reasons, three-row risk table; partial: the SQLite WAL page was cut at 6,000 characters, so two WAL details stayed [unverified], plus citation false positives: *tool/setting* (fetch length, by design) and *Amoeba's logic* |
| missing capability | **fail** | no_deliverable | $0.92 | 55 | step 1 knew it had no Nest access (BLOCKED nest_sdm_read) but Box 4 retried it seven times; the cap then left no model for the answer step, so the honest stop never reached the answer. *Amoeba's logic* (a capability nothing can supply should go straight to the honest stop, D129) |
| drone | pass | ok | $0.85 | 40 | NDVI 0.600 / 0.100, east half stressed, ndvi.png |

Step 2 total: **$6.70 of $8** (eight probes $5.77, the files re-run $0.93). Only the files probe was re-run: its failure
was the one caused by a tool or setting. The research and missing-capability failures are Amoeba's logic under a
$1 budget, so they are reported here, not patched.

## Fixed during Step 2 (general, tests first)
- `dc8dc32` runner: git, curl and Node trust the runner CA (the pool had no skills behind the proxy).
- `7aa4c0f` Box 4: the run's USD cap reached in a fix or proposer call ends that step's adaptation; the run finishes.
- `d02bcf8` prices.yaml: Gemma 4 is free, as in the registry (an unpriced model unpriced the whole run and Box 4).
- `2a63ed5` cost estimate: a call that never ran (no model) costs nothing.
- `4d2f794` D146 under the router: with `--routing routed`, the default and the only mode with a USD cap, the profile's Gemma
  verifier was filtered out and Sonnet verified its own work in every probe before the files re-run. Now the verifier
  is an allowed model and the preference for verify steps and the plan observer.
- `582b3d0` frozen judge: a task's own input files (workspace/inputs/) are not delivered work.

## Seen, not changed
- Gemma's free tier (15 requests per minute) put it in cooldown during the files re-run; 9 of 25 verify calls fell
  back to Sonnet by the router's design, so that check counts as same_model.
- When Sonnet reached the cap, the summariser fell back to Gemma (free) and the files probe still delivered its answer.
