**CPI-U, U.S. city average, all items, not seasonally adjusted, series CUUR0000SA0: annual averages (period M13, "Annual"), 2015–2023, index 1982-84=100**

Source for all nine values: BLS Public Data API v2, fetched 2026-10-23. Each value comes from the M13 record in the API response saved as [S59]. I extracted the values with a local script [S63].

| year | CPI-U annual average (index, 1982-84=100) | source URL | retrieved date |
|---|---|---|---|
| 2015 | 237.017 [S63] | https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true [S59] | 2026-10-23 |
| 2016 | 240.007 [S63] | same URL [S59] | 2026-10-23 |
| 2017 | 245.120 [S63] | same URL [S59] | 2026-10-23 |
| 2018 | 251.107 [S63] | same URL [S59] | 2026-10-23 |
| 2019 | 255.657 [S63] | same URL [S59] | 2026-10-23 |
| 2020 | 258.811 [S63] | same URL [S59] | 2026-10-23 |
| 2021 | 270.970 [S63] | same URL [S59] | 2026-10-23 |
| 2022 | 292.655 [S63] | same URL [S59] | 2026-10-23 |
| 2023 | 304.702 [S63] | same URL [S59] | 2026-10-23 |

The API returned status REQUEST_SUCCEEDED, series ID CUUR0000SA0 and period M13 / periodName "Annual" when fetched on 2026-10-23 [S59, S62]. Nothing was estimated or filled from memory.

**Series-definition points (for the fit rationale)**
- **Series ID breakdown:** CUUR0000SA0 is the CPI for All Urban Consumers (CPI-U). "CU" is the CPI-U survey, "U" means not seasonally adjusted, "0000" is U.S. city average, and "SA0" is all items. This is the BLS series-ID convention from my own knowledge [unverified]. The fetched API response (2026-10-23) confirms only the series ID, M13 and "Annual" [S59].
- **Base period:** the index base 1982-84=100 comes from the task's working interpretation. It is not in the fetched API output or in the saved text of the BLS CPI overview page (a search for the base-period years found no match there) [S63].
- **Definition page:** https://www.bls.gov/cpi/overview.htm, "Consumer Price Indexes Overview", fetched 2026-10-23 [S61]. Citing it as the CPI definition page is my own judgement. The saved text did not show the words for the base period or "urban" in the searches I ran [S63], so I could not quote a definition from it.
- **Why the series fits:** it is the BLS headline all-items price index for the U.S. city average. The annual average (M13) matches the annual ACS income reference, and it is the series the task names.

**Limitations**
- The base 1982-84=100 and the NSA / all-items / U.S. city average meaning of the series ID rest on the task's working interpretation and BLS convention. They are not quoted from a fetched BLS page. Checking them against a BLS series-ID or CPI factsheet page would close this gap.
- The API's annual value was used as published; I did not recompute it from the monthly values.
MISSING DATA: Explicit BLS statement of the 1982-84=100 base and NSA/all-items/U.S. city average definition — searched the BLS API response [S59] and the CPI overview page text [S61]; neither text contained the base-period years
