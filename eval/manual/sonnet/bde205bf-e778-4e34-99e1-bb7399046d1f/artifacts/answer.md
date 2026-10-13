## Step 1: Retrieve ACS B19013 values

**Step 1 result: ACS 1-year B19013 retrieval. NOT COMPLETE. No estimate or margin of error was retrieved.**

Retrieval date: 2026-10-13 (today, America/Chicago).

| geography | year | B19013_001E | B19013_001M | dollar basis | primary path + URL | second path + URL | retrieval date | match? |
|---|---|---|---|---|---|---|---|---|
| United States | 2015 | NOT RETRIEVED | NOT RETRIEVED | not confirmed (expected "2015 inflation-adjusted dollars") | Census API, FAILED, "Missing Key": https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 [S1] | Not attempted (data.census.gov ACSDT1Y2015.B19013 not fetched) | 2026-10-13 | n/a |
| Indiana | 2015 | NOT RETRIEVED | NOT RETRIEVED | not confirmed | Census API for=state:18 not attempted for 2015 | Not attempted | 2026-10-13 | n/a |
| United States | 2023 | NOT RETRIEVED | NOT RETRIEVED | "2023 Inflation-Adjusted Dollars" (title of the table page) [S2] | Census API, FAILED, "Missing Key": https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 [S7] | data.census.gov table page loaded, but the cell values were not in the visible text: https://data.census.gov/table/ACSDT1Y2023.B19013?tid=ACSDT1Y2023.B19013 [S2] | 2026-10-13 | n/a |
| Indiana | 2023 | NOT RETRIEVED | NOT RETRIEVED | "2023 Inflation-Adjusted Dollars" [S2] | Census API for=state:18 not attempted for 2023 | Same data.census.gov page [S2]; Indiana values not visible | 2026-10-13 | n/a |

**Notes on failed paths and discrepancies**
- **Census API:** Both attempted requests (US 2015 and US 2023, without a key) returned "Missing Key: A valid key must be included with each data API request" [S1][S7]. No API key was available to me. The state:18 queries were not run, because they would have failed the same way.
- **data.census.gov, 2023 1-year:** The page ACSDT1Y2023.B19013 exists. It is titled "B19013 Median Household Income in the Past 12 Months (in 2023 Inflation-Adjusted Dollars)", universe Households, "2023: ACS 1-Year Estimates Detailed Tables" [S2]. The fetch returned only the first 6000 of 12165 characters, which were page navigation and filters. The data grid was not rendered. A search snippet showed a fragment "±186" with "United States" [S2]. I cannot tell which cell it belongs to, so I do not use it as a value.
- **2015 vintage:** I did not test it on any Census path. I cannot say whether it is retrievable. The role card's stop rule applies only if it proves unretrievable, so I only report that it is untested.
- **No cross-check was possible**, so every "match?" entry is n/a. There is no discrepancy to report, because no value was retrieved on any path.
- **Sanity check:** Not applicable, since no values were retrieved. I give no figures from memory.

**BLOCKED:** Census API key. Every api.census.gov request needs a key, and I had none, so the API values for 2015 and 2023 could not be retrieved.
**BLOCKED:** Rendering of data.census.gov table grids. The fetch returned only the page shell and no cell values.

**For the team:**
- Use the following paths, none of which was tried in this step:
  - the Census API with a free key (request it at the Census key signup page);
  - the data.census.gov 2015 page ACSDT1Y2015.B19013;
  - Census-hosted flat files or published ACS 1-year tables found via web_search.
- Do not use any income value in later steps until it is retrieved from Census with a cited URL.
- Source IDs: [S1] and [S7] are API "Missing Key" responses, and [S2] is the data.census.gov 2023 table shell.

## Step 2: Retrieve CPI-U annual averages and rationale

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

## Step 3: Compute, compare, write CSV, draw chart

sed -i 's/error bar = 90% MOE/error bar = 90%% MOE/' build.py && python3 build.py && ls -la mi_income_indiana_us.csv plotted_values.json real_median_household_income.png && cat plotted_values.json && python3 -c "
import csv
for r in csv.DictReader(open('mi_income_indiana_us.csv')): print(r['geography'],'|',r['metric'],'|',r['year'],'|',r['value'])
" | head -40

## Limitations
- Mislabelled citation: step 1 cites S1 for '2015 inflation-adjusted dollars', which S1 does not contain (added by plain code)
- Mislabelled citation: step 1 cites S1 for 'Missing Key: A valid key must be included with each data API request', which S1 does not contain (added by plain code)
- Mislabelled citation: step 1 cites S2 for '6000', which S2 does not contain (added by plain code)
- Mislabelled citation: step 1 cites S2 for '12165', which S2 does not contain (added by plain code)
- Mislabelled citation: step 2 cites S16 for '237.017', which S16 does not contain; it is in S12, S14 (added by plain code)
- Mislabelled citation: step 2 cites S16 for '304.702', which S16 does not contain; it is in S10, S12, S14 (added by plain code)

