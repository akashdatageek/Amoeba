Verdict: PASS
# Verification report, Step A (scripts and averages)

**Scope:** This covers Step A only: fetch_chirpstack.py, analyse_vwc.py and probe_averages.csv. Step B (the irrigation order) is not part of this step. No order can exist, because Step 1 reported NOT PULLED and gave no probe-to-row mapping.

## 1. Payload-key check (VWC, no conversion)
- **Docstring.** The fetch script says VWC is "decoded payload key as reported (default 'vwc'); no conversion from raw counts" [S28]. The key is set with `--key`, shown in the usage line [S28].
- **Code.** The key is matched with `if a.key in (name, met.get("name"), ds.get("label"))`. Rows are then appended as `(eui, t, "" if v is None else v)` [S30]. The value goes through unchanged: no scale factor and no division. A device without the key is collected in `nokey` and produces a WARNING [S30].
- **Token.** `tok = os.environ.get("CHIRPSTACK_TOKEN")` reads the token from the environment, and the script exits if it is unset [S31]. The token is not hard-coded.
- **analyse_vwc.py.** It uses the value as reported. Values outside 0-100 are excluded and counted, and below_20 is strict (mean < 20.0) [S30].
- **Result: PASS.** I also ran a grep for scale, factor, `*N`, `/100` and `/1000` in fetch_chirpstack.py [S41]. That part of the output was truncated in my view, so my "no conversion" conclusion rests on the code excerpts above.

## 2. SYNTHETIC test (not farm data)
I wrote `verify_synth/SYNTHETIC_readings.csv` with 12 probes, V01 to V12. I ran `analyse_vwc.py` on it and got `verify_synth/SYNTHETIC_out.csv` [S41]. Expected values are hand-calculated.

| # | Case | Expected (hand/calc) | Actual [S41] | Pass/fail |
|---|---|---|---|---|
| 1 | V01: 24 x 20.0, exactly on the boundary | mean 20.0, below_20 FALSE (strict <) | 24, 100.0%, 20.0, FALSE, OK | PASS |
| 2 | V02: 24 x 19.99 | mean 19.99, below_20 TRUE | 24, 100.0%, 19.99, TRUE, OK | PASS |
| 3 | V03: no readings | n=0, coverage 0.0%, blank average (none invented), not flagged | 0, 0.0%, blank, blank, status "LOW COVERAGE" | PASS on the numbers; label is an advisory (see Defects) |
| 4 | V04: 22 x 25.0 plus -5 and 140 | the 2 out-of-range values are excluded and counted; mean (22*25.0)/22 = 25 (calc); n=22, coverage 22/24 = 91.7% | stdout "V04: excluded out-of-range=2"; 22, 91.7%, 25.0, FALSE, OK | PASS |
| 5 | V05: 12 x 25.0, 50% coverage | coverage 50.0%, LOW COVERAGE (under 75%), mean 25.0, not flagged | 12, 50.0%, 25.0, FALSE, LOW COVERAGE | PASS |
| 6 | 12 probes in total | 12 rows | "12 rows" and V01 to V12 listed | PASS |
| 7 | V06-V12: normal, 24 x 30.0 | 30.0, FALSE, OK | all rows 24, 100.0%, 30.0, FALSE, OK | PASS |
| 8 | No readings file (NOT PULLED path) | 12 rows, all NOT PULLED, blank averages | "12 rows; pulled=False", placeholder rows PROBE_ID_UNK… [S41] | PASS |
| 9 | Step 1's own synthetic run (SYN_1 15.0, SYN_2 25.0, SYN_3 19.9 with 10/24) | 15.0 TRUE; 25.0 FALSE; SYN_3 coverage 10/24 = 41.7% | matches [S31] | PASS |

## 3. Real data and independent recompute
- No real ChirpStack data exists: Step 1 had no token and no network, and its status is NOT PULLED [S31]. No means can be recomputed against the real CSV. The success criterion allows this.
- I confirmed that no averages were invented in the NOT PULLED output. Step 1's probe_averages.csv has 12 placeholder rows PROBE_ID_UNKNOWN_01 to _12. All are NOT PULLED, with blank n_readings, coverage, avg_vwc_pct and below_20 [S31]. My own no-readings run produced the same pattern [S41].
- The truncated part of my last run output included `head -3 probe_averages.csv`. I could not see it, so I rely on [S31] and [S34] for the contents of the final file.
- For the synthetic data I recomputed independently: V04 gives (22*25.0)/22 = 25 and 22/24 = 91.7% (calc). Both match the script.

## 4. Where my pre-computed expectation differed from the outputs
- **V04 coverage.** My own expectation said 100% coverage for 22 valid readings out of 24 expected. That was inconsistent, because 22/24 = 91.7%. The script (91.7%) is right.
- **Out-of-range readings and coverage.** My expectation counted out-of-range readings as received. The script excludes them from both the mean and n_readings. Both approaches give the same mean here. The script's behaviour is acceptable and is documented in its docstring [S30].
- **No-data status.** I expected NOT PULLED for a probe with no readings. The script prints LOW COVERAGE for that probe in a run where other probes did have data. This changes no number and no flag.

## 5. Defects and advisories (none changes a number or conclusion)
1. **analyse_vwc.py.** A probe with 0 readings in a pulled dataset gets status LOW COVERAGE (V03). Fix: write "NO DATA" or "NOT PULLED" for n=0 so it is not confused with partial coverage.
2. **analyse_vwc.py.** The out-of-range exclusion count goes only to stdout ("V04: excluded out-of-range=2"). It is not a CSV column. Fix: add an `n_excluded` column so the count travels with the file.
3. **run_status.md.** It says "No synthetic test was run" [S31], but a synthetic run exists in synthetic_test/ [S31]. Fix: update the Testing line.
4. **Step 1 memo.** It says synthetic test probes were only SYN_1 and SYN_2. The synthetic files also contain SYN_3 (19.9, 10/24, LOW COVERAGE) [S31]. It also says it could not confirm the exclusion count or missing-key handling; my run confirms the exclusion count (stdout), and the code shows the missing-key warning [S30].
5. **fetch_chirpstack.py.** The REST endpoint paths are untested against a live server, as the docstring states [S28]. This cannot be checked without access. It must be validated on site against the server's /api swagger page.

## VERDICT: PASS
The scripts handle every edge case correctly: 20.0 not flagged, 19.99 flagged, a missing probe, out-of-range values excluded and counted, 50% coverage, and 12 rows. The payload key is configurable with no conversion. The NOT PULLED output contains no invented averages. This PASS covers scripts and synthetic behaviour only. No real farm means exist to verify, and the live fetch and the irrigation order are unverified.
BLOCKED: ChirpStack API access — real 24h readings could not be pulled or independently recomputed (no token, no network)
MISSING DATA: Real Field 7 probe readings — not available in workspace or sandbox
MISSING DATA: Full output of grep for scale/factor in fetch_chirpstack.py and head of probe_averages.csv — truncated in my last tool result (tool_results/step2_6.txt)
Issues: none
