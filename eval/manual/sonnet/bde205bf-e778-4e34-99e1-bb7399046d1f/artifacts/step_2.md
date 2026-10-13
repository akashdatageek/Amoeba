**STATUS: done_when NOT met.** No value was confirmed on two BLS paths. 2023 = 304.702 is confirmed only by secondary sources [S10][S12][S14]. 2015 is not confirmed by any tool result.

### CPI source table
Retrieval date: 2026-10-13 (as of the fetch). Series CUUR0000SA0: CPI-U, all items, U.S. city average, not seasonally adjusted, base period 1982-84=100 [S16].

| year | series ID | annual average | base period | primary path + URL | second path + URL | retrieval date | match? |
|---|---|---|---|---|---|---|---|
| 2015 | CUUR0000SA0 | **Not retrieved.** From my own memory about 237.017 [unverified]. The task's sanity expectation is "about 237" (task instruction, not a source), and this value is consistent with it. | 1982-84=100 [S16] | BLS API v1, M13: https://api.bls.gov/publicAPI/v1/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2015 [S9]. The response held only 2024–2026 rows, with no 2015 row. | BLS Data Viewer: https://data.bls.gov/timeseries/CUUR0000SA0?years_option=all_years&include_graphs=false&annual_averages=true [S16]. The fetch was truncated at 6,000 of 14,667 characters (the table had reached only the late 1950s), so no 2015 row was seen. | 2026-10-13 | **NO. Unverified.** |
| 2023 | CUUR0000SA0 | **304.702** (secondary sources only) | 1982-84=100 [S16] | BLS API v1: https://api.bls.gov/publicAPI/v1/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023 [S8]. The response held only 2024–2026 rows, with no 2023 row. | BLS Data Viewer [S16], truncated, no 2023 row. | 2026-10-13 | **NO. Not confirmed on two BLS paths.** Secondary agreement: CPSC document citing BLS series CUUR0000SA0, "2023 index = 304.702" [S10]; surecalcs.com table, 2023 = 304.702 [S12]; commoditieshistory.com, 304.702 "BLS annual average" [S14]. These are not BLS pages, so they are cross-checks only. |

Supporting checks:
- The BLS API returned 2024 annual (M13) = 313.689 and 2025 annual (M13) = 321.943 [S8].
- S12 reproduces both exactly (2024 = 313.689, 2025 = 321.943) [S12]. This is some evidence that S12 mirrors BLS correctly, but it is not an official source.
- S10 gives 2013 = 232.957 [S10]. This fits a 2015 value near the expected 237.
- Sanity range: 2023 = 304.702 [S10][S12] is close to the task's expected "about 305". 2015 cannot be checked from the tool results.

### Provisional adjustment factor
This depends on the unverified 2015 value (237.017 [unverified]):
- 304.702 / 237.017 = 1.2856, so 2015 dollars × 1.2856 gives 2023 dollars.
- This is provisional and must not be treated as final until 2015 is confirmed from BLS.

### Paths tried, so the auditor can choose different ones
- Tried:
  - BLS API v1, two requests [S8][S9]. Both returned only 2024–2026 rows and ignored the year parameters.
  - Data Viewer all-years page [S16], truncated.
  - A Data Viewer specific-years request (2015–2023) was blocked by the fetch limit of 3 per step, so it returned nothing.
- Not yet tried:
  - The Data Viewer with `years_option=specific_years&from_year=2015&to_year=2015` (and the same for 2023).
  - The BLS historical CPI-U table at bls.gov/cpi/tables/supplemental-files (cpiai.txt).
  - The BLS CPI news release annual-average tables for Dec 2015 and Dec 2023.
  - The BLS API v2 with a registration key.
  - Fetching the rest of S16 beyond character 6,000.

### Latest-value note
The latest monthly CPI-U in the API is August 2026 = 334.980 (as of the fetch on 2026-10-13) [S8]. It is not needed here, because the task compares fixed annual averages for 2015 and 2023 (2023 dollars). The most recent annual average available is 2025 = 321.943 [S8].

### Why CPI-U (rationale)
1. **Official BLS series.** CUUR0000SA0 is the headline all-items U.S. city average index, base 1982-84=100 [S16]. It is the index BLS features in its monthly release (per S12, non-official).
2. **Annual average matches the survey.** ACS 1-year estimates describe a calendar-year reference period [unverified]. The annual-average CPI-U (M13) fits that better than a December-to-December change.
3. **Final when issued.** The not-seasonally-adjusted CPI-U is not revised after release (per S12, non-official; it supports but is not the authority). Converted dollars therefore will not shift later.
4. **Widely used and covers most households.** CPI-U covers the urban population, which is most U.S. households [unverified]. It is a standard deflator for income comparisons.
5. **Matches the working interpretation** fixed for this task: CPI-U, U.S. city average, annual average.

Caveats:
- It is a national index, not Indiana's own price level. Applying it to Indiana assumes Indiana prices moved like the national average.
- CPI-U-RS (a research series Census uses for some income tables) and C-CPI-U (chained) exist and would give slightly different adjustments [unverified].
- Annual averages are rounded to three decimals, so percent changes are accurate only to that precision.
- The 2025 annual average is affected by the missing October 2025 observation (lapse in appropriations) [S8]. This does not affect 2015 or 2023.

BLOCKED: complete BLS-sourced retrieval of the 2015 and 2023 M13 values — the API ignored the year range, the Data Viewer fetch was truncated, and the fetch limit was reached. 2015 is unverified, and 2023 rests on secondary sources.
