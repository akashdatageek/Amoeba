# D171 — real scorers, all inside the frozen judge

Status: **built** (branch claude/zen-fermi-mnaurm, Oct 22). This fixes a review finding on D161 (main @ 9f1fb29).
It is general: a scorer reads a per-task key and names no task.

## Why
D161 left one deterministic stand-in, which looks at the first number of the answer. The outer loop (D166) compares
arms by this score, and a learning check needs a score per task. Neither can work on real tasks with only that.

## What
Four scorers join `SCORERS` (amoeba/eval/sim_score.py):

| scorer | reads | score |
|---|---|---|
| `answer_key` | `<judge_set>_keys/<task>.json`: `numbers` (`value`, absolute `tol` and/or `rel_tol`, `name`) and exact `strings` | the share found in the answer (a number counts when any number in the answer is within the tolerance; a string must appear exactly) |
| `hidden_tests` | `<judge_set>_hidden/<task>/`: a pytest folder | the share of tests passed. The run's workspace (without `sources/`, `skills/`, `made_tools/` and `inputs/`, the copies of the task's own files) is copied to a temporary folder, the tests are copied next to it as `_hidden_tests/` and run there with `PYTHONPATH` on the copy. The workspace is never touched, and the tests are never in the task's files or the workspace. A run over 300 s, or no report, scores 0 |
| `files` | the key's `files` list: `{check, path (a glob), min, max}`, where check is `exists`, `rows` (csv data rows), `formulas_live` (xlsx cells holding a formula, at least `min`, default 1), `pages` (pdf) or `image` (png / jpg header) | the share of checks passed; an unreadable file fails its check |
| `rubric` | the key's `rubric` text; the fixed grader of `amoeba/eval/judge.yaml` | the **median** of 3 grader calls |

**The rubric grader.**
- **Prompt.** It is `prompts/rubric_grader.txt`, written in our words. It sees only the task, the rubric and the answer.
- **Rules it applies.** It credits only what the answer states. An invented value fails the point it touches, or the
  whole answer when the rubric says so. An honest "could not find" meets a point that rewards it.
- **Reply.** One line per point, then `SCORE: <0..1>`. An unreadable reply scores 0.
- **Model.** It is the registry entry `gemma-4-31b`, at temperature 0.0, with 1,024 tokens of reply room and 3 calls
  per score. It is built by `grader_client` from `models.yaml`, never from the team's client. Its key is read from
  the environment only.
- **When the team also uses Gemma.** In the profile claude-sonnet+gemma-verify the team uses Gemma as its verifier.
  The grader is still a separate client with its own fixed prompt and temperature, and it never sees the team's
  messages.

**Several scorers.**
- A task lists `sim.scorers: [{name, weight}]`. Its score is the weighted mean, and each part (with its detail) is
  kept in `sim_score.json`.
- D161's form `{"scorer": name}` is still read as one scorer.
- `sim.judge_set` (for example `tasks/stage1`) is the prefix of the task set's judge folders: `tasks/stage1_keys/` and
  `tasks/stage1_hidden/`.
- This one field replaces separate `keys` and `hidden` fields, and the unused D161 `config` field is gone. That keeps
  `Task` within the 24 optional fields Claude's structured outputs accept (`tests/test_anthropic_d134.py`).

**The judge hash.**
- `frozen.yaml` now also lists `amoeba/config/prompts/rubric_grader.txt`, `tasks/*_keys` and `tasks/*_hidden`.
  `amoeba/eval` already covers the scorers and `judge.yaml`, which holds the grader's model id, temperature and calls.
- A frozen path may hold `*`: every match is hashed with its own path. A changed key, a changed hidden test, or a new
  task set therefore changes the judge hash.

**Leaks.**
- `run_task` refuses (exit 2) a task whose input files lie inside its key or hidden folders, or inside any
  `tasks/*_keys` or `tasks/*_hidden` folder (`check_no_leak`).
- A scorer that cannot score (for example, the grader key is missing) leaves `sim_score.json` with `score: null` and
  the error, never a crash. D166 then refuses to compare that run.

## Tests (tests/test_scorers_d171.py, red on 9f1fb29)
- **answer_key.** Numbers within an absolute and a relative tolerance and an exact string give 1.0, repeatably. A
  near miss, a hit and a wrong string give 1/3, with the detail.
- **hidden_tests.** Two hidden tests, one failing, give 0.5 twice, and the workspace still holds only the delivered
  file.
- **files.** A live xlsx formula, a csv with 3 data rows and a png pass. A missing pdf fails, giving 0.75 twice.
- **rubric.** With a recorded mock grader (0.4, 0.9, 0.6), the score is 0.6 on both rounds, from 3 calls. The prompt
  holds the task, the rubric and the answer, and the record names the grader model.
- **Weights.** answer_key weight 3 (passed) with files weight 1 (failed) gives 0.75.
- **The judge hash.** A changed key file, then a changed hidden test, gives three different hashes, and the new paths
  are listed.
- **Leaks.** A task whose files include its own key is refused.
