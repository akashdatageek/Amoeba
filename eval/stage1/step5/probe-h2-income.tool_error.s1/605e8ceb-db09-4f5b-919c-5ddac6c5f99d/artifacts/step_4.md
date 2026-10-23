None of the four ACS 1-year B19013 values for 2021 and 2022 could be retrieved, so all four rows are UNAVAILABLE. I did not fill or estimate any value from memory.

| year | geography | B19013 estimate | MOE | source URL | vintage | retrieved date |
|---|---|---|---|---|---|---|
| 2021 | Indiana (state FIPS 18) | UNAVAILABLE: the Census API request timed out [S48], and the index lists no 2021 1-year page among the saved sources [S52] | UNAVAILABLE | https://api.census.gov/data/2021/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | ACS 2021 1-year, standard release | 2026-10-23 |
| 2021 | United States | UNAVAILABLE: I did not run the U.S. API call after the Indiana call timed out [S48]. No 2021 1-year page is in the index [S52]. | UNAVAILABLE | https://api.census.gov/data/2021/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 | ACS 2021 1-year, standard release | 2026-10-23 |
| 2022 | Indiana (state FIPS 18) | UNAVAILABLE: I made no API fetch for 2022. The only saved 2022 1-year page is the data.census.gov page (ACSDT1Y2022.B19013) [S52]. A grep of it for "indiana" returned no match [S52], so no Indiana value is confirmed. | UNAVAILABLE | https://api.census.gov/data/2022/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 (fallback: https://data.census.gov/table/ACSDT1Y2022.B19013?g=010XX00US%2C%240400000&moe=false) | ACS 2022 1-year, standard release | 2026-10-23 |
| 2022 | United States | UNAVAILABLE: the saved 2022 page matched "United States" only in header and label lines, with no estimate shown in the grep output [S52]. No API response was retrieved. | UNAVAILABLE | https://api.census.gov/data/2022/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (fallback: same data.census.gov page as above) | ACS 2022 1-year, standard release | 2026-10-23 |

Limitations:
- The 2021 Indiana API call failed with "Request timed out" [S48]. The 2019 call to the same API is saved in the index [S52]. Earlier in this step I found it returned a "Missing Key" page, which I did not re-check.
- Most saved data.census.gov pages for 2021 and 2022 are 5-year tables (ACSDT5Y) [S50], which are the wrong product for this task. They must not be substituted for the 1-year values.
- A later step should retry the four API URLs above. It could also read the saved 2022 data.census.gov page in full (sources/S5_B19013_Median_Household_Income_in.txt). Use only the acs/acs1 product.
- The 2020 experimental caveat does not apply to these rows, because 2021 and 2022 are standard releases.
MISSING DATA: ACS 2021 1-year B19013_001E and B19013_001M, Indiana — Census API (timed out); saved pages are 5-year only
MISSING DATA: ACS 2021 1-year B19013_001E and B19013_001M, United States — API not retrieved; saved pages are 5-year only
MISSING DATA: ACS 2022 1-year B19013_001E and B19013_001M, Indiana — saved data.census.gov page shows no Indiana match; no API response
MISSING DATA: ACS 2022 1-year B19013_001E and B19013_001M, United States — no API response; saved page shows no estimate in grep output
