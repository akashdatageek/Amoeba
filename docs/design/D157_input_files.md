# D157 — task input files

Status: **built** (branch claude/gemma-preflight, Oct 21).

## Why
Some test categories start from files the user gives, for example the drone task, which gives red.png and nir.png.
Until now a task was only text. A run could not be handed a CSV or an image, so a helper could only be told about
the file in words.

## What
1. **A task may name files.**
   - `Task.files` is a list of paths: `"files": [...]` in a `--tasks` file, or `--file PATH` (repeatable) for a
     free-text task.
   - A task without files is unchanged.
2. **Copied read-only, before any model call.** `run_one` copies each file to `runs/<id>/workspace/inputs/<name>`
   with mode 0444, like the fetched files in `sources/` (D107).
   - A path that does not exist stops the run before anything is spent.
   - In sandbox mode the files are also put into the sandbox's `/sandbox/workspace/inputs/` right after it is
     created, read-only there too.
   - Given files are never counted as files the team made, and they are not copied back out of the sandbox.
3. **Writes refused.** `inputs` joins `sources` and `skills` among the protected workspace parts. A Write or Edit
   into it is refused, and so is a Bash command that writes, moves, deletes or copies into it. Reading it and copying
   out of it are allowed.
4. **Everyone is told, with sizes.** One block, `amoeba/task/inputs.py::inputs_text`, lists each file as
   `inputs/<name> (<n> bytes)`, says the files are read-only, and says that a step that needs one names it. The block
   goes to:
   - Box 1 (the task reading, on its Environment slot);
   - Box 2 (the Planner and both observers, with the tool list, in both d19 and d24/v2 prompts);
   - every helper's role card (Box 3).

   The task text itself is not changed, so D52's number coverage does not count file sizes as task numbers.
5. **Box 2 checks.** The new HARD check `input_files_named` passes when every given file is named, by path or by
   file name, in some step's text, do, output or done_when. Otherwise the quality gate sends the plan back: "Input
   files given with the task that no step names: …". It is n/a when no file is given.
6. **Recorded.** result.json has `input_files: [{path, size}]`, and the trace has an `input_files` event.

## As built (Oct 21)
- New `amoeba/task/inputs.py` (`copy_inputs`, `inputs_text`).
- `Task.files` and `RunResult.input_files` (`amoeba/task/models.py`).
- `run_one` and `--file` (`scripts/run_task.py`).
- `draft_team(inputs=…)` (`amoeba/task/draft.py`).
- `quality.input_files_named` and `HARD_CHECKS` (`amoeba/task/quality.py`).
- The pool item `kind: "inputs"` is rendered by `plan_card` and `role_card`.
- `gate.PROTECTED_PARTS` and `PROTECTED_COMMAND`.
- `LocalToolbox._push_given`, and `add_input(folder=)`.
- The sandbox pull excludes `./inputs`.

**Existing tests that changed: one count.** `tests/test_quality.py` counts the n/a checks, and there is now one more
(input_files_named, n/a without files).

## Tests
`tests/test_input_files_d157.py`:
- a task may name files, and old tasks have none;
- files are copied read-only and listed with their sizes;
- a missing file stops the run;
- writes into inputs/ are refused, while reading and copying out are not;
- with a CSV and a PNG, both are in workspace/inputs and named, with sizes, in every interpreter, planner and helper
  prompt, and result.json lists them;
- the Box 2 check;
- the CLI flag;
- in sandbox mode the files go into the sandbox read-only and are not counted as made.
