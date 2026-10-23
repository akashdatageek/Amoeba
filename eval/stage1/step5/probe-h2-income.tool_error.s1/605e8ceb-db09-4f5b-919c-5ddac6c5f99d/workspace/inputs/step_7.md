I read "between 2015 and 2023" as Every year from 2015 through 2023, inclusive; if you meant Only the two endpoint years, 2015 and 2023, the answer below may not apply.

**Result in one line:** `income_cpi_adjusted.csv` exists, but every ACS income cell is blank. Steps 1–5 could not retrieve any B19013 value, because the Census API returned "Missing Key" [S53][S58][S31]. I did not fill, estimate or recall any ACS value. So there are no adjusted incomes, ratios, gaps or percent changes. The CPI-U values and the deflation factors are complete.

**File:** income_cpi_adjusted.csv, in the workspace (6,352 bytes, written 2026-10-23 [S66]). It has the 12 required columns, 18 data rows (2015–2023 × Indiana and United States) and 2 summary rows with year = "2015-2023" [S66]. I re-read it and it parsed as 20 rows [S66]. The 2020 rows carry the note "EXPERIMENTAL: no standard 2020 ACS 1-year release (pandemic nonresponse); ACS value UNAVAILABLE…" [S65]. The CPI-U values are copied from the BLS API, series CUUR0000SA0, annual average M13, retrieved 2026-10-23 [S59][S63]. Every row's `acs_source_url` is the api.census.gov request URL for that year and geography. Every row's `cpi_source_url` is https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true [S59].

**Calculation log**

Factor = CPI_2023 / CPI_year = 304.702 / CPI_year, computed in the sandbox [S66]. "blank" means the value was not retrieved. The "formula check" column is n/a because there is no nominal value to test.

| year | geography | nominal | CPI-U (1982-84=100) | factor | adjusted 2023 $ | Indiana as % of U.S. | gap $ | formula check |
|---|---|---|---|---|---|---|---|---|
| 2015 | Indiana | blank | 237.017 [S63] | 1.2856 [S66] | blank | blank | blank | n/a |
| 2015 | United States | blank | 237.017 [S63] | 1.2856 [S66] | blank | blank | blank | n/a |
| 2016 | Indiana | blank | 240.007 [S63] | 1.2696 [S66] | blank | blank | blank | n/a |
| 2016 | United States | blank | 240.007 [S63] | 1.2696 [S66] | blank | blank | blank | n/a |
| 2017 | Indiana | blank | 245.120 [S63] | 1.2431 [S66] | blank | blank | blank | n/a |
| 2017 | United States | blank | 245.120 [S63] | 1.2431 [S66] | blank | blank | blank | n/a |
| 2018 | Indiana | blank | 251.107 [S63] | 1.2134 [S66] | blank | blank | blank | n/a |
| 2018 | United States | blank | 251.107 [S63] | 1.2134 [S66] | blank | blank | blank | n/a |
| 2019 | Indiana | blank | 255.657 [S63] | 1.1918 [S66] | blank | blank | blank | n/a |
| 2019 | United States | blank | 255.657 [S63] | 1.1918 [S66] | blank | blank | blank | n/a |
| 2020 (EXPERIMENTAL) | Indiana | blank | 258.811 [S63] | 1.1773 [S66] | blank | blank | blank | n/a |
| 2020 (EXPERIMENTAL) | United States | blank | 258.811 [S63] | 1.1773 [S66] | blank | blank | blank | n/a |
| 2021 | Indiana | blank | 270.970 [S63] | 1.1245 [S66] | blank | blank | blank | n/a |
| 2021 | United States | blank | 270.970 [S63] | 1.1245 [S66] | blank | blank | blank | n/a |
| 2022 | Indiana | blank | 292.655 [S63] | 1.0412 [S66] | blank | blank | blank | n/a |
| 2022 | United States | blank | 292.655 [S63] | 1.0412 [S66] | blank | blank | blank | n/a |
| 2023 | Indiana | blank | 304.702 [S63] | 1.0000 [S66] | blank (will equal nominal) | blank | blank | n/a |
| 2023 | United States | blank | 304.702 [S63] | 1.0000 [S66] | blank (will equal nominal) | blank | blank | n/a |

**Percent-change table, 2015 to 2023**

| geography | nominal % change | real (2023 $) % change | status |
|---|---|---|---|
| Indiana | blank | blank | not computable: 2015 and 2023 ACS values missing |
| United States | blank | blank | not computable: 2015 and 2023 ACS values missing |
| CPI-U, all items, annual average (context) | 28.6% = (304.702 / 237.017 − 1) × 100 [S66] | n/a | computed from [S63] |

Any nominal income change below that CPI-U rise of 28.6% would be a real decline. This is context only, not a result.

**Assumptions**
- Years are every year from 2015 through 2023, inclusive, as the task states. This is the settled assumption.
- ACS means the standard 1-year release of detailed table B19013, with Indiana as state FIPS 18 and the United States as us:1.
- 2020 has only experimental ACS 1-year estimates. Any 2020 value must be labelled EXPERIMENTAL, and the CSV flags it.
- CPI-U is NSA, U.S. city average, all items, annual average (M13). The 1982-84=100 base comes from the task's interpretation. It is not quoted from a fetched BLS page.
- The 5-year B19013 files in the workspace (S34, S35, S37, S38) are a different product. I did not substitute them for 1-year values.
- No ACS value was invented. Missing cells are blank, and the note column says why.

**Formulas**
- adjusted_2023 = nominal × CPI_2023 / CPI_year. For 2023 the factor is 1, so adjusted equals nominal.
- nominal % change = (nominal_2023 / nominal_2015 − 1) × 100.
- real % change = (adjusted_2023 for 2023 / adjusted_2023 for 2015 − 1) × 100.
- Indiana as % of U.S. = Indiana adjusted / U.S. adjusted × 100.
- gap $ = Indiana adjusted − U.S. adjusted.
- All are computed from unrounded values.

**Rounding rules**
- CPI to 3 decimals, dollars to the nearest dollar, percentages to one decimal place.
- Factors are shown to 4 decimals for display only.

**Why these sources fit**
- B19013 is the Census Bureau's own median household income table, and it gives a margin of error (B19013_001M). It is titled in the survey year's inflation-adjusted dollars [unverified]. Values for different years therefore sit in different dollars, and a common-year CPI-U deflator is needed.
- CPI-U all items, U.S. city average, is the BLS headline price index. Its annual average matches the annual ACS reference period.

**To finish:** rerun the 18 api.census.gov URLs in the CSV with a free Census API key (`&key=...`), or read table B19013 on data.census.gov. Then rerun build.py (in the workspace) with the values filled in `nom`. build.py currently has `nom = {}`. That will fill the adjusted values, the ratios and gaps, and the summary percent changes. The chart step cannot plot real incomes until those values exist.
BLOCKED: Census API key — ACS 1-year B19013 values for Indiana and the U.S., 2015–2023, could not be retrieved (Missing Key), so adjusted values, ratios, gaps and percent changes could not be computed
MISSING DATA: ACS 1-year B19013_001E and B19013_001M, Indiana and United States, 2015–2019 and 2021–2023 — api.census.gov (Missing Key / timeout) and data.census.gov saved pages (steps 1–5)
MISSING DATA: ACS 2020 experimental B19013, Indiana and United States — files S41 and S42 contain no 'median household' text (grep found no match [S65])
MISSING INPUT: ACS B19013 estimates and margins of error for all 18 year-geography pairs — steps 1–5 (all UNAVAILABLE)