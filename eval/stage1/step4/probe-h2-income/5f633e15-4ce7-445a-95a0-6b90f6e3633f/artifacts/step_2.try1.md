CPI-U, U.S. city average, all items, not seasonally adjusted, 1982-84=100, series CUUR0000SA0, ANNUAL AVERAGE (BLS period code M13 = annual average; not December or any monthly value).

| Year | Annual average CPI-U | Series ID | Source URL | Retrieval date |
|---|---|---|---|---|
| 2015 | 237.017 [S44][S52] | CUUR0000SA0 | https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true (BLS Public API v2, primary) | 22 October 2026 |
| 2023 | 304.702 [S44][S52] | CUUR0000SA0 | https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true (BLS Public API v2, primary) | 22 October 2026 |

Cross-check (second BLS page, a different BLS publication, not a mirror): BLS Mid-Atlantic Information Office, "Summary of annual and semi-annual indexes", https://www.bls.gov/regions/mid-atlantic/data/consumerpriceindexannualandsemiannual_table.htm [S46], retrieved 22 October 2026. Its U.S. city average annual-average column shows 2015 = 237.017 and 2023 = 304.702 [S46][S52]. These match the API values exactly. That table is titled "CPI-U, U.S. city average and selected metropolitan areas, annual average and percent change, 2015-2025 (1982-84=100)" [S46]. It is a table of the all-items CPI-U. The search excerpt did not show the series ID or the seasonal-adjustment status, so the series identity rests on the API result [S44].

Derived for later steps (from the values above): CPI2023 / CPI2015 = 304.702 / 237.017 = 1.2856 (approx.). Adjusted 2015 income = nominal 2015 × 304.702 / 237.017.

Limits: FRED mirror fetch (https://fred.stlouisfed.org/data/CUUR0000SA0.txt) returned 404, so no FRED check was made. The retrieval date is today's run date; the BLS API response itself carries no date stamp.
MISSING DATA: FRED mirror of CUUR0000SA0 — fetch of fred.stlouisfed.org/data/CUUR0000SA0.txt returned 404; not checked
