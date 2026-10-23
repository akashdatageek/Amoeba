I read "weekly retail on-highway diesel price for Indiana" as EIA weekly Midwest (PADD 2) retail diesel price, used as a proxy because EIA publishes no Indiana-only weekly series; if you meant EIA weekly Indiana-specific retail diesel price, if such a series exists or EIA weekly Midwest regional price, with Indianapolis or a nearby metro as a cross-check or EIA weekly US national average diesel price, as the fallback, the answer below may not apply.

Step 4 result: I added the Summary and Sources sheets to fuel_surcharge_workbook.xlsx. Sheet order is Weekly, Inputs, Bands, Summary, Sources. LibreOffice recalculation found 387 formulas and 0 errors [S92].

Fix made after the plain-code check: the typed ATRI numbers (2.336 and 1.854) now sit on Sources!B21 and B22 (yellow cells, blue font, each with source and date). Summary!B15 is =Sources!B21 and Summary!B16 is =Sources!B22, so no Summary cell holds a typed number. Recalculation confirmed this [S92].

Table: Summary sheet map (metric | formula | cell | value after recalculation)

| Metric | Formula | Cell | Value |
|---|---|---|---|
| Average price ($/gal) | =AVERAGE(Weekly!$B$2:$B$53) | Summary!B4 | 4.787 |
| Average surcharge ($/mi) | =AVERAGE(Weekly!$C$2:$C$53) | B5 | 0.5708 |
| Highest price ($/gal) | =MAX(Weekly!$B$2:$B$53) | B6 | 6.680 |
| Highest week (week ending) | =INDEX(Weekly!A, MATCH(B6, Weekly!B, 0)) | B7 | 2026-09-21 |
| Surcharge in highest week ($/mi) | =INDEX(Weekly!C, MATCH(B6, Weekly!B, 0)) | B8 | 0.88 |
| Lowest price ($/gal) | =MIN(Weekly!$B$2:$B$53) | B9 | 3.365 |
| Lowest week (week ending) | =INDEX(Weekly!A, MATCH(B9, Weekly!B, 0)) | B10 | 2026-01-12 |
| Surcharge in lowest week ($/mi) | =INDEX(Weekly!C, MATCH(B9, Weekly!B, 0)) | B11 | 0.34 |
| 52-week total fleet fuel cost ($) | =SUM(Weekly!$E$2:$E$53) | B12 | 3,232,256.77 |
| Average weekly fleet fuel cost ($) | =AVERAGE(Weekly!$E$2:$E$53) | B13 | 62,158.78 |
| Carrier average fuel cost per mile ($/mi) | =AVERAGE(Weekly!$F$2:$F$53) | B14 | 0.7722 |
| ATRI total marginal cost per mile ($/mi) | =Sources!B21 (typed 2.336 on Sources) | B15 | 2.336 |
| ATRI cost per mile excluding fuel ($/mi) | =Sources!B22 (typed 1.854 on Sources) | B16 | 1.854 |
| ATRI fuel cost per mile ($/mi), SUBSTITUTE (orange) | =B15-B16 | B17 | 0.482 |
| ATRI fuel share of total marginal cost | =B17/B15 | B18 | 20.6% (0.482 ÷ 2.336) |
| Gap: carrier minus ATRI fuel per mile ($/mi) | =B14-B17 | B19 | 0.2902 |
| Gap as % of ATRI fuel per mile | =B19/B17 | B20 | 60.2% (0.2902 ÷ 0.482) |

Each row also carries a source and "as of" note in columns C and D. The ATRI inputs read: "ATRI, An Analysis of the Operational Costs of Trucking (2026 ed.), cost data year 2025; released 2026-07-15; retrieved 2026-10-23" [S46]. A legend in Summary!A22 explains the colours: yellow = typed input on Sources, orange = substitute.

Independent Decimal check: average price 4.78738, total fleet fuel cost $3,232,256.77, average fuel $/mi 0.77216, highest 6.68, lowest 3.365. These match the workbook [S91][S92].

Sources sheet (Item | Detail | Retrieved or as of), cells A3:C18, plus the ATRI input block in A20:C22:
- Proxy statement: EIA publishes no Indiana-only weekly series; Midwest (PADD 2) is used as a proxy, an assumption.
- EIA series ID: EMD_EPD2D_PTE_R20_DPG, Weekly Midwest No. 2 Diesel Retail Prices, $/gal [S1]. Retrieved 2026-10-23.
- EIA page URL: https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=emd_epd2d_pte_r20_dpg&f=W [S1]. The EIA API v2 URL is in Weekly!I1 [S64].
- Price period: 52 weeks, weeks ending 2025-10-27 to 2026-10-19. The latest week, as of 2026-10-19, is 6.352 $/gal, and FRED shows the same value [S58]. Retrieved 2026-10-23.
- ATRI report: "An Analysis of the Operational Costs of Trucking", 2026 edition. Press headline: "New ATRI Report Details Accelerating Costs and Low Profitability Despite Cuts". URL: https://truckingresearch.org/2026/07/new-atri-report-details-accelerating-costs-and-low-profitability-despite-cuts [S35][S46].
- ATRI release date: 2026-07-15. The page dateline reads "Wednesday, July 15, 2026" [S47].
- ATRI cost data year: 2025. The sample is 182,248 trucks and 14.67 billion miles [S46].
- ATRI figures used: total marginal cost 2.336 $/mi (+3.4%); cost excluding fuel 1.854 $/mi (+4.2%) [S46].
- ATRI SUBSTITUTE, marked in orange: ATRI's fuel cost per mile as a stated table value was NOT FOUND. I read only the press release and summary page, not the full PDF. Substitute: 2.336 − 1.854 = 0.482 $/mi, a fuel share of 0.482 ÷ 2.336 = 20.6%.
- ATRI scope caveat: this is an industry-wide, miles-weighted average from 2025 data, not specific to Indiana or to a 6.2 mpg Class 8 fleet. The carrier figure uses 2025–26 prices at 6.2 mpg, so year and basis differ.
- Newer ATRI edition: none seen in a search run this step, as of 2026-10-23; only search snippets were checked [S34][S35][S36]. The 2026 edition (July 2026) is used.
- Carrier parameters and surcharge method: base 1.25 $/gal, 6.2 mpg, 35 tractors and 2,300 miles per tractor per week come from the task. The surcharge is ROUND((price − 1.25) ÷ 6.2, 2) on every mile.

Findings for later steps:
- The carrier's 52-week average fuel cost is 0.772 $/mi, against ATRI's derived 0.482 $/mi for 2025. The gap is +0.290 $/mi, or 60.2% of the ATRI figure (0.2902 ÷ 0.482). The main reason is that Midwest diesel over the past 52 weeks is much higher than in ATRI's 2025 data year. This is not a like-for-like comparison.
- Highest week: 2026-09-21 at $6.68. Lowest week: 2026-01-12 at $3.365.
- Prices from about $5.00 to $6.68 lie above the $3.00–$5.00 band grid. The memo should say the 40-band schedule does not cover the current range. The base formula still applies above $5.00; for example, 6.68 gives a surcharge of 0.88.

Files: fuel_surcharge_workbook.xlsx (updated). The chart, memo and stats tables are not part of this step.
MISSING DATA: ATRI fuel cost per mile as a stated table value — looked in ATRI press release and summary page (S35, S46); substituted 2.336 − 1.854 = 0.482 and marked it on Summary and Sources
MISSING DATA: Confirmation that no ATRI edition newer than July 2026 exists — only search snippets checked, no dedicated ATRI site check
