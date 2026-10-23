I read "between 2015 and 2023" as Every year from 2015 through 2023, inclusive; if you meant Only the two endpoint years, 2015 and 2023, the answer below may not apply.

**Step 3: ACS B19013 for 2019 (standard) and 2020 (experimental).** No value could be confirmed in this step. Every row is UNAVAILABLE rather than filled from memory.

| year | geography | B19013 estimate | MOE | status | source URL | vintage | retrieved date |
|---|---|---|---|---|---|---|---|
| 2019 | Indiana (state:18) | UNAVAILABLE. The saved API response is a "Missing Key" page, not data [S31]. | UNAVAILABLE | standard | https://api.census.gov/data/2019/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 [S31] | ACS 2019 1-year | 2026-10-23 |
| 2019 | United States (us:1) | UNAVAILABLE. No saved response for the 2019 us:1 call appears in the sources index I could read [S47]. | UNAVAILABLE | standard | https://api.census.gov/data/2019/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (pattern from the role card; not confirmed fetched) | ACS 2019 1-year | 2026-10-23 |
| 2020 | Indiana | UNAVAILABLE. I could not confirm a B19013 value for Indiana in the experimental files [S40][S41][S42]. | UNAVAILABLE | EXPERIMENTAL (no standard release) | https://www.census.gov/programs-surveys/acs/data/experimental-data/1-year.html (the page saved as [S40]) | ACS 2020 1-year experimental | 2026-10-23 |
| 2020 | United States | UNAVAILABLE. Same reason as the Indiana 2020 row [S40][S41][S42]. | UNAVAILABLE | EXPERIMENTAL (no standard release) | https://www.census.gov/programs-surveys/acs/data/experimental-data/1-year.html (the page saved as [S40]) | ACS 2020 1-year experimental | 2026-10-23 |

**Census note on 2020 (one line):** The Census Bureau did not release standard 2020 ACS 1-year estimates because pandemic-related data-collection disruption caused nonresponse bias. It published only experimental 2020 1-year tables instead. The experimental-data page is [S40]. The nonresponse rationale comes from the task's settled interpretation. I did not confirm the exact wording on the saved page, so I am not quoting it.

**Limitations:**
- The Census API calls for ACS 1-year returned a "Missing Key" page [S31], so the 2019 standard values were not retrieved. Any of those values from memory would be [unverified], so I left them out.
- The 2020 experimental files [S41][S42] (XK200501, XK200503) were saved. The output I could see showed other tables (nativity and similar columns) and no B19013 median household income for Indiana or the U.S. I did not confirm that those files hold B19013 at all.
- The 2019 5-year B19013 pages [S34][S35] are a different product from the 1-year estimates. They must not be substituted for the 1-year values.
- Next step: retry the 2019 1-year B19013 through data.census.gov table ACSDT1Y2019.B19013, or the Census API with a key. For 2020, look for the experimental B19013 file, or mark 2020 unavailable in the final deliverable.
BLOCKED: Census API access with a key — the 2019 ACS 1-year B19013 values for Indiana and the U.S. could not be retrieved (API returned a Missing Key page [S31])
MISSING DATA: ACS 2019 1-year B19013_001E and MOE, Indiana (state:18) — api.census.gov 2019 acs1 (Missing Key response, S31)
MISSING DATA: ACS 2019 1-year B19013_001E and MOE, United States (us:1) — api.census.gov 2019 acs1 (no usable response)
MISSING DATA: ACS 2020 experimental 1-year B19013, Indiana and United States — Census experimental data page S40 and files S41/S42 (no B19013 value confirmed)
MISSING DATA: Exact wording of Census statement on 2020 nonresponse — S40 (not confirmed in the output I could read)
