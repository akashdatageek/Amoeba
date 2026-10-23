I read "weekly retail on-highway diesel price for Indiana" as EIA weekly Midwest (PADD 2) retail diesel price, used as a proxy because EIA publishes no Indiana-only weekly series; if you meant EIA weekly Indiana-specific retail diesel price, if such a series exists or EIA weekly Midwest regional price, with Indianapolis or a nearby metro as a cross-check or EIA weekly US national average diesel price, as the fallback, the answer below may not apply.

Step 3 result: the core sheets of fuel_surcharge_workbook.xlsx are built (Inputs, Weekly, Bands). The Summary and Sources sheets are not yet added (step B).

Checks:
- LibreOffice recalculation found 370 formulas and 0 errors [S75].
- Weekly has 52 data rows. Columns C to F are all formulas [S73, S74].
- An independent Decimal half-up recalculation found 0 mismatches across the 52 weekly surcharges and the 40 band surcharges [S74].
- After a plain-code check, the Weekly headers were renamed to: Week ending, Price, Surcharge, Gallons, Fleet fuel cost, Fuel cost per mile, Source [S75]. Units are in cell comments on the header cells: $/gal, $/mi, gallons per week, $ per week [S75].
- Sheet order in the file: Weekly, Inputs, Bands [S73].

Table: workbook sheet map (sheet | key column or cell | formula or content)

| Sheet | Key column / cell | Formula or content |
|---|---|---|
| Inputs | B4 base price = 1.25 | Hard-coded parameter, from the task |
| Inputs | B5 mpg = 6.2 | Hard-coded parameter, from the task |
| Inputs | B6 tractors = 35 | Hard-coded parameter, from the task |
| Inputs | B7 miles per tractor per week = 2300 | Hard-coded parameter, from the task |
| Inputs | B8 fleet miles per week = 80,500 | Formula: tractors x miles, 35 x 2300 [S74] |
| Inputs | B9 fleet gallons per week = 12,983.87 | Formula: fleet miles / mpg, 80,500 / 6.2 [S74] |
| Inputs | Assumption notes (text) | Constant gallons every week; midpoint band convention; surcharge on every loaded and empty mile; Class 8 = GVWR over 33,000 lb; Midwest PADD 2 proxy for Indiana; band grid start 3.00 and 5-cent step |
| Weekly | A Week ending | Date values from weekly_prices.csv, 2025-10-27 to 2026-10-19 [S64] |
| Weekly | B Price ($/gal) | Values from weekly_prices.csv, EIA series EMD_EPD2D_PTE_R20_DPG [S1, S64] |
| Weekly | C Surcharge ($/mi) | =ROUND((B2-Inputs!$B$4)/Inputs!$B$5,2), filled down to row 53 [S75] |
| Weekly | D Gallons | =Inputs!$B$9 |
| Weekly | E Fleet fuel cost ($) | =B2*D2 [S75] |
| Weekly | F Fuel cost per mile ($/mi) | =B2/Inputs!$B$5 |
| Weekly | G Source | Text: EIA series EMD_EPD2D_PTE_R20_DPG, Midwest PADD 2 weekly retail diesel, retrieved 2026-10-23 [S1, S64]; API URL in cell I1 [S75] |
| Bands | A Band | Numbers 1 to 40 |
| Bands | B Low, C High | Low runs 3.00 to 4.95; high runs 3.05 to 5.00 |
| Bands | D Midpoint | (Low + High) / 2; first 3.025, last 4.975 |
| Bands | E Surcharge | =ROUND((D2-Inputs!$B$4)/Inputs!$B$5,2), same pattern in all 40 rows |

Spot checks [S74, S75]:
- First week, 2025-10-27: price 3.715, surcharge 0.40, fleet cost $48,235.08, fuel cost 0.5992 $/mi.
- Last week, 2026-10-19: price 6.352, surcharge 0.82, fleet cost $82,473.55, fuel cost 1.0245 $/mi. This is the latest EIA week, as of 2026-10-19, retrieved 2026-10-23. FRED shows the same value [S58].
- Band 1 (3.00 to 3.05): midpoint 3.025, surcharge 0.29. Band 40 (4.95 to 5.00): midpoint 4.975, surcharge 0.60 [S74].

Data basis: EIA series EMD_EPD2D_PTE_R20_DPG, Weekly Midwest No. 2 Diesel Retail Prices in $/gal, weeks ending 2025-10-27 to 2026-10-19 [S1, S64]. Midwest (PADD 2) is a proxy for Indiana.

Not done in this step: Summary and Sources sheets, ATRI figures, chart, memo, stats and 40-band tables. Those belong to later steps.
