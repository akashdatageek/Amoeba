# D135 — `python -m scripts.model_check <profile>`

Status: **built** (branch claude/protocol-v2) and run live on Oct 16 on claude-sonnet, claude-sonnet-compat and
gemma-api. The differences from the request are listed under "As built" at the end.

**Why.** Nothing checked a new model before Amoeba used it. The `supports` flags in models.yaml were set by hand. The
probe re-run found the planning block only after a full paid run.

## Design

1. **One tiny call per call type.** Each uses Amoeba's real prompt builder on a toy task (a van's weekly fuel cost):
   - reading (Box 1, `read_task`);
   - the planner, one round, and its first observer (Box 2, `draft_team` with the CLI's default d19 prompts);
   - one native-tools step turn (Box 3, a one-step team holding `calc`, PlanOptions `native_tools=on`, `--protocol`
     v2 by default);
   - the fix proposer (Box 4, `fix_proposer.txt`);
   - the pool pick (`pool.stock.pick`).

   A **gate** in front of the client lets each probe's own call through and raises on any other. The pipeline stops
   right after the probe's call, so no probe pays for a whole run. A repair call of the same kind (a reply that did
   not parse) marks the probe unreadable.
2. **Output modes, in order:**
   - `schema`: the API's structured output (`schema=`, D134);
   - `submit_tool`: a tool `submit_toy_answer` with the schema as its parameters, offered and not forced;
   - `json_prompt`: JSON asked for in the prompt, validated by pydantic, with one repair call.

   `supports.output_mode` is the first mode that validated.
3. **Each probe records** ok / blocked (+ refusal category, + the prompt files found) / unreadable / error / skipped,
   plus latency, tokens and cost (prices.yaml). The result goes to `data/model_checks/<registry entry>.json`, and a
   table is printed.
4. **Budget** (`--budget-usd`, default 0.25). Before each probe the spend so far is compared with the budget. Once it
   is spent, the remaining probes are recorded as skipped.
5. **`--write`** sets the registry entry's `supports.tools`, `supports.output_mode` and `checked_at` in models.yaml. It
   edits only those lines, keeps every comment and shows the diff.
6. **A `reasoning_extraction` refusal** fails the check (exit 2) with a `FAIL:` line naming the probe and the prompt
   file.
7. **Keys** come only from the profile's `api_key_env`. A missing key is named, never printed.

## As built (Oct 16) — where the code differs from the request

- The JSON file is named after the registry entry (`claude-sonnet-5-5`, `claude-sonnet-5-5-compat`, `gemma-4-31b`),
  not the model id. Native Claude and compat Claude share one model id and would overwrite each other.
- `--protocol v2|legacy` picks the step turn's protocol (default v2).
- All three output modes are probed every time (they are cheap), so the table shows each one. `supports.output_mode`
  is the first that worked.
- `--write` was applied to the two Claude entries only. Gemma's check showed working native tool calls, but writing
  `supports.tools: true` would switch every Gemma run to native tools (`--native-tools auto`). That is left to the
  user.
- `ModelEntry` gained `checked_at` so the registry still loads after `--write`.

Tests: tests/test_model_check_d135.py (every probe once through the gate, a reasoning refusal failing with its prompt
file, the output modes falling through, the budget skip, `--write` touching only the entry's supports and checked_at).
