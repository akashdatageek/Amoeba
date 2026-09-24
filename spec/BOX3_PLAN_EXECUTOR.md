# Box 3: run the plan Box 2 now writes (proposed D31–D36)

Hand this to Claude Code from the Amoeba repo root. Box 2 (d24) now produces requirements, fully defined roles,
steps with `covers / depends_on / do / output / done_when`, and capability requests. Box 3 still runs the
AutoAgents way:
- `run_flat` walks the steps in list order and hands every helper the whole history (`previous`, group.py:76).
- `run_boss_reviewers` ignores the plan entirely.
- `depends_on`, `output` and `done_when` are never used.
- The only tools are `echo` and `calc`, so steps that need current facts either answer BLOCKED or invent them.

**Goal:** a runner that carries out a d24 plan faithfully, uses real tools for current facts, can show where every
fact came from, and is scored end to end with the Box 1 rubric. Keep the existing runners unchanged as baselines.

Work in stages. Commit after each stage with tests passing, and add each as a D-row in `spec/BUILD_SPEC_PHASE1.md`.

---

## Stage A (D31): plan executor over `depends_on` (new topology `plan`)

1. `interp/plan_runner.py`: `run_plan(cfg, task, ep)`, selected with `--topology plan`. `flat` and
   `boss_reviewers` stay exactly as they are.
2. Build a graph from `depends_on`. Validate it (unknown step, cycle → error before any LLM call). Run the
   steps in topological order. Group steps whose dependencies are all done into "waves". Run each wave
   sequentially for now, but record the wave number so parallel execution can come later without changing traces.
3. **Artifact store**: each step's result is saved as `runs/<id>/artifacts/step_<n>.md` with metadata
   `{step, roles, covers, output_spec, status, sources[]}`. A step receives **only the task, its own step
   detail, and the artifacts of the steps it depends on**, not the whole history. Record what each step received.
4. The worker prompt for a plan step: the role card (goal, skills, constraints, prompt) + the step's
   `do / output / done_when` + the dependency artifacts + the tool list. Keep the Thought / Action /
   ActionInput format and the 5-turn cap per step.
5. Multi-role steps: the roles take turns within the step's turn budget, as they do now. Record who contributed what.
6. Tests: diamond graph (1→2,3→4) runs in a valid order; a cycle is rejected; a step never sees an
   artifact it doesn't depend on; toy tasks with a d19 draft still run (no depends_on → treat as a chain).

## Stage B (D32): web search and page fetch, the first real tools

1. Add `web_search(query) → top results [{title, url, snippet}]` and `fetch_url(url) → cleaned text (truncated)`
   to the registry, behind one provider interface. Ask me which provider to use before implementing; the
   options are Tavily, Brave Search API or SerpAPI. Read the key from an environment variable, never from a file.
2. Every tool result gets a `source_id` (S1, S2, …) stored in the artifact's `sources[]` with url, title and time
   fetched.
3. Map the canonical capability `web_search` (D29 aliases) to these tools, so a d24 role that requested
   web search is given them automatically. Record the mapping in the trace.
4. Limits: max searches per step, max fetched characters, a timeout. On tool failure → an error string to the helper
   and a trace event, never a crash.
5. Tests with a mocked provider (no network in tests). One real smoke test script, not in pytest.
6. Cloud note: the provider's domain must be added to the Claude Code cloud environment's Custom network
   allowlist. Write the exact domain into the README.

## Stage C (D33): provenance, with no invented facts

1. The worker prompt rule: every number, price, date, law or benchmark figure must carry `[S#]` pointing to
   a tool result, or `[unverified]` if it comes from model knowledge. It must never be invented without a tag.
2. Code check after each step (deterministic): extract numbers and `[S#]` tags. Record `cited`, `unverified` and
   `untagged` counts, and flag any `[S#]` that doesn't exist in that step's sources (a hallucinated citation).
3. Derived numbers (arithmetic on cited inputs) are allowed if the step shows the calculation, or used `calc`.
4. Store the counts in `result.json` under `provenance`.

## Stage D (D34): check `done_when` and the verification step

1. After each step, a deterministic check where possible: required output format present (a table, a list,
   headings named in `output`), numbers present, the dependency artifacts referenced. Record pass/fail.
2. If the check fails and turns remain: one retry with the failed check listed. Otherwise mark the step
   `incomplete` and continue. Downstream steps see the status of their inputs.
3. Verification steps (the d24 "independent verification"): the verifier gets the artifacts under review
   and must return `## Verdict: PASS | FAIL` plus the issues. On FAIL, the producer step re-runs once with the
   issues (limited to 1 rework per step), then the run continues whatever the result. Record the rework.

## Stage E (D35): the summariser only assembles

1. The summariser step gets all artifacts plus their statuses and provenance, and the task's deliverable list
   (from the Box 2 requirements, never from the rubric).
2. The prompt says: assemble and edit, add no new analysis or numbers, list gaps (blocked or incomplete steps,
   unverified facts) in a final "Limitations" section.
3. Code check: any number in the final answer that appears in no artifact → flag `new_number_in_summary`.

## Stage F (D36): BLOCKED policy for capabilities we still don't have

1. If a step needs a capability that isn't registered (for example `database_sandbox`), the helper does what it
   can and marks the rest `BLOCKED: <capability>`. The artifact status becomes `partial`, with the gap listed.
2. The run always continues. The final answer's Limitations section must name each blocked capability.
3. `result.json`: `blocked_capabilities` with counts, which feeds the tool-building queue later.

---

## Evaluation (run after Stage F)

- **Regression:** toy tasks, `flat` and `plan`, mock and Gemini. `plan` must be at least as good as `flat` on toy tasks.
- **Complex tasks, end to end** (Box 1 → d24 Box 2 → Box 3), 3 repeats, gemini-3.1-flash-lite and gemini-3.5-flash:
  - arms: `flat` (AutoAgents baseline) · `boss_reviewers` · `plan` without web tools · `plan` with web tools
  - metrics: rubric score and per-item pass/fail (D30), provenance counts (cited / unverified / untagged /
    hallucinated citations), steps complete / partial / incomplete, verification FAIL→rework rate,
    `new_number_in_summary`, blocked capabilities, tokens, calls, wall time
- Write `docs/real_runs/<date>_box3_arms.md` with the table and one full Box 3 transcript for `db-choice` (plan
  + web), in the same readable format as the Box 2 transcripts (every step: input artifacts, tool calls with
  sources, output, checks).
- Regenerate the as-built page with the new Box 3 view.

## Rules

- Existing runners and their tests stay unchanged. They are the baselines.
- No rubric content in any prompt (the existing leakage test must cover the new prompts).
- Every limit is in code and in the trace: turns per step, reworks, searches, fetch size, tokens per run.
- Report back with only the arms table, the three biggest failure types from the transcript, and anything that got worse.
