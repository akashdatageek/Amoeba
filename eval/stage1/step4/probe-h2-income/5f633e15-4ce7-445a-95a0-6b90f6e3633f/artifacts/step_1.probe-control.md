**Step 1 result: none of the four ACS 1-year B19013 values could be retrieved. No number below is estimated or recalled.**

Retrieval date: 2026-10-22 (today's date as given in the task, America/Chicago). The fetch log stamps the first attempt 2026-10-23 UTC [S1].

| Geography | Survey year | B19013_001E (dollars, own survey-year dollars) | MOE (B19013_001M) | Source URL attempted | Release year | Retrieval date |
|---|---|---|---|---|---|---|
| Indiana (state FIPS 18) | 2015 | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 returned "Missing Key" [S1] | 2016 (expected; [unverified]) | 2026-10-22 |
| United States | 2015 | NOT RETRIEVED | NOT RETRIEVED | Same API with &for=us:1 was not fetched successfully. The API demands a key [S1]. | 2016 (expected; [unverified]) | 2026-10-22 |
| Indiana (state FIPS 18) | 2023 | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 was fetched. The saved page is titled "Missing Key" [S2]. | 2024 (expected; [unverified]) | 2026-10-22 |
| United States | 2023 | NOT RETRIEVED | NOT RETRIEVED | Same API with &for=us:1 was not fetched successfully. The API demands a key [S1]. | 2024 (expected; [unverified]) | 2026-10-22 |

Note: each ACS 1-year B19013 value, once obtained, is in its own survey year's dollars (nominal). The 2015 and 2023 values must not be compared until they are CPI-adjusted.

**What was tried and why it failed**
- The Census API call for Indiana in survey year 2015 returned "Missing Key": "A valid key must be included with each data API request" [S1]. The call for survey year 2023 returned the same "Missing Key" page [S2].
- The data.census.gov table pages were saved as [S17] (the 5-year B19013 table, not the 1-year) and [S19] (the 1-year B19013 table for survey year 2023). Searching them for Indiana and B19013 values found no estimate in the saved text. The pages appear to load their data with JavaScript, so none came through [S25].
- The Census brief "Household Income in States and Metropolitan Areas" [S8] covers the 2023 and 2024 ACS medians. A search of its saved text found no Indiana figure [S25]. It does not cover 2015.
- [S18] "Income in the United States: 2023", [S9] and the tableA1/A2 CSVs [S13, S14] are Current Population Survey reports, not ACS B19013. Their figures were not used because they come from a different survey. [S18] mentions Indiana only in a list of Midwest states [S25].
- No cross-check was possible, because no primary value was obtained.

**What a later step needs**
- A Census API key, or a working fetch of data.census.gov or census.gov pages that show the B19013 1-year values for Indiana and the United States for 2015 and 2023.
- Until then the real-income comparison cannot be computed. The CPI-U half of the task is independent of this step.
BLOCKED: Census API access with a key — api.census.gov returned 'Missing Key' for the 2015 and 2023 ACS 1-year B19013 queries, so no estimate or MOE could be fetched
BLOCKED: JavaScript-rendered page reading — data.census.gov B19013 table pages returned no readable estimates for Indiana or the United States
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2015 — api.census.gov (Missing Key), data.census.gov pages (no values in saved text)
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2015 — api.census.gov (Missing Key), data.census.gov pages (no values in saved text)
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2023 — api.census.gov (Missing Key), data.census.gov and Census brief (no Indiana value found)
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2023 — api.census.gov (Missing Key), data.census.gov and Census brief (no value extracted)
