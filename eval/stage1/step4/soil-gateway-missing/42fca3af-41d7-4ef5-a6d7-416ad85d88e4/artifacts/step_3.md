# Irrigation Order - Field 7: DRAFT - NOT ISSUED (NOT SENT, saved as a file only)

Files saved in the workspace: irrigation_order.docx and probe_row_map_used.csv. Neither file was sent or posted anywhere.

## Banner in the document
The soil-moisture data for Field 7 was NOT PULLED, and the probe-to-row mapping is MISSING. No probe has an average VWC, so no row can be named for irrigation. The order was NOT SENT.

## Header block in the document
- Field: Field 7.
- Prepared: Friday 23 October 2026 (America/Chicago).
- Data window (UTC): intended as the last 24 h, [pull time - 24 h, pull time]. Nothing was pulled, so there is no actual UTC start or end.
- Data source: ChirpStack v4 at 10.20.0.5, Field 7 application or device group. VWC % is taken as reported in the probe payload, with no conversion.
- Data status: NOT PULLED. Step 1 had no API token and no network [S46]. The step-2 verdict is PASS, but it covers the scripts on synthetic data only, not farm data.
- Mapping status: MISSING. No probe-to-row layout or probe-location list was found in the workspace. I checked with `ls | grep -i -E "map|layout|location|row"`, which returned no matches [S46].
- Threshold: a probe is flagged when its strictly below 20.0 % h mean VWC is strictly below 20.0 %.
- Delivery: NOT SENT.

## Table in the document
The table has 2 rows: the header and one placeholder row [S47].

| Priority | Row | Probes | Avg VWC % | Action | Volume / Duration / Start time |
|---|---|---|---|---|---|
| - | MAPPING REQUIRED | None identified. 12 probes, all NOT PULLED. The IDs PROBE_ID_UNKNOWN_01 to _12 are placeholders, not real probe IDs. | NOT PULLED (blank) | Irrigate, but only for the rows of probes below 20 %, once data and mapping exist | TO BE CONFIRMED by farm manager |

## Notes in the document
- No volumes, durations, start times or application rates are given. They are TO BE CONFIRMED by the farm manager from farm-supplied parameters.
- Once real averages exist:
  - Take the probes with below_20 TRUE and map each to its row.
  - List each row once, driest first, ranked by the lowest average VWC among that row's flagged probes. The farm manager should confirm how a row with several flagged probes is ranked.
  - Unmapped probes stay under the row "MAPPING REQUIRED".
- LOW COVERAGE: a probe with fewer than 75 % of its 24 expected hourly readings is marked LOW COVERAGE by the analysis script. Its average is less reliable and must be checked before it drives an irrigation decision. A probe with no data has no average and is not flagged. At present all 12 probes are NOT PULLED.
- Missing inputs:
  - CHIRPSTACK_TOKEN.
  - The Field 7 application or device-group ID, and the REST port (the script default is 8090).
  - Confirmation that the payload key is `vwc`.
  - The probe-to-row layout.
  - The real probe IDs and device count.
- To complete on site: export the token, run fetch_chirpstack.py and then analyse_vwc.py, add a probe_id,row_id mapping file, and re-issue the order.
- The fetch script's REST paths are untested against the live server (step 2).
- Sign-off lines: Prepared by (Irrigation Planner); Reviewed by (Farm manager); Approved to issue (Farm manager); Parameters confirmed (volume / duration / start time). All are left blank for signature and date.

## probe_row_map_used.csv
- Columns: probe_id,row_id,avg_vwc_pct,below_20.
- It has 12 data rows plus the header. The `wc -l` count shows 13 lines [S47].
- Every row has row_id "MAPPING REQUIRED" and blank avg_vwc_pct and below_20. Example: `PROBE_ID_UNKNOWN_01,MAPPING REQUIRED,,` [S47].

## Status
The order is only a DRAFT because the data and mapping are missing. No flagged probes or rows could be listed, and no figures or rates were invented.
BLOCKED: ChirpStack API access — no token and no network, so the 24 h Field 7 readings were not available to build a real order
BLOCKED: Probe-to-row mapping source — no farm layout or probe-location list was supplied, so probes could not be assigned to rows
MISSING DATA: Real 24 h VWC averages for the 12 Field 7 probes — probe_averages.csv (all NOT PULLED)
MISSING DATA: Probe-to-row mapping (probe_id,row_id) — workspace search for map/layout/location/row files
MISSING DATA: Farm-supplied irrigation volume/duration/start-time parameters — not in task or workspace
MISSING INPUT: Real probe averages and flagged-probe list — step 1 (NOT PULLED)
MISSING INPUT: Probe-to-row mapping — step 1 (not supplied)
