Verdict: FAIL
I read "weekly retail on-highway diesel price for Indiana" as EIA weekly retail on-highway diesel prices, all types, for the state of Indiana (if EIA publishes a state series); if you meant EIA Midwest (PADD 2) regional weekly diesel price used as a stand-in for Indiana or EIA U.S. national average weekly diesel price, the answer below may not apply.

# Verification memo: data, workbook and chart (step 5), as of 2026-10-16

## Verdict: FAIL
Two defects change the numbers and the conclusions.
1. The 52-week window is stale. It ends 2026-09-21, but EIA's latest data point is 2026-10-12.
2. The ATRI total, fuel cost per mile and fuel share are missing, so the required ATRI comparison does not exist.

The arithmetic that was built is sound. The problem is the window and the missing ATRI figures. Step 6 (memo) must not run until these are fixed.

## Checks run
| # | Check | Result |
|---|---|---|
| 1 | Raw CSV (eia_weekly.csv) has 52 distinct weekly rows | PASS. 52 rows, 2025-09-29 to 2026-09-21 [S66]. |
| 2 | Dates are consecutive Mondays with no gaps | PASS. "mondays True gaps []" [S66]. |
| 3 | CSV prices match the saved EIA series page S4 | PASS. "csv vs S4 mismatches []" [S66]. |
| 4 | Re-check of 4 EIA prices against the saved EIA page (first, last, two others). This is the saved fetch, not a live re-fetch, because there is no network. | PASS. 2025-09-29 = 3.731, 2026-01-12 = 3.365, 2026-03-09 = 4.801, 2026-09-21 = 6.680 [S66]. Each matches the S4 table [S29][S30]. |
| 5 | Is 2026-09-21 the latest EIA week? | FAIL. The EIA workbook S6 says "Latest Data for 10/12/2026, Release Date: 10/14/2026, Next Release Date: 10/20/2026" [S70][S29]. The saved page S4 is the older 9/22/2026 release [S30]. Mondays 2026-09-28, 10-05 and 10-12 are missing from the CSV, workbook and chart. FRED shows 6.286 for 2026-10-05 [S54]. |
| 6 | Workbook inputs | PASS. Trucks 35, MilesPerTruckWeek 2300, MPG 6.2, Base 1.25, WeeklyMiles 80500, WeeklyGallons 12983.87 (= 80,500 ÷ 6.2) [S70]. |
| 7 | Formulas are live and reference Inputs | PASS. Weekly C2 = `=ROUND((B-Base)/MPG,2)`. Gallons = `=WeeklyGallons`. Cost = `=D*B`. Bands B2 references Base. Row 54 holds live total and average formulas [S49][S48]. |
| 8 | 52-week reconciliation: workbook cached values vs my Decimal ROUND_HALF_UP recompute (surcharge, price, cost to $0.01) | NOT FULLY CONFIRMED BY ME. My script ran (S69), but its "mismatch" line was cut off in the output I could read. Step 3 reports 0 mismatches over 52 weeks and 41 bands, with total $3,091,355.81 [S49]. The worked examples I checked by hand agree: (6.680 − 1.25) ÷ 6.2 = 0.8758, which rounds to $0.88, the chart maximum [S52]. (3.365 − 1.25) ÷ 6.2 = 0.3411, which rounds to $0.34, the chart minimum [S52]. Even if this check passes, it covers the wrong window (see check 5). |
| 9 | Summary average, high and low | The values are internally consistent, but they are for the stale window. Average price $4.5787, average surcharge $0.5371, high $6.680 on 2026-09-21, low $3.365 on 2026-01-12 [S70]. They will change when the window moves. |
| 10 | Bands: 41 rows from $3.00 to $5.00 in 5-cent steps | PASS on structure. (5.00 − 3.00) ÷ 0.05 + 1 = 41. B2 ($3.00) = 0.28 (1.75 ÷ 6.2 = 0.2823). B42 ($5.00) = 0.60 (3.75 ÷ 6.2 = 0.6048) [S49]. The Bands sheet also has extra reference rows above $5.00 (floors 5.25 to 7.00). These are a workbook-only modelling choice and must be labelled as such in the memo. |
| 11 | PNG chart | PARTIAL. 2100 x 1350 px, 52 weekly points, dual axis, series named, PADD 2 stand-in flagged in the source note [S61][S52]. I did not view the image myself. It is stale: it ends 2026-09-21 and must be redrawn for the corrected window. |
| 12 | Indiana series and stand-in flag | Stand-in justified, but not fully proven. The EIA page's area list shows U.S., PADD regions, California, Colorado, Florida, Massachusetts, Minnesota, New York, Ohio, Texas, Washington and 10 cities. Indiana is not listed [S26]. The Midwest (PADD 2) series is flagged as a stand-in everywhere I looked [S52][S49]. The series page links to "Retail Prices for Diesel (On-Highway) - All Types" [S30], which supports treating it as the all-types series. |
| 13 | ATRI total, fuel and share re-confirmed at source | FAIL. Step 2 never obtained these. The excerpt is cut off at "the overall industry average reached $2." [S43]. Only the truckload-sector figure of $2.21 for 2025 is visible, and it must not be used as the total [S43]. The edition is the ATRI 2026 Update, July 2026 per the URL [S37]. I could not re-confirm any ATRI figure, because it never reached the workbook (the ATRI Summary cells read "not available" [S70]). |
| 14 | Memo | Not yet produced, so not checked (all-41-band table, source and date on every figure, ≤2 pages). |

## Defects and required fixes
1. **Step 1 and step 3 (data and workbook): stale 52-week window. This changes every aggregate.** The series ends 2026-09-21, but EIA's latest week is 2026-10-12 [S70]. Fix:
   - Re-parse the EIA workbook (hist_xls/EMD_EPD2D_PTE_R20_DPGw.xls, release 10/14/2026) [S6], or re-fetch the LeafHandler page, which now carries the 10/14 release.
   - Take the 52 latest Mondays, 2025-10-06 to 2026-10-12.
   - Check that the dates are 7 days apart, with no duplicates.
   - Rebuild eia_weekly.csv and the workbook, recalculate in LibreOffice, and check that the cached values exist.
   - Update the Summary average, high, low and total.
   - State "latest week 2026-10-12, EIA release 2026-10-14, as of 2026-10-16".
   - If the 10/12 value turns out not to be in the saved files, say so plainly rather than estimating. The FRED value of 6.286 for 2026-10-05 [S54] is a cross-check only, not the primary series.
2. **Step 4 (chart): redraw.** Re-run chart.py on the corrected CSV so that it covers 2025-10-06 to 2026-10-12. Update the title, date range and axis ranges. Keep the PADD 2 stand-in note and the 1200 px or wider size.
3. **Step 2 (ATRI): missing total, fuel and share.** Fetch the full ATRI 2026 Update (truckingresearch.org, July 2026) [S37]. Read the total marginal cost per mile (the overall industry average, which the excerpt cut off at "$2.") and the fuel cost per mile from the same report. Record the edition, release date, data year, and ATRI's diesel price and mpg basis. Compute share = fuel ÷ total. Enter ATRI_Total and ATRI_Fuel on the Inputs sheet so the Summary comparison activates. Compare the carrier's average fuel cost per mile over the corrected 52 weeks (average price ÷ 6.2) with ATRI's fuel cost per mile. The ATRI share of total is context only. If the figures truly cannot be obtained, the memo must state that ATRI is unavailable and what was used instead. Do not use $2.21 as the total [S43].
4. **Step 3 (workbook), minor.** Label the Bands rows above $5.00 as "workbook-only reference" and make sure the memo's 41-band table covers only $3.00 to $5.00. Update the Summary note on the last week ("Latest week available in saved EIA page") once the window is corrected.
5. **Step 1 (documentation), minor.** Record the EIA release date for the new window (10/14/2026 [S6]) and the retrieval date. Add the Indiana-not-listed evidence ([S26], area list from S1) to the sources.

## What I could not confirm
- The cell-by-cell workbook vs recompute mismatch count, because the output line was cut off. Step 3's own check reports none [S49].
- Any ATRI figure.
- The EIA prices for 2026-09-28, 10-05 and 10-12.
- A live re-fetch of EIA. The re-checks used the saved fetched pages, because there is no network in this step.
- A visual check of the PNG.
- The memo, which does not exist yet.
BLOCKED: Network access / live re-fetch — EIA and ATRI figures could only be re-checked against the pages already saved, not re-fetched live
MISSING DATA: ATRI 2026 Update total marginal cost per mile, fuel cost per mile and fuel share — truncated in saved S37/S43; no source re-fetch possible in this step
MISSING DATA: EIA Midwest diesel prices for 2026-09-28, 2026-10-05, 2026-10-12 — not in the saved files except FRED 6.286 for 10-05 [S54]
MISSING DATA: Cell-by-cell workbook vs recompute mismatch count — the output line was cut off
MISSING DATA: Visual inspection of the PNG — not done
MISSING INPUT: ATRI total, fuel and share — step 2 did not deliver them
MISSING INPUT: Memo document — not yet produced, so not verified
Issues:
1. Step 1/3 (data, workbook): 52-week window is stale. It ends 2026-09-21, but EIA's latest data is 2026-10-12 (released 2026-10-14) [S70]. Fix: re-parse EIA xls/page to take 2025-10-06 to 2026-10-12, rebuild CSV and workbook, recalculate; the average, high, low and total will change.
2. Step 4 (chart): the PNG ends 2026-09-21 and is stale. Fix: redraw from the corrected CSV (2025-10-06 to 2026-10-12), update the title and axes, keep the PADD 2 stand-in note.
3. Step 2 (ATRI): total marginal cost per mile, fuel cost per mile and fuel share were not obtained; the excerpt is cut off at '$2.' [S43]. Fix: read the full ATRI 2026 Update [S37], get total and fuel from the same report with edition and date, compute the share, and enter ATRI_Total and ATRI_Fuel on Inputs so the comparison with the carrier's fuel cost per mile works. If it is truly unavailable, the memo must say so.
4. Step 3 (workbook), minor: label the Bands rows above $5.00 as workbook-only reference rows, and update the Summary last-week note after the window correction.
5. Step 1 (documentation), minor: record the EIA release date (10/14/2026) and retrieval date, and cite the area list showing no Indiana series [S26].
