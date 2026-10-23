I read "weekly retail on-highway diesel price for Indiana" as EIA weekly Midwest (PADD 2) on-highway diesel price used as a proxy for Indiana; if you meant EIA weekly retail on-highway diesel price, Indiana, all types (PADD 2 Midwest state series, if published) or EIA weekly U.S. national average on-highway diesel price as a fallback, the answer below may not apply.

Proxy note: Midwest (PADD 2) prices are a proxy for Indiana (an assumption). No Indiana series was used.

SOURCE AND SERIES
- Series: Weekly Midwest No 2 Diesel Retail Prices, Dollars per Gallon, series ID EMD_EPD2D_PTE_R20_DPG [S6].
- URL: https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=emd_epd2d_pte_r20_dpg&f=W
- Retrieved 2026-10-22 (America/Chicago). The page states "Release Date: 10/14/2026" and "Next Release Date: 10/20/2026" [S8].
- Latest price in the fetched page: $6.259/gal, week of 2026-10-12 (as of the 2026-10-14 release) [S6][S9].

FILE: eia_weekly_diesel.csv in the workspace. It has a header plus 52 data rows. Columns: week_date, price_usd_per_gal, series_id, source_url, retrieved_date. Every row has series_id EMD_EPD2D_PTE_R20_DPG, the URL above, and retrieved_date 2026-10-22.

CHECKS (Python on the fetched page text)
- The first parse had duplicate rows and failed the spacing check. After de-duplication it passed: spacing7 True, allMonday True [S9].
- Date range: 2025-10-20 to 2026-10-12, 52 weekly rows.
- 52-week mean $4.734/gal (weeks 2025-10-20 to 2026-10-12) [S9].
- Low $3.365 in the week of 2026-01-12 [S9].
- High $6.680 in the week of 2026-09-21 [S9].

THE 52 ROWS (week_date = Monday EIA price date; price in $/gal; all from [S6], parsed in [S9]; each price is dated by its week_date)
2025-10-20 3.564 | 2025-10-27 3.715 | 2025-11-03 3.773 | 2025-11-10 3.891 | 2025-11-17 3.913 | 2025-11-24 3.850 | 2025-12-01 3.755 | 2025-12-08 3.635 | 2025-12-15 3.567 | 2025-12-22 3.483 | 2025-12-29 3.424 | 2026-01-05 3.387 | 2026-01-12 3.365 | 2026-01-19 3.445 | 2026-01-26 3.579 | 2026-02-02 3.625 | 2026-02-09 3.636 | 2026-02-16 3.664 | 2026-02-23 3.798 | 2026-03-02 3.888 | 2026-03-09 4.801 | 2026-03-16 4.970 | 2026-03-23 5.160 | 2026-03-30 5.105 | 2026-04-06 5.304 | 2026-04-13 5.382 | 2026-04-20 5.165 | 2026-04-27 5.131 | 2026-05-04 5.742 | 2026-05-11 5.815 | 2026-05-18 5.749 | 2026-05-25 5.623 | 2026-06-01 5.392 | 2026-06-08 5.182 | 2026-06-15 5.011 | 2026-06-22 4.751 | 2026-06-29 4.583 | 2026-07-06 4.458 | 2026-07-13 4.659 | 2026-07-20 4.988 | 2026-07-27 5.196 | 2026-08-03 5.262 | 2026-08-10 5.181 | 2026-08-17 5.435 | 2026-08-24 5.636 | 2026-08-31 5.571 | 2026-09-07 5.946 | 2026-09-14 6.250 | 2026-09-21 6.680 | 2026-09-28 6.526 | 2026-10-05 6.286 | 2026-10-12 6.259

GAPS AND FLAGS
1. The newest row may not be the latest EIA release. The newest row is the week of 2026-10-12 ($6.259), as of the 2026-10-14 release [S8]. Today is 2026-10-22. The page's "Next Release Date: 10/20/2026" suggests a 2026-10-19 price exists. It was not in the fetched copy, and I had no turns left to re-search. The 2026-10-19 value is NOT OBTAINED. If it exists, shift the window one week: add 2026-10-19 and drop 2025-10-20. I settled on 2026-10-12 as the newest date.
2. The Indiana series was not used. Prices are Midwest averages and may differ from Indiana's.
3. Prices are kept at the 3 decimals shown on EIA's page.
4. The EIA API was not used. I parsed the public history page.
MISSING DATA: EIA Midwest diesel price for week of 2026-10-19 (release dated 10/20/2026) — fetched EIA history page (retrieved 2026-10-22) showed release date 10/14/2026 only; no turns left to re-search
