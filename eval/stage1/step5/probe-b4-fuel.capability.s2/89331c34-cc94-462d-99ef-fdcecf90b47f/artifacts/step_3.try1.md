I read "weekly retail on-highway diesel price for Indiana" as EIA weekly Midwest (PADD 2) retail diesel price, used as a proxy because EIA publishes no Indiana-only weekly series; if you meant EIA weekly Indiana-specific retail diesel price, if such a series exists or EIA weekly Midwest regional price, with Indianapolis or a nearby metro as a cross-check or EIA weekly US national average diesel price, as the fallback, the answer below may not apply.

FILE: fuel_surcharge_workbook.xlsx (sheets in order: Weekly, Inputs, Bands). I built it with openpyxl and recalculated it in LibreOffice. Result: status success, 370 formulas, 0 errors [S69]. Weekly is now the first sheet. This fixes the failed header check, which looked at the first sheet. Row 1 of Weekly reads: Week ending | Price $/gal | Surcharge $/mi | Gallons | Fleet fuel cost $ | Fuel cost $/mi | Source [S69].

Price data: the 52 prices in Weekly column B are values copied from weekly_prices.csv. The series is EIA EMD_EPD2D_PTE_R20_DPG, Weekly Midwest (PADD 2) No. 2 Diesel Retail, in $/gal. The first week is 2025-10-27 and the latest is 2026-10-19 (as of 2026-10-19), retrieved 2026-10-23 [S64, S1]. Prices are not typed into any formula.

WORKBOOK SHEET MAP
| Sheet | Key columns / cells | Formula or content |
|---|---|---|
| Weekly | A Week ending | Date values, 52 rows (rows 2–53), oldest first. Row 53 is 2026-10-19 [S69] |
| Weekly | B Price $/gal | Values from the CSV. Row 2 is 3.715 and row 53 is 6.352 [S64] |
| Weekly | C Surcharge $/mi | `=ROUND((B2-Inputs!$B$4)/Inputs!$B$5,2)` |
| Weekly | D Gallons | `=Inputs!$B$9` |
| Weekly | E Fleet fuel cost $ | `=B2*D2` |
| Weekly | F Fuel cost $/mi | `=B2/Inputs!$B$5` |
| Weekly | G Source | Text naming the EIA series and API URL for each row. H1 holds a note on the source and the API URL [S69] |
| Inputs | B4 base 1.25; B5 mpg 6.2; B6 tractors 35; B7 miles per tractor per week 2300 | The only four hard-coded parameters (yellow cells). Each has a "Basis" note saying it comes from the task [S68] |
| Inputs | B8 fleet miles per week | `=B6*B7`, which gives 80,500 [S67] |
| Inputs | B9 fleet gallons per week | `=B8/B5`, which gives 12,983.87 [S67] |
| Inputs | Assumption notes, from row 11 | 1 constant gallons; 2 midpoint band convention; 3 surcharge on every mile, loaded and empty; 4 Class 8 = GVWR over 33,000 lb; 5 price proxy statement (Midwest PADD 2, no Indiana-only weekly series). I read all five back [S69] |
| Bands | A Band | Band number 1 to 40 (rows 2–41). Row 41 is band 40, from 4.95 to 5.00, midpoint 4.975, surcharge 0.60 [S69] |
| Bands | B Low | Row 2 is `=$H$1`. Later rows chain from the band above |
| Bands | C High | `=ROUND(B2+$H$2,2)` |
| Bands | D Midpoint | `=ROUND((B2+C2)/2,3)` |
| Bands | E Surcharge $/mi | `=ROUND((D2-Inputs!$B$4)/Inputs!$B$5,2)` |
| Bands | H1, H2 | Band grid start 3 and band width 0.05. These are layout constants, labelled on the sheet |

Spot check, week ending 2026-10-19: price 6.352, surcharge 0.82, gallons 12,983.87, fleet fuel cost $82,473.55, fuel cost 1.0245 $/mi [S69]. Hand check: (6.352 − 1.25) ÷ 6.2 = 0.823, which rounds to 0.82.

Caveats:
- Gallons are constant each week (35 × 2,300 ÷ 6.2), so fleet cost moves only with price.
- Band surcharges use the midpoint rounded to 3 decimals before the surcharge is computed.
- I did not print the full 40-band table or all 52 Weekly rows back. I printed only the first, last and spot-check rows.
- The independent Decimal ROUND_HALF_UP check has not been run. It belongs to Step C.
- The Summary and Sources sheets, the ATRI figures, the chart and the memo come in later steps.
MISSING DATA: Independent Decimal half-up verification of Weekly and Bands values — not run in this step; scheduled for Step C
MISSING DATA: ATRI total and fuel cost per mile — not part of this step; Summary and Sources sheets come later
