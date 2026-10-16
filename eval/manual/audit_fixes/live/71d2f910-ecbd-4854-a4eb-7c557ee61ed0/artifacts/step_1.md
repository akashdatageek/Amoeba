I read "weekly retail on-highway diesel price for Indiana" as EIA weekly retail on-highway diesel prices, all types, for the state of Indiana (if EIA publishes a state series); if you meant EIA Midwest (PADD 2) regional weekly diesel price used as a stand-in for Indiana or EIA U.S. national average weekly diesel price, the answer below may not apply.

STATUS: PARTIAL. Do not use eia_weekly.csv. The 52-week price table was not delivered.

**State of eia_weekly.csv**
- My last command rewrote eia_weekly.csv with the six required column headers and no data rows. It found no prices when it parsed the saved EIA files, so the file now has 0 rows [S35].
- Before that, the file had 52 rows. Each of 26 distinct Monday dates appeared twice, from 2026-03-30 to 2026-09-21 [S33]. That version was invalid too.
- I ran out of turns before I could rebuild the file.
- The table below is the only price data I can vouch for. It has the 16 distinct weeks I saw in the cut-off output [S33]. It is not a 52-week series.
- Fixing the file needs a re-parse of the saved EIA history page (sources/S4_Weekly_Midwest_No_2_Diesel_Retail_Prices.txt [S4]). The parser must read that page's actual table layout. My regex patterns matched nothing in S4 or S6 [S35]. After parsing, drop duplicates and take the 52 latest Mondays. Check that the dates are 7 days apart.

**Partial table (distinct weeks seen, not 52)**
Every row below uses the same series_name, series_id, area and source_url:
- series_name: Weekly Midwest No 2 Diesel Retail Prices (Dollars per Gallon) [S4]
- series_id: EMD_EPD2D_PTE_R20_DPG [S4]
- area: Midwest (PADD 2), a stand-in for Indiana
- source_url: https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMD_EPD2D_PTE_R20_DPG&f=W

| week_date | price_usd_per_gal | series_id | area |
| --- | --- | --- | --- |
| 2026-03-30 | 5.105 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-04-06 | 5.304 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-04-13 | 5.382 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-04-20 | 5.165 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-04-27 | 5.131 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-05-04 | 5.742 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-05-11 | 5.815 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-05-18 | 5.749 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-05-25 | 5.623 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-06-01 | 5.392 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-06-08 | 5.182 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-06-15 | 5.011 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-06-22 | 4.751 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-06-29 | 4.583 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-07-06 | 4.458 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |
| 2026-09-21 | 6.680 [S33] | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in |

Weeks from 2026-07-13 to 2026-09-14 are missing from this table. I did not see their values, and I have not estimated any of them. All 52 weeks, and the weeks before 2026-03-30, are missing from this deliverable.

**Data note**
- Indiana series found: not confirmed.
  - I fetched EIA's weekly retail gasoline and diesel page, https://www.eia.gov/dnav/pet/pet_pri_gnd_dcus_nus_w.htm [S1].
  - My last search of the saved page text for "ndiana" returned a count of 0 for both S1 and S4 [S35]. The S1 text does list Midwest (PADD 2) and the state names Minnesota, New York, Ohio, Texas and Washington [S34]. Indiana is not among the names I saw there.
  - The page text shows no Indiana series, so "no" is likely. I did not read the full areas list, so it is not proven. The evidence URL is the S1 page above.
- Series used: Weekly Midwest No 2 Diesel Retail Prices (Dollars per Gallon), series ID EMD_EPD2D_PTE_R20_DPG, Midwest (PADD 2) [S4]. This is a regional stand-in for Indiana, not an Indiana price.
  - The title says "No 2 Diesel", while the task asks for all types. I did not check whether the two are the same series.
- Latest week seen: 2026-09-21 at 6.680 USD/gal, as of that date [S33].
  - Today is 2026-10-16. Mondays 2026-09-28, 2026-10-05 and 2026-10-12 may be published. I did not check for them, so the latest EIA release is unconfirmed. I did not make the required second search for a newer value.
- EIA release date on the page: not extracted. A search for "release date" text in S1 and S4 returned nothing I could read [S34].
- Retrieval date: I assume the pages were fetched on 2026-10-16, the run date. The sources index did not show a fetch date.
- Anomalies:
  - The earlier file had every week duplicated [S33].
  - The final overwrite left the file empty [S35].
  - The prices are high for diesel (5.815 on 2026-05-11, 6.680 on 2026-09-21) [S33]. I did not check them against the EIA page. I only saw values from the cut-off output.

Later steps should not compute surcharges or fleet cost until the 52 weekly prices exist.
MISSING DATA: 52 distinct consecutive weekly Midwest diesel prices — eia_weekly.csv is currently header-only after my final overwrite; saved S4/S6 files were not parsed successfully (parser matched 0 rows)
MISSING DATA: Prices for 2026-07-13 to 2026-09-14 and for weeks before 2026-03-30 — not seen in any output
MISSING DATA: Evidence that EIA lists no Indiana diesel series — 'ndiana' count was 0 in S1 and S4, but the full areas list was not read
MISSING DATA: EIA release date on the history page — searched S1 and S4 text, not found
MISSING DATA: Mondays after 2026-09-21 (09-28, 10-05, 10-12) — newer-value search not done
