I read "between 2015 and 2023" as Endpoints only: 2015 and 2023; if you meant Every year from 2015 through 2023, with change from 2015 to 2023, the answer below may not apply.

**The chart was NOT produced. real_median_household_income.png does not exist, so there is no pixel size to report.** figures.csv has no income data to plot.

- Chart file name: real_median_household_income.png. NOT produced.
- Pixel size: none, because there is no file.
- Values labelled on the chart: none.
- figures.csv has 4 data rows but is only a skeleton. Its nominal, adjusted and percent-change cells hold the text "NOT RETRIEVED" or "NOT COMPUTED" [S115].
- Step 3 never received the four ACS B19013 1-year values for Indiana and the United States for 2015 and 2023. The Census API returned "Missing Key" [S1].
- I searched the saved source files for Indiana or U.S. median income figures and found none [S113] [S114]. I did not fill any ACS figure from memory. Bars built from placeholder or invented numbers would misstate the data.

**What is available**
- CPI-U inputs from step 3 (series CUUR0000SA0, annual average): 2015 = 237.017 [S55]; 2023 = 304.702 [S57].
- Deflator for 2015 = 304.702 / 237.017 = 1.2855702333587886. Deflator for 2023 = 1.0 exactly.
- Once the ACS values are supplied, the chart needs these grouped bars in 2023 dollars:
  - Indiana 2015 = nominal × 1.2855702333587886.
  - Indiana 2023 = nominal.
  - United States 2015 = nominal × 1.2855702333587886.
  - United States 2023 = nominal.
- Each geography is annotated with its real % change, adjusted2023 / adjusted2015 − 1.
- The footnote must carry the sources and dates: ACS 1-year table B19013 with its release year, BLS CUUR0000SA0, and retrieval date 2026-10-22.

**To finish:** supply the four ACS 1-year B19013_001E values. Use a Census API key, or data.census.gov tables ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013. Then re-run calc.py to fill figures.csv and re-run the chart job.
BLOCKED: Census ACS data access (API key / data.census.gov values) — the four ACS B19013 1-year values were not obtained, so figures.csv holds no numbers and real_median_household_income.png was NOT produced
MISSING DATA: Indiana B19013_001E ACS 1-year 2015 — api.census.gov (Missing Key) [S1], saved sources [S113] [S114]
MISSING DATA: United States B19013_001E ACS 1-year 2015 — api.census.gov, saved sources
MISSING DATA: Indiana B19013_001E ACS 1-year 2023 — api.census.gov, saved sources
MISSING DATA: United States B19013_001E ACS 1-year 2023 — api.census.gov, saved sources
MISSING INPUT: ACS B19013 1-year values for Indiana and United States, 2015 and 2023 — step 1 (via step 3 figures.csv, which holds only placeholders)
