# D161 — the frozen judge and the task scorer

Status: **built** (branch claude/zen-fermi-mnaurm, Oct 21). It is stage 0 of `spec/BUILD_SPEC_BOX4_RSI.md`.
Following the user's decision, it is general: no niche is chosen.

## Why
The outer loop (D166) will change Amoeba's settings and keep a change only if results get better. That needs two
things:
- **A number that says "better".** Many tasks have no ground truth, so a task must be able to name a scorer.
- **A judge the loop cannot move.** If a change could also change the checks or the score, "better" would mean
  nothing. So the judging files are fixed, and every run records exactly which judge scored it.

## What
1. **The frozen list.** `amoeba/config/frozen.yaml` names the judge:
   - `amoeba/checks/` (domain checks);
   - `amoeba/task/quality.py` (Box 2's plain-code plan checks);
   - `amoeba/task/evaluate.py` (the answer score);
   - `amoeba/eval/` (the scorers and this hash);
   - `frozen.yaml` itself;
   - `data/baselines/` (baseline results; none yet).
2. **The hash.** At the start of every run, `amoeba/eval/judge.py::judge_hash` hashes each listed path:
   - it reuses `manifest_entries` and `sha256_text` from the evidence log, so a folder is hashed file by file, and
     `__pycache__` is skipped;
   - a missing path is recorded as missing, so adding it later changes the hash;
   - the digest goes to `result.json` (`judge_hash`) and to the trace (`judge_hash`).
3. **No mixed comparisons.** `same_judge(results)` returns the shared hash, or raises `JudgeMismatch` when the hashes
   differ or one is missing. D166 calls it before comparing two arms.
4. **The task scorer.** A task may carry `sim: {scorer, expected, baseline, config}`, which is typed (`SimSpec`), not
   free-form.
   - After the run, `amoeba/eval/sim_score.py::score_run` asks that scorer and writes `<run>/sim_score.json`: score,
     baseline, delta, seed, scorer and judge hash. The same data goes to `result.json` (`sim_score`).
   - The seed is `--sim-seed`, or `--seed` when it is not given.
   - Box 4 never reads the score.
5. **The stand-in scorer**, the only one for now. It takes the answer's first number and compares it with
   `sim.expected`:
   - 1.0 when they are equal, falling linearly to 0 at 100% relative error;
   - 0 when the answer has no number.

   `sim.baseline` is the baseline's score. The scorer is deterministic, so the seed is recorded but changes nothing.
   A real simulator becomes one more entry in `SCORERS`.
6. **Task sets.** A task may carry `set: stream` (learned from) or `set: replay` (never learned from; only D166's
   test reads it). `tasks/general_example.jsonl` holds four toy tasks, two of each, all with the stand-in scorer.

## As built (Oct 21)
- New:
  - `amoeba/config/frozen.yaml`;
  - `amoeba/eval/judge.py` (`judge_hash`, `same_judge`, `JudgeMismatch`, `frozen_paths`);
  - `amoeba/eval/sim_score.py` (`SimScorer`, `StandInScorer`, `SCORERS`, `score_run`);
  - `tasks/general_example.jsonl`.
- `amoeba/task/models.py`: `SimSpec`, `Task.task_set` (JSONL `set`), `Task.sim`, `RunResult.judge_hash` and
  `RunResult.sim_score`. `sim_score` is left out of `result.json` when it is None.
- `scripts/run_task.py`: the hash at run start, the score after the answer is on disk, and `--sim-seed`.
- A new as-built box, `frozen_judge`.

**Existing tests that changed: none.** `result.json` gains one field, `judge_hash`, for every run.

## Tests
`tests/test_frozen_judge_d161.py`:
- the frozen list names the judge;
- **changing a frozen file changes the hash, and only that file's part, and the comparison refuses**;
- an unknown hash is refused;
- a file outside the judge does not change the hash;
- the stand-in is deterministic;
- `score_run` writes `sim_score.json`, and an unknown scorer is an error;
- `set` and `sim` are read from JSONL;
- **a toy run twice with `--sim-seed 7` gives the same score, and its `result.json`, `sim_score.json` and today's
  judge hash agree.**
