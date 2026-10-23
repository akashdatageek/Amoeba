Table: ACS 1-year B19013 (median household income, past 12 months), standard release, for 2017 and 2018

| year | geography | B19013 estimate | MOE | source URL | vintage | retrieved date |
|---|---|---|---|---|---|---|
| 2017 | Indiana (state FIPS 18) | UNAVAILABLE: the Census API returned a "Missing Key" page, not data [S17]. No other primary source was read in this step. | UNAVAILABLE | https://api.census.gov/data/2017/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | ACS 2017 1-year, standard release | 2026-10-23 |
| 2017 | United States | UNAVAILABLE: the same API needs a key. The `for=us:1` request was not run, because the key requirement was already clear from the Indiana request [S17]. | UNAVAILABLE | https://api.census.gov/data/2017/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 | ACS 2017 1-year, standard release | 2026-10-23 |
| 2018 | Indiana (state FIPS 18) | UNAVAILABLE: the request was not run. The 2017 request showed the API rejects keyless calls [S17], and no turns were left. | UNAVAILABLE | https://api.census.gov/data/2018/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | ACS 2018 1-year, standard release | 2026-10-23 |
| 2018 | United States | UNAVAILABLE: same reason as the 2018 Indiana row. | UNAVAILABLE | https://api.census.gov/data/2018/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 | ACS 2018 1-year, standard release | 2026-10-23 |

Notes on limits:
- The keyless Census API request for 2017 Indiana returned the page "Missing Key": "A valid key must be included with each data API request" [S17]. The 2016 Indiana request in the workspace showed the same page [S24]. The 2015 and 2016 Indiana requests and the 2015 U.S. request were saved under sources/ [S25]. I did not check what they returned. This step does not need them.
- One web search for Indiana 2017 B19013 ran (result [S22]). I did not read any B19013 value from it, and the other saved sources (S1–S3, S7, S8, S13) did not give a 2017 or 2018 value I could verify. I did not fill any value from memory, estimate or interpolate.
- Neither 2017 nor 2018 is the experimental 2020 year, so both would be standard releases. Both rows are UNAVAILABLE only because of access.
- To finish: re-run the four URLs above with a free Census API key appended (`&key=...`), or read table B19013 for ACS 1-year 2017 and 2018 on data.census.gov. Both give the estimate and the margin of error (B19013_001E and B19013_001M).
BLOCKED: Census API key — could not call api.census.gov, which returns 'Missing Key' for keyless requests, so none of the four 2017/2018 B19013 values (Indiana, U.S.) could be retrieved
MISSING DATA: ACS 2017 1-year B19013_001E and _001M for Indiana — api.census.gov (Missing Key page [S17]) and one web search [S22]
MISSING DATA: ACS 2017 1-year B19013_001E and _001M for United States — not retrieved; same API key requirement
MISSING DATA: ACS 2018 1-year B19013_001E and _001M for Indiana — not fetched; no turns left
MISSING DATA: ACS 2018 1-year B19013_001E and _001M for United States — not fetched; no turns left
