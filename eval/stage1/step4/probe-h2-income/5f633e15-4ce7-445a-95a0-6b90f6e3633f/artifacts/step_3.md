I read "between 2015 and 2023" as Endpoints only: 2015 and 2023; if you meant Every year from 2015 through 2023, with change from 2015 to 2023, the answer below may not apply.

**Step 3 result: the real-income calculation could NOT be completed, because step 1 delivered none of the four ACS B19013 values.** I did not fill any ACS figure from memory. I computed only what the verified CPI inputs allow.

**CPI inputs (from step 2; series CUUR0000SA0, CPI-U NSA, 1982-84=100, annual average M13)**
- 2015 = 237.017 [S55]
- 2023 = 304.702 [S57]
- Both values match the BLS cross-check table [S46].

**Computed deflator factors** (CPI2023 / CPIyear; script calc.py output [S65])
- 2015 factor = 304.702 / 237.017 = 1.2855702333587886
- 2023 factor = 304.702 / 304.702 = 1.0
- Because the 2023 factor is exactly 1.0, the 2023 adjusted value will equal the 2023 nominal value once that nominal value is available.

**Results table** (retrieval date 2026-10-22). ACS source attempted: Census API api.census.gov/data/{year}/acs/acs1, variable B19013_001E. It returned "Missing Key" [S1]. CPI source: BLS Public API series CUUR0000SA0 [S44], cross-checked against the BLS table [S46].

| Geography | Year | Nominal median household income | CPI-U annual avg | CPI base (2023) | Adjusted 2023 dollars | Nominal % change 2015-2023 | Real % change 2015-2023 |
|---|---|---|---|---|---|---|---|
| Indiana | 2015 | NOT RETRIEVED | 237.017 [S55] | 304.702 [S57] | NOT COMPUTED (= nominal × 1.2855702333587886) | NOT COMPUTED | NOT COMPUTED |
| Indiana | 2023 | NOT RETRIEVED | 304.702 [S57] | 304.702 [S57] | NOT COMPUTED (= nominal × 1.0) | NOT COMPUTED | NOT COMPUTED |
| United States | 2015 | NOT RETRIEVED | 237.017 [S55] | 304.702 [S57] | NOT COMPUTED (= nominal × 1.2855702333587886) | NOT COMPUTED | NOT COMPUTED |
| United States | 2023 | NOT RETRIEVED | 304.702 [S57] | 304.702 [S57] | NOT COMPUTED (= nominal × 1.0) | NOT COMPUTED | NOT COMPUTED |

**File: figures.csv**
- calc.py wrote figures.csv in the workspace. I re-read it and it has 4 data rows and all 11 required columns: geography, year, nominal_median_household_income, cpi_u_annual_avg, cpi_base_2023, adjusted_2023_dollars, nominal_pct_change_2015_2023, real_pct_change_2015_2023, acs_source, cpi_source, retrieval_date [S65].
- **The file is only a skeleton.** The CPI columns are real. The nominal, adjusted and percent-change cells hold the text "NOT RETRIEVED" or "NOT COMPUTED". The acs_source cells record the attempted API URL and say "NOT RETRIEVED (Missing Key)".
- The file must not be used as a data table until the four ACS values are supplied and calc.py is re-run.

**Which geography gained more in real terms:** this cannot be determined without the ACS values. I will not guess.

**To finish:** supply the ACS 1-year B19013_001E values for Indiana and the United States for 2015 and 2023, either through a Census API key or from the data.census.gov tables ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013. Then re-run calc.py with these formulas:
- adjusted = nominal × 304.702 / CPIyear
- nominal % change = nominal2023 / nominal2015 − 1
- real % change = adjusted2023 / adjusted2015 − 1

Searches of the saved sources found no usable ACS 1-year values. The only mention of Indiana is in the CPS report [S18], which is a different survey, and the ACS 5-year page [S17] is the wrong product [S64].
BLOCKED: Census ACS data access (API key / data.census.gov fetch) — the ACS 1-year B19013 values for Indiana and the United States for 2015 and 2023 could not be obtained, so adjusted values and percentage changes could not be computed
MISSING DATA: Indiana B19013_001E ACS 1-year 2015 — api.census.gov (Missing Key) [S1], saved sources [S64]
MISSING DATA: United States B19013_001E ACS 1-year 2015 — api.census.gov, saved sources
MISSING DATA: Indiana B19013_001E ACS 1-year 2023 — api.census.gov, data.census.gov, saved sources
MISSING DATA: United States B19013_001E ACS 1-year 2023 — api.census.gov, data.census.gov, saved sources
MISSING INPUT: ACS B19013 1-year estimates for Indiana and United States, 2015 and 2023 — step 1 (status partial, no values delivered)
