Verdict: PASS
# Verification report, Step 2: scripts and averages (Field 7 VWC)
Run date: Fri 23 Oct 2026 (America/Chicago). Scope: analyse_vwc.py, fetch_chirpstack.py, probe_averages.csv. The irrigation order (Step B) does not exist yet because Step 1 is NOT PULLED. It is not covered here.

## Real data
Real Field 7 data was NOT PULLED. The sandbox has no ChirpStack API access and no token. The recompute of real means is **NOT COVERED**, because there is nothing to recompute.
- Re-check run: `probe_averages.csv` has 12 rows. An awk check found 0 rows that are not "NOT PULLED" or that have a non-blank average ("rows 12 bad 0") [S45].
- The file's md5 is 9267465de076bfacc7b41b295e289287 [S44].
- No averages were invented. The IDs PROBE_ID_UNKNOWN_01..12 are placeholders, and Step 1 says so.
- The earlier synthetic rows (SYN_1, SYN_2) are not in the current CSV.

## Payload-key check
- `fetch_chirpstack.py` reads the token only from env `CHIRPSTACK_TOKEN`.
- The VWC key is configurable through `--key`, default `vwc`. The code matches `a.key` against the metric name or dataset label "as reported" [S30].
- I grepped for `* <number>`, `/ 100`, scale, factor and mul in `fetch_chirpstack.py`. There were no hits, so there is no unit conversion [S45].
- The script warns if a probe lacks the key.
- Not covered: `fetch_chirpstack.py` was never run against a live server. Its REST endpoint paths are untested, as its own docstring says [S28].

## SYNTHETIC test (labelled SYNTHETIC; file verify_synth/SYNTHETIC_readings.csv, 12 probes V01–V12)
I ran `analyse_vwc.py` on it. I then recomputed the means independently with a separate Python script using statistics.mean [S45]. Hand calculations are shown in the Expected column.

| Case | Expected (hand calc) | Actual | Pass/fail |
|---|---|---|---|
| V01: 24 × 20.0, boundary | mean 20.0, NOT flagged | 20.0, FALSE, OK [S44] | PASS |
| V02: 24 × 19.99 | mean 19.99, flagged | 19.99, TRUE [S44] | PASS |
| V03: no readings | n=0, blank avg, no invented number | n=0, coverage 0.0%, blank avg, blank flag, status LOW COVERAGE [S44] | PASS (see difference 1) |
| V04: 22 × 25.0 plus -5 and 140 | both bad values excluded and counted; mean 25.0 = 550/22; coverage 22/24 = 91.7% | n=22, coverage 91.7% (22/24), mean 25.0, FALSE; console "excluded out-of-range=2" [S44] | PASS (see difference 2) |
| V05: 12 × 25.0, 50% coverage | coverage 12/24 = 50.0%, LOW COVERAGE | 50.0, 25.0, LOW COVERAGE [S44] | PASS |
| V06: 24 × 30.0, normal | 30.0, not flagged | 30.0, FALSE [S44] | PASS |
| V07: 12 × 10.0 + 12 × 29.0 | mean (120+348)/24 = 19.5, flagged | 19.5, TRUE [S44] | PASS |
| V08: 4 blank values + 20 × 18.0 | blanks counted as missing; mean 18.0; coverage 20/24 = 83.3% | n=20, coverage 83.3%, mean 18.0; "missing/blank key=4" [S44] | PASS |
| V09: 24 × 0.0, lower bound | 0 is valid; mean 0.0, flagged | 0.0, TRUE [S44] | PASS |
| V10: 24 × 100.0, upper bound | 100 is valid; mean 100.0, not flagged | 100.0, FALSE [S44] | PASS |
| V11: 18 × 19.0 | coverage 18/24 = 75.0%, not low (threshold is below 75) | 75.0, OK [S44] | PASS |
| V12: 17 × 19.0 | coverage 17/24 = 70.8%, LOW COVERAGE | 70.8, LOW COVERAGE [S44] | PASS |
| Output has 12 rows | 12 | "12 rows" [S44] | PASS |
| Independent recompute vs script | all means within 0.1 pt | identical for V01–V12 except V03 (no data): V01 20.0, V02 19.99, V04 25.0, V05 25.0, V07 19.5, V08 18.0, V11 19.0, V12 19.0 [S45] | PASS |

## Differences from my own pre-computed result
1. **No-data probe status.** I expected NOT PULLED. The script prints LOW COVERAGE with blank values when readings.csv exists but a probe has no rows. NOT PULLED is used only when the file is missing. No number is invented, so no conclusion changes. The script's behaviour is acceptable.
2. **Coverage count.** I counted out-of-range readings toward coverage (V04 100%). The script excludes them (V04 22/24 = 91.7%). The script is the more defensible side, because an invalid reading is not usable coverage. No flag changes. My own LOW COVERAGE cut-off (50% or below) was also looser than the script's (below 75%). The script's 75% matches the Step 1 design, and the task only requires the 50% case to be flagged, so the script is right.
3. **Step 1 claim.** Step 1 said it could not confirm the exclusion count or the missing-key handling. I confirmed both by running the script (V04 and V08 lines above) [S44].

## Non-blocking defects (none changes a number or conclusion)
1. `analyse_vwc.py`: the out-of-range and missing counts go only to the console. Fix: add `n_excluded` and `n_missing` columns to probe_averages.csv so the count is auditable.
2. `analyse_vwc.py`: a probe with zero readings in a pulled run gets "LOW COVERAGE". Fix: use "NO DATA" or "NOT PULLED" for n=0 so the status is clearer.
3. `fetch_chirpstack.py`: untested against a live ChirpStack. Fix: verify the endpoint paths on site against the server's swagger page.

## Not covered by this work-around
- Real-data recompute, because no readings were pulled.
- The live fetch path (no ChirpStack API access, no token).
- Step B (irrigation order): no order exists and no probe-to-row mapping was supplied.

VERDICT: PASS
Defect list: no blocking defects. Advisory items 1–3 above.
BLOCKED: ChirpStack API access — real Field 7 24h readings could not be pulled, so the real-data recompute is not covered
BLOCKED: Probe-to-row mapping source — irrigation order (Step B) could not be checked because none exists
MISSING DATA: Real Field 7 probe readings — no token or network in the sandbox
MISSING DATA: Probe-to-row layout for Field 7 — not in workspace
Issues: none
