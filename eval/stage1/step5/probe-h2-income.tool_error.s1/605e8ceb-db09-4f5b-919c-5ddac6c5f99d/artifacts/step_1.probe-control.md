All four values are UNAVAILABLE. I did not fill any from memory, and I did not estimate or interpolate.

| year | geography | B19013 estimate | MOE | source URL | vintage | retrieved date |
|---|---|---|---|---|---|---|
| 2015 | Indiana (state:18) | UNAVAILABLE: the Census API returned a "Missing Key" page, not data [S8] | UNAVAILABLE | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | ACS 2015 1-year, standard release | 2026-10-23 |
| 2015 | United States (us:1) | UNAVAILABLE: not fetched. The same endpoint needs a key [S8], and no key was available. | UNAVAILABLE | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 | ACS 2015 1-year, standard release | 2026-10-23 |
| 2016 | Indiana (state:18) | UNAVAILABLE: not fetched, for the same reason | UNAVAILABLE | https://api.census.gov/data/2016/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | ACS 2016 1-year, standard release | 2026-10-23 |
| 2016 | United States (us:1) | UNAVAILABLE: not fetched, for the same reason | UNAVAILABLE | https://api.census.gov/data/2016/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 | ACS 2016 1-year, standard release | 2026-10-23 |

Limitations:
- The 2015 Indiana request to api.census.gov returned the "Missing Key" page: "A valid key must be included with each data API request" [S8]. The API needs a free key from https://api.census.gov/data/key_signup.html. The other three URLs use the same pattern and would fail the same way without a key. I did not run them because of the turn limit, so the "Missing Key" result is confirmed only for the 2015 Indiana request.
- Earlier tool calls, including a local file read, failed with "injected fault" errors.
- I also saved data.census.gov table pages (S1 is the ACSDT1Y2015.B19013 page, S2 and S3 are other B19013 pages). A grep of them showed no B19013 values for Indiana or the U.S. for 2015 or 2016 [S9]. I cannot confirm any figure from them. They are likely JavaScript-rendered and are not primary API output.
- Next step: rerun the four URLs with `&key=<CENSUS_KEY>`. Neither year is 2020, so there is no experimental-release issue for this step.
- The CPI-U series and the later years are outside this step.
BLOCKED: Census API key — api.census.gov returned 'Missing Key' [S8], so B19013_001E and _001M for Indiana and the U.S. for 2015 and 2016 could not be retrieved
MISSING DATA: ACS 1-year B19013_001E/_001M, state:18, 2015 — api.census.gov (Missing Key page), data.census.gov pages S1-S3 (no values found)
MISSING DATA: ACS 1-year B19013_001E/_001M, us:1, 2015 — not fetched; same keyed endpoint
MISSING DATA: ACS 1-year B19013_001E/_001M, state:18, 2016 — not fetched; same keyed endpoint
MISSING DATA: ACS 1-year B19013_001E/_001M, us:1, 2016 — not fetched; same keyed endpoint
