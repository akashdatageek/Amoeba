I read "weekly retail on-highway diesel price for Indiana" as EIA weekly retail on-highway diesel prices, all types, for the Midwest PADD 2 region, used as a proxy for Indiana; if you meant A true Indiana state-level EIA weekly series, if one exists or Indianapolis city or Midwest regional price used in place of the state, the answer below may not apply. I read "each 5-cent price band from $3.00 to $5.00" as Bands such as $3.00–3.049, $3.05–3.099, and so on up to $5.00, with the surcharge computed at the band's price; if you meant Bands stepping from $3.00 by $0.05 to $5.00 as 41 price points, with the surcharge at each point, the answer below may not apply.

**STEP 2: EIA weekly Midwest (PADD 2) on-highway diesel prices, 52 weeks**

Series: EMD_EPD2D_PTE_R20_DPG, "Weekly Midwest No 2 Diesel Retail Prices (Dollars per Gallon)" [S10].
URL: https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMD_EPD2D_PTE_R20_DPG&f=W
Retrieved 2026-10-16 (today).

**File:** eia_prices.csv has a header and 52 data rows (53 lines) [S14]. Columns: week_date, price_usd_per_gal, series_id, source_url, retrieved_date. Every row carries the series ID, the URL above and retrieved_date 2026-10-16.

**Checks run in code:**
- 1,697 unique weekly values were parsed from the page [S13].
- The last 52 values run from 2025-09-29 to 2026-09-21 [S13].
- All 52 dates are Mondays and exactly 7 days apart [S13].
- No week is missing in that window.

**Latest week:** 2026-09-21 = $6.680/gal, as of 2026-09-21. This is the last data point on the fetched EIA page [S12]. It is earlier than today (2026-10-16). I did not run a second search for newer weeks (2026-09-28, 10-05, 10-12), so I cannot confirm whether EIA has published them. If it has, the 52-week window would shift forward.

**Release date:** The page's text shows "Release Date: 9/22/2026" and also "Release Date: 9/29/2026" [S14]. I could not tell which one applies to the table I read. The last data point is dated 2026-09-21, which fits a 9/22/2026 release. A 9/29/2026 date might mean a newer release with a 2026-09-28 week. That is unconfirmed. I settled on 2026-09-21 as the latest week.

**Indiana series:** I found no Indiana state-level weekly diesel series in any page I fetched. The only Indiana mention was a PADD 2 description that lists Indiana as a member state [S6]. I did not check EIA's full state list. Midwest PADD 2 is therefore the proxy, as the settled interpretation says.

**Table (series for every row: EMD_EPD2D_PTE_R20_DPG; URL: https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMD_EPD2D_PTE_R20_DPG&f=W; retrieved 2026-10-16):**

| week_date | price_usd_per_gal | series_id | source_url |
|---|---|---|---|
| 2025-09-29 | 3.731 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-10-06 | 3.670 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-10-13 | 3.606 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-10-20 | 3.564 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-10-27 | 3.715 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-11-03 | 3.773 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-11-10 | 3.891 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-11-17 | 3.913 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-11-24 | 3.850 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-12-01 | 3.755 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-12-08 | 3.635 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-12-15 | 3.567 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-12-22 | 3.483 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2025-12-29 | 3.424 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-01-05 | 3.387 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-01-12 | 3.365 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-01-19 | 3.445 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-01-26 | 3.579 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-02-02 | 3.625 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-02-09 | 3.636 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-02-16 | 3.664 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-02-23 | 3.798 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-03-02 | 3.888 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-03-09 | 4.801 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-03-16 | 4.970 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-03-23 | 5.160 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-03-30 | 5.105 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-04-06 | 5.304 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-04-13 | 5.382 [S14] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-04-20 | 5.165 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-04-27 | 5.131 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-05-04 | 5.742 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-05-11 | 5.815 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-05-18 | 5.749 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-05-25 | 5.623 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-06-01 | 5.392 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-06-08 | 5.182 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-06-15 | 5.011 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-06-22 | 4.751 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-06-29 | 4.583 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-07-06 | 4.458 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-07-13 | 4.659 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-07-20 | 4.988 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-07-27 | 5.196 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-08-03 | 5.262 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-08-10 | 5.181 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-08-17 | 5.435 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-08-24 | 5.636 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-08-31 | 5.571 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-09-07 | 5.946 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-09-14 | 6.250 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |
| 2026-09-21 | 6.680 [S12] | EMD_EPD2D_PTE_R20_DPG | EIA URL above |

**Gaps and caveats:**
- All 52 weeks have a value. None is MISSING.
- Not confirmed: whether weeks after 2026-09-21 exist on EIA. No newer-value search was run, and the page also shows a 9/29/2026 release date [S14].
- Not confirmed: the Indiana state series. None was found, and the check was not exhaustive.
- Many prices here sit well above the typical $3–4 range, and the series jumps from 3.888 to 4.801 in the week of 2026-03-09. These are the values on the fetched EIA page [S12][S14], and I did not independently verify them. Later steps should use them as published.
MISSING DATA: Whether EIA has published weeks after 2026-09-21 (09-28, 10-05, 10-12) — no newer-value search run; the page also shows a 9/29/2026 release date, unresolved
MISSING DATA: Indiana state-level weekly EIA diesel series — none found in fetched pages; EIA state list not exhaustively checked
