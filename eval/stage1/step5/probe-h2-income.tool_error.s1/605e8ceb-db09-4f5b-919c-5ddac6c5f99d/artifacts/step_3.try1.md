I read "between 2015 and 2023" as Every year from 2015 through 2023, inclusive; if you meant Only the two endpoint years, 2015 and 2023, the answer below may not apply.

**Step 3 result: ACS B19013 for 2019 (standard) and 2020 (experimental). No estimate or MOE was retrieved for any of the four rows.**

| year | geography | B19013 estimate | MOE | status (standard/EXPERIMENTAL) | source URL | vintage | retrieved date |
|---|---|---|---|---|---|---|---|
| 2019 | Indiana (state:18) | UNAVAILABLE: the Census API returned a "Missing Key" page, not data [S31] | UNAVAILABLE | standard | https://api.census.gov/data/2019/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 [S31] | ACS 2019 1-year (not obtained) | 2026-10-23 |
| 2019 | United States (us:1) | UNAVAILABLE: not fetched. The same API endpoint demands a key [S31], and no fetch turns were left | UNAVAILABLE | standard | https://api.census.gov/data/2019/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (not fetched) | ACS 2019 1-year (not obtained) | 2026-10-23 |
| 2020 | Indiana (state:18) | UNAVAILABLE: the experimental-tables page was fetched [S40], but the Indiana B19013 value was not extracted from it. The only data file it yielded, sources/S42_XK200503.csv, is documentation text, not B19013 values [S42] | UNAVAILABLE | EXPERIMENTAL (no standard release) | https://www.census.gov/programs-surveys/acs/data/experimental-data/1-year.html [S40] | ACS 2020 1-year experimental (not obtained) | 2026-10-23 |
| 2020 | United States (us:1) | UNAVAILABLE: same reason as the Indiana 2020 row [S40][S42] | UNAVAILABLE | EXPERIMENTAL (no standard release) | https://www.census.gov/programs-surveys/acs/data/experimental-data/1-year.html [S40] | ACS 2020 1-year experimental (not obtained) | 2026-10-23 |

**Census note on 2020 (one line):** The Census Bureau page titled "2020 ACS 1-Year Experimental Data Tables" (https://www.census.gov/programs-surveys/acs/data/experimental-data/1-year.html, fetched 2026-10-23 [S40]) is where it published experimental estimates in place of standard 2020 ACS 1-year estimates. The reason, pandemic-related nonresponse bias, is from my own knowledge [unverified]. The visible excerpt of the page I could read did not show that sentence.

**Limitations**
- The 2019 Indiana API call returned "Missing Key", so the Census API needs a key [S31]. I did not retry it and did not fetch the U.S. row.
- The 2019 search hits were ACS 5-year tables, not 1-year: data.census.gov ACSDT5Y2019.B19013 [S34] and the acs5 API group page [S35]. I did not use them as 1-year values. The variable metadata [S37] gives the B19013_001E label but holds no values.
- I filled no value from memory and estimated nothing.
- Next steps for whoever finishes this: get the four values from a keyed Census API call, or from data.census.gov tables ACSDT1Y2019.B19013 and the 2020 experimental release. Values for 2019 are in 2019 dollars. They still need CPI-U adjustment to 2023 dollars.
BLOCKED: Census API access with a key — the api.census.gov 2019 ACS 1-year B19013 request returned 'Missing Key', so no 2019 estimates could be retrieved
BLOCKED: Reading the full fetched page text — only the first 6000 characters of the 2020 experimental page were visible and no B19013 values were found in them
MISSING DATA: ACS 2019 1-year B19013 estimate and MOE for Indiana — api.census.gov acs1 state:18 returned Missing Key [S31]
MISSING DATA: ACS 2019 1-year B19013 estimate and MOE for the United States — not fetched, same API key requirement
MISSING DATA: ACS 2020 experimental 1-year B19013 for Indiana and the U.S. — experimental-data page [S40] fetched, but no B19013 values in the visible excerpt
MISSING DATA: Census wording on why standard 2020 estimates were not released — not visible in the excerpt of [S40]; the note is [unverified]
