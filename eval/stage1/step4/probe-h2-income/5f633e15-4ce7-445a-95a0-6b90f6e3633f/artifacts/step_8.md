I read "between 2015 and 2023" as Endpoints only: 2015 and 2023; if you meant Every year from 2015 through 2023, with change from 2015 to 2023, the answer below may not apply.

# Real median household income, Indiana vs. United States, 2015 to 2023 (2023 dollars)

**Status: incomplete. The independent verification verdicts were FAIL (steps 5, 6 and 7).**
- None of the four ACS B19013 1-year values (Indiana and United States, 2015 and 2023) could be retrieved. The Census API returned a "Missing Key" page for both Indiana queries [S1][S2], retrieved 2026-10-22. The data.census.gov pages that were fetched showed no usable estimates.
- **No nominal income, adjusted income or percentage change exists, so the comparison could not be made.** No ACS number was filled from memory.
- figures.csv exists in the workspace, but it is a skeleton. Its income cells hold "NOT RETRIEVED" or "NOT COMPUTED" [S135][S136].
- **real_median_household_income.png was not produced.** The workspace check found no PNG [S135][S136]. The bar chart requirement is therefore not met.
- Only the two CPI-U values are verified.

## Results

CPI-U is series CUUR0000SA0, annual average (BLS period M13), not seasonally adjusted, 1982-84=100. It was retrieved from the BLS Public API on 2026-10-22 [S44] and matches the BLS annual table [S46], also retrieved 2026-10-22. Verifiers confirmed it [S111], 2026-10-22.

| Geography | Nominal 2015 (ACS B19013, 2015 dollars) | CPI-U 2015 | Adjusted 2015 (2023 dollars) | Nominal 2023 (ACS B19013, 2023 dollars) | CPI-U 2023 | Adjusted 2023 | Real % change | Nominal % change |
|---|---|---|---|---|---|---|---|---|
| Indiana | NOT RETRIEVED (API "Missing Key" [S1], 2026-10-22) | 237.017 [S44][S46], 2026-10-22 | NOT COMPUTED (= nominal × 1.2855702333587886 [S65], 2026-10-22) | NOT RETRIEVED (API "Missing Key" [S2], 2026-10-22) | 304.702 [S44][S46], 2026-10-22 | NOT COMPUTED (= nominal × 1.0 [S65], 2026-10-22) | NOT COMPUTED | NOT COMPUTED |
| United States | NOT RETRIEVED (query not run; API needs a key [S1], 2026-10-22) | 237.017 [S44][S46], 2026-10-22 | NOT COMPUTED (= nominal × 1.2855702333587886 [S65], 2026-10-22) | NOT RETRIEVED (query not run; API needs a key [S2], 2026-10-22) | 304.702 [S44][S46], 2026-10-22 | NOT COMPUTED (= nominal × 1.0 [S65], 2026-10-22) | NOT COMPUTED | NOT COMPUTED |

- **Verified so far:** the 2015 deflator is 304.702 / 237.017 = 1.2855702333587886 (recomputed in steps 3 and 6 [S65], 2026-10-22). Prices rose 28.557% from 2015 to 2023 [S92], retrieved 2026-10-22.
- **Who gained more in real terms:** this cannot be determined, because the ACS values are missing. I will not guess.
- **Margin of error:** no ACS margin of error (B19013_001M) was retrieved for any cell. I cannot say whether the gap between Indiana and the United States is within the ACS margins of error.

## Method
- Adjusted = nominal × CPI2023 / CPIyear, with CPI2023 = 304.702 [S44], retrieved 2026-10-22.
- The 2023 factor is 304.702 / 304.702 = 1, so adjusted 2023 equals nominal 2023.
- Nominal % change = nominal2023 / nominal2015 − 1.
- Real % change = adjusted2023 / adjusted2015 − 1.
- These formulas could not be applied, because the ACS inputs are missing.

## Assumptions
These were fixed before retrieval.
- "Between 2015 and 2023" means endpoints only: 2015 and 2023.
- Indiana means the U.S. state of Indiana (FIPS 18).
- United States means the 50 states and DC, as published in ACS table B19013.
- Income is ACS 1-year estimate B19013_001E (standard, not experimental), all households, as published for each survey year.
- ACS values are in each survey year's own dollars. The B19013 label says "inflation-adjusted", but that means the survey year's dollars, so the values are not already in 2023 dollars.
- 2023 dollars use the annual-average CPI-U for 2023 as the base.
- Rounding rule: keep full precision in calculations and round only for display.

## Why these sources fit
- **ACS 1-year B19013:** it is the Census Bureau's annual state and national median household income, on one consistent definition for both geographies and both years.
- **CPI-U CUUR0000SA0:** it is the standard BLS all-items index. Its annual average matches annual ACS data, and the not-seasonally-adjusted annual average is the usual choice for adjusting annual figures.

## Files
- **figures.csv** was produced in the workspace by calc.py. It has 4 data rows and 11 columns (geography, year, nominal_median_household_income, cpi_u_annual_avg, cpi_base_2023, adjusted_2023_dollars, nominal_pct_change_2015_2023, real_pct_change_2015_2023, acs_source, cpi_source, retrieval_date). The CPI columns are real (237.017 and 304.702 [S44][S46], 2026-10-22). The nominal income cells say "NOT RETRIEVED"; the adjusted and percentage-change cells say "NOT COMPUTED". **It must not be used as a data table.** Its cpi_source cell wrongly says "released 2026"; the BLS pages show no release year [S46], so that text should be removed.
- **real_median_household_income.png was NOT produced.** It is not in the workspace (see Limitations).
- Working files in tool_results/ (step1_1.txt through step7_2.txt) hold the raw fetched pages, searches and checks from steps 1 to 7. They are evidence, not deliverables.

## Files made
- tool_results/step1_2.txt (2,129 bytes, made in step 1; listed by plain code)
- tool_results/step1_3.txt (2,128 bytes, made in step 1; listed by plain code)
- tool_results/step1_4.txt (2,130 bytes, made in step 1; listed by plain code)
- tool_results/step1_5.txt (2,128 bytes, made in step 1; listed by plain code)
- tool_results/step1_6.txt (5,228 bytes, made in step 1; listed by plain code)
- tool_results/step1_7.txt (2,132 bytes, made in step 1; listed by plain code)
- tool_results/step1_8.txt (2,138 bytes, made in step 5; listed by plain code)
- tool_results/step1_9.txt (4,979 bytes, made in step 2; listed by plain code)
- tool_results/step2_1.txt (4,785 bytes, made in step 2; listed by plain code)
- tool_results/step2_2.txt (6,673 bytes, made in step 2; listed by plain code)
- tool_results/step2_3.txt (3,878 bytes, made in step 2; listed by plain code)
- tool_results/step2_4.txt (5,420 bytes, made in step 2; listed by plain code)
- tool_results/step3_1.txt (4,884 bytes, made in step 3; listed by plain code)
- tool_results/step3_2.txt (2,734 bytes, made in step 3; listed by plain code)
- tool_results/step3_3.txt (4,320 bytes, made in step 3; listed by plain code)
- tool_results/step4_1.txt (2,130 bytes, made in step 4; listed by plain code)
- tool_results/step4_2.txt (2,129 bytes, made in step 4; listed by plain code)
- tool_results/step4_3.txt (6,616 bytes, made in step 4; listed by plain code)
- tool_results/step4_4.txt (5,932 bytes, made in step 4; listed by plain code)
- tool_results/step4_5.txt (8,013 bytes, made in step 7; listed by plain code)
- tool_results/step5_1.txt (2,286 bytes, made in step 5; listed by plain code)
- tool_results/step5_2.txt (3,170 bytes, made in step 5; listed by plain code)
- tool_results/step5_3.txt (6,331 bytes, made in step 5; listed by plain code)
- tool_results/step5_4.txt (6,436 bytes, made in step 5; listed by plain code)
- tool_results/step5_5.txt (4,102 bytes, made in step 5; listed by plain code)
- tool_results/step5_6.txt (2,083 bytes, made in step 4; listed by plain code)
- tool_results/step5_7.txt (4,005 bytes, made in step 5; listed by plain code)
- tool_results/step5_8.txt (2,489 bytes, made in step 5; listed by plain code)
- tool_results/step6_1.txt (5,600 bytes, made in step 6; listed by plain code)
- tool_results/step6_2.txt (2,354 bytes, made in step 6; listed by plain code)
- tool_results/step6_3.txt (4,809 bytes, made in step 6; listed by plain code)
- tool_results/step6_4.txt (5,727 bytes, made in step 6; listed by plain code)
- tool_results/step6_7.txt (2,262 bytes, made in step 6; listed by plain code)
- tool_results/step7_1.txt (2,245 bytes, made in step 7; listed by plain code)

## Limitations
- **Missing deliverable, not made: real_median_household_income.png.** Step 4 lacked ACS data and ran no plotting code; step 7 confirmed no PNG exists [S135][S136]. The bar chart (R7) is not delivered, so the chart's size, labels and footnote were never checked.
- **Steps 1, 3, 4, 5, 6 and 7 were partial or FAIL.**
  - Step 1 lacked Census API access and data.census.gov table rendering. Step 3 lacked ACS data access and is stale, because it was built before steps 1 and 2 were reworked. Step 4 lacked ACS data access.
  - The four ACS figures, the adjusted values, the percentage changes and the chart are missing.
  - Retrieving the four ACS values needs a Census API key or the data.census.gov tables ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013.
- **Unconfirmed lead, not used:** an excerpt of the data.census.gov 2015 1-year page showed "United States / Estimate / 55,775" [S110], 2026-10-22. It is [unverified], because the full table was not read. It is not used in the results.
- **Substitute series not used:** FRED MEHOINUSA672N [S119] is a Current Population Survey series, not ACS B19013, and has no Indiana figure.
- **Margins of error:** no ACS margin of error was retrieved, so none can be applied. Once values exist, the ACS margin of error should be used to judge any gap.
- **National CPI:** the national CPI-U is applied to Indiana, so it does not reflect Indiana's own price changes.
- **Endpoints only:** intermediate years are not examined.
- **United States figure:** it excludes Puerto Rico.
- **CPI-U release year:** the BLS pages do not show it [S44][S46].

## Sources
- **CPI-U, series CUUR0000SA0** (U.S. city average, all items, not seasonally adjusted, 1982-84=100, annual average M13): 2015 = 237.017 and 2023 = 304.702.
  - BLS Public API: https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true [S44]. Retrieved 2026-10-22. Release year not shown.
  - BLS cross-check table: https://www.bls.gov/regions/mid-atlantic/data/consumerpriceindexannualandsemiannual_table.htm [S46]. Retrieved 2026-10-22. Release year not shown.
  - Verification re-check: [S111], 2026-10-22.
- **ACS 1-year table B19013** (B19013_001E and B19013_001M), Indiana and United States:
  - https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 [S1]. Retrieved 2026-10-22. Returned "Missing Key", so no data.
  - https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 [S2]. Retrieved 2026-10-22. Returned "Missing Key", so no data.
  - data.census.gov pages ACSDT1Y2015.B19013 [S108] and ACSDT1Y2023.B19013 [S100]. Retrieved 2026-10-22. No usable Indiana estimates. Release years (2016 and 2024) are [unverified].
BLOCKED: Census API key access — api.census.gov returned 'Missing Key', so ACS B19013 1-year values for Indiana and the United States (2015, 2023) could not be retrieved
BLOCKED: data.census.gov table rendering — fetched pages showed no usable estimates
BLOCKED: Chart production — real_median_household_income.png could not be built without ACS values
MISSING DATA: ACS B19013_001E and B19013_001M, Indiana, 2015 — api.census.gov (Missing Key), data.census.gov
MISSING DATA: ACS B19013_001E and B19013_001M, United States, 2015 — api.census.gov, data.census.gov (only unverified excerpt 55,775)
MISSING DATA: ACS B19013_001E and B19013_001M, Indiana, 2023 — api.census.gov, data.census.gov
MISSING DATA: ACS B19013_001E and B19013_001M, United States, 2023 — api.census.gov, data.census.gov
MISSING DATA: BLS CPI-U release year — not shown on BLS API response or BLS table
MISSING DATA: real_median_household_income.png — not in workspace
MISSING INPUT: ACS B19013 1-year values for Indiana and United States, 2015 and 2023 — step 1
MISSING INPUT: Filled adjusted values and percentage changes in figures.csv — step 3
MISSING INPUT: real_median_household_income.png — step 4

- BLOCKED: Census ACS data access (the team had no such capability; added by plain code)
- Mislabelled citation: step 1 cites S1 for '0:47', which S1 does not contain; it is in S28, S33, S36 (added by plain code)
- Mislabelled citation: step 1 cites S1 for '2016', which S1 does not contain; it is in S4, S10, S14 (added by plain code)
- Mislabelled citation: step 1 cites S2 for '0:56', which S2 does not contain; it is in S15, S22, S23 (added by plain code)
- Mislabelled citation: step 2 cites S92 for '1.2855702333587886', which S92 does not contain; it is in S65 (added by plain code)
- Mislabelled citation: step 2 cites S92 for '28.557%', which S92 does not contain (added by plain code)
- Mislabelled citation: step 2 cites S92 for '1.2855702', which S92 does not contain; it is in S65 (added by plain code)
- Mislabelled citation: step 3 cites S65 for '4', which S65 does not contain; it is in S3, S4, S5 (added by plain code)
- Mislabelled citation: step 3 cites S65 for '11', which S65 does not contain; it is in S3, S4, S5 (added by plain code)
- Mislabelled citation: step 4 cites S133 for 'Real Median Household Income in the United States', which S133 does not contain; it is in S119, S131, S132 (added by plain code)
- Mislabelled citation: step 5 cites S110 for 'United States / Estimate / 55,775', which S110 does not contain (added by plain code)
- Mislabelled citation: step 6 cites S46 for 'BLS cross-check table (released 2026)', which S46 does not contain; it is in S112, S121 (added by plain code)
- Mislabelled citation: step 7 cites S136 for 'NOT COMPUTED', which S136 does not contain; it is in S112, S115, S121 (added by plain code)
- Mislabelled citation: step 8 cites S65 for '304.702', which S65 does not contain; it is in S44, S45, S46 (added by plain code)
- Mislabelled citation: step 8 cites S65 for '237.017', which S65 does not contain; it is in S44, S45, S46 (added by plain code)
- Mislabelled citation: step 8 cites S65 for '3', which S65 does not contain; it is in S3, S4, S5 (added by plain code)
- Mislabelled citation: step 8 cites S65 for '6', which S65 does not contain; it is in S3, S4, S5 (added by plain code)
- Mislabelled citation: step 8 cites S92 for '28.557%', which S92 does not contain (added by plain code)
- NOT MET: R1 — Retrieve ACS 1-year table B19013 median household income (all households) for Indiana and the United States for 2015 and 2023 (endpoints only), as published for (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R2 — Retrieve BLS CPI-U (CUUR0000SA0, U.S. city average, all items, not seasonally adjusted, 1982-84=100) annual averages for 2015 and 2023. (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R3 — Compare real median household income for Indiana and the United States between 2015 and 2023 in 2023 dollars (nominal × CPI2023 / CPIyear), with percentage chan (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R4 — Report the nominal values, the CPI-U values used, the adjusted values and the percentage changes for both Indiana and the United States. (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R5 — Say why the ACS 1-year B19013 and CPI-U CUUR0000SA0 sources fit this comparison, including limitations (margins of error, national CPI applied to a state). (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R7 — Deliver a bar chart as a PNG. (file not made: a png file; checked by plain code on the final answer)
- NOT MET: R8 — Cite every figure with its source (URL, table or series ID) and date (release year and retrieval date). (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R9 — The final answer must open with the mandated line: I read "between 2015 and 2023" as Endpoints only: 2015 and 2023; if you meant Every year from 2015 through 20 (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R11 — State plainly in the final answer which of Indiana and the United States gained more in real terms 2015 to 2023, and whether the gap is within ACS margins of er (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R12 — Use the ACS 1-year estimates of median household income (standard, not experimental) from table B19013, as published for each year, for the income data. (marked BLOCKED; checked by plain code on the final answer)
- MISSING FILE: a png file (promised by the plan, not in the workspace; checked by plain code)
- OLD INPUT: step 3 used step 1's output from before step 1 was re-run for a missing input; it was not redone, so it may not match step 1's final output (added by plain code)

