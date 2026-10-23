**ACS 2023 1-year, table B19013 (standard release): Indiana and United States. The values were NOT retrieved.**

I could not read the 2023 estimate or margin of error for Indiana or the United States from any page I fetched. I have not filled the gap from memory.

| geography | year | estimate (B19013_001E) | MOE (B19013_001M) | dollar year | source URL / table ID (fetched 2026-10-23) | release date | retrieved date |
|---|---|---|---|---|---|---|---|
| Indiana (state:18) | 2023 | NOT FETCHED | NOT FETCHED | 2023 dollars is expected for the standard 1-year release, but no fetched page confirms it | API https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 [S41, fetched 2026-10-23]; table page https://data.census.gov/table/ACSDT1Y2023.B19013 (table ID ACSDT1Y2023.B19013) [S42, fetched 2026-10-23] | not found in any fetched page | 2026-10-23 (attempt date) |
| United States (us:1) | 2023 | NOT FETCHED | NOT FETCHED | 2023 dollars is expected, but not confirmed | the us:1 API call was not made; table page https://data.census.gov/table/ACSDT1Y2023.B19013 (table ID ACSDT1Y2023.B19013) [S42, fetched 2026-10-23] | not found in any fetched page | 2026-10-23 (attempt date) |

**What happened**
- **Census API:** the state:18 request returned a "Missing Key" page, not data [S41, fetched 2026-10-23]. I did not run the us:1 request, because it would hit the same block.
- **data.census.gov table page:** it fetched, but it is a JavaScript-rendered shell. A grep of the saved text found no Indiana or United States B19013 value, margin of error or release date [S42, S45, fetched 2026-10-23].
- **Related page S43:** it is another B19013 page. I did not confirm any 2023 Indiana or US value in it [S46, checked 2026-10-23].
- **Not confirmed:** from a fetched page, that the 2023 figures are standard 1-year estimates in 2023 dollars. The table ID ACSDT1Y2023 names the standard 1-year product, not the 5-year or the Comparison Profile. I inferred this from the ID and did not see it stated in a fetched page.

**Fit note**
ACS 1-year B19013 is the Census Bureau's official single-year median household income. It is published for Indiana and for the 50 states plus DC as one national figure, so both can be compared with the same method in the 2015 and 2023 endpoint years. The estimates are survey-based and carry sampling error, which is why the margin of error matters. Each year is in that survey year's dollars, so the 2015 and 2023 values must be adjusted with CPI-U (2023 annual average as base) in a later step. The standard 2020 1-year release was not published; only experimental estimates exist. This does not affect an endpoint-only 2015 vs 2023 comparison.

**Needed to finish:** the 2023 Indiana and US B19013_001E and _001M, taken from the Census API with a key or from a rendered table export, plus the 2023 release date.
BLOCKED: Census API access with a key — the 2023 B19013 request returned 'Missing Key' [S41], so no estimate or MOE could be fetched
BLOCKED: Rendered data.census.gov table content — the page is a JavaScript shell with no values in the fetched text [S42]
MISSING DATA: Indiana 2023 B19013_001E and B19013_001M — API [S41] blocked, data.census.gov page [S42] had no values
MISSING DATA: United States 2023 B19013_001E and B19013_001M — us:1 API not run (same block); data.census.gov page [S42] had no values
MISSING DATA: 2023 ACS 1-year release date — not found in any fetched page
MISSING DATA: Confirmation that the values are in 2023 dollars from the standard release — not stated in any fetched page
