# D160 — Gemma quota handling

Status: **built** (branch claude/gemma-preflight, Oct 21).

## Why
Gemma on the free tier has two limits: requests per minute (15) and requests per day (1,500). Each one sends back a
429.
- **Per-minute limit.** A wait and a retry clear it. The client already retried every 429 (D48), but it waited
  2, 4, 8 … seconds. It ignored the wait the reply itself asks for ("retryDelay": "39s"), so the first retries came
  too early and were wasted.
- **Daily limit.** It does not clear until the next day. The client still retried it five times (about a minute of
  waits). Then the run ended as `api: … 429` (status infra_error), and nothing said that it could be continued.
  Rerunning meant paying again for every step that had already finished.

## What
1. **Per-minute: wait as asked, then retry.** When the 429 has no Retry-After header, the wait is the reply's
   `retryDelay` (or its "Please retry in N s"), at most 60 s. The retry cap and the trace records are as before.
2. **Daily: no retry.** `amoeba/llm/quota.py::parse_quota` (D156) reads the reply. A daily quota marks the error
   (`amoeba_quota`) and raises it at once; `client.quota_exhausted(e)` says so.
3. **The run stops cleanly with status `quota_exhausted`.**
   - While planning: run_task records `quota_exhausted: <the error>`.
   - In a plan step: the plan runner stops the way D122/D123 stop a run. The answer is assembled from the finished
     steps, and the steps not run are named.
   - In the flat and boss_reviewers runs: the same error text.
   - `run_status` maps it to `quota_exhausted`.
   - run_task does not start the remaining tasks of a task file, because they would stop the same way.
4. **What is saved.** `runs/<id>/resume.json` holds the flags, the task, the response cache and its namespace, the
   date the run's helpers were told, and the time zone. run_task prints the command to resume.
5. **`python -m scripts.run_task --resume <run_id> [--runs-dir …]`.** It runs the same task with the same flags,
   the same cache namespace, and the same date (`--run-date`). So every prompt up to the stop is byte-identical,
   and every finished call replays from the cache (D73) without being paid again. result.json records
   `resumed_from`.
6. **A live run always has a cache.** Without `--llm-cache`, a live run now records its responses under
   `<runs-dir>/llm_cache` in a namespace of its own (`run-<id>`). That is what makes any live run resumable. The
   namespace is new for each invocation, so separate runs never replay each other. The mock is unchanged.
7. **`--run-date YYYY-MM-DD`** sets the date the helpers are told (D75). Resume uses it. Without it, a run takes
   today's date once, at start.

## Limits
- **Local tool calls run again on resume**, as in D73. They change the workspace, so they are not cached. Their
  output is the same unless it depends on the time.
- **In in-process mode a step prompt can contain the run's own folder path**, which differs between the two runs.
  From such a prompt on, calls are paid again. Sandbox mode uses the fixed path /sandbox/workspace.

## As built (Oct 21)
- `amoeba/llm/client.py`: `quota_exhausted`, and the daily / per-minute branches in `chat_messages`.
- `amoeba/task/models.py`: `run_status` and `RunResult.resumed_from`.
- `PlanRunner.run` and `Interpreter.run` (flat).
- `scripts/run_task.py`:
  - the `--resume` and `--run-date` flags;
  - `default_cache`, `save_resume` and `run_date`;
  - `run_one(today=, resumed_from=)`.

**Existing tests that changed: none.**

## Tests
`tests/test_quota_d160.py`, with a mock client that answers daily-quota errors:
- a per-minute 429 waits the 39 s it asks for, then succeeds;
- a daily 429 is not retried;
- the status;
- a daily quota mid-plan, and one while planning, both stop the run cleanly as quota_exhausted;
- **resume the next day:**
  - the first run stops at call 7 and saves resume.json;
  - the next day, `--resume <id>` pays for exactly (all calls − 6) and ends with the same answer and status as a run
    that never stopped, although the clock moved a day;
- a live run gets a cache, and the mock and `--llm-cache-mode off` do not.
