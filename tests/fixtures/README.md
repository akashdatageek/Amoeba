# Test fixtures (spec §8)

All are plain text the `MockLLMClient` returns. None comes from a live model.

| File | Plays | Notes |
|---|---|---|
| `manager_output_real.txt` | Planner | **Composed by hand** in the exact shape of AutoAgents' `FORMAT_EXAMPLE` (`create_roles.py:61-95`): fenced role blobs, a colon-suffixed `## Question or Task:`, a three-step plan. Phase 1 was built without API access, so no captured run existed; replace with a real capture when one does. T3 checks our parsers reproduce what `environment.py` would produce on it. |
| `draft_round_ok.txt` | Planner | Two created roles; one lists an unknown tool (`web_search`) that must be kept out of its tools and recorded as a capability request (D19); no `## Capability Requests` section (optional — no repair call); the plan names a role that does not exist (`Editor`) in step 3, which must be dropped. |
| `draft_no_summariser.txt` | Planner | Every role has a tool; the last step's role (`Checker`) is flagged summariser and becomes the boss_reviewers solver — nothing is appended (D20). |
| `draft_capability_requests.txt` | Planner | A `## Capability Requests` section with a tool (nested JSON example) and a skill; `Researcher` names the unregistered `web_search` (D19). |
| `draft_bad_json_blob.txt` | Planner | First blob has a trailing comma (as in the FORMAT_EXAMPLE) → skipped, not crashed. |
| `draft_three_roles.txt` | Planner | Three roles for the boss+reviewers tests; the last step's `Writer` is the solver. |
| `observer_no_suggestions.txt` / `observer_complaint.txt` | Both observers | The `No Suggestions` sentinel vs. a complaint. |
| `worker_final_output.txt` | Worker | `Final Output` on turn 1. |
| `worker_calc.txt` | Worker | Uses the `calc` tool (intermediate turn). |
| `worker_never_final.txt` | Worker | `Print` every turn → 5 turns → `error="max_turns"`. |
| `worker_blocked.txt` | Worker | `Final Output` with `BLOCKED: web_search` → recorded in `blocked_steps` (D21). |
| `worker_unknown_tool.txt` | Worker | Action `web_search`, which the helper lacks → `unknown_tool` event, no echo (D21). |
| `critic_agree.txt`, `critic_agree_with_period.txt`, `critic_disagree.txt`, `critic_unparseable.txt` | Critic | `Action: Agree.` must parse as agree; a `Thought:` first line is unparseable (→ silent = agree). |
