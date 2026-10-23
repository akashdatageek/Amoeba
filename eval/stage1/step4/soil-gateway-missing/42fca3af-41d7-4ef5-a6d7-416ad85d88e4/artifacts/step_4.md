Verdict: PASS
# Verification report, step 4: irrigation order for Field 7 (checked Friday 23 October 2026, America/Chicago)

Scope: irrigation_order.docx and probe_row_map_used.csv from step 3, checked against probe_averages.csv. No real farm data exists. The data status is NOT PULLED and the probe-to-row map is MISSING. I therefore could not recompute real means or real flagged rows. I checked that nothing was invented and that the placeholder state is carried through correctly.

## Re-checks I ran
- Re-check 1 [S53]: I re-read both CSVs with python. probe_averages.csv has 12 rows, and every status is NOT PULLED. The list of non-blank avg_vwc_pct values is empty. probe_row_map_used.csv has 12 rows. Its only row_id value is "MAPPING REQUIRED", and no row has a value or a flag.
- Re-check 2 [S54]: I opened the docx with python-docx and counted strings across paragraphs and table cells.
  - "NOT SENT" appears 2 times, "DRAFT" 1, "NOT PULLED" 6, "Friday 23 October 2026" 1, "America/Chicago" 1, "UTC" 3, "TO BE CONFIRMED" 2, "MAPPING" 3.
  - A regex for numbers with units (L, mm, min, hours, gal, m3 and similar) returned an empty list.
  - The table has 2 rows: the header and one placeholder row.
  - The flagged-probe list is empty, and the probe IDs in the map match those in probe_averages.csv in the same order.
- Re-check 3 [S54]: `ls | grep -i -E "map|layout|location|row"` returned only probe_row_map_used.csv, which the planner made. No real layout file exists.
- Re-check 4 [S53]: the header paragraphs say "Data window (UTC): Intended: last 24 h, [pull time - 24 h, pull time] in UTC. NOT PULLED, so no actual UTC start/end exists." They also say "Delivery: NOT SENT - saved as a file only".
- Re-check 5, by calc: 0 flagged probes gives 0 rows. The order lists only the placeholder row, and that row is not a real row.

## Reconciliation table
| Check | Expected | Found | Pass/fail |
|---|---|---|---|
| Rows in the order equal the rows of the flagged probes | No flagged probes, so no real rows; only a placeholder | Flagged list is empty and the only row is "MAPPING REQUIRED", which is not a real row [S54] | PASS |
| Rows ordered driest first | Not applicable (no averages) | One placeholder row; the notes give the ranking rule for later (lowest flagged-probe mean per row, listed once) | PASS (N/A) |
| No invented volumes, durations, start times or rates | None | The unit-number regex found nothing. The Volume / Duration / Start time cell reads "TO BE CONFIRMED by farm manager" [S54] | PASS |
| No invented averages | All blank | Zero non-blank avg_vwc_pct in either CSV [S53] | PASS |
| DRAFT / NOT PULLED carried through | In banner, table and CSV | Banner "DRAFT - NOT ISSUED". The table shows "NOT PULLED (blank)". The CSV has blank averages and all 12 rows are "MAPPING REQUIRED" [S53][S54] | PASS |
| Data window stated | Last 24 h in UTC, with the run date | Intended window and "Friday 23 October 2026 (America/Chicago)" present. No actual start or end exists because nothing was pulled [S53][S54] | PASS |
| Marked not sent | NOT SENT | "NOT SENT" appears twice in the docx. The planner's own text says nothing was sent or posted | PASS |
| probe_row_map_used.csv matches probe_averages.csv | Same 12 IDs, same order, blank values | Match is True, 12 rows [S54] | PASS |
| Unflagged "no data" probes not flagged | None flagged | below_20 is blank for all rows | PASS |
| Sign-off and confirmation lines left blank | Present and blank | Prepared / Reviewed / Approved / Parameters-confirmed lines present for signature (per the step 3 description); I did not print each one | PASS (not individually re-read) |

## Differences from my own result (worked out before seeing the step outputs)
- I could not confirm the window/date line or the "NOT SENT" label earlier, because the docx text was cut off. Re-checks 2 and 4 now confirm both are present. Step 3 was right on this point.
- All other points agree: 0 flagged probes, one placeholder row, no invented numbers, 12 placeholder rows in the CSV.

## Observations (none changes a number or a conclusion)
- The placeholder row's Action cell begins "Irrigate". It is conditional ("only for rows of probes below 20 %, once data and mapping exist"). It could be misread by a skimming reader. Suggested fix in build_order.py: change the wording to "No irrigation action until data and mapping exist".
- The docx contains no real UTC window start or end. This is expected while the data is NOT PULLED.
- The step 3 claim that the step-2 PASS covers synthetic data only is consistent with the files in the workspace.
- The fetch script's REST paths are untested against a live server. This was stated in step 2 and carried into the order.

## Limits
- This PASS covers only the placeholder (NOT PULLED) state.
- No real order exists. Real means, flagged probes and rows are unverified because the token, network access, the Field 7 application ID and the probe-to-row map were all absent.
- A new verification is needed once the farm supplies them.

VERDICT: PASS

Defects: none that change a number or a conclusion. The wording suggestion above is minor and optional.
BLOCKED: ChirpStack API access — real 24 h readings and real probe-to-row mapping do not exist, so real means and flagged rows could not be recomputed
MISSING DATA: Real Field 7 24 h VWC averages — probe_averages.csv (all NOT PULLED)
MISSING DATA: Probe-to-row mapping — workspace search for map/layout/location/row files found only the planner's own probe_row_map_used.csv
Issues: none
