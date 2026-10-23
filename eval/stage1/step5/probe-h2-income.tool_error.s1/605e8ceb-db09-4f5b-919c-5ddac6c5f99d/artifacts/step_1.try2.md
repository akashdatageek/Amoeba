| year | geography | B19013 estimate | MOE | source URL | vintage | retrieved date |
|---|---|---|---|---|---|---|
| 2015 | Indiana (state:18) | UNAVAILABLE: the Census API returned "Missing Key" instead of data [S8] | UNAVAILABLE | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | ACS 2015 1-year, standard release | 2026-10-23 |
| 2015 | United States (us:1) | UNAVAILABLE: not fetched. The same API endpoint demands a key [S8], and no turns were left to try. | UNAVAILABLE | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (not fetched) | ACS 2015 1-year, standard release | 2026-10-23 |
| 2016 | Indiana (state:18) | UNAVAILABLE: the Census API returned "Missing Key" instead of data [S13] | UNAVAILABLE | https://api.census.gov/data/2016/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | ACS 2016 1-year, standard release | 2026-10-23 |
| 2016 | United States (us:1) | UNAVAILABLE: not fetched. The same API endpoint demands a key [S13], and no turns were left to try. | UNAVAILABLE | https://api.census.gov/data/2016/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (not fetched) | ACS 2016 1-year, standard release | 2026-10-23 |

Notes on limitations:
- The Census API returned a "Missing Key" page for the keyless requests for 2015 [S8] and 2016 [S13]. It says a valid key must be sent with each request [S7]. I did not have a key, so no B19013 values came back.
- The fallback, data.census.gov/table/ACSDT1Y2015.B19013?g=040XX00US18, failed to load. The web search only surfaced data.census.gov table pages [S1][S2][S3]. I could not read a confirmed 2015 or 2016 Indiana or U.S. 1-year median from them. One of them is a 5-year American Indian and Alaska Native table, which is the wrong product [S2].
- I made no estimates and filled nothing from memory. Later steps should request a free Census API key, or open the data.census.gov table B19013 for ACSDT1Y2015 and ACSDT1Y2016, and re-run these four rows.
- Retrieval date for every row is 2026-10-23.
BLOCKED: Census API key — the api.census.gov requests returned 'Missing Key', so no B19013 values could be fetched
BLOCKED: data.census.gov page fetch — the table page for ACSDT1Y2015.B19013 failed to load
MISSING DATA: B19013_001E and B19013_001M, Indiana, ACS 2015 1-year — api.census.gov (Missing Key), data.census.gov (fetch failed)
MISSING DATA: B19013_001E and B19013_001M, United States, ACS 2015 1-year — api.census.gov (not fetched, key required)
MISSING DATA: B19013_001E and B19013_001M, Indiana, ACS 2016 1-year — api.census.gov (Missing Key)
MISSING DATA: B19013_001E and B19013_001M, United States, ACS 2016 1-year — api.census.gov (not fetched, key required)
