I read "between 2015 and 2023" as Endpoints only (2015 and 2023), with percentage change computed between them; if you meant Every year from 2015 to 2023, with percentage change from 2015 to 2023, the answer below may not apply.

**Step 1: ACS 2015 standard 1-year, table B19013 (partial result)**

| geography | year | estimate (B19013_001E) | MOE (B19013_001M) | dollar year | source | release date | retrieved date |
|---|---|---|---|---|---|---|---|
| United States | 2015 | 55,775 [S20], fetched 2026-10-23. The page text did not label the geography, so this is unconfirmed as the US figure. | NOT FETCHED | 2015 inflation-adjusted dollars, from the table title on [S20] (page fetched 2026-10-23) | data.census.gov table B19013, ACS 2015 1-year, saved as sources/S20_B19013_MEDIAN_HOUSEHOLD_INCOME_IN.txt [S20] | Not stated on any fetched page | 2026-10-23 [S20] |
| Indiana (state:18) | 2015 | NOT FETCHED | NOT FETCHED | 2015 dollars (table title only [S20], fetched 2026-10-23) | Attempted: https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18. It returned "Missing Key" [S1][S2][S3], fetched 2026-10-23. | Not stated on any fetched page | 2026-10-23 [S1] |

**What happened**
- The Census API requests for Indiana and the US returned "Missing Key: A valid key must be included with each data API request" [S1][S2][S3] (all fetched 2026-10-23). The API gave no data.
- The data.census.gov table page [S20] (fetched 2026-10-23) is titled "Median household income in the past 12 months (in 2015 Inflation-adjusted dollars)". It contains the value 55,775. That supports the 2015-dollar basis of the table.
- The Census Reporter grid view for B19013, ACS 2015 1-year, covering Indiana (04000US18) and the US (01000US), was fetched on 2026-10-23 [S28]. Its saved text showed the page title and the release label "acs2015_1yr", but I saw no Indiana figures. A later search of the saved files for "Indiana" found only an unrelated STATS Indiana topic page [S12] and no 2015 B19013 Indiana value [S40].

**Not confirmed**
1. No Indiana estimate or MOE appears in any fetched file, so I give none. I did not use any figure from memory.
2. No MOE was seen for either geography.
3. No official 2015 release date appears on any fetched page, so I give none.
4. The "standard 1-year, not experimental, not 5-year, not Comparison Profile" status rests only on the table title [S20] and the "acs2015_1yr" label [S28]. No Census release page confirms it.
5. The 55,775 on [S20] is probably the US figure, but the page does not label it, so this is not confirmed.

**Fit note**
ACS 1-year B19013 is the Census Bureau's official annual state and national estimate of median household income. It uses the same definition for Indiana and the US, so the two can be compared. It is published in each survey year's own dollars, so the 2015 and 2023 values must be re-based with CPI-U before they are compared. Both estimates carry sampling error, so the MOEs matter for small differences. The 2015 MOEs are still to be fetched.

**Next step needed:** get Indiana's 2015 estimate and MOE, and the US MOE, using a Census API key or a page that lists Indiana. Also get the 2015 release date from a Census release page.
BLOCKED: Census API access with a key — the 2015 ACS 1-year API request returned 'Missing Key', so Indiana and US estimates and MOEs could not be retrieved this way
MISSING DATA: Indiana 2015 ACS 1-year B19013_001E — Census API (Missing Key), data.census.gov page [S20], Census Reporter grid [S28]
MISSING DATA: Indiana 2015 B19013_001M — same sources
MISSING DATA: United States 2015 B19013_001M — same sources
MISSING DATA: Official 2015 ACS 1-year release date — no fetched page stated it
MISSING DATA: Confirmation that 55,775 is the US estimate — page text did not label the geography
