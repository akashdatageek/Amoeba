**Step 1: standard ACS 1-year B19013, survey year 2015. The estimates and MOEs could not be fetched.**

I typed no figure from memory. Both 2015 value cells are empty. Every date below is the retrieval date, 2026-10-23.

| geography | year | estimate (B19013_001E) | MOE (B19013_001M) | dollar year | source | release date | retrieved date |
|---|---|---|---|---|---|---|---|
| Indiana (state:18) | 2015 | NOT FETCHED | NOT FETCHED | 2015 dollars per the table title in [S20]; no value fetched to check | Table ID ACSDT1Y2015.B19013, page https://data.census.gov/cedsci/table?q=B19013&tid=ACSDT1Y2015.B19013&hidePreview=false [S20], search snippet only, retrieved 2026-10-23. API attempt: https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 [S3], retrieved 2026-10-23, returned "Missing Key". | not confirmed (not found in fetched sources) | 2026-10-23 |
| United States (us:1) | 2015 | NOT FETCHED | NOT FETCHED | 2015 dollars per the table title in [S20]; no value fetched to check | Table ID ACSDT1Y2015.B19013, page https://data.census.gov/cedsci/table?q=B19013&tid=ACSDT1Y2015.B19013&hidePreview=false [S20], search snippet only, retrieved 2026-10-23. API attempt: https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 [S2], retrieved 2026-10-23, returned "Missing Key". | not confirmed (not found in fetched sources) | 2026-10-23 |

**What happened**
- The Census API returned a "Missing Key" page, not data, for state:18 [S3], us:1 [S2] and the combined request [S1]. All three were retrieved 2026-10-23. No estimate or MOE came back.
- The search result [S20], retrieved 2026-10-23, identifies the standard 1-year table ID ACSDT1Y2015.B19013. Its title reads "MEDIAN HOUSEHOLD INCOME IN THE PAST 12 MONTHS (IN 2015 INFLATION-ADJUSTED DOLLARS)". That supports the dollar year only. The snippet is cut off and does not tie any value to Indiana or the US, so I did not use any number from it.
- Other pages did not help:
  - [S4] is an American Indian and Alaska Native 5-year table (ACSDT5YAIAN2015). That is the wrong product.
  - [S5] is the 2022 1-year table page. That is the wrong year.
  - [S6] is a generic B19013 search page.
  - [S11] is 2015 ACS documentation with no Indiana or US B19013 values.
- I could not confirm the release date, or that the values come from the standard 1-year release. The dollar-year label rests on the table title in [S20], which is a search snippet only.

**Fit note**
- ACS 1-year B19013 is the Census Bureau's official single-year median household income estimate for states and the nation. It comes with margins of error and is published in that survey year's dollars. That makes it a sound base for a CPI-U adjustment to 2023 dollars, and an endpoint comparison of 2015 and 2023 works.
- Limits: these are sample estimates with MOEs, so small changes may not be statistically significant. The 2020 standard 1-year release does not exist, but that does not affect the 2015 and 2023 endpoints.

**Next step needed:** retry the Census API with a valid key, or fetch the data.census.gov page for ACSDT1Y2015.B19013 and read the Indiana and United States cells. Until then, the 2015 figures are missing and downstream computation cannot use them.
BLOCKED: Census API access — the API returned a 'Missing Key' page, so no 2015 B19013 estimate or MOE was retrieved for Indiana or the US
MISSING DATA: Indiana 2015 B19013_001E and B19013_001M (standard ACS 1-year) — Census API [S3], data.census.gov pages [S4, S5, S6, S20], ACS 2015 documentation [S11]
MISSING DATA: United States 2015 B19013_001E and B19013_001M (standard ACS 1-year) — Census API [S2], data.census.gov pages [S4, S5, S6, S20], ACS 2015 documentation [S11]
MISSING DATA: 2015 ACS 1-year release date — not found in the fetched sources
