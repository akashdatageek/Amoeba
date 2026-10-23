I could not get any ACS B19013 value for 2015 or 2016, so all four rows below are UNAVAILABLE. The Census API returned a "Missing Key" page instead of data, and I did not fill any value from memory.

| year | geography | B19013 estimate | MOE | source URL | vintage | retrieved date |
|---|---|---|---|---|---|---|
| 2015 | Indiana (state:18) | UNAVAILABLE: API returned a "Missing Key" page, not data [S8] | UNAVAILABLE | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | ACS 2015 1-year, standard release | 2026-10-23 |
| 2015 | United States (us:1) | UNAVAILABLE: API returned a "Missing Key" page, not data [S7] | UNAVAILABLE | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 | ACS 2015 1-year, standard release | 2026-10-23 |
| 2016 | Indiana (state:18) | UNAVAILABLE: API returned a "Missing Key" page, not data [S13] | UNAVAILABLE | https://api.census.gov/data/2016/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | ACS 2016 1-year, standard release | 2026-10-23 |
| 2016 | United States (us:1) | UNAVAILABLE: not fetched. The per-step fetch limit was reached, and the matching 2015 us:1 call had already returned "Missing Key" [S7] | UNAVAILABLE | https://api.census.gov/data/2016/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 | ACS 2016 1-year, standard release | 2026-10-23 |

Limitations:
- **API key:** The api.census.gov calls for 2015 and 2016 returned "Missing Key" pages. In this environment the API appears to need a key to serve data [S7, S8, S13].
- **data.census.gov:** The fallback page https://data.census.gov/table/ACSDT1Y2015.B19013?g=040XX00US18 failed to load (fetch error).
- **Search results:** The searches returned data.census.gov pages for other ACS products, such as B19013 5-year tables [S2]. They gave no usable 1-year B19013 figure for Indiana or the U.S. in 2015 or 2016.
- **Secondary sources:** I did not use Census Reporter or other aggregators, because the role requires primary Census sources.
- **Step 7 need:** Step 7 needs B19013 for every year 2015–2023, and this step cannot supply it. The Census API with a key, or the official data.census.gov tables ACSDT1Y{year}.B19013, must be reached some other way. 2020 has no standard 1-year release and must be shown as 'EXPERIMENTAL (no standard release)'.
- **Downstream:** Later steps must not treat any 2015 or 2016 income figure as sourced from this step.
BLOCKED: Census API access with a key — api.census.gov returned 'Missing Key' for the 2015 and 2016 ACS 1-year B19013 queries, so no estimate or MOE could be retrieved
BLOCKED: data.census.gov page fetch — the B19013 1-year 2015 table page could not be loaded
MISSING DATA: ACS 2015 1-year B19013_001E and _001M, Indiana — api.census.gov (Missing Key), data.census.gov (fetch failed), web search (only 5-year pages)
MISSING DATA: ACS 2015 1-year B19013_001E and _001M, United States — api.census.gov (Missing Key)
MISSING DATA: ACS 2016 1-year B19013_001E and _001M, Indiana — api.census.gov (Missing Key)
MISSING DATA: ACS 2016 1-year B19013_001E and _001M, United States — api.census.gov (not fetched, fetch limit reached)
MISSING DATA: ACS B19013 values for the remaining years through 2023 (required by step 7) — not in this step's assignment and not retrieved
