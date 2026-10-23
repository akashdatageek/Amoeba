I read "between 2015 and 2023" as Every year from 2015 through 2023, inclusive; if you meant Only the two endpoint years, 2015 and 2023, the answer below may not apply.

**Step 7 result: the CSV is written, but no ACS B19013 value exists, so no adjusted value or percent change could be computed.**
File: income_cpi_adjusted.csv, saved in the workspace. A re-read showed 20 rows (18 data rows plus 2 summary rows) and the 12 required columns [S98].

**ACS B19013 values (required by later steps): all 18 are UNAVAILABLE.** No step returned a value, and I did not fill any from memory.
- Steps 1–5 got a "Missing Key" page, a timeout, or no usable data from api.census.gov and data.census.gov for every year from 2015 through 2023 (Indiana and U.S.).
- My search of the saved sources for B19013 Indiana and U.S. figures found none [S96][S97].
- The ACS cells (acs_nominal_usd, acs_moe_usd) are blank in the CSV. The note column says "ACS B19013 value UNAVAILABLE (Census API returned Missing Key; not filled from memory); adjusted value not computed" [S98].
- The 2020 rows start with "EXPERIMENTAL (no standard 2020 ACS 1-year release)" in the note column [S98]. The Census Bureau published only experimental 2020 1-year estimates (settled working interpretation).

**Calculation log**
CPI-U values are BLS API v2 annual averages (M13) for series CUUR0000SA0, fetched 2026-10-23 [S59]. Index base 1982-84=100.

| year | geography | nominal (ACS B19013) | CPI-U | adjusted 2023 $ | Indiana as % of U.S. | gap $ | formula check |
|---|---|---|---|---|---|---|---|
| 2015 | Indiana | UNAVAILABLE | 237.017 [S59] | not computed | not computed | not computed | factor 304.702/237.017 = 1.28557 (calc); no nominal to apply it to |
| 2015 | United States | UNAVAILABLE | 237.017 [S59] | not computed | not computed | not computed | same factor; no nominal |
| 2016 | Indiana | UNAVAILABLE | 240.007 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2016 | United States | UNAVAILABLE | 240.007 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2017 | Indiana | UNAVAILABLE | 245.120 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2017 | United States | UNAVAILABLE | 245.120 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2018 | Indiana | UNAVAILABLE | 251.107 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2018 | United States | UNAVAILABLE | 251.107 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2019 | Indiana | UNAVAILABLE | 255.657 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2019 | United States | UNAVAILABLE | 255.657 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2020 (EXPERIMENTAL) | Indiana | UNAVAILABLE | 258.811 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2020 (EXPERIMENTAL) | United States | UNAVAILABLE | 258.811 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2021 | Indiana | UNAVAILABLE | 270.970 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2021 | United States | UNAVAILABLE | 270.970 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2022 | Indiana | UNAVAILABLE | 292.655 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2022 | United States | UNAVAILABLE | 292.655 [S59] | not computed | not computed | not computed | formula only; no nominal |
| 2023 | Indiana | UNAVAILABLE | 304.702 [S59] | not computed (will equal nominal) | not computed | not computed | factor 304.702/304.702 = 1, so adjusted = nominal once a value is supplied |
| 2023 | United States | UNAVAILABLE | 304.702 [S59] | not computed (will equal nominal) | not computed | not computed | same: factor = 1 |

**Percent-change table, 2015 to 2023**

| geography | nominal % change | real (2023 $) % change | status |
|---|---|---|---|
| Indiana | blank | blank | the 2015 and 2023 ACS values are unavailable |
| United States | blank | blank | the 2015 and 2023 ACS values are unavailable |

The CSV has two summary rows (year = "2015-2023", one per geography). Their percent-change cells are blank, and the note says why [S98].

One CPI-only figure can be computed: the CPI-U rose by 304.702/237.017 − 1 = 1.28557 − 1 = 28.6% from 2015 to 2023 (calc result 1.28557). This applies to prices, not to income.

**Assumptions**
- The year range is every year from 2015 through 2023, inclusive.
- Income is ACS 1-year B19013_001E (estimate) and B19013_001M (margin of error), standard release. 2020 is experimental only.
- Inflation is the NSA CPI-U, all items, U.S. city average, annual average (M13), base 1982-84=100. The base period and series-ID meaning rest on the task's working interpretation and are not quoted from a fetched BLS page (Step 6).
- Each ACS vintage is in its own survey-year dollars [unverified]. That is why every year is re-based to 2023 dollars.
- No ACS value was estimated, interpolated or taken from 5-year tables. Missing values stay blank.

**Formulas**
- adjusted_2023 = nominal × CPI_2023 / CPI_year, with CPI_2023 = 304.702 [S59].
- nominal % change = (nominal_2023 / nominal_2015 − 1) × 100.
- real % change = (adjusted_2023 in 2023 / adjusted_2023 in 2015 − 1) × 100.
- Indiana as % of U.S. = Indiana adjusted / U.S. adjusted × 100.
- gap $ = Indiana adjusted − U.S. adjusted.
- All are computed from unrounded numbers.

**Rounding rules**
- CPI is shown to 3 decimals.
- Dollars are rounded to the nearest dollar.
- Percentages are rounded to one decimal place.

**To finish:** supply a free Census API key, or the B19013 values from data.census.gov (ACSDT1Y2015 to ACSDT1Y2023, Indiana and U.S.). Then fill the ACS dict in build_csv.py and re-run it. The script already holds the CPI values, the formulas and the URLs.

**Success criteria not met:** the adjusted values, the percent changes and the formula check on real numbers could not be produced, because the nominal inputs are missing.

Retrieval date for every row is 2026-10-23.
BLOCKED: Census API key — ACS B19013 values for 2015–2023 (Indiana and U.S.) could not be obtained, so adjusted values and percent changes could not be computed
MISSING DATA: ACS 1-year B19013_001E and B19013_001M, Indiana and United States, 2015–2023 — api.census.gov (Missing Key/timeout), data.census.gov, saved sources searched [S96][S97]
MISSING INPUT: ACS B19013 values for 2015–2023 — steps 1, 2, 3, 4 and 5 (all returned UNAVAILABLE)
