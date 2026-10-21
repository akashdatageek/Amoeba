# D156 — preflight: check everything before a real run

Status: **built** (branch claude/gemma-preflight, Oct 21). The first of five decisions (D156–D160) that make sure
everything Amoeba needs for the eight test categories is there, on Gemma only, before any real test runs.

## Why
A real run finds a missing piece late: after the planner has been paid for, or halfway through a step. Earlier runs
lost time to things a one-minute check would have caught: a missing library in the sandbox, LibreOffice missing, a
sandbox that would not start, a spent quota. We want one command that says, before anything is spent, what is
there, what is missing, and how to fix each missing thing.

## What
`python -m scripts.preflight [--profile gemma-api] [--mode sandbox|inprocess] [--skip-model-check]` prints one
table. Each row is one check: `ok`, `missing`, `warn` or `n/a`, what was seen, how to fix it, and which task
categories need it (research, exact, files, software, chain, decision, missing, drone). It exits 1 when anything a
category needs is missing; a `warn` (for example Tavily not reporting its credits) never fails it.

The checks:
1. **Keys.** GEMINI_API_KEY and TAVILY_API_KEY are set. The table says "set" or "not set"; a key is never printed.
2. **One tiny live call each.** Gemma answers "ok"; Tavily returns a search result.
3. **model_check.** `scripts.model_check <profile> --protocol v2` runs (about 5 minutes on Gemma). The reading,
   planner, step-turn and Final_Output probes must all pass.
4. **Rate limits.** RPM and RPD come from models.yaml, because Gemini's API does not report how much is left. A quota
   reply (429) seen during the checks is read by `amoeba/llm/quota.py::parse_quota`:
   - a per-minute quota is a warning, because runs wait and retry on their own (D48);
   - a daily quota is missing for every category until the reset.
5. **Tavily credits.** Read from `/usage` when the API reports them; otherwise a warning that says so.
6. **Sandbox host** (sandbox mode only; `n/a` in in-process mode, which instead needs AMOEBA_SANDBOX=1):
   - Docker is running;
   - the OpenShell gateway is healthy;
   - the image amoeba-sandbox:local is built;
   - the pool cache lists its skills.
7. **Local tools.** These go through the run's own `LocalToolbox`, started exactly as a run starts it: a fresh
   OpenShell sandbox in sandbox mode, this host in in-process mode. So what is checked is what a helper gets.
   - One call each of Bash, Read, Write, Edit, Glob and Grep.
   - Import each library in `LIBS` (numpy, pandas, matplotlib, PIL, openpyxl, docx, pptx, pypdf, scipy, pytest).
   - `soffice` is found.
   - `office_check()` passes: office.py's own check is written into the workspace and run there.
8. **Skills.** xlsx, docx, pptx and pdf are listed, and each one attaches to a helper.

## As built (Oct 21)
- `scripts/preflight.py`:
  - `World` holds every outside call (one method each); `LiveBox` wraps the real toolbox.
  - `check_keys`, `check_model`, `check_tavily`, `check_host` and `check_local` return rows.
  - `run_checks` turns a check that crashes into a missing row, never a crash.
  - `exit_code` and `table` produce the exit status and the printed table.
- `amoeba/llm/quota.py::parse_quota(text)` returns `{kind: minute | daily, quota_id, limit, retry_s}`. It reads
  `quotaId` (`...PerMinute...` / `...PerDay...`), `quotaValue` and `retryDelay` from Gemini's 429 body. D160 reuses
  it.
- **First live run (sandbox mode, model_check skipped)** found real gaps, before any task was run:
  - **The sandbox would not start.** The gateway image (3 weeks old) and the sandbox supervisor image (pulled a day
    ago) did not match ("unknown field `outer_fence`"). Pulling the current gateway image fixed it. The fix hint for
    this error now says so.
  - **scipy and pytest were not in the image, and neither was LibreOffice**, so office_check failed. D158 adds them.
  - **Glob and Grep were never offered.** Claude Code 2.1.289's `mcp serve` no longer lists Glob or Grep, so
    `local:Glob` and `local:Grep` were refused as not_allowed. D158 adds them in plain code.

## Tests
`tests/test_preflight_d156.py` (14 tests, offline, with a fake World):
- per-minute and daily quota replies are read;
- with everything present the exit code is 0 and every check is in the table;
- a missing key gives a "how to fix" that says where to add it, and no key value is ever printed;
- a daily quota fails every category, while a per-minute one is only a warning;
- model_check needs Final_Output;
- a missing library names the categories that need it, with a Dockerfile fix in sandbox mode and pip in in-process
  mode;
- no office suite, or a skill that is missing or does not attach, fails "files";
- Docker down fails sandbox mode but is n/a in in-process mode;
- a crashing check becomes a row;
- Tavily credits are reported, and 0 left means missing;
- the server's JSON Bash replies are read;
- the exit-code rule;
- main prints the table.

## Addendum (Oct 21, after a container reset)
The session's container was reset. The preflight was run again on a fresh machine and found three more setup gaps:
- The gateway's signing certificates were missing ("docker sandboxes require launch-scoped gateway authentication").
  The fix is the one-time `generate-certs` step in docs/RUNNING_ON_A_VM.md.
- The `amoeba` package was not installed in the venv, so the sandbox bridge (`python -m amoeba.localtools.sandbox`)
  could not start.
- The pool cache (`data/pool`) was gone. `python -m amoeba pool refresh` brings it back.

When the toolbox does not start, the row now shows the last line of the server's stderr and names the matching fix
(image mismatch, missing certificates, or `pip install -e .`). Test: `test_a_toolbox_that_will_not_start_names_the_fix`.
