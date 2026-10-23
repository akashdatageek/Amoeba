I read "weekly retail on-highway diesel price for Indiana" as EIA weekly Midwest (PADD 2) retail diesel price, used as a proxy because EIA publishes no Indiana-only weekly series; if you meant EIA weekly Indiana-specific retail diesel price, if such a series exists or EIA weekly Midwest regional price, with Indianapolis or a nearby metro as a cross-check or EIA weekly US national average diesel price, as the fallback, the answer below may not apply.

# Final answer: fuel-surcharge schedule and 52-week fuel cost, 35 Class 8 tractors (as of 2026-10-23)

## Basis
- **Price series (R1):** EIA series EMD_EPD2D_PTE_R20_DPG, Weekly Midwest (PADD 2) No. 2 Diesel Retail Prices, in $/gal. The Midwest price is a proxy for Indiana. Series title and units are from the EIA dnav page, released 10/14/2026 and retrieved 2026-10-23 [S1].
- **Weeks covered:** 52 weekly releases, weeks ending 2025-10-27 to 2026-10-19. The data were pulled from the EIA API on 2026-10-23 [S3][S64]. Each week's price, with its week-ending date, series ID, source URL and retrieval date, is in `weekly_prices.csv` and on the Weekly sheet of the workbook. This answer does not repeat all 52 pairs.
- **Latest week:** $6.352/gal for the week ending 2026-10-19. FRED series GASDESMWW shows the same value for 2026-10-19, retrieved 2026-10-23 [S58].
- **Fleet basis:** 35 tractors × 2,300 miles per week = 80,500 miles. At 6.2 mpg that is 12,983.871 gallons per week, held constant every week (workbook check, 2026-10-23) [S74].
- **Surcharge:** ROUND((price − 1.25) ÷ 6.2, 2) per mile, applied to every loaded and empty mile (workbook check, 2026-10-23) [S75].
- **Band convention:** each 5-cent band is priced at its midpoint.

## Key results
| Item | Value | Source and date |
|---|---|---|
| Average price, 52 weeks | $4.787/gal (4.78738) | EIA PADD 2 weekly, weeks ending 2025-10-27 to 2026-10-19, retrieved 2026-10-23 [S94][S86] |
| Average surcharge | $0.57/mi (0.5708, mean of the rounded weekly values) | computed 2026-10-23 [S94] |
| Highest week | Week ending 2026-09-21: $6.68/gal, surcharge $0.88/mi, fleet cost $86,732.26 | EIA, retrieved 2026-10-23 [S1][S3]; fleet cost from the step 9 recompute, 2026-10-23 [S120] |
| Lowest week | Week ending 2026-01-12: $3.365/gal, surcharge $0.34/mi, fleet cost $43,690.73 | EIA, retrieved 2026-10-23 [S3]; fleet cost from the step 9 recompute, 2026-10-23 [S120] |
| Weekly surcharge range | $0.34 to $0.88/mi | computed 2026-10-23 [S94] |
| First week | Week ending 2025-10-27: $3.715/gal, surcharge $0.40, fleet cost $48,235.08 | workbook, 2026-10-23 [S74][S75] |
| Latest week | Week ending 2026-10-19: $6.352/gal, surcharge $0.82, fleet cost $82,473.55 | EIA, as of 2026-10-19 [S75][S58] |
| Total fleet fuel cost, 52 weeks | $3,232,256.77 | computed 2026-10-23 [S94][S92] |
| Average weekly fleet fuel cost | $62,158.78 | computed 2026-10-23 [S94] |
| Carrier average fuel cost per mile | $0.7722/mi (average price ÷ 6.2) | computed 2026-10-23 [S94] |
| ATRI total marginal cost per mile | $2.336/mi, cost data year 2025, up 3.4% on the prior year | ATRI, released 15 Jul 2026, retrieved 2026-10-23 [S46][S47] |
| ATRI cost per mile excluding fuel | $1.854/mi, cost data year 2025, up 4.2% | ATRI, released 15 Jul 2026 [S46] |
| ATRI fuel cost per mile | $0.482/mi, derived (2.336 − 1.854), not a published table value | ATRI, released 15 Jul 2026 [S46]; derivation by step 2, 2026-10-23 |
| ATRI fuel share of total | 20.6% (0.482 ÷ 2.336), derived, cost data year 2025 | computed 2026-10-23 [S94] |

**ATRI comparison (R3).** The carrier's $0.7722/mi is $0.2902/mi above ATRI's derived $0.482/mi. That gap is 60.2% of $0.482 (step 9 hand check, 2026-10-23) [S120]. The comparison is not like-for-like. ATRI is a national industry average on 2025 data, from a sample of 182,248 trucks and 14.67 billion miles (report released 15 Jul 2026) [S46]. The carrier figure uses Midwest prices for 2025-10-27 to 2026-10-19 at the task's 6.2 mpg.

**ATRI report details (R13).** The report is "An Analysis of the Operational Costs of Trucking", 2026 edition. It was released 15 Jul 2026, and its cost data year is 2025 [S35][S46][S47]. Its period (2025) and national scope differ from the carrier's 52 Midwest weeks.

**Surcharge schedule (R7).** The memo and the workbook Bands sheet give 40 bands from $3.00 to $5.00 in 5-cent steps (workbook, 2026-10-23). The $3.00–$3.05 band (midpoint 3.025) has a surcharge of $0.29. The $4.95–$5.00 band (midpoint 4.975) has a surcharge of $0.60 [S74][S95]. Prices above $5.00 fall outside the 40-band grid. The 52-week high was $6.68 and the latest week was $6.352 (EIA, as of 2026-10-19). The base formula still applies above $5.00. For example, $6.68 gives $0.88 [S92].

## Files delivered
- **`fuel_surcharge_workbook.xlsx`**: sheets Weekly, Inputs, Bands, Summary and Sources. A LibreOffice recalculation on 2026-10-23 found 387 formulas and 0 errors [S92]. Weekly has 52 data rows with live formulas. Inputs records the assumptions. Sources holds the ATRI figures, each with source and date.
- **`price_surcharge_chart.png`**: line chart of price and surcharge over the 52 weeks. It was not viewed after it was drawn (see Limitations).
- **`fuel_surcharge_memo.docx`**: the Word memo, **2 pages**, converted with soffice and counted with pypdf on 2026-10-23 [S111]. Its sections are bottom line, data and method, surcharge schedule, 52-week results, ATRI comparison, not obtained/substituted, and sources. The chart is not embedded in it. A PDF copy, `fuel_surcharge_memo.pdf`, was also made.
- **Supporting data file:** `weekly_prices.csv` holds the 52 week/price pairs for series EMD_EPD2D_PTE_R20_DPG (step 11, retrieved 2026-10-23) [S57][S64]. `raw_eia.txt` was also made in step 11. It is a text copy of the EIA pull.
- **Build and check scripts** (workspace): `build_core.py` (step 3, builds the Weekly, Inputs and Bands sheets), `add_summary.py` (step 4, adds Summary and Sources), `step5.py` (step 5, Decimal recompute and chart), `mk.py` and `parse.py` (step 11, build the CSV from the EIA pull), `verify7.py` (step 7, workbook check), `v9.py` and `v9b.py` (step 9, memo recompute), `memo.py` (step 8, builds the memo).
- **Saved tool output** (workspace): `tool_results/step1_1.txt` to `step1_6.txt`, `step2_1.txt` to `step2_5.txt`, `step3_2.txt` to `step3_5.txt`, `step4_1.txt` to `step4_3.txt`, `step5_1.txt`, `step5_2.txt`, `step6_1.txt`, `step6_2.txt`, `step6_3.txt`, `step6_7.txt` to `step6_9.txt`, `step7_1.txt` to `step7_4.txt`, `step7_6.txt` to `step7_10.txt`, `step8_5.txt`, `step9_1.txt`, `step9_3.txt`, `step9_6.txt` to `step9_9.txt`, `step11_1.txt` and `step11_5.txt`. They hold the raw fetch and check output behind the figures above.

## Verifier verdicts (all checks run 2026-10-23)
- **Step 6, data and ATRI verification: PASS.** The tool field accepts only PASS or FAIL, so "PASS WITH FIXES" was recorded as PASS. The CSV matched the EIA API pull with no mismatches [S86]. The fixes were labelling and citation only, and no number changed.
- **Step 7, workbook and chart verification: PASS** (recorded as "PASS WITH FIXES"). Its recompute found no mismatches in the 52 weekly rows and none in the 40 bands [S63][S104]. Open fixes:
  - The band-grid start and width are typed on the Bands sheet, not on Inputs.
  - The ATRI fuel figure must stay labelled as derived.
  - The chart was not viewed.
  - The memo must say that prices above $5.00 are outside the grid.
- **Step 9, memo verification: PASS** in the report, recorded as PASS WITH FIXES. The pipeline's automatic header flags it "DISPUTED". Some check comparisons (such as "price 1.25" and "count 19") do not match the report. The verifier's own hand checks match the figures above [S120]. The page count is 2 [S120]. The 40-band comparison output was cut off, so a full 40-of-40 match is not confirmed by this verifier. Open fixes:
  - Confirm that the memo labels $0.482 and 20.6% as derived.
  - Confirm that it states no newer-edition search was run.
  - The chart is not embedded in the memo.

## Files made
- tool_results/step1_2.txt (2,128 bytes, made in step 2; listed by plain code)
- tool_results/step1_3.txt (2,768 bytes, made in step 2; listed by plain code)
- tool_results/step1_4.txt (6,310 bytes, made in step 2; listed by plain code)
- tool_results/step1_5.txt (3,796 bytes, made in step 2; listed by plain code)
- tool_results/step2_2.txt (2,128 bytes, made in step 11; listed by plain code)
- tool_results/step2_3.txt (2,134 bytes, made in step 11; listed by plain code)
- tool_results/step2_4.txt (2,127 bytes, made in step 2; listed by plain code)
- tool_results/step3_3.txt (5,902 bytes, made in step 3; listed by plain code)
- tool_results/step3_4.txt (3,582 bytes, made in step 3; listed by plain code)
- tool_results/step4_2.txt (2,725 bytes, made in step 4; listed by plain code)
- tool_results/step6_8.txt (3,717 bytes, made in step 6; listed by plain code)
- tool_results/step7_2.txt (3,180 bytes, made in step 7; listed by plain code)
- tool_results/step7_3.txt (3,789 bytes, made in step 7; listed by plain code)
- tool_results/step7_7.txt (3,167 bytes, made in step 7; listed by plain code)
- tool_results/step7_8.txt (4,481 bytes, made in step 7; listed by plain code)
- tool_results/step7_9.txt (2,320 bytes, made in step 7; listed by plain code)
- tool_results/step9_7.txt (5,129 bytes, made in step 9; listed by plain code)
- tool_results/step9_8.txt (5,129 bytes, made in step 9; listed by plain code)

## Limitations
- **Proxy.** EIA publishes no Indiana-only weekly diesel series. The Midwest (PADD 2) price (EMD_EPD2D_PTE_R20_DPG) stands in for Indiana. Indiana prices may differ, so a surcharge built on Indiana prices may differ.
- **Step 1 was partial** and did not extract any prices. Step 11 supplied the 52 prices (retrieved 2026-10-23), and step 6 checked them against the saved EIA pull. The EIA dnav page copy was released 10/14/2026, so the API data were used [S1]. This answer does not list all 52 weekly prices. They are in `weekly_prices.csv` and the Weekly sheet.
- **ATRI fuel cost per mile was not found as a stated table value.** Step 2 read only the ATRI press release and summary page (report released 15 Jul 2026), not the full report PDF. The substitute is $2.336 − $1.854 = $0.482/mi, with a fuel share of 20.6%. Both are marked as derived [S46].
- **No search for a newer ATRI edition was run** (steps 2, 4, 6 and 8). The July 2026 edition is the newest one found. Nothing newer is confirmed to be absent.
- **ATRI period and scope mismatch.** ATRI covers cost data year 2025 and is a national industry sample. The carrier figure covers 52 Midwest weeks, 2025-10-27 to 2026-10-19, at the task's 6.2 mpg. The $0.2902/mi gap therefore mixes differences in period, region and basis.
- **Band convention.** Each 5-cent band is priced at its midpoint. The 40-band schedule stops at $5.00, while prices in the 52 weeks ran up to $6.68. Weekly surcharges use the exact price, so they can differ from the band value by a cent or so.
- **Assumptions.** Gallons per week are constant at 12,983.871. The surcharge applies to every loaded and empty mile. The average surcharge is the mean of the rounded weekly values.
- **Capabilities lacking.**
  - No live re-fetch of EIA or ATRI was possible, so checks used files saved on 2026-10-23 (steps 6, 7, 8 and 9).
  - No rendered view of the chart PNG or memo pages was possible (steps 7, 8 and 9). The chart and memo layout rest on script checks and the page count.
  - The FRED cross-check of the 2026-10-19 value rests on step 11 and was not re-read independently [S58].
- **Stale flags.** The pipeline flags steps 7 and 8 as built before step 6's rework. The checks above found no number changes.
- **Citation tags.** The pipeline flagged some tags as mislabelled, for example "0.482" and the report title against [S35]. These are labelling issues. The numbers match the ATRI figures in [S46].

## Sources and dates
- [S1] EIA dnav page for EMD_EPD2D_PTE_R20_DPG, released 10/14/2026, retrieved 2026-10-23.
- [S3], [S64] EIA API v2 pull for the same series, weeks ending 2025-10-27 to 2026-10-19, retrieved 2026-10-23.
- [S58] FRED series GASDESMWW, value for 2026-10-19, retrieved 2026-10-23.
- [S35], [S46], [S47] ATRI press release and summary page for the 2026 edition of "An Analysis of the Operational Costs of Trucking", released 15 Jul 2026 (cost data year 2025), retrieved 2026-10-23.
- [S57], [S74], [S75], [S86], [S92], [S94], [S95], [S104], [S111], [S120], [S63] Team files and check outputs (CSV, workbook, recompute scripts, page count), all made or run on 2026-10-23.
BLOCKED: network/live fetch — EIA and ATRI pages could not be re-fetched live in verification steps 6 to 9
BLOCKED: image inspection — chart PNG and memo pages were not viewed
MISSING DATA: ATRI fuel cost per mile as a stated table value — only press release and summary page read; derived as 2.336 − 1.854 = 0.482
MISSING DATA: Search for an ATRI edition newer than July 2026 — not run
MISSING DATA: Independent re-read of FRED GASDESMWW 2026-10-19 value — relied on step 11
MISSING INPUT: Confirmed 52 week/price pairs — step 1 delivered none (step 11 supplied them)
MISSING INPUT: Full 40-band memo table comparison output — step 9 output cut off

- NOT MET: R1 — Get the weekly retail on-highway diesel price for the 52 most recent weeks from EIA (Midwest PADD 2 proxy for Indiana). Cite the series and the week of each pri (the final answer does not cover it; checked by plain code on the final answer)
- NOT MET: R3 — Find the latest ATRI average marginal cost per mile (from its latest 'An Analysis of the Operational Costs of Trucking' report) and the share of it that is fuel (the final answer does not cover it; checked by plain code on the final answer)
- NOT MET: R6 — Deliver a Word memo of at most 2 pages. (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R8 — The memo gives the source and date of every figure. (the final answer does not cover it; checked by plain code on the final answer)
- NOT MET: R9 — State any figure that could not be obtained and what was used instead (including the Midwest-for-Indiana proxy). (the final answer does not cover it; checked by plain code on the final answer)
- NOT MET: R10 — The final answer opens with the mandated line, which reads 'weekly retail on-highway diesel price for Indiana' as the EIA weekly Midwest (PADD 2) price used as  (the final answer does not cover it; checked by plain code on the final answer)
- NOT MET: R11 — Independently verify the data, the spreadsheet formulas, the statistics, the ATRI figures, the citations and the deliverables (workbook, chart, memo) before the (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R13 — Report the ATRI report's title, release date and cost data year, and flag that its period and national scope differ from the carrier's 52 EIA weeks. (the final answer does not cover it; checked by plain code on the final answer)
- UNDATED: 52 [S63] — the source's date (publication or data period) is not stated (added by plain code)
- DISPUTED: price — step 7 gives 4.78738; the check in step 9, worked out independently, gives 1.25. Neither a source quote nor a re-run settled it (added by plain code)
- DISPUTED: cost excluding fuel — step 6 gives 4.2; the check in step 9, worked out independently, gives 1.854. Neither a source quote nor a re-run settled it (added by plain code)
- DISPUTED: count — step 6 gives 52; the check in step 9, worked out independently, gives 19. Neither a source quote nor a re-run settled it (added by plain code)

