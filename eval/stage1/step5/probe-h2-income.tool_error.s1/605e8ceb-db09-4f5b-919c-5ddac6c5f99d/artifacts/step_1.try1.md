| year | geography | B19013 estimate | MOE | source URL | vintage | retrieved date |
|---|---|---|---|---|---|---|
| 2015 | Indiana (state:18) | UNAVAILABLE: the data.census.gov page [S1] showed no readable Indiana value. The API request returned "Missing Key" [S8]. | UNAVAILABLE | https://data.census.gov/cedsci/table?q=B19013&tid=ACSDT1Y2015.B19013&hidePreview=false [S1]; https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 [S8] | ACS 2015 1-year, standard release | 2026-10-23 |
| 2015 | United States (us:1) | UNAVAILABLE: the page [S1] is script-rendered and its value cells could not be read. | UNAVAILABLE | https://data.census.gov/cedsci/table?q=B19013&tid=ACSDT1Y2015.B19013&hidePreview=false [S1] | ACS 2015 1-year, standard release | 2026-10-23 |
| 2016 | Indiana (state:18) | UNAVAILABLE: no 2016 B19013 page was fetched, because the turn budget ran out. | UNAVAILABLE | Intended source, not fetched: https://data.census.gov/table/ACSDT1Y2016.B19013 | ACS 2016 1-year, standard release | 2026-10-23 |
| 2016 | United States (us:1) | UNAVAILABLE: no 2016 B19013 page was fetched, because the turn budget ran out. | UNAVAILABLE | Intended source, not fetched: https://data.census.gov/table/ACSDT1Y2016.B19013 | ACS 2016 1-year, standard release | 2026-10-23 |

Limitations:
- The Census API needs a key in this run. The one request I made returned "Missing Key" [S8]. The data.census.gov pages are script-rendered, and the saved 2015 page [S1] kept the headings but not the value cells.
- Local file reads and shell commands failed with injected faults on several turns, and the turn limit was reached.
- I filled in nothing from memory, and I estimated and interpolated nothing. All four values stay UNAVAILABLE until they are read from the Census API with a key or from a rendered Census table.
- 2015 and 2016 are standard 1-year releases, so the experimental 2020 flag does not apply to this step.
- The later CPI-U adjustment steps cannot use 2015 or 2016 ACS values until they are retrieved.
BLOCKED: Census API access — could not query api.census.gov for B19013_001E/_001M for state:18 and us:1 (2015, 2016); the request returned Missing Key
BLOCKED: Readable rendering of data.census.gov table values — value cells in the fetched 2015 page were not legible, and the 2016 page was not fetched
MISSING DATA: ACS 2015 1-year B19013 estimate and MOE, Indiana — data.census.gov ACSDT1Y2015.B19013 [S1]; api.census.gov 2015 [S8]
MISSING DATA: ACS 2015 1-year B19013 estimate and MOE, United States — data.census.gov ACSDT1Y2015.B19013 [S1] (value not readable)
MISSING DATA: ACS 2016 1-year B19013 estimate and MOE, Indiana — not fetched
MISSING DATA: ACS 2016 1-year B19013 estimate and MOE, United States — not fetched
