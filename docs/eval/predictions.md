# Predictions, written before the runs

Each prediction is committed and pushed before the runs it is about, so it cannot be fitted to the results. The
report for those rounds says whether it held.

## Rounds 3b and 4 — written 2026-09-26, before any run of either round

**Setup.** Both rounds use current main (D61 merged, `ab107d1`) and the same ten tasks (`tasks/observer_round1.jsonl`,
rubric `eval/round1/rubrics.yaml`, unchanged). They also share round 1's Box 2 drafts, `--pool on --local-tools on`,
Gemma 4 31B, 3 repeats per task and a $5 guard per round. The only difference is the flag:
- **3b:** `--step-contract off`. It isolates the local-tools fixes: P14 (local candidates no longer crowd out better
  internet ones), P17 (fenced commands) and G7 (local results are sources).
- **4:** `--step-contract on`.

Baseline, round 3 (one run per task, C1–C5 36/50): C1 7, C2 10, C3 7, C4 5, C5 7, C6 6/10.

### Main prediction: round 4 against 3b
**C3 (honest) and C5 (gaps reported) rise first with the step contract.** The contract acts on step status and on the
Limitations section, and those are what C3 and C5 score. The checks that depend on other things should not move:
- C1 and C2 are fixed by the reused drafts.
- C4 depends on what the tools can reach.
- C6 depends on the toolbox step.

In numbers (sum over the ten tasks, each task's mean over its 3 repeats):
- C5 rises by at least 1.5 (of 10). The contract appends every undeclared missing capability and every unused
  attached item to Limitations. Expected to gain: fx-email (email sender), route (routing tool), code-run and weather.
- C3 rises by at least 1 (of 10). A step that ran without its capability can no longer end "done" silently, and a
  helper that invents data now gets a refine turn telling it to mark BLOCKED instead. Expected to gain: route
  (distances from memory), deck (invented brand).
- C1 and C2 stay equal: identical drafts.
- C4 moves by less than 1 either way. A `partial` status does not remove useful content. The G5 answer check may add
  back a figure or file left out (xlsx totals) and so help slightly.
- C6 is equal or up by at most 1. The G2 refine turn may make a helper call a tool it was given (deck: pptx), but
  C6 is mostly decided before the step.
- Cost: the contract adds 10–30 % more model calls per run (the refine turns plus longer prompts). No run hits the
  400,000-token or 150-call cap.

The prediction **holds** if C3 and C5 together rise by at least 2 (of 20) from 3b to round 4, C5 rises more than any
check except C3, and no other check falls by more than 1. It **fails** if C3+C5 rise by less than 1, or C4 falls by
more than 1 (the contract made answers worse).

### Secondary prediction: 3b against round 3 (the local-tools fixes alone)
- C4 recovers by about 1–2. Round 3 lost the live weather forecast and the FX rate to weak local candidates (P14);
  with P14 fixed the internet servers should be shown again.
- C3 rises by up to 1. Code-run's executed result is now a real source [S#] instead of a made-up citation (G7).
- C5 and C6 stay within ±1 of round 3. Sampling noise alone can move a single run by one check; the 3 repeats and
  the range are there to show that.

### What would surprise me
- The contract marking many steps `partial` whose output was in fact complete. That would be a NOT NEEDED line the
  helper failed to write, or a role-wide tool the step never needed.
- NOT NEEDED used evasively: the step writes "NOT NEEDED: route_engine" but its output still contains distances that
  only that tool could have supplied. Each such line is judged in the round 4 report.
