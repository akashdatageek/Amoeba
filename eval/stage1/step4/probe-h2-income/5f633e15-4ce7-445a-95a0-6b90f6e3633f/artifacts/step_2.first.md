I read "between 2015 and 2023" as Endpoints only: 2015 and 2023; if you meant Every year from 2015 through 2023, with change from 2015 to 2023, the answer below may not apply.

**CPI-U, U.S. city average, all items, not seasonally adjusted, 1982-84=100. Series CUUR0000SA0, annual average (BLS period code M13 = annual average, not a monthly or December value).**

| Year | Annual average CPI-U | Series ID | Source URL | Retrieval date |
|---|---|---|---|---|
| 2015 | 237.017 [S55] | CUUR0000SA0 | https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true (BLS Public API, primary) | 2026-10-22 (fetched 2026-10-23 00:06 UTC) [S44] |
| 2023 | 304.702 [S57] | CUUR0000SA0 | https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true (BLS Public API, primary) | 2026-10-22 (fetched 2026-10-23 00:06 UTC) [S44] |

**Cross-check (second BLS page, a published table rather than the API):** "Consumer Price Indexes for All Urban Consumers (CPI-U), U.S. city average and selected metropolitan areas, annual average and percent change, 2015-2025 (1982-84=100)", https://www.bls.gov/regions/mid-atlantic/data/consumerpriceindexannualandsemiannual_table.htm, retrieved 2026-10-22 (fetched 2026-10-23 UTC) [S46]. The U.S. city average column shows 2015 = 237.017 (0.1% change) and 2023 = 304.702 (4.1% change) [S56][S57]. Both pages give the same two values, so there is no discrepancy.

Notes:
- Both values are the published annual averages (period M13, "Annual") from the API response, and the API response labels the series as the not seasonally adjusted CPI-U [S44]. No seasonally adjusted series and no C-CPI-U were used. The C-CPI-U table (S48) was not used.
- No values came from memory. No gaps.
- Deflator for the next step: adjusted = nominal × 304.702 / 237.017 (2023 base), per the task's formula.
