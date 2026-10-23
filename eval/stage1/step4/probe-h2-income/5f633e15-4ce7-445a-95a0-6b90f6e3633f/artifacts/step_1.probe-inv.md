**ACS B19013 1-year (B19013_001E and B19013_001M): no values could be verified, so none are reported.**

I did not fill any value from memory. The Census API returned "Missing Key" for the two queries I ran. The data.census.gov page for the 2023 1-year table did not show estimates in the text I could read. The Census Reporter API fallback returned a 404 error. It was fetched on 2026-10-22 and has no [S#] tag.

| Geography | Survey year | B19013_001E (USD) | MOE (B19013_001M) | Source URL tried | Release year | Retrieval date |
|---|---|---|---|---|---|---|
| Indiana (state FIPS 18) | 2015 | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 returned "Missing Key" [S28] | Not confirmed | 2026-10-23T00:00:47 UTC (2026-10-22 Chicago time) [S1] |
| United States | 2015 | NOT RETRIEVED | NOT RETRIEVED | The `for=us:1` query for 2015 was not run (turn limit). | Not confirmed | Not fetched |
| Indiana (state FIPS 18) | 2023 | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 returned "Missing Key" [S2] | Not confirmed | 2026-10-22 Chicago time; the exact timestamp is in the fetch log [S27] |
| United States | 2023 | NOT RETRIEVED | NOT RETRIEVED | https://data.census.gov/table/ACSDT1Y2023.B19013?tid=ACSDT1Y2023.B19013. A text search of the saved copy found no Indiana or United States estimate [S28]. | Not confirmed | 2026-10-23T00:02:58 UTC (2026-10-22 Chicago time) [S19] |

Release years are shown as "Not confirmed" because no fetched page stated them.

**What happened**
- The Census API calls for Indiana in 2015 [S1] and 2023 [S2] both returned a "Missing Key" page. The API needs a key that I do not have.
- The data.census.gov 1-year 2023 B19013 page [S19] is JavaScript-rendered. A text search of the saved copy found no estimate.
- Another data.census.gov page I fetched [S17] is titled ACSDT5Y2023.B19013. That is the 5-year product, not the 1-year one, so I did not use it.
- I also fetched the Census report "Income in the United States: 2023" [S18], another Census income report [S9], Census tables A1 and A2 [S13, S14], a Census data-profiles page [S10], and a Census page on household income in states and metropolitan areas [S8]. I could not pull a B19013_001E value for Indiana or the U.S. from any of them. They are not the 1-year B19013 table.
- The Census Reporter API fetch (api.censusreporter.org, table B19013, acs2023_1yr) failed with a 404, so it gave no value.

**Note:** each B19013 value, once obtained, is in its own survey year's dollars. Downstream steps must not use any value from memory. They need either a Census API key (add `&key=...`) or a Census page that displays the B19013 1-year values for Indiana and the U.S. for 2015 and 2023.
BLOCKED: Census API access (API key) — api.census.gov returned 'Missing Key' for the 2015 and 2023 ACS 1-year B19013 queries, so no estimate or MOE could be retrieved
BLOCKED: JavaScript page rendering — data.census.gov B19013 1-year table pages did not expose values in fetched text
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2015 — api.census.gov (Missing Key [S1])
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2015 — no successful fetch; the us:1 API call was not run
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2023 — api.census.gov (Missing Key [S2])
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2023 — data.census.gov [S19] showed no values; Census Reporter API returned 404
