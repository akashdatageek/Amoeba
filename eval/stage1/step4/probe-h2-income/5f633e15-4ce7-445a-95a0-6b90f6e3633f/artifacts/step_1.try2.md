**ACS B19013 1-year (standard) figures: NOT RETRIEVED. No value is filled in.**

I could not fetch any of the four B19013_001E estimates or margins of error (MOE) from a Census page. Nothing below comes from memory or estimation. The table lists the four required cells. Each cell is a gap.

| Geography | Survey year | B19013_001E (own-year dollars) | MOE | Source URL attempted | Release year | Retrieval date | Status |
|---|---|---|---|---|---|---|---|
| Indiana (state FIPS 18) | 2015 | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | Not confirmed | 2026-10-22 (run date given in the task) | The API returned a "Missing Key" page and no data [S1]. |
| United States | 2015 | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 | Not confirmed | 2026-10-22 (run date given in the task) | Not attempted. The first API call hit the missing-key block [S1], and I ran out of turns. |
| Indiana (state FIPS 18) | 2023 | NOT RETRIEVED | NOT RETRIEVED | https://data.census.gov/table/ACSDT1Y2023.B19013?g=040XX00US18 | Not confirmed | 2026-10-22 (run date given in the task) | The data.census.gov fetch failed ("Failed to fetch url"). An earlier data.census.gov API fetch timed out. No data was returned. |
| United States | 2023 | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 | Not confirmed | 2026-10-22 (run date given in the task) | Not attempted. See above. |

**What happened**
- The Census API request for Indiana 2015 returned a "Missing Key" page, not data. It was fetched 2026-10-23T00:00:47 UTC [S1]. A similar "Missing Key" page is saved as [S2]. The API appears to need a key, or to block unkeyed fetches from this environment.
- Two data.census.gov fetches for the 2023 Indiana B19013 table failed. One was an API URL that timed out. The other was the table page URL, which failed to fetch.
- The web search found the data.census.gov B19013 page only in its 5-year version (ACSDT5Y2023.B19013) [S17]. That is the wrong product, so I did not use it.
- The saved pages [S8] (ACS brief), [S9] (Income in the United States: 2024), [S10] (Data Profiles), [S13] and [S14] did not give a verified Indiana or US B19013 1-year value for 2015 or 2023 that clearly shows table, geography and year. I use none of them.
- I could not cross-check any value.

**Note:** Once retrieved, each value is in its own survey year's dollars. The 2015 survey is in 2015 dollars and the 2023 survey is in 2023 dollars. The CPI adjustment belongs to a later step.

**Needed to finish:** Re-run the API URLs above with a Census API key appended (`&key=...`). For Indiana 2023, use the same API pattern with `/data/2023/acs/acs1` and `for=state:18`. Alternatively, load the ACS 1-year B19013 table pages ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013 for Indiana and the United States.

**Consequence for later steps:** The CSV, bar chart and percentage changes cannot be produced from verified data until these four values are obtained. Do not substitute remembered values.
BLOCKED: Census API access (api.census.gov) — returned 'Missing Key' for the 2015 Indiana query, so no B19013_001E or MOE values could be fetched
BLOCKED: data.census.gov table fetch — the 2023 Indiana B19013 1-year table page and API both failed (timeout / failed to fetch)
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2015 — api.census.gov 2015 acs1 (Missing Key) [S1]
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2015 — api.census.gov (not attempted after key error)
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2023 — data.census.gov (fetch failed), search returned only the 5-year table [S17]
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2023 — not fetched; the only Census data access attempts failed
