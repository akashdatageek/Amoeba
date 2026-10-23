Verdict: FAIL
I read "between 2015 and 2023" as Every year from 2015 through 2023, inclusive; if you meant Only the two endpoint years, 2015 and 2023, the answer below may not apply.

# Verification report: steps 7 and 8 (income_cpi_adjusted.csv and real_income_indiana_vs_us.png)

## Summary
The CPI-U half of the deliverable checks out. The ACS half is missing. Every ACS B19013 income cell in the CSV is blank, so the chart plots no bars. I could not re-fetch any ACS value either. The Census API returned "Missing Key" [S8][S13][S17], and the data.census.gov pages and web searches gave no readable Indiana or U.S. value [S1][S3]. I did not fill any value from memory. The task asks for nominal values, adjusted values, percentage changes and a bar chart of incomes. None of those exist, so the deliverable does not meet the task.

## Re-checks I ran
1. I read the CSV with local:Read and parsed it with Python (Bash). It has 20 data rows: 18 year-by-geography rows plus 2 summary rows [S91][S94]. The ACS nominal and adjusted cells are blank in every row [S91].
2. I checked the 2020 rows. They carry "EXPERIMENTAL: no standard 2020 ACS 1-year release (pandemic nonresponse); ACS value UNAVAILABLE" [S94].
3. I checked the PNG header. It is 1800 x 1050 px and 145,897 bytes [S94].
4. I inspected chart.py. It reads the `adjusted_2023_usd` column of the CSV, and it draws the text "NO DATA PLOTTED: ACS B19013 values are blank…" [S94].
5. I recomputed the CPI deflators CPI_2023 / CPI_year by hand. I had no calculator tool in this step, so this is hand arithmetic.
6. I searched for the CPI-U 2023 annual average. The BLS PDF excerpts [S77][S92] showed only monthly values and no annual figure, so they did not confirm any of the nine annual averages.

## Check table
| item | claimed | checked | match? |
|---|---|---|---|
| ACS B19013 Indiana 2015 (nominal) | blank, "UNAVAILABLE" [S91] | Could not re-fetch; API said Missing Key [S8] | n/a. Value missing; the deliverable is incomplete |
| ACS B19013 U.S. 2015 | blank [S91] | Could not re-fetch [S8] | n/a. Missing |
| ACS B19013 Indiana and U.S., a middle year (2019) | blank [S91] | Could not re-fetch [S17] | n/a. Missing |
| ACS B19013 Indiana and U.S. 2023 | blank [S91] | Could not re-fetch [S3] (no readable value) | n/a. Missing |
| ACS 2020 flagged experimental | Flag text present on both 2020 rows [S94] | Confirmed in the CSV [S94] | Yes (flag only; no value) |
| CPI-U 2015 annual average | 237.017 [S63] | CSV holds 237.017 [S91]. Step 6's BLS API extraction is the source [S59]. No independent BLS page re-read | Consistent; not independently re-fetched |
| CPI-U 2018 annual average | 251.107 [S63] | Saved BLS API text shows M13 = 251.107 [S59]. I did not re-read that file this step; this rests on my earlier inspection | Yes |
| CPI-U 2023 annual average | 304.702 [S63] | CSV holds 304.702 [S91]. Searches [S77][S92] showed no annual figure | Consistent; not independently re-fetched |
| CPI-U 2016, 2017, 2019–2022 | 240.007, 245.120, 255.657, 258.811, 270.970, 292.655 [S63] | Only seen in step 6's extraction; no independent source | UNVERIFIED |
| Factor 2015 | 1.2856 [S66] | 304.702 / 237.017 = 1.28557 | Yes |
| Factor 2016 | 1.2696 [S66] | 304.702 / 240.007 = 1.26955 | Yes |
| Factor 2017 | 1.2431 [S66] | 304.702 / 245.120 = 1.24301 | Yes |
| Factor 2018 | 1.2134 [S66] | 304.702 / 251.107 = 1.21340 | Yes |
| Factors 2019–2022 (not itemised in the step 7 excerpt) | not shown in the excerpt I received | My hand values: 1.19184, 1.17728, 1.12449, 1.04117 | Not comparable |
| CPI-only rise 2015→2023 | 28.6% [S66] | 304.702 / 237.017 − 1 = 28.56% | Yes |
| Adjusted 2023 values, nominal % change, real % change (Indiana and U.S.) | blank / "not computable" [S91] | Cannot be recomputed without ACS nominals | FAIL. Missing |
| CSV rows and columns | 12 columns, 20 rows [S91] | 20 rows confirmed [S91][S94]. The retrieved_date column shows 2026-10-23 [S91] | Yes (structure only) |
| CSV URL and date columns | Every row has an ACS URL, a CPI URL and a date [S91] | Rows show api.census.gov and api.bls.gov URLs with 2026-10-23 [S94]. The ACS URLs point to endpoints that returned no data [S8] | Present, but the ACS URLs never yielded data |
| PNG size | 1800 x 1050 px [S68] | 1800 x 1050 [S94] | Yes (≥1000 px wide) |
| PNG plots numbers from the CSV | Method only; 0 of 18 values plotted [S68] | chart.py reads `adjusted_2023_usd` [S94], which is blank | FAIL. The chart has no income bars |

## Why FAIL
The deliverable does not contain what the task asks for, so any user relying on it would get no comparison of Indiana and U.S. real income.
- Step 7: the nominal, adjusted and percentage-change columns are blank. Fix: obtain the 18 B19013_001E values (Indiana and U.S., 2015–2019 and 2021–2023, plus 2020 experimental if wanted). Use a free Census API key, or read the data.census.gov tables for ACS1Y2015–2023.B19013. Enter them in build.py's `nom` dictionary and rerun it.
- Step 8: the chart has no bars. Fix: rerun chart.py after the CSV is filled. Also confirm that the 2020 hatched bars are labelled experimental.
- Step 7: the CPI-U values for 2016, 2017 and 2019–2022 were not independently confirmed. A BLS table page, for example the annual-average CPI-U table, would confirm them.
- Step 7: the task says to report the ACS table as inflation-adjusted dollars of each survey year. After the values are filled in, check that the deflator is applied correctly to each year.

## Not confirmed
- All ACS values (no Census key, no readable table).
- Nine CPI-U annual averages against an independent BLS page. Only 2015 and 2018 trace to raw saved BLS text, and the rest rest on step 6's extraction [S59][S63].
- I did not view the PNG image. Its content is known only from chart.py text [S94] and the step 8 description [S68].

VERDICT: FAIL. Required corrections: fill all ACS B19013 values, rebuild the CSV and the adjusted values, rebuild the chart with real bars, and independently confirm the remaining CPI-U annual averages.
BLOCKED: Census API key — ACS B19013 values for Indiana and the U.S. (2015, a middle year, 2023) could not be re-fetched independently
BLOCKED: Image viewing — PNG content could not be visually inspected
MISSING DATA: ACS 1-year B19013_001E Indiana and United States 2015-2023 — Census API (Missing Key), data.census.gov pages, web searches
MISSING DATA: CPI-U annual averages 2016, 2017, 2019-2023 from an independent BLS page — web searches returned only monthly values
MISSING INPUT: ACS B19013 values — steps 1-5 delivered none, so step 7 CSV and step 8 chart contain no income data
Issues:
1. Step 7: every ACS nominal, adjusted and percent-change cell in income_cpi_adjusted.csv is blank because the Census API returned Missing Key [S8][S91]. Fix: retrieve the 18 B19013_001E values with a Census API key or from data.census.gov, put them in build.py `nom`, and rerun.
2. Step 8: real_income_indiana_vs_us.png has 0 of 18 bars and shows 'NO DATA PLOTTED' [S68][S94]. Fix: rerun chart.py once the CSV is filled, and keep the 2020 bars hatched and labelled experimental.
3. Step 7: CPI-U annual averages for 2016, 2017 and 2019-2023 were not independently confirmed against raw BLS text. Only 2015 and 2018 trace to saved text [S59]. Fix: cross-check them against a BLS annual-average table.
4. Step 7: the deflator arithmetic matches my hand recompute for 2015-2018 and the 28.6% CPI rise [S66]. No number is wrong, but no income-based result exists to check.
