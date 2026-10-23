**ACS B19013 1-year (B19013_001E with margin of error B19013_001M): no values could be retrieved. All four cells below are gaps.**

I did not fill any number from memory, because the role rules forbid it.

| Geography | Survey year | B19013_001E (that survey year's own dollars) | MOE (B19013_001M) | Source URL tried and result | Release year | Retrieval date |
|---|---|---|---|---|---|---|
| Indiana (state FIPS 18) | 2015 | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 returned a "Missing Key" page, not data [S1] | 2016 (ACS 2015 1-year) [unverified] | 2026-10-22 (fetched 2026-10-23T00:00:47 UTC [S1]) |
| United States | 2015 | NOT RETRIEVED | NOT RETRIEVED | The for=us:1 query was not run. The API needs a key [S1], and no other Census page with this value was fetched. | 2016 [unverified] | 2026-10-22 |
| Indiana (state FIPS 18) | 2023 | NOT RETRIEVED | NOT RETRIEVED | https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 returned a "Missing Key" page, not data [S2]. The data.census.gov page for table B19013 (2023, Indiana) was fetched earlier, but its saved text had no estimate. | 2024 (ACS 2023 1-year) [unverified] | 2026-10-22 (fetched 2026-10-23T00:00:56 UTC [S2]) |
| United States | 2023 | NOT RETRIEVED | NOT RETRIEVED | The for=us:1 query was not run. The API needs a key [S2], and no other Census page with this value was fetched. | 2024 | 2026-10-22 |

**What I found**
- Both Census API calls that I ran, Indiana 2015 [S1] and Indiana 2023 [S2], returned a "Missing Key" page. The page says "A valid *key* must be included with each data API request." No API key is available in this environment, so keyless API queries cannot return data.
- Earlier local searches of the saved sources found only B19013 variable metadata and a 2023 ACS 5-year group listing, which is the wrong product (5-year, not 1-year). They also found a data.census.gov page with no estimate values, and Wikipedia pages, which are not acceptable sources for this step. None gave an Indiana or United States B19013 1-year estimate.
- I did not cross-check any value, because there was no value to check.

**Note:** Each ACS value, once obtained, is in its own survey year's dollars. The B19013 label says "inflation-adjusted", but that means the survey year's dollars. The 2015 and 2023 values must not be treated as already in 2023 dollars.

**Effect on later steps:** The CPI adjustment, CSV and chart step cannot be completed from verified data. It needs these four values from the Census API with a key, or from rendered data.census.gov B19013 table pages for Indiana and the US. Once the values exist, the adjustment is: adjusted = nominal × CPI2023 / CPIyear.
BLOCKED: Census API access (api.census.gov) — the 2015 and 2023 Indiana queries returned 'Missing Key' and no key is available, so no B19013 estimates could be retrieved; the US queries were not run
BLOCKED: data.census.gov table rendering — the fetched B19013 2023 Indiana page text contained no estimate values
MISSING DATA: Indiana B19013_001E and B19013_001M, ACS 2015 1-year — api.census.gov (Missing Key [S1])
MISSING DATA: United States B19013_001E and B19013_001M, ACS 2015 1-year — not retrieved
MISSING DATA: Indiana B19013_001E and B19013_001M, ACS 2023 1-year — api.census.gov (Missing Key [S2]) and a data.census.gov page with no values
MISSING DATA: United States B19013_001E and B19013_001M, ACS 2023 1-year — not retrieved
