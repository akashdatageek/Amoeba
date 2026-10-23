**Step 1: standard ACS 1-year B19013 for survey year 2015. The estimates and margins of error were NOT retrieved (retrieval attempts dated 2026-10-23).**

Both Census API requests returned a "Missing Key" page instead of data. The page says a valid key must be included with each data API request [S3][S2]. They were fetched 2026-10-23 (S3 at 06:37 UTC, S2 at 06:36 UTC). I have no verified 2015 figures for Indiana or the US, and I did not type any value from memory.

| geography | year | estimate (B19013_001E) | MOE (B19013_001M) | dollar year | source (URL / table ID) | release date | retrieved date |
|---|---|---|---|---|---|---|---|
| Indiana (state:18) | 2015 | NOT FETCHED | NOT FETCHED | 2015 dollars expected. The table title reads "in 2015 inflation-adjusted dollars" [S20], retrieved 2026-10-23. This is not confirmed for Indiana because no value was returned. | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 (table B19013, standard 1-year). It returned "Missing Key" [S3]. | not confirmed (not found in any fetched page) | 2026-10-23, attempt only, no data returned [S3] |
| United States (us:1) | 2015 | NOT FETCHED | NOT FETCHED | 2015 dollars expected [S20], retrieved 2026-10-23. Not confirmed, because no value was returned. | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (table B19013, standard 1-year). It returned "Missing Key" [S2]. | not confirmed (not found in any fetched page) | 2026-10-23, attempt only, no data returned [S2] |

**What I checked in the saved sources (all retrieved 2026-10-23)**
- A search found the data.census.gov table ID ACSDT1Y2015.B19013. This is the standard 1-year table for 2015 (the "1Y" in the ID), titled "Median household income in the past 12 months (in 2015 inflation-adjusted dollars)" [S20]. The page is JavaScript-rendered. Its snippet shows a "United States" column and an unlabeled "±85", but I could not tie that figure to a geography or to an estimate. I did not use it.
- The other saved data.census.gov B19013 pages that I found are 5-year tables (for example ACSDT5YAIAN2015.B19013, and ACSDT5Y2023.B19013 in the search results) [S4]. The 5-year release is not allowed here, so I did not use them.
- The only 2015 acs1 API file saved is a metadata page for the annotation variable B19013F_001EA [S21][S23]. It belongs to the race-iteration table B19013F. It is not the Indiana or US B19013_001E estimate.
- I found no verified B19013_001E or B19013_001M values for Indiana or the US in S10, S11 or S12.
- The 2015 standard 1-year release date is not confirmed from any fetched page. I did not fill it in from memory.

**Fit note**
ACS 1-year B19013 fits this comparison because it is the Census Bureau's official annual median household income for both states and the nation. It is published in each survey year's own dollars, so the BLS CPI-U ratio (CPI_2023 / CPI_2015) can adjust it directly. Its limits are sampling error, which is why the margin of error should be reported, and the fact that no standard 2020 1-year release exists. That second limit does not affect the 2015 and 2023 endpoints.

**What the next step needs**
It needs a working route to the 2015 standard 1-year B19013_001E and B19013_001M for state 18 and for the US. Options are the Census API with a key, a readable copy of ACSDT1Y2015.B19013, or a Census 2015 ACS 1-year release page that also gives the release date.
BLOCKED: Census API access with a key — api.census.gov returned 'Missing Key' for both the Indiana (state:18) and US (us:1) 2015 B19013 requests, so the estimates and MOEs could not be fetched
BLOCKED: data.census.gov JavaScript table rendering — ACSDT1Y2015.B19013 could not be read as a data table
MISSING DATA: Indiana 2015 B19013_001E and B19013_001M (standard ACS 1-year) — api.census.gov 2015/acs/acs1 state:18 returned Missing Key [S3]; saved data.census.gov pages are 5-year tables [S4]
MISSING DATA: United States 2015 B19013_001E and B19013_001M (standard ACS 1-year) — api.census.gov 2015/acs/acs1 us:1 returned Missing Key [S2]
MISSING DATA: 2015 ACS 1-year release date — not found in any fetched page
MISSING DATA: Confirmation that the values are standard 1-year in 2015 dollars — no values fetched to confirm
