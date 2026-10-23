| year | geography | B19013 estimate | MOE | source URL | vintage | retrieved date |
|---|---|---|---|---|---|---|
| 2017 | Indiana (04000US18) | UNAVAILABLE: the Census Reporter page was fetched [S27]. A local grep of the saved file for "indiana", "united states" and "median" returned no matching lines [S30]. The page text therefore holds no readable Indiana estimate (it is probably rendered by JavaScript). The api.censusreporter.org JSON fetch failed with an HTTP error. | UNAVAILABLE | https://censusreporter.org/data/table/?table=B19013&geo_ids=04000US18,01000US&primary_release=acs2017_1yr [S27] | ACS 2017 1-year, standard release | 2026-10-23 |
| 2017 | United States (01000US) | UNAVAILABLE: same reason as the Indiana 2017 row [S27][S30]. | UNAVAILABLE | https://censusreporter.org/data/table/?table=B19013&geo_ids=04000US18,01000US&primary_release=acs2017_1yr [S27] | ACS 2017 1-year, standard release | 2026-10-23 |
| 2018 | Indiana (04000US18) | UNAVAILABLE: the acs2018_1yr Census Reporter page was never fetched because I ran out of turns. The one web search for 2018 returned only data.census.gov table pages, not a 1-year value [S22]. | UNAVAILABLE | Intended, not fetched: https://censusreporter.org/data/table/?table=B19013&geo_ids=04000US18,01000US&primary_release=acs2018_1yr . Official API (needs a key, not usable here): https://api.census.gov/data/2018/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 | ACS 2018 1-year, standard release | 2026-10-23 |
| 2018 | United States (01000US) | UNAVAILABLE: same reason as the Indiana 2018 row. | UNAVAILABLE | Intended, not fetched: https://censusreporter.org/data/table/?table=B19013&geo_ids=04000US18,01000US&primary_release=acs2018_1yr . Official API (needs a key, not usable here): https://api.census.gov/data/2018/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 | ACS 2018 1-year, standard release | 2026-10-23 |

Limitations:
- This step ended with no estimate or MOE for any of the four rows. A downstream step needs another route. Options are the official API with a key, a FRED series for Indiana and U.S. median household income, or the published Census B19013 table files.
- 2017 and 2018 are standard ACS 1-year releases, so the 2020 experimental caveat does not apply to these rows.
- B19013 values are in inflation-adjusted dollars of the survey year. Treat them as that year's dollars when re-adjusting with CPI-U.
- The work-around uses Census Reporter, a secondary mirror of Census data. It does not give the official api.census.gov response. Any value taken from it would be secondary to the primary Census source.
BLOCKED: Census API key for api.census.gov — official API values for 2017 and 2018 could not be retrieved without a key
BLOCKED: JavaScript-rendering web fetch — the Census Reporter page text held no readable estimates
MISSING DATA: Indiana B19013 estimate and MOE, ACS 2017 1-year — Census Reporter page S27 (no values in saved text, S30)
MISSING DATA: United States B19013 estimate and MOE, ACS 2017 1-year — Census Reporter page S27
MISSING DATA: Indiana B19013 estimate and MOE, ACS 2018 1-year — acs2018_1yr page not fetched; web search returned only data.census.gov table pages
MISSING DATA: United States B19013 estimate and MOE, ACS 2018 1-year — same as above
