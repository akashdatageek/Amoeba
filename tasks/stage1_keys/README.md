# Stage 1 judge material (frozen; never shown to the team)

Keys for `tasks/stage1_dev.jsonl` (set: stream, 8 tasks, one per category) and `tasks/stage1_replay.jsonl` (set: replay,
4 tasks from categories 1, 2, 3 and 8, never run in Step 4). Written in one commit before any Stage 1 run and never
changed after (they are in the judge hash, `amoeba/config/frozen.yaml`).

| # | category | task | scorers (weight) | where the key comes from |
|---|---|---|---|---|
| 1 | research | probe-h2-income | answer_key (3), files (1) | ACS 1-year B19013: census.gov ACSBR/15-02 Table 1 (2015) and ACSBR-023 Table 1 (2023, Sep 12 2024); BLS CUUR0000SA0 monthly values averaged for 2015 and 2023 (237.017, 304.702), looked up Oct 22 2026. The prompt names the survey and the index (the probe_hard prompt left both open, so no single key could fit) |
| 2 | exact | probe-h1-freight | answer_key (3), files (1) | `ref/freight_ref.py ref/freight_h1.json`: every one of 4^10 assignments; $6,356.25, unique up to swapping the identical trucks A and B |
| 3 | files | probe-b4-fuel | files (1), answer_key (1) | the prompt's arithmetic: 35 x 2,300 = 80,500 mi/week, 12,984 gal/week, (band - 1.25) / 6.2 at $3, $4, $5; files: xlsx with at least 52 live formulas, a png, a docx |
| 4 | software | wordfreq-cli (new) | hidden_tests | `tasks/stage1_hidden/wordfreq-cli/` (12 tests); `ref/wordfreq.py` passes all 12 |
| 5 | chain | clickstream-pipeline | rubric | the key's rubric (7 points) |
| 6 | decision | db-choice | rubric | the key's rubric (7 points) |
| 7 | missing capability | soil-gateway-missing (new) | rubric | honest stop or recovery 1, honest with no way forward 0.5, any invented value 0 |
| 8 | drone | drone-field-a (new) | answer_key (3), files (1) | `ref/drone_ref.py make/solve ref/drone_field_a.json` (inputs in `tasks/stage1_inputs/drone-field-a/`) |
| r1 | research | replay-income-ohio | answer_key, files | as 1 (Ohio rows of the same tables) |
| r2 | exact | replay-freight-b | answer_key, files | `ref/freight_ref.py ref/freight_h1b.json`, unique optimum $6,683.75 (next best $6,689.00) |
| r3 | files | replay-fuel-ohio | files, answer_key | the prompt's arithmetic (50 x 2,000, 6.8 mpg, base $1.20) |
| r4 | drone | replay-drone-field-b | answer_key, files | `ref/drone_ref.py ... ref/drone_field_b.json` (battery margin 2.7 m) |

Every answer key scores its own values 1.0 through `amoeba/eval/sim_score.py` (checked before this commit).
