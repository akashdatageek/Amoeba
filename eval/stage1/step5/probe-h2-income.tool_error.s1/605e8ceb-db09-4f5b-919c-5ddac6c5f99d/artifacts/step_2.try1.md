**Step 2: ACS B19013 (1-year, standard release), 2017 and 2018. No values retrieved. All 4 rows are UNAVAILABLE.**

| year | geography | B19013 estimate | MOE | source URL | vintage | retrieved date |
|---|---|---|---|---|---|---|
| 2017 | Indiana (state:18) | UNAVAILABLE: the Census API returned "Missing Key" [S17] | UNAVAILABLE | https://api.census.gov/data/2017/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | ACS 2017 1-year | 2026-10-23 |
| 2017 | United States (us:1) | UNAVAILABLE: not fetched. Indiana's 2017 call was rejected for lack of a key [S17], and no turns were left. | UNAVAILABLE | https://api.census.gov/data/2017/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (not fetched) | ACS 2017 1-year | 2026-10-23 |
| 2018 | Indiana (state:18) | UNAVAILABLE: the fetch failed with a tool error ("could not extract ... Failed to fetch") | UNAVAILABLE | https://api.census.gov/data/2018/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | ACS 2018 1-year | 2026-10-23 |
| 2018 | United States (us:1) | UNAVAILABLE: not fetched. The 2018 state call had already failed, and no turns were left. | UNAVAILABLE | https://api.census.gov/data/2018/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (not fetched) | ACS 2018 1-year | 2026-10-23 |

**Limitations**
- The Census API now requires a key on each request. The 2017 Indiana call returned the page "A valid *key* must be included with each data API request" [S17]. The sibling 2015 and 2016 API calls in the workspace (S7, S8, S13) are also titled "Missing Key", so the keyless API pattern does not work in this environment.
- The 2018 Indiana call failed with a tool error. I found no other 2017 or 2018 B19013 values in the saved sources. S1 is the 2015 1-year table page, S2 is a 2015 5-year AIAN table page, and S3 is the 2023 5-year table page. None of them gives 2017 or 2018 Indiana or U.S. 1-year values.
- I did not use remembered values, estimates or interpolation. Later steps need a keyed Census API call or the data.census.gov tables ACSDT1Y2017.B19013 and ACSDT1Y2018.B19013 (a different route, not tried here) to fill these rows.
- Neither 2017 nor 2018 is the experimental 2020 year. Both are standard 1-year releases. The B19013 values in those releases are in each survey year's own dollars, so they must be CPI-adjusted to 2023 dollars later.
BLOCKED: Census API access with a valid key — could not retrieve ACS 2017 and 2018 B19013 values for Indiana or the U.S. (keyless requests return 'Missing Key' [S17]; the 2018 fetch errored)
MISSING DATA: ACS 2017 1-year B19013_001E/M, Indiana — api.census.gov 2017 acs1 (Missing Key [S17])
MISSING DATA: ACS 2017 1-year B19013_001E/M, United States — not fetched, same key barrier
MISSING DATA: ACS 2018 1-year B19013_001E/M, Indiana — api.census.gov 2018 acs1 (fetch error)
MISSING DATA: ACS 2018 1-year B19013_001E/M, United States — not fetched, same key barrier
