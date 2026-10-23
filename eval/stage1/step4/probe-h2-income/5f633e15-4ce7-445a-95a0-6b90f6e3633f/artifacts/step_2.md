I read "between 2015 and 2023" as Endpoints only: 2015 and 2023; if you meant Every year from 2015 through 2023, with change from 2015 to 2023, the answer below may not apply.

**CPI-U, U.S. city average, all items, not seasonally adjusted, 1982-84=100. Series CUUR0000SA0, annual average (BLS period code M13 = "Annual" = annual average; not a monthly or December value) [S92].**

| Year | Annual average CPI-U | Series ID | Source URL | Retrieval date |
|---|---|---|---|---|
| 2015 | 237.017 [S44][S92] | CUUR0000SA0 | https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true (BLS Public API, primary source) | 2026-10-22 [S44] |
| 2023 | 304.702 [S44][S92] | CUUR0000SA0 | https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true (BLS Public API, primary source) | 2026-10-22 [S44] |

**Cross-check (second BLS page, a published table, not the API):** "Consumer Price Indexes for All Urban Consumers (CPI-U), U.S. city average and selected metropolitan areas, annual average and percent change, 2015-2025 (1982-84=100)", https://www.bls.gov/regions/mid-atlantic/data/consumerpriceindexannualandsemiannual_table.htm, retrieved 2026-10-22 [S46]. Its U.S. city average column shows 2015 = 237.017 and 2023 = 304.702 [S92]. Both BLS pages give identical values; no discrepancy. Both are BLS pages, so no secondary mirror was needed.

Verification: the API records read "year":"2015","period":"M13","periodName":"Annual","value":"237.017" and "year":"2023","period":"M13","periodName":"Annual","value":"304.702" [S92].

Deflator for the next step (2023 base): CPI2023 / CPI2015 = 304.702 / 237.017 = 1.2855702 (Python result 1.2855702333587886) [S92]. Adjusted value = nominal × 304.702 / CPIyear; for 2023 the factor is 304.702 / 304.702 = 1. The CPI-U rose 28.557% from 2015 to 2023 (1.2855702 − 1 = 0.2855702, from the same calculation) [S92].

Notes:
- Release year: the fetched BLS pages [S44][S46] do not show a publication or release year for these values. They were read on 2026-10-22 as currently published. No release year is stated from memory.
- No seasonally adjusted series and no C-CPI-U were used. No values came from memory.
- The CPI inputs are complete and verified. The ACS B19013 inputs are outside this step (step 1) and are still needed before the CSV and chart can be built.
MISSING DATA: Publication/release year of the BLS CPI-U annual averages — not shown on the fetched BLS API response [S44] or the BLS annual table [S46]
