**2023 ACS 1-year B19013 (median household income): both values are UNAVAILABLE. I did not fill them from memory.** Both Census API calls returned a "Missing Key" page, not data. Both were fetched on 2026-10-23.

| year | geography | B19013 estimate | MOE | source URL | vintage | retrieved date |
|---|---|---|---|---|---|---|
| 2023 | Indiana (state:18) | UNAVAILABLE. The API returned a "Missing Key" page [S53]. | UNAVAILABLE | https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 [S53] | 2023 ACS 1-year, standard release (requested) | 2026-10-23 |
| 2023 | United States (us:1) | UNAVAILABLE. The API returned a "Missing Key" page [S58]. | UNAVAILABLE | https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 [S58] | 2023 ACS 1-year, standard release (requested) | 2026-10-23 |

**Limitation:**
- Both api.census.gov calls (fetched 2026-10-23) said "A valid key must be included with each data API request" [S53, S58]. No key was available in this environment.
- A search of the saved workspace files found no 2023 B19013 figure for Indiana or the U.S. [S57].
- To finish, rerun the two URLs above with a free Census API key (`&key=...`). Alternatively, read the values from data.census.gov table ACSDT1Y2023.B19013 for Indiana and the United States.

**Documentation points (fit rationale).** I did not fetch any of these pages in this step. All three come from my own knowledge, so each is tagged [unverified] and needs checking against the URL given.
- **"Inflation-adjusted dollars" in B19013.** The table is titled "Median household income in the past 12 months (in [survey year] inflation-adjusted dollars)" [unverified]. Each ACS vintage is expressed in that survey year's own dollars, so 2015 to 2023 values must be re-adjusted to 2023 dollars with CPI-U. This is why the task pairs ACS with CPI-U [unverified]. Table page: https://data.census.gov/table/ACSDT1Y2023.B19013 [unverified; not fetched].
- **Primary-source API with margins of error.** B19013_001E is the estimate and B19013_001M is its margin of error [unverified]. The endpoint pattern is https://api.census.gov/data/{YEAR}/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18. The pattern is the one in my instructions, and the fetched pages show the endpoint exists but needs a key [S53, S58]. Variable listing: https://api.census.gov/data/2023/acs/acs1/variables.html [unverified; not fetched].
- **2020 is not a standard 1-year release.** The Census Bureau published only experimental 1-year estimates for 2020 because of pandemic nonresponse [unverified; from the settled working interpretation]. Any 2020 value must be labelled "EXPERIMENTAL (no standard release)". Page: https://www.census.gov/programs-surveys/acs/data/experimental-data/1-year.html [unverified; not fetched in this step].
BLOCKED: Census API key — 2023 ACS 1-year B19013 for state:18 and us:1 could not be retrieved; api.census.gov returned 'Missing Key' for both calls [S53, S58]
MISSING DATA: 2023 ACS 1-year B19013_001E and B19013_001M for Indiana (state:18) — api.census.gov 2023 acs1 endpoint returned Missing Key [S53]; saved sources had no 2023 value [S57]
MISSING DATA: 2023 ACS 1-year B19013_001E and B19013_001M for United States (us:1) — api.census.gov 2023 acs1 endpoint returned Missing Key [S58]; saved sources had no 2023 value [S57]
MISSING DATA: Census B19013 table description page (2023 label for 'inflation-adjusted dollars') — not fetched; documentation points are [unverified]
