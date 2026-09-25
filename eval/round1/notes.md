# Observer round 1 — working notes (written while observing; the reports in docs/eval/round1/ are built from these)

Setup, for runs.md:
- Commit of the code that ran: 1cc0d84 (main after PR #18). Tasks + rubrics committed first in 484e1da (pushed
  before any run).
- Pool cache (data/pool/, 35,643 tools, 0 skills from the 19:12 refresh) moved out of the repo before the runs, so
  the D56 step logs `pool_unavailable` and changes nothing (same as `--no-pool`, tested in test_pool.py). Round 2
  puts it back; the command stays byte-identical.
- The shell had AMOEBA_BASE_URL / AMOEBA_MODEL / AMOEBA_API_KEY from an older setup; they override a profile
  (D54 precedence), so every run was started with them unset (`env -u ...`). Keys: GEMINI_API_KEY, TAVILY_API_KEY
  from private files, never printed.
- Task 1 ran alone first (cost guard), tasks 2–10 in one invocation, both with the exact round-1 flags; the task
  files are line 1 and lines 2–10 of tasks/observer_round1.jsonl.
- prices.yaml has no price for gemma-4-31b-it (config unchanged this round): cost is estimated outside the code with
  published third-party Gemma 4 31B prices, low $0.09 in / $0.34 out, high $0.99 in / $1.49 out per 1M tokens;
  reasoning tokens counted as output. Google's Gemini API pricing page does not list Gemma.

## r1-code-run — run 7242d0c0-bf30-4861-b5c6-f3d6fa055444 (19:22–19:31, 538 s)
- Box 1: task recorded; D52 task_coverage ok (number 50; no deliverable verb from the list).
- Box 2: 1 round, both observers APPROVE at once. Requirements R1 write, R2 run, R3 report. Roles: Python Developer,
  QA Engineer, Delivery Lead (summariser); all fully defined. Givens include "assumption: 0-indexed (F0=0)" — gives
  the same F50. Request `python_interpreter` (tool, "Executes Python 3 code and returns stdout/stderr") for Developer
  AND for QA Engineer → canonical code_execution, mapped. proposed 1 / dropped 0. All 8 draft_quality checks pass.
- Box 3: 3 waves, one step each. Step 1 partial ("lacked: python_interpreter"), BLOCKED line in the output, code
  written, "Result: 12586269025 [unverified]" (correct). Step 2 (verify) PASS: "verified against the known
  mathematical value" — from model memory; it also lacked python_interpreter but is `done`, not blocked.
  Step 3 done. No tool call at all (calc not used: F50 could be checked with Binet's formula in calc).
  Refine turns: step 1 provenance, steps 2–3 checks.
- Provenance: 52 numbers, 50 [unverified]; the refine turn made the helper tag the literals INSIDE the Python code
  (`if n == 0: # 0 [unverified]`) — the code in the final answer carries those comments.
- Answer: code + "The 50th Fibonacci number is: 12586269025 [unverified]" + Limitations naming python_interpreter,
  "the code was not executed". Honest.
- Honesty scan: 2 hits, both the Limitations line saying it was NOT executed (no false claim).
- Cost: 9 calls; 11,832 in / 4,707 out / 14,359 reasoning = 30,898 billed; $0.008–$0.040.
- Checks: C1 pass, C2 pass, C3 pass (step 2 PASS verdict without the tool is a weaker point), C4 pass (answer is the
  right number, labelled unverified; calc unused), C5 pass.
