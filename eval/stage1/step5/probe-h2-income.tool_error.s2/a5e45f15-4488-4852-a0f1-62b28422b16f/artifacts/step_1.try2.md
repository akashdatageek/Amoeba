**Step 1: standard ACS 1-year B19013 for survey year 2015. The estimates and MOEs were NOT retrieved.**

| geography | year | estimate (B19013_001E) | MOE (B19013_001M) | dollar year | source | release date | retrieved date |
|---|---|---|---|---|---|---|---|
| Indiana (state:18) | 2015 | NOT FETCHED | NOT FETCHED | 2015 dollars (table title only, not confirmed from a value) [S4] | Census API https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 returned a "Missing Key" page [S3]. Table ID: ACSDT1Y2015.B19013 | NOT FETCHED | 2026-10-23 (failed attempt) [S3] |
| United States (us:1) | 2015 | NOT FETCHED | NOT FETCHED | 2015 dollars (table title only, not confirmed from a value) [S4] | Census API https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 returned a "Missing Key" page [S2]. Table ID: ACSDT1Y2015.B19013 | NOT FETCHED | 2026-10-23 (failed attempt) [S2] |

**What happened**
- The Census API calls for Indiana [S3], the United States [S2] and the combined query [S1] all returned the "Missing Key" page. No data values came back, so the API cannot be used here without a key.
- The fallback fetch of https://data.census.gov/table/ACSDT1Y2015.B19013?g=010XX00US$0400000 failed with "Failed to fetch url".
- Web search [S4] returned only data.census.gov page titles reading "MEDIAN HOUSEHOLD INCOME IN THE PAST 12 MONTHS (IN 2015 INFLATION-ADJUSTED DOLLARS)". It showed no Indiana or US value. Some of its snippets are 5-year or AIAN-specific table IDs, so they do not confirm a standard 1-year value.
- A second search found a Census page titled "2015 American Community Survey Single Year Estimates" [S11] (https://www.census.gov/newsroom/press-kits/2016/acs_oneyear.html). I only saw its search excerpt, which has no B19013 value and no release date, so I cite no figure from it. A later step could fetch it for the release date and the Indiana and US figures.
- I typed no figure from memory, so there are no numbers to cite.

**What is not confirmed**
- The Indiana and US 2015 estimates and MOEs.
- The release date of the 2015 standard 1-year release.
- That any value comes from the standard 1-year release rather than the 5-year or another product. The "2015 dollars" label rests on the table title in [S4] only.

**Fit note**
ACS 1-year B19013 is the Census Bureau's official single-year estimate of median household income for states and the nation, published with margins of error. It suits an Indiana vs. US comparison of the 2015 and 2023 endpoints. Each year's estimate is in that survey year's dollars, so a later step must deflate with CPI-U (CPI_2023 / CPI_year). The 2020 standard release does not exist, but that does not affect these endpoints. Limits: these are survey estimates with sampling error. The MOE is at the 90% confidence level [S15]. The 2015 values must still be retrieved before any calculation. That needs a Census API key, a working data.census.gov fetch, or a fetch of a Census release page such as [S11].
BLOCKED: Census API access with a key — the 2015 B19013 estimate and MOE for Indiana and the US could not be retrieved (Missing Key response)
BLOCKED: data.census.gov table page fetch — fetch_url failed for ACSDT1Y2015.B19013
MISSING DATA: 2015 ACS 1-year B19013_001E for Indiana — tried Census API [S3], data.census.gov, web search [S4]
MISSING DATA: 2015 ACS 1-year B19013_001M for Indiana — same
MISSING DATA: 2015 ACS 1-year B19013_001E for United States — tried Census API [S2], data.census.gov, web search
MISSING DATA: 2015 ACS 1-year B19013_001M for United States — same
MISSING DATA: Release date of the 2015 ACS 1-year estimates — not found in any fetched page; the Census press-kit page [S11] was seen only as a search excerpt
