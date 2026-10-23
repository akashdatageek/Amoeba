**ACS 1-year B19013_001E (Median Household Income in the Past 12 Months, all households): Indiana and United States, survey years 2015 and 2023**

**Result: none of the four values could be confirmed from a fetched Census page. I have not filled any value from memory.**

| Geography | Survey year | B19013_001E (dollars) | MOE (B19013_001M) | Source URL | Release year | Retrieval date |
|---|---|---|---|---|---|---|
| Indiana | 2015 | NOT RETRIEVED | NOT RETRIEVED | none (no 2015 page showing a value was read) | 2016 [unverified] | 2026-10-22 |
| United States | 2015 | NOT RETRIEVED | NOT RETRIEVED | none | 2016 [unverified] | 2026-10-22 |
| Indiana | 2023 | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 [S2]. The saved response is a "Missing Key" file [S1][S2], not data. | 2024 | 2026-10-22 |
| United States | 2023 | NOT RETRIEVED | NOT RETRIEVED | none | 2024 | 2026-10-22 |

**What I tried and found**
- The Census API call for 2023, Indiana (state FIPS 18), returned a "Missing Key" response [S1][S2]. No value came back. Retrieved 2026-10-22.
- A Census Reporter API fetch for table B19013 (acs2023_1yr, Indiana and the US) failed with "404 page not found" on 2026-10-22 (fetch_url result in this step). No Census Reporter value was obtained for any year.
- Two saved Census pages, a B19013 page [S17] and a Census Bureau table page [S19], showed no Indiana or United States value for 2015 or 2023 in what I read, so I cite nothing from them.
- Other saved Census pages are the "Income in the United States" report [S9][S13][S14][S18] and ACS data profiles [S10]. The report pages are mostly Current Population Survey (CPS) material, not ACS 1-year B19013. They are a different survey and must not be used as B19013 values.
- There was no second-source cross-check, because no first value was obtained.

**Note:** each ACS value, once obtained, is in its own survey year's dollars (2015 values in 2015 dollars, 2023 values in 2023 dollars).

**What the work-around does not cover:** the Census API needs a key, and the data.census.gov table fetch is not available. The substitute route (Census Reporter, or Census ACS 1-year pages found by search) gave no usable values. All four estimates and margins of error are still missing. Downstream steps cannot compute adjusted values or percentage changes for Indiana or the United States until these are fetched from Census pages. No ACS figure can be cited or dated yet.

BLOCKED: Census API access — the 2023 call returned 'Missing Key', so B19013_001E and B19013_001M for Indiana and the US could not be fetched
BLOCKED: data.census.gov table fetch — B19013 values could not be read from table pages
BLOCKED: Census Reporter API — the acs2023_1yr fetch returned 404, so no values were obtained
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2015 — Census API, saved B19013 pages [S17][S19]
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2015 — Census API, saved B19013 pages [S17][S19]
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2023 — Census API [S2], saved B19013 pages [S17][S19]
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2023 — Census API, saved B19013 pages [S17][S19]
