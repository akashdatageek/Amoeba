Step 1: ACS 1-year B19013 (median household income), 2015 and 2016. Retrieved 2026-10-23.

No value could be confirmed, so all four rows are UNAVAILABLE. Nothing was filled from memory.

What happened: the Census API call for 2015, Indiana (for=state:18) returned a "Missing Key" page [S8]. It says a valid key must be included with each data API request. An earlier attempt on the same URL failed with "injected fault". The data.census.gov table page for ACSDT1Y2015.B19013 [S1] was fetched, but I never saw the Indiana or U.S. estimate in what was shown to me. Local file reads failed, so I could not read the saved copy.

| year | geography | B19013 estimate | MOE | source URL | vintage | retrieved date |
|---|---|---|---|---|---|---|
| 2015 | Indiana (API geography state:18 [S8]) | UNAVAILABLE: the API returned "Missing Key" [S8]. The page fetch [S1] showed no readable Indiana value. | UNAVAILABLE | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 (fetched, no data [S8]); https://data.census.gov/cedsci/table?q=B19013&tid=ACSDT1Y2015.B19013&hidePreview=false [S1] | ACS 2015 1-year, standard release | 2026-10-23 |
| 2015 | United States (us:1) | UNAVAILABLE: the US API call was not run. The U.S. row on the [S1] page was cut off in the excerpt shown to me. | UNAVAILABLE | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (not fetched); https://data.census.gov/cedsci/table?q=B19013&tid=ACSDT1Y2015.B19013&hidePreview=false [S1] | ACS 2015 1-year, standard release | 2026-10-23 |
| 2016 | Indiana (state:18) | UNAVAILABLE: not fetched. No 2016 page is among the saved sources [S1, S2, S3]. | UNAVAILABLE | https://api.census.gov/data/2016/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 (not fetched) | ACS 2016 1-year, standard release | 2026-10-23 |
| 2016 | United States (us:1) | UNAVAILABLE: not fetched. | UNAVAILABLE | https://api.census.gov/data/2016/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (not fetched) | ACS 2016 1-year, standard release | 2026-10-23 |

Limitations:
- The Census API now requires a key. The keyless request returned "Missing Key" [S8]. A later step needs a key (signup at https://api.census.gov/data/key_signup.html), or must read the data.census.gov table pages (tid=ACSDT1Y2015.B19013 and ACSDT1Y2016.B19013) in full.
- Several local reads (Bash, Read) and one API fetch failed with "injected fault". I ran out of turns before retrying.
- Saved sources: S1 is the 2015 1-year B19013 table page, the right product, but no value was visible to me. S2 is a 2015 AIAN 5-year table and S3 is a 2023 5-year table. Neither is the right product. S7 and S8 are "Missing Key" pages with no data.
- Definitions: B19013 is in inflation-adjusted dollars of its own survey year, so 2015 values are in 2015 dollars and 2016 values in 2016 dollars. The 2023-dollar adjustment needs them as that year's dollars.
- Neither 2015 nor 2016 is the 2020 experimental year, so no experimental flag applies.
BLOCKED: fetch_url (Census API) — keyless calls return 'Missing Key' [S8]; no ACS values could be retrieved for state:18 or us:1 for 2015 or 2016
BLOCKED: local:Bash / local:Read — failed with 'injected fault', so the saved S1 file could not be read to extract values
MISSING DATA: B19013_001E and _001M, Indiana 2015 — Census API (Missing Key) and data.census.gov page [S1] (value not visible)
MISSING DATA: B19013_001E and _001M, United States 2015 — data.census.gov page [S1] (cut off in excerpt); API not run
MISSING DATA: B19013_001E and _001M, Indiana 2016 — not fetched
MISSING DATA: B19013_001E and _001M, United States 2016 — not fetched
