Verdict: FAIL
Verdict: FAIL
I read "between 2015 and 2023" as Endpoints only: 2015 and 2023; if you meant Every year from 2015 through 2023, with change from 2015 to 2023, the answer below may not apply.

Verdict: FAIL

Verification memo, Job C (chart and citations). Review date 2026-10-22 (America/Chicago).

## File checks
Re-check 1, PNG existence. I ran ls -la real_median_household_income.png figures.csv, then Python os.path.exists, then find for *.png and *.jpg.
- Result: "png exists False" [S128]. ls said "No such file or directory". find found no image.
- PNG size and readability cannot be reported because the file does not exist. The check for at least 600 px was not performed.
- Step 4 also states that it did not produce the chart.

Re-check 2, chart numbers versus CSV. Not performed. There is no chart and so no labelled numbers.
- I read figures.csv with local:Read [S127] and with Python csv [S128]. It has 4 data rows (Indiana 2015, Indiana 2023, United States 2015, United States 2023) and the 11 required columns.
- It is a skeleton. In all 4 rows nominal_median_household_income is "NOT RETRIEVED", adjusted_2023_dollars is "NOT COMPUTED", and both percent-change columns are "NOT COMPUTED" [S127][S128].
- Only the CPI columns hold numbers. The 2015 CPI-U is 237.017 and the 2023 CPI-U is 304.702 (BLS series CUUR0000SA0, annual average, 1982-84=100, retrieved 2026-10-22) [S127][S128].

Re-check 3, CPI inputs found again in the saved BLS sources.
- grep found 237.017 and 304.702 once each in the BLS API file [S44] and once each in the BLS annual-index table [S46] [S128]. Both were retrieved 2026-10-22 (UTC timestamp 2026-10-23). This confirms CPI-U 2015 annual average = 237.017 and CPI-U 2023 annual average = 304.702.
- Python recomputed the factor 304.702 / 237.017 = 1.2855702333587886 [S128]. It matches steps 3 and 4 (1.2855702333587886) [S65].
- The 2023 factor is 304.702 / 304.702 = 1.0, so the 2023 adjusted value will equal the 2023 nominal value.

Re-check 4, ACS inputs. Not re-confirmed.
- Step 1 delivered no ACS 1-year B19013 values.
- The Census API returned "Missing Key" for the 2015 request [S1] and for the 2023 request [S2], both fetched 2026-10-23T00:00 UTC (the evening of 2026-10-22 in Chicago).
- Steps 3 and 4 correctly did not invent values. No ACS figure can be confirmed or contradicted.

## Citation check
- Each of the 4 CSV rows has a non-empty acs_source, a non-empty cpi_source and retrieval_date 2026-10-22 [S128].
- cpi_source gives the BLS API URL, series CUUR0000SA0, annual average M13, "1982-84=100" and "released 2026" [S127]. Both CPI figures therefore carry a source and a date.
- acs_source gives the Census API URL and survey year, but it is marked "NOT RETRIEVED (Missing Key)" [S127]. No ACS figure exists to cite, so the ACS citations are empty. The ACS source and date requirement is not met.
- The chart footnote could not be checked because there is no chart.
- Step 3 is marked STALE. It was built before steps 1 and 2 were reworked and was not rebuilt on the current inputs.

## Corrections
1. Step 4: real_median_household_income.png is missing. Build it from the four ACS values. It needs grouped bars in 2023 dollars for Indiana and the United States, 2015 and 2023, labelled with the values and the real % change. It needs a footnote giving the Census B19013 ACS 1-year release years, BLS CUUR0000SA0 and the retrieval date. The image must be at least 600 px wide.
2. Step 3: figures.csv holds placeholders in the nominal, adjusted and percent-change columns for all 4 rows. Fill them once the ACS values are available:
   - adjusted = nominal × 304.702 / CPI of the year, so 2015 uses 1.2855702333587886 and 2023 uses 1.0.
   - nominal % change = nominal2023 / nominal2015 − 1.
   - real % change = adjusted2023 / adjusted2015 − 1.
3. Step 1: the four ACS 1-year B19013_001E values (Indiana and the United States, 2015 and 2023) are still missing. Get them with a Census API key or from the data.census.gov tables ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013. Record each with its source URL, release year and retrieval date.
4. No CPI numbers need correcting. 237.017 and 304.702 are confirmed [S44][S46].

This is not a full PASS. The chart check could not be run, and the deliverables lack the ACS data.
BLOCKED: Image file inspection (PNG size, readability, labelled numbers) — could not be done because real_median_household_income.png does not exist
BLOCKED: Census ACS data access (API key or data.census.gov values) — ACS B19013 values could not be re-confirmed because none were delivered
MISSING DATA: Indiana B19013_001E ACS 1-year 2015 — not in saved sources; Census API returned Missing Key [S1]
MISSING DATA: Indiana B19013_001E ACS 1-year 2023 — not in saved sources; Census API returned Missing Key [S2]
MISSING DATA: United States B19013_001E ACS 1-year 2015 — not in saved sources
MISSING DATA: United States B19013_001E ACS 1-year 2023 — not in saved sources
MISSING DATA: real_median_household_income.png — not in the workspace [S128]
MISSING INPUT: Chart PNG real_median_household_income.png — step 4 (not produced)
MISSING INPUT: ACS B19013 1-year values for Indiana and the United States, 2015 and 2023 — steps 1, 3 and 4 (placeholders only)
Issues:
1. Step 4: real_median_household_income.png does not exist (os.path.exists False [S128]), so PNG size, readability, labelled numbers and footnote could not be checked. Fix: produce the bar chart (>=600 px) once the ACS values are available.
2. Step 3: figures.csv has 4 rows and 11 columns but nominal, adjusted and percent-change cells hold 'NOT RETRIEVED' or 'NOT COMPUTED' [S127]. Fix: fill from the four ACS values with adjusted = nominal*304.702/CPIyear and re-run calc.py.
3. Step 1: the four ACS 1-year B19013 values for Indiana and the United States, 2015 and 2023, were never obtained (Census API Missing Key [S1][S2]). Fix: use a Census API key or the data.census.gov tables ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013, and cite each with release year and retrieval date.
4. Citations: acs_source cells cite no figure, and the chart footnote cannot be checked. Fix: add source URL, release year and retrieval date for every ACS value and in the chart footnote.
5. Step 3 is stale (built before the rework of steps 1 and 2). Fix: rebuild it on the current inputs.
