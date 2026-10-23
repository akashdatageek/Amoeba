**ACS 1-year B19013_001E (Median Household Income in the Past 12 Months, all households): Indiana and United States, 2015 and 2023**

I could not retrieve any of the four values. I did not fill any value from memory, from a different table, survey or year, or from a non-Census page.

| Geography | Survey year | B19013_001E (USD) | MOE (USD) | Source URL attempted | Release year | Retrieval date |
|---|---|---|---|---|---|---|
| Indiana (FIPS 18) | 2015 ACS 1-year | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 returned a "Missing Key" page and no data [S1] | Not confirmed by any fetched page | Attempted 2026-10-22 (Chicago time) |
| United States | 2015 ACS 1-year | NOT RETRIEVED | NOT RETRIEVED | The same API with for=us:1 was not completed. It needs the same key [S1]. | Not confirmed | Attempted 2026-10-22 |
| Indiana (FIPS 18) | 2023 ACS 1-year | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 returned "Missing Key" and no data [S2], fetched 2026-10-23T00:00:56+00:00 (the evening of 2026-10-22 in Chicago). The data.census.gov 1-year page for Indiana failed to fetch or showed no readable estimate. | Not confirmed | Attempted 2026-10-22 |
| United States | 2023 ACS 1-year | NOT RETRIEVED | NOT RETRIEVED | The API call for us:1 was not completed. No saved data.census.gov page showed a readable United States value. | Not confirmed | Attempted 2026-10-22 |

**Note:** any value eventually obtained is in its own survey year's dollars. The 2015 value is in 2015 dollars and the 2023 value is in 2023 dollars.

**Sources found but not used (none is a Census 1-year B19013 estimate for the required place and year):**
- A saved data.census.gov B19013 page is for survey year 2022, not 2015 or 2023.
- Other saved Census pages are ACS 5-year tables, an American Indian and Alaska Native 5-year table, API variable metadata, and a search page. None gives a 1-year Indiana or United States value for 2015 or 2023.
- CPS ASEC "Income in the United States" tables are a different survey and cannot stand in for ACS B19013.
- A Wikipedia snippet gives an Indiana median household income for 2023 [S84]. It is not a Census page, so it fails the success criteria (the Census Bureau must be the source). It also shows no MOE, and I did not use it. Wikipedia names no ACS table, so I cannot confirm it is B19013 1-year.

**Release year:** no fetched page shows it. The normal ACS 1-year schedule would put the 2015 data out in 2016 and the 2023 data out in 2024. Treat both as unconfirmed.

**What is needed to finish:**
- A Census API key, because the keyless api.census.gov calls return "Missing Key" [S1][S2].
- Or working copies of the ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013 tables from data.census.gov, with the Indiana and United States rows and their MOE.
- Or the Census "Median Household Income by State" 1-year tables for 2015 and 2023.

**Consequence for later steps:** the CSV, the CPI adjustment and the chart must not be built until the four ACS values are retrieved and verified. The CPI-U inputs from the earlier step (2015 = 237.017, 2023 = 304.702) are unaffected.
BLOCKED: Census API key — api.census.gov returns a 'Missing Key' page for keyless ACS 1-year B19013 queries (2015 and 2023), so no estimates or MOEs could be retrieved
BLOCKED: data.census.gov table content — the 1-year B19013 pages for Indiana and the United States failed to fetch or showed no readable values, and the 2015 1-year table was never retrieved
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2015 — api.census.gov (Missing Key)
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2015 — api.census.gov (not completed)
MISSING DATA: Indiana B19013_001E and MOE, ACS 1-year 2023 — api.census.gov (Missing Key), data.census.gov (no readable value)
MISSING DATA: United States B19013_001E and MOE, ACS 1-year 2023 — api.census.gov (not completed), data.census.gov (no readable value)
MISSING DATA: Release year for each ACS value — not shown in any fetched page
