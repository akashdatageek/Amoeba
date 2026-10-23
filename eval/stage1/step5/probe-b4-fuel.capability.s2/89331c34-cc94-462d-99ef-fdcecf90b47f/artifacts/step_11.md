**weekly_prices.csv is in the workspace.** A check after writing it found 52 rows, 52 unique week_ending dates, one series_id, one retrieved_date and one source_url value [S57, S64].

**Series:** EMD_EPD2D_PTE_R20_DPG, EIA Weekly Midwest (PADD 2) No. 2 Diesel Retail Prices, in dollars per gallon. The title and units come from the EIA dnav page, retrieved 2026-10-23 [S1]. The API response also says "$/GAL" [S5].

**Proxy:** EIA has no Indiana-only weekly diesel series, and nothing I fetched contradicts that. Midwest (PADD 2) is the proxy for Indiana, as agreed.

**Latest week:** as of 2026-10-19, $6.352 per gallon, retrieved 2026-10-23 [S3, S64].
- FRED series GASDESMWW shows the same value for 2026-10-19, 6.352, retrieved 2026-10-23 [S58].
- The dnav page copy was released 10/14/2026 [S1]. It is older than the API pull, so the API data was used.
- The 2026-10-19 week is the newest in both EIA and FRED. I made one more search for a newer week and found none [S58].

**Source URL in the CSV (every row):** https://api.eia.gov/v2/petroleum/pri/gnd/data/?frequency=weekly&data[0]=value&facets[series][]=EMD_EPD2D_PTE_R20_DPG&sort[0][column]=period&sort[0][direction]=desc&length=52 (api_key=DEMO_KEY) [S64]. EIA's page for the same series is https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=emd_epd2d_pte_r20_dpg&f=W [S1].

**Date check:** The first week is 2025-10-27 and the last is 2026-10-19 [S64]. Consecutive weeks are 7 days apart with no gaps and no duplicates, so 52 rows (51 steps) [S57].

**Summary from my parse** [S56]:
- Minimum $3.365, week of 2026-01-12.
- Maximum $6.68, week of 2026-09-21.
- Simple average about $4.787 per gallon.

**Table: weekly_prices.csv** (oldest first). In the table, the source_url column is shortened to the API route. The full URL is given above. Every row has series_id EMD_EPD2D_PTE_R20_DPG and retrieved_date 2026-10-23. Prices are from [S64].

| week_ending | price_usd_per_gal | series_id | source_url | retrieved_date |
|---|---|---|---|---|
| 2025-10-27 | 3.715 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2025-11-03 | 3.773 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2025-11-10 | 3.891 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2025-11-17 | 3.913 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2025-11-24 | 3.85 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2025-12-01 | 3.755 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2025-12-08 | 3.635 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2025-12-15 | 3.567 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2025-12-22 | 3.483 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2025-12-29 | 3.424 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-01-05 | 3.387 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-01-12 | 3.365 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-01-19 | 3.445 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-01-26 | 3.579 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-02-02 | 3.625 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-02-09 | 3.636 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-02-16 | 3.664 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-02-23 | 3.798 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-03-02 | 3.888 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-03-09 | 4.801 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-03-16 | 4.97 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-03-23 | 5.16 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-03-30 | 5.105 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-04-06 | 5.304 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-04-13 | 5.382 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-04-20 | 5.165 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-04-27 | 5.131 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-05-04 | 5.742 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-05-11 | 5.815 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-05-18 | 5.749 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-05-25 | 5.623 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-06-01 | 5.392 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-06-08 | 5.182 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-06-15 | 5.011 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-06-22 | 4.751 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-06-29 | 4.583 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-07-06 | 4.458 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-07-13 | 4.659 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-07-20 | 4.988 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-07-27 | 5.196 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-08-03 | 5.262 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-08-10 | 5.181 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-08-17 | 5.435 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-08-24 | 5.636 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-08-31 | 5.571 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-09-07 | 5.946 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-09-14 | 6.25 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-09-21 | 6.68 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-09-28 | 6.526 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-10-05 | 6.286 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-10-12 | 6.259 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |
| 2026-10-19 | 6.352 | EMD_EPD2D_PTE_R20_DPG | api.eia.gov/v2/petroleum/pri/gnd/data/ | 2026-10-23 |

**Not covered here:** the ATRI figures are not part of this step. raw_eia.txt was not written. The data went straight from sources/S3 to weekly_prices.csv.
MISSING DATA: ATRI total and fuel cost per mile — not part of this step (step 11 covers the EIA prices only)
