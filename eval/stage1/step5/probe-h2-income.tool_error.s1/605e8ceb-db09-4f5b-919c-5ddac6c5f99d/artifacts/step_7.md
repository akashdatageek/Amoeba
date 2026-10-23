I read "between 2015 and 2023" as Every year from 2015 through 2023, inclusive; if you meant Only the two endpoint years, 2015 and 2023, the answer below may not apply.

**Step 7 result: PARTIAL. The CSV was written, but every ACS B19013 value is blank.** Steps 1–5 could not retrieve any ACS 1-year B19013 estimate or margin of error for Indiana or the U.S. for any year in the range. api.census.gov returned a "Missing Key" page or timed out [S8, S13, S17, S31, S48, S53, S58]. I did not fill any value from memory, so there are no adjusted values or income percentage changes. Only the CPI-U side is complete.

**File:** `income_cpi_adjusted.csv` is in the workspace. It has 21 lines: 1 header, 21 lines (1 header, 18 data rows, 2 summary rows) and 12 col data rows (9 years × 2 geographies) and 2 summary rows with year='2015-2023' [S111]. The 12 required columns are present [S110]. `acs_nominal_usd`, `acs_moe_usd`, `adjusted_2023_usd` and the two percent-change columns are empty. The `note` column says "ACS B19013 value UNAVAILABLE…". The experimental-year rows start with "EXPERIMENTAL (no standard 2020 ACS 1-year release)". The retrieved date is 2026-10-23 in every row.

**Calculation log**

CPI-U is series CUUR0000SA0, annual average, 1982-84=100. The values are from the BLS API v2 M13 records, fetched 2026-10-23 [S59, S63]. URL: https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true

The multiplier is CPI_2023 / CPI_year = 304.702 / CPI_year. It is computed from the CPI values in the table [S110].

| year | geography | nominal (ACS B19013) | CPI | adjusted 2023 $ | Indiana as % of U.S. | gap $ (IN − US) | formula check |
|---|---|---|---|---|---|---|---|
| 2015 | Indiana | UNAVAILABLE | 237.017 [S63] | n/a | n/a | n/a | multiplier 1.2856; no nominal to check |
| 2015 | United States | UNAVAILABLE | 237.017 [S63] | n/a | n/a | n/a | multiplier 1.2856; no nominal to check |
| 2016 | Indiana | UNAVAILABLE | 240.007 [S63] | n/a | n/a | n/a | multiplier 1.2696; no nominal to check |
| 2016 | United States | UNAVAILABLE | 240.007 [S63] | n/a | n/a | n/a | multiplier 1.2696; no nominal to check |
| 2017 | Indiana | UNAVAILABLE | 245.120 [S63] | n/a | n/a | n/a | multiplier 1.2431; no nominal to check |
| 2017 | United States | UNAVAILABLE | 245.120 [S63] | n/a | n/a | n/a | multiplier 1.2431; no nominal to check |
| 2018 | Indiana | UNAVAILABLE | 251.107 [S63] | n/a | n/a | n/a | multiplier 1.2134; no nominal to check |
| 2018 | United States | UNAVAILABLE | 251.107 [S63] | n/a | n/a | n/a | multiplier 1.2134; no nominal to check |
| 2019 | Indiana | UNAVAILABLE | 255.657 [S63] | n/a | n/a | n/a | multiplier 1.1918; no nominal to check |
| 2019 | United States | UNAVAILABLE | 255.657 [S63] | n/a | n/a | n/a | multiplier 1.1918; no nominal to check |
| 2020 (EXPERIMENTAL) | Indiana | UNAVAILABLE | 258.811 [S63] | n/a | n/a | n/a | multiplier 1.1773; no nominal to check |
| 2020 (EXPERIMENTAL) | United States | UNAVAILABLE | 258.811 [S63] | n/a | n/a | n/a | multiplier 1.1773; no nominal to check |
| 2021 | Indiana | UNAVAILABLE | 270.970 [S63] | n/a | n/a | n/a | multiplier 1.1245; no nominal to check |
| 2021 | United States | UNAVAILABLE | 270.970 [S63] | n/a | n/a | n/a | multiplier 1.1245; no nominal to check |
| 2022 | Indiana | UNAVAILABLE | 292.655 [S63] | n/a | n/a | n/a | multiplier 1.0412; no nominal to check |
| 2022 | United States | UNAVAILABLE | 292.655 [S63] | n/a | n/a | n/a | multiplier 1.0412; no nominal to check |
| 2023 | Indiana | UNAVAILABLE | 304.702 [S63] | n/a (would equal nominal) | n/a | n/a | multiplier 1.0000, so adjusted = nominal by construction |
| 2023 | United States | UNAVAILABLE | 304.702 [S63] | n/a (would equal nominal) | n/a | n/a | multiplier 1.0000, so adjusted = nominal by construction |

The CPI side was checked with a local script: 304.702/237.017 = 1.2856 and 304.702/304.702 = 1.0000 [S110]. No two-row check of the adjusted-value formula on real data was possible, because there are no nominal values.

**Percent-change table, 2015 → 2023**

| measure | Indiana | United States |
|---|---|---|
| Nominal median household income change | n/a (2015 and 2023 ACS values unavailable) | n/a (2015 and 2023 ACS values unavailable) |
| Real change in 2023 dollars | n/a (same reason) | n/a (same reason) |
| CPI-U change 2015 → 2023 (the only computable figure) | 28.6% = (304.702/237.017 − 1) × 100 [S110] | same |

Both summary rows in the CSV carry this CPI-U change in the note column.

**Assumptions**
- "Between 2015 and 2023" means every year from 2015 through 2023, inclusive (the task's working assumption).
- Income is ACS 1-year, standard release, table B19013 (B19013_001E estimate, B19013_001M margin of error). Each vintage is in its own survey year's dollars [unverified]. That is why every year needs CPI re-adjustment to 2023 dollars.
- The experimental year has no standard 1-year release, only experimental estimates. It is flagged EXPERIMENTAL in the CSV note. No value for it was retrieved.
- CPI-U is the not seasonally adjusted, 1982-84=100, U.S. city average, all items annual average (M13), used as published by BLS [S59, S63]. The base year and the meaning of the series ID come from the task's working interpretation and BLS convention. No fetched BLS page states them [S63].
- The 5-year B19013 pages seen in earlier steps are a different product and were not substituted.
- Indiana is the State of Indiana (FIPS 18). The U.S. is us:1.

**Formulas**
- adjusted_2023 = nominal × CPI_2023 / CPI_year, using the unrounded CPI values.
- nominal % change = (nominal_2023 / nominal_2015 − 1) × 100.
- real % change = (adjusted_2023 for 2023 / adjusted_2023 for 2015 − 1) × 100. The 2023 adjusted value equals the 2023 nominal value.
- Indiana as % of U.S. = adjusted_IN / adjusted_US × 100.
- gap $ = adjusted_IN − adjusted_US.
- All are calculated from unrounded values and rounded only for display.

**Rounding rules:** CPI to three decimals, dollars to the nearest dollar, percentages to one decimal place. Multipliers are shown to four decimals for reference only.

**To complete:** get the 18 ACS B19013 estimates and margins of error with a free Census API key (`&key=...`) on the URL pattern https://api.census.gov/data/{year}/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 (and `for=us:1`). Alternatively, read data.census.gov tables ACSDT1Y{year}.B19013. Then fill the `NOM` dict in `build_csv.py` and re-run it. The script is already in the workspace.

File name: income_cpi_adjusted.csv
BLOCKED: Census API key / data.census.gov access — the ACS 1-year B19013 estimates and margins of error for Indiana and the U.S. could not be retrieved, so adjusted values, ratios, gaps and income percentage changes could not be computed
MISSING DATA: ACS 1-year B19013_001E and _001M, Indiana and United States, every year 2015 to 2023 (2020 experimental) — api.census.gov (Missing Key/timeouts, steps 1–5), data.census.gov (fetch failed), saved sources S99/S101 (no B19013 values)
MISSING INPUT: ACS B19013 values for 2015 to 2023, Indiana and United States — steps 1–5 (all UNAVAILABLE)
