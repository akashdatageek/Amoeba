Verdict: FAIL
I read "between 2015 and 2023" as Every year from 2015 through 2023, inclusive; if you meant Only the two endpoint years, 2015 and 2023, the answer below may not apply.

# Real median household income, Indiana vs. the United States, 2015–2023 (2023 dollars)

**VERDICT: FAIL.** The income half of the analysis could not be done. No ACS 1-year B19013 value was retrieved for any year, for Indiana or the U.S. I did not fill any value from memory. The CPI-U half is complete and was independently re-checked on 2026-10-23.

## 1. Headline findings

- **No Indiana vs. U.S. comparison can be reported.** The 2015→2023 nominal change, the real change in 2023 dollars and the gap between Indiana and the U.S. are all UNAVAILABLE. The ACS inputs are missing (steps 1–5, 7).
- **The only computable figure is inflation.** CPI-U rose 28.6% from 2015 to 2023, which is (304.702/237.017 − 1) × 100 [S63, S115]. This uses BLS series CUUR0000SA0, annual averages, fetched 2026-10-23.
- **The 2015 multiplier is 1.2856.** To convert a 2015 dollar to 2023 dollars, multiply by 304.702/237.017 = 1.2856 [S110]. This was calculated on 2026-10-23.
- **Cause of the gap.** Every api.census.gov request returned a "Missing Key" page or timed out, as tried on 2026-10-23 [S8, S13, S17, S31, S48, S53, S58]. The data.census.gov fallback pages either failed to load or showed no usable 1-year value.

## 2. Figures by year and geography

CPI source for all rows: BLS Public Data API v2, series CUUR0000SA0, M13 annual average, 1982-84=100, fetched 2026-10-23 [S59, S63]. URL: https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true

The deflator is CPI_2023 / CPI_year, recomputed by the verifier on 2026-10-23 [S115]. The ACS source for every row is ACS 1-year B19013 (standard release), requested through api.census.gov on 2026-10-23. It returned no data (see section 6).

| Year | Geography | ACS nominal B19013 (own-year $) | CPI-U annual avg (1982-84=100) | Deflator to 2023 $ | Adjusted (2023 $) | Indiana as % of U.S. |
|---|---|---|---|---|---|---|
| 2015 | Indiana | UNAVAILABLE | 237.017 [S63] | 1.2856 [S115] | n/a | n/a |
| 2015 | United States | UNAVAILABLE | 237.017 [S63] | 1.2856 [S115] | n/a | n/a |
| 2016 | Indiana | UNAVAILABLE | 240.007 [S63] | 1.2696 [S115] | n/a | n/a |
| 2016 | United States | UNAVAILABLE | 240.007 [S63] | 1.2696 [S115] | n/a | n/a |
| 2017 | Indiana | UNAVAILABLE | 245.120 [S63] | 1.2431 [S115] | n/a | n/a |
| 2017 | United States | UNAVAILABLE | 245.120 [S63] | 1.2431 [S115] | n/a | n/a |
| 2018 | Indiana | UNAVAILABLE | 251.107 [S63] | 1.2134 [S115] | n/a | n/a |
| 2018 | United States | UNAVAILABLE | 251.107 [S63] | 1.2134 [S115] | n/a | n/a |
| 2019 | Indiana | UNAVAILABLE | 255.657 [S63] | 1.1918 [S115] | n/a | n/a |
| 2019 | United States | UNAVAILABLE | 255.657 [S63] | 1.1918 [S115] | n/a | n/a |
| 2020 | Indiana | EXPERIMENTAL (no standard 2020 ACS 1-year release); UNAVAILABLE | 258.811 [S63] | 1.1773 [S115] | n/a | n/a |
| 2020 | United States | EXPERIMENTAL (no standard 2020 ACS 1-year release); UNAVAILABLE | 258.811 [S63] | 1.1773 [S115] | n/a | n/a |
| 2021 | Indiana | UNAVAILABLE | 270.970 [S63] | 1.1245 [S115] | n/a | n/a |
| 2021 | United States | UNAVAILABLE | 270.970 [S63] | 1.1245 [S115] | n/a | n/a |
| 2022 | Indiana | UNAVAILABLE | 292.655 [S63] | 1.0412 [S115] | n/a | n/a |
| 2022 | United States | UNAVAILABLE | 292.655 [S63] | 1.0412 [S115] | n/a | n/a |
| 2023 | Indiana | UNAVAILABLE | 304.702 [S63] | 1.0000 [S115] | n/a (would equal nominal) | n/a |
| 2023 | United States | UNAVAILABLE | 304.702 [S63] | 1.0000 [S115] | n/a (would equal nominal) | n/a |

The ACS margins of error (B19013_001M) are also UNAVAILABLE for every row.

## 3. Percent changes, 2015 → 2023

| Measure | Indiana | United States | Source and date |
|---|---|---|---|
| Nominal median household income change | UNAVAILABLE | UNAVAILABLE | ACS B19013 not retrieved, attempted 2026-10-23 |
| Real (2023 dollars) median household income change | UNAVAILABLE | UNAVAILABLE | ACS B19013 not retrieved, attempted 2026-10-23 |
| Indiana-minus-U.S. gap in change | UNAVAILABLE | UNAVAILABLE | n/a |
| CPI-U change (the only computable figure) | 28.6% | 28.6% | BLS CUUR0000SA0 [S63, S115], fetched 2026-10-23 |

## 4. Why these sources fit, and their limits

**ACS 1-year, table B19013**
- It is the Census Bureau's standard annual source of median household income for states and the nation. The 1-year product gives timely yearly values, and each estimate comes with a margin of error. B19013_001E is the estimate and B19013_001M is its margin of error [unverified; not fetched, step 5].
- Limits:
  - There is no standard 2020 1-year release because of pandemic nonresponse. Only experimental estimates exist, so 2020 is flagged as experimental. No 2020 value was confirmed (step 3).
  - The estimates have margins of error, so small year-to-year differences may not be statistically meaningful.
  - ACS values are in each survey year's own dollars, so they must be deflated before comparing years.

**CPI-U, CUUR0000SA0**
- It is the standard BLS all-items national price index. Each ACS year maps to one annual-average deflator (period M13, "Annual") [S59].
- By BLS series-ID convention, CU is CPI-U, U is not seasonally adjusted, 0000 is U.S. city average and SA0 is all items [unverified: my own knowledge, step 6]. The 1982-84=100 base comes from the task's working interpretation. No fetched BLS page states it [S63].
- Limit: it is a national index, not an Indiana-specific price index. Applying it to Indiana assumes Indiana prices moved with U.S. prices.

## 5. Assumptions and method (planning record)

- **Objective and deliverables:** compare real median household income for Indiana and the U.S. for 2015–2023 in 2023 dollars. The deliverables are this memo, a CSV and a bar chart PNG.
- **Assumption (interpretation):** "between 2015 and 2023" means every year from 2015 through 2023, inclusive. "Indiana" means the State of Indiana.
- **Planned formulas** (the ACS inputs are missing, so none was applied to real data):
  - adjusted_2023 = nominal × CPI_2023 / CPI_year, using unrounded CPI values.
  - nominal % change = (nominal_2023 / nominal_2015 − 1) × 100.
  - Real % change: the same formula applied to the adjusted values.
  - Indiana as % of U.S.: Indiana divided by U.S. for each year.
- **Rounding:** deflators to four decimals, the CPI change to one decimal.
- **CPI values:** used as published by BLS. The annual value was not recomputed from monthly values.
- **Checks run:** the verifier recomputed all nine deflators and the 28.6% CPI change on 2026-10-23, and they matched [S115]. The adjusted-income formula could not be checked on real data.
- **Main risk that materialised:** the Census API needs a key, and none was available in this environment.

## 6. Citations (source, vintage, retrieval date)

**CPI-U (all CPI figures above)**
- BLS Public Data API v2, series CUUR0000SA0, M13 annual averages 2015–2023, status REQUEST_SUCCEEDED, retrieved 2026-10-23 [S59, S62, S63].
- URL: https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true
- Definition page, cited by judgement and not quoted: https://www.bls.gov/cpi/overview.htm, retrieved 2026-10-23 [S61].
- The deflators and the 28.6% change are calculations from these CPI values, recomputed 2026-10-23 [S110, S115].
- The verifier did not check the CPI values for 2016, 2017, 2019, 2020 and 2023 against raw BLS text. They rest on step 6's extraction [S63]. The 2021 and 2022 values were confirmed in the saved BLS text [S115].

**ACS B19013 (ACS 1-year, standard release, vintage = survey year)**
- Every request below was made on 2026-10-23. None returned data.
- URL pattern: https://api.census.gov/data/{year}/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 (Indiana), or the same URL ending &for=us:1 (U.S.).

| Year | Geography | Outcome (attempted 2026-10-23) |
|---|---|---|
| 2015 | Indiana, U.S. | "Missing Key" [S7, S8] |
| 2016 | Indiana | "Missing Key" [S13] |
| 2016 | U.S. | Not fetched (fetch limit reached) |
| 2017 | Indiana | "Missing Key" [S17] |
| 2017 | U.S. | Not run (no turns left after the Indiana call) |
| 2018 | Indiana, U.S. | Not run (no turns left) |
| 2019 | Indiana | "Missing Key" [S31] |
| 2019 | U.S. | No usable response |
| 2020 | Indiana, U.S. | No experimental value confirmed |
| 2021 | Indiana | Request timed out [S48] |
| 2021 | U.S. | Not run |
| 2022 | Indiana, U.S. | No API fetch made; the saved data.census.gov page showed no usable value [S52] |
| 2023 | Indiana | "Missing Key" [S53] |
| 2023 | U.S. | "Missing Key" [S58] |

- A web search run 2026-10-23 gave no readable 1-year value [S34]. The Census Reporter API returned an error on 2026-10-23.

## 7. Files

- `income_cpi_adjusted.csv` (step 7): 18 data rows (9 years × 2 geographies) plus 2 summary rows, 12 columns, retrieved date 2026-10-23 in every row [S110, S111, S114].
  - The CPI columns are filled.
  - The ACS nominal, margin-of-error, adjusted and percent-change columns are empty, with a note "ACS B19013 value UNAVAILABLE…".
  - The 2020 rows are labelled "EXPERIMENTAL (no standard 2020 ACS 1-year release)".
- `real_income_indiana_vs_us.png` (step 8): 1800 × 1050 px, 150 dpi [S70].
  - It was rendered, but it plots 0 of 18 bars and shows a "no data plotted" box.
  - The title, axes, legend, 2020 hatching and dated footnote are present.
  - It is not a usable bar chart. It was built on the step 7 output before rework (marked STALE).
- Scripts: `build.py` and `build_csv.py` (step 7, build the CSV) and `chart.py` (step 8, draws the PNG).
- Working logs (raw fetch and check output, not deliverables):
  - Step 1: tool_results/step1_2.txt, step1_4.txt, step1_5.txt, step1_6.txt, step1_7.txt, step1_8.txt, step7_4.txt.
  - Step 2: tool_results/step2_2.txt, step2_3.txt, step2_5.txt.
  - Step 3: tool_results/step3_1.txt, step3_2.txt, step3_3.txt, step3_4.txt, step3_6.txt.
  - Step 4: tool_results/step3_5.txt, step4_2.txt, step4_3.txt, step4_5.txt.
  - Step 5: tool_results/step5_2.txt, step5_3.txt, step5_4.txt.
  - Step 6: tool_results/step5_5.txt, step6_1.txt, step6_4.txt.
  - Step 7: tool_results/step1_9.txt, step7_1.txt, step7_2.txt, step7_3.txt.
  - Step 9: tool_results/step9_1.txt through step9_9.txt.

## 8. Verification verdict and corrections

- **VERDICT: FAIL** (step 9, run 2026-10-23). The CPI values and deflators were confirmed. The income half does not exist.
- **Corrections applied:** none that resolve the failure. I added the missing explanation of why the sources fit (section 4), which the verifier flagged as absent. I also dated the figures and named the files.
- **Fixes still needed:**
  - Re-run the ACS requests with a free Census API key (`&key=...`), or read tables ACSDT1Y{year}.B19013 on data.census.gov.
  - Rebuild the CSV and re-run chart.py.
  - Cite fetched tables rather than API endpoints that returned "Missing Key".
  - Check the remaining CPI years against raw BLS text.

## Files made
- tool_results/step9_2.txt (3,104 bytes, made in step 9; listed by plain code)
- tool_results/step9_3.txt (3,860 bytes, made in step 9; listed by plain code)
- tool_results/step9_4.txt (2,128 bytes, made in step 9; listed by plain code)
- tool_results/step9_5.txt (3,675 bytes, made in step 9; listed by plain code)
- tool_results/step9_6.txt (6,662 bytes, made in step 9; listed by plain code)
- tool_results/step9_7.txt (4,734 bytes, made in step 9; listed by plain code)
- tool_results/step9_8.txt (2,128 bytes, made in step 9; listed by plain code)

## Limitations

- **Steps 1–5 (Federal Statistics Researcher), partial.** Lacked Census API access with a key, and data.census.gov page fetches.
  - Missing: ACS 1-year B19013_001E and _001M for Indiana and the U.S., for every year 2015–2023. 2020 is experimental-only and was not confirmed either.
  - The step 4 outputs carry five untagged figures and mislabelled citations.
- **Step 6, partial.** The BLS base period (1982-84=100) and the CUUR0000SA0 naming convention are not quoted from a fetched BLS page. Both are [unverified].
- **Step 7, partial.** The CSV has no ACS, adjusted or income percentage-change values.
- **Step 8, partial and STALE.** The PNG has no income bars. Lacked: ACS inputs.
- **Step 9, FAIL.** Lacked Census API access and image viewing. CPI values for 2016, 2017, 2019, 2020 and 2023 were not checked against raw BLS pages.
- **Main figures affected:** nominal income, real income, Indiana as % of U.S. and the 2015→2023 income percentage changes are missing for both geographies. Only the CPI-U values, the deflators and the 28.6% CPI change are reported.
BLOCKED: Census API access with a key — ACS 1-year B19013 estimates and margins of error for Indiana and the U.S., 2015–2023, could not be retrieved, so nominal and adjusted income, the Indiana-to-U.S. ratio and the income percentage changes could not be reported
BLOCKED: Image viewing — the PNG could not be visually inspected by the verifier
MISSING DATA: ACS 1-year B19013_001E and _001M, Indiana and United States, 2015–2019 and 2021–2023 — api.census.gov (Missing Key/timeout), data.census.gov (fetch failed or no usable value)
MISSING DATA: ACS 2020 experimental B19013, Indiana and United States — Census experimental data pages, no value confirmed
MISSING DATA: BLS statement of the 1982-84=100 base and the CUUR0000SA0 definition — BLS API response and CPI overview page text
MISSING INPUT: ACS B19013 values for 2015–2023, Indiana and United States — steps 1–5 (all UNAVAILABLE)
MISSING INPUT: Populated CSV and bar chart with income bars — steps 7 and 8 (blank and 0 of 18 bars)
Issues:
1. Steps 1–5: no ACS B19013 values retrieved; re-run with a Census API key or read data.census.gov tables ACSDT1Y{year}.B19013.
2. Step 7: CSV has blank ACS, adjusted and percent-change columns; rebuild after the ACS values are filled.
3. Step 8: PNG plots 0 of 18 bars; re-run chart.py after the CSV is filled.
4. Steps 6/9: CPI values for 2016, 2017, 2019, 2020 and 2023 not checked against raw BLS pages.

- BLOCKED: Census API key / data.census.gov access (the team had no such capability; added by plain code)
- NOT MET: R1 — Open the final answer with the exact line: I read "between 2015 and 2023" as Every year from 2015 through 2023, inclusive; if you meant Only the two endpoint ye (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R2 — Compare real median household income for Indiana and the United States between 2015 and 2023, expressed in 2023 dollars: side by side for every year, with the I (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R3 — Use the U.S. Census Bureau's American Community Survey 1-year estimates (standard release) of median household income, table B19013 (B19013_001E estimate and _0 (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R4 — Use the BLS CPI-U, U.S. city average, all items, not seasonally adjusted, 1982-84=100, annual average (series CUUR0000SA0) for 2015-2023 as the inflation measur (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R5 — Compute real median household income in 2023 dollars for each year and both geographies (nominal x CPI_2023 / CPI_year). (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R6 — Compute the percentage change from 2015 to 2023 for Indiana and the U.S., both nominal and real. (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R7 — Report the nominal values, the CPI-U values used, the adjusted values and the percentage changes for both geographies. (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R8 — Say why these sources fit (ACS B19013 and CPI-U CUUR0000SA0), including their limits: the 2020 gap, ACS margins of error, ACS values being in each survey year's (marked BLOCKED; checked by plain code on the final answer)
- NOT MET: R11 — Cite every figure with its source and date (data vintage and retrieval date). (the final answer does not cover it; checked by plain code on the final answer)
- OLD INPUT: step 8 used step 7's output from before step 7 was re-run for a missing input; it was not redone, so it may not match step 7's final output (added by plain code)

