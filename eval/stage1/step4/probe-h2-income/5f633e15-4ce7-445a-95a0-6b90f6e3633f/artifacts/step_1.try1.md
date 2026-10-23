**ACS B19013 (Median Household Income in the Past 12 Months, all households), variable B19013_001E, ACS 1-year standard: retrieval result**

I could not verify any of the four values. I did not fill any number from memory, so the estimate and MOE cells below are empty.

| Geography | Survey year | B19013_001E (dollars) | MOE (B19013_001M) | Source URL | Release year | Retrieval date |
|---|---|---|---|---|---|---|
| Indiana (state FIPS 18) | 2015 | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 returned "Missing Key" [S1] | 2016 [unverified] | 2026-10-22 |
| United States | 2015 | NOT RETRIEVED (the `for=us:1` query was not run) | NOT RETRIEVED | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (not fetched) | 2016 [unverified] | 2026-10-22 |
| Indiana (state FIPS 18) | 2023 | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 returned "Missing Key" [S2] | 2024 [unverified] | 2026-10-22 |
| United States | 2023 | NOT RETRIEVED (the `for=us:1` query was not run) | NOT RETRIEVED | https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (not fetched) | 2024 [unverified] | 2026-10-22 |

**What happened**
- The Census API query for Indiana in 2015 returned a "Missing Key" page, not data [S1]. The same query for 2023 did the same [S2]. The API appears to need a key from this environment. I did not run the `us:1` queries because they would almost certainly fail the same way.
- A web search for the 2023 Indiana value surfaced Census pages [S3]–[S9]. I fetched the Census brief "Household Income in States and Metropolitan Areas: 2024" (https://www.census.gov/library/publications/2025/acs/acsbr-025.html) [S8]. The part of the result I could read contained no Indiana or US B19013 figure. The page covers ACS 2023 and 2024 estimates, so a later step could read its state table for 2023 values. I have not seen those values and cannot confirm them.
- No data.census.gov table page for 2015 was found or fetched. No cross-check was possible.

**Note:** each B19013 value, once obtained, is in its own survey year's dollars, so the 2015 value is in 2015 dollars and the 2023 value is in 2023 dollars. The values are not yet inflation-adjusted.

**Gap for later steps:** all four estimates and MOEs are missing. Options are:
- a Census API key;
- the data.census.gov table B19013 pages for 2015 and 2023;
- Census's ACS 1-year state income tables for 2015 and 2023, such as the 2015 and 2023 ACS Income briefs or the Census table CSV files.

The release years and the row dates are for labelling only. Only the retrieval timestamps for [S1] and [S2] (2026-10-23 UTC, which is 2026-10-22 in America/Chicago) come from a tool.
BLOCKED: Census API access (API key) — api.census.gov returned 'Missing Key' for the 2015 and 2023 B19013 queries, so no values could be retrieved
BLOCKED: data.census.gov table fetch — no B19013 table page with Indiana or US values for 2015 or 2023 was retrieved
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2015 — api.census.gov (Missing Key); no table page found
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2015 — api.census.gov us:1 query not run; no table page found
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2023 — api.census.gov (Missing Key); census.gov brief acsbr-025 fetched but no Indiana value seen in the readable portion
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2023 — api.census.gov us:1 query not run; no value seen in the readable portion of acsbr-025
