**ACS 1-year B19013_001E (Median Household Income in the Past 12 Months, all households): Indiana and United States, 2015 and 2023**

I could not retrieve any of the four values. The Census API calls returned no data, and I did not fill any figure from memory.

| Geography | Survey year | B19013_001E (USD) | MOE (USD) | Source URL attempted | Release year | Retrieval date |
|---|---|---|---|---|---|---|
| Indiana (FIPS 18) | 2015 ACS 1-year | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 returned a "Missing Key" page and no data [S1] (fetched 2026-10-23T00:00:47 UTC, which is the evening of 22 October 2026 in Chicago) | not confirmed | attempt on 22 October 2026 |
| United States | 2015 ACS 1-year | NOT RETRIEVED | NOT RETRIEVED | The same API with for=us:1 was not completed | not confirmed | attempt on 22 October 2026 |
| Indiana (FIPS 18) | 2023 ACS 1-year | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 is also a "Missing Key" page [S2]. https://data.census.gov/table/ACSDT1Y2023.B19013?g=040XX00US18 failed to fetch. | not confirmed | attempt on 22 October 2026 |
| United States | 2023 ACS 1-year | NOT RETRIEVED | NOT RETRIEVED | Not completed | not confirmed | attempt on 22 October 2026 |

**Why the other sources I found cannot be used:**
- The page https://data.census.gov/table/ACSDT5Y2023.B19013 [S17] is the ACS 5-year table (ACSDT5Y), not the required 1-year table. I did not use it.
- "Income in the United States: 2023" [S18] and the tables [S13] and [S14] are from the Current Population Survey (CPS ASEC), not ACS B19013. Their national figures are a different series and must not stand in for ACS values.
- A text search of the saved pages found "Indiana" only in [S18]. I could not confirm that [S8], [S10] or [S19] show a 1-year B19013 estimate for Indiana or the United States for 2015 or 2023. I report no value from them.

**Note:** any value eventually obtained is in its own survey year's dollars, so the 2015 value is in 2015 dollars and the 2023 value is in 2023 dollars.

**What the next step needs:**
- A Census API key, because the API answers "Missing Key" to keyless calls here [S1].
- Or a working copy of the data.census.gov 1-year tables ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013 (the national and Indiana rows).
- Or the Census "Median Household Income by State" 1-year ACS tables.

Until then, the CSV, the CPI adjustment and the chart cannot be built from verified inputs.
BLOCKED: Census API access (API key) — api.census.gov returned a 'Missing Key' page for the 2015 and 2023 ACS 1-year B19013 queries, so no estimates or margins of error were retrieved
BLOCKED: data.census.gov page fetch — the ACSDT1Y2023.B19013 page for Indiana failed to fetch, so the 1-year values could not be read
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2015 — api.census.gov (Missing Key)
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2015 — api.census.gov (not completed)
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2023 — api.census.gov (Missing Key), data.census.gov (fetch failed)
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2023 — api.census.gov (not completed), data.census.gov (fetch failed)
