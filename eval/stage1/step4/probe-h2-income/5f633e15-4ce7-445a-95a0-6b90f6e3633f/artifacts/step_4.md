I read "between 2015 and 2023" as Endpoints only: 2015 and 2023; if you meant Every year from 2015 through 2023, with change from 2015 to 2023, the answer below may not apply.

**The chart was NOT produced. real_median_household_income.png does not exist, so there is no pixel size to report.** I did not run any plotting code, because no sourced ACS values are available to plot.

- Chart file name: real_median_household_income.png. NOT produced.
- Pixel size: none, because there is no file.
- Values labelled on the chart: none.
- Footnote: none, because there is no chart.

**Why**
- The four ACS 1-year B19013 values were never obtained. These are Indiana and the United States for 2015 and 2023. The Census API returned "Missing Key" [S1][S2].
- figures.csv is still a skeleton from step 3. It has 4 rows and 11 columns, but the nominal, adjusted and percent-change cells hold "NOT RETRIEVED" or "NOT COMPUTED". It cannot be rebuilt without the ACS inputs.
- I re-checked the saved sources S93, S100, S108, S117 and S119 [S129][S130][S131][S132][S133].
  - S93 is an ACS 5-year page (2015-2019) for block groups. It is the wrong product and geography.
  - S119 is the FRED series MEHOINUSA672N, "Real Median Household Income in the United States". It shows 84,730 for 2023 [S133]. That is a Current Population Survey (CPS) series with its own price adjustment. It is not ACS B19013 and has no Indiana figure, so I did not use it.
- I did not fill any ACS figure from memory. I could not check such figures against a source in this step, and bars built from unverified numbers would misstate the data.

**What is available**
- CPI-U series CUUR0000SA0, annual average: 2015 = 237.017 [S55]; 2023 = 304.702 [S57].
- Deflator for 2015 = 304.702 / 237.017 = 1.2855702333587886. Deflator for 2023 = 1.0, so the 2023 adjusted value equals the 2023 nominal value.
- The chart needs four bars in 2023 dollars. For each geography, 2015 = nominal × 1.2855702333587886 and 2023 = nominal.
- Each geography gets a label for its real % change, adjusted2023 / adjusted2015 − 1.
- The footnote must give: ACS 1-year table B19013 with its release year (2015 and 2023), BLS CUUR0000SA0, and retrieval date 2026-10-22.

**To finish:** supply the four ACS 1-year B19013_001E values. Use a Census API key, or the data.census.gov tables ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013. Then re-run calc.py to fill figures.csv and re-run this chart job.
BLOCKED: Census ACS data access (API key / data.census.gov values) — the four ACS B19013 1-year values for Indiana and the United States, 2015 and 2023, could not be obtained, so figures.csv holds no numbers and real_median_household_income.png was NOT produced
MISSING DATA: Indiana B19013_001E ACS 1-year 2015 — api.census.gov (Missing Key) [S1], saved sources S93/S100/S108/S117/S119
MISSING DATA: United States B19013_001E ACS 1-year 2015 — api.census.gov, saved sources
MISSING DATA: Indiana B19013_001E ACS 1-year 2023 — api.census.gov, saved sources
MISSING DATA: United States B19013_001E ACS 1-year 2023 — api.census.gov, saved sources
MISSING INPUT: ACS B19013 1-year values for Indiana and United States, 2015 and 2023 — step 1 (via step 3 figures.csv, which holds only placeholders)
