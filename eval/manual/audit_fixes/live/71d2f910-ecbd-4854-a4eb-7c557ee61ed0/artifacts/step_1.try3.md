I read "weekly retail on-highway diesel price for Indiana" as EIA weekly retail on-highway diesel prices, all types, for the state of Indiana (if EIA publishes a state series); if you meant EIA Midwest (PADD 2) regional weekly diesel price used as a stand-in for Indiana or EIA U.S. national average weekly diesel price, the answer below may not apply.

STATUS: PARTIAL. The 52-week table is NOT complete and the eia_weekly.csv on disk is defective. Details are in the data note. Below are only the weekly prices I actually saw in tool output [S24]. Nothing is estimated or interpolated.

Series used (stand-in, not Indiana): Midwest (PADD 2) No 2 Diesel Retail Prices, weekly, $/gal, ID EMD_EPD2D_PTE_R20_DPG. Source URL for every row: https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMD_EPD2D_PTE_R20_DPG&f=W [S4]

| week_date | price_usd_per_gal | series_name | series_id | area | source_url |
|---|---|---|---|---|---|
| 2026-03-30 | 5.105 | Midwest No 2 Diesel Retail Prices, weekly | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2), stand-in for Indiana | https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMD_EPD2D_PTE_R20_DPG&f=W |
| 2026-04-06 | 5.304 | same | same | same | same |
| 2026-04-13 | 5.382 | same | same | same | same |
| 2026-04-20 | 5.165 | same | same | same | same |
| 2026-04-27 | 5.131 | same | same | same | same |
| 2026-05-04 | 5.742 | same | same | same | same |
| 2026-05-11 | 5.815 | same | same | same | same |
| 2026-05-18 | 5.749 | same | same | same | same |
| 2026-05-25 | 5.623 | same | same | same | same |
| 2026-06-01 | 5.392 | same | same | same | same |
| 2026-06-08 | 5.182 | same | same | same | same |
| 2026-06-15 | 5.011 | same | same | same | same |
| 2026-06-22 | 4.751 | same | same | same | same |
| 2026-06-29 | 4.583 | same | same | same | same |
| 2026-07-06 | 4.458 | same | same | same | same |
| 2026-07-13 | 4.659 | same | same | same | same |
| 2026-07-20 | 4.988 | same | same | same | same |
| 2026-07-27 | 5.196 | same | same | same | same |
| 2026-08-03 | 5.262 | same | same | same | same |
| 2026-08-10 | 5.181 | same | same | same | same |

Rows shown: 20 weeks (2026-03-30 to 2026-08-10), all Mondays, 7 days apart, taken from the printed output of my extraction script [S24]. The remaining weeks through 2026-09-21, and the 26 weeks before 2026-03-30, were not visible to me. The printed output was cut off ("971 characters cut") [S24].

DATA NOTE
- Indiana series: NOT CONFIRMED either way, and most likely none exists. The areas list on EIA's weekly retail gasoline and diesel page, https://www.eia.gov/dnav/pet/pet_pri_gnd_dcus_nus_w.htm [S1], reads in the part I could see: "U.S., East Coast (PADD 1), New England (PADD 1A), Central Atlantic (PADD 1B), Lower Atlantic (PADD 1C), Midwest (PADD 2), Gulf Coast (PADD 3), Rocky Mountain (PADD 4), West Coast (PADD 5), West Coast les[s CA]..." [S24]. The line was cut off, so I could not see whether states follow. No "Indiana" text was shown to me. The stand-in is therefore Midwest PADD 2, as the role card instructs when no Indiana series is found. A later step should re-check [S1] for "Indiana" (the count command I ran printed a figure I could not see).
- Series used: Midwest (PADD 2) No 2 Diesel Retail Prices (Dollars per Gallon), weekly, ID EMD_EPD2D_PTE_R20_DPG [S4]. It is a regional stand-in, NOT an Indiana price. The XLS download is EMD_EPD2D_PTE_R20_DPGw.xls [S6].
- Latest week on the Midwest history page: 2026-09-21, with a 52-row window of 2026-03-30 to 2026-09-21 [S24]. The page release date is 9/22/2026 [S4]. The national page release date is 10/6/2026 [S1], [S20], [S23]. The Midwest history page therefore appears to stop at 2026-09-21, before the latest Monday of 2026-10-12 and later releases up to today (2026-10-16). I did not find a newer Midwest release. The "as of" date I can support is 2026-09-21, from a page released 2026-09-22.
- Retrieval date: 2026-10-16, when the page [S4] was fetched.
- DEFECT in eia_weekly.csv: my script [S24] wrote a file with 52 data rows, but each date appears twice. The check printed day spacings {0, 7}, so the rows are duplicated pairs and the file holds only about 26 distinct weeks (2026-03-30 to 2026-09-21), not 52. The total parsed row count was 3394, roughly twice the number of weeks since 1997, so the history table is parsed twice (the page probably shows the same table in two blocks). The fix is to de-duplicate by date (for example with a dict keyed by date) and then take the last 52 distinct Mondays, which would reach back to about 2025-09-29. I had no turns left to apply it. Do not use the current eia_weekly.csv as delivered.
- Price range in the defective window (2026-03-30 to 2026-09-21): minimum 4.458 and maximum 6.680 $/gal [S24]. Prices are 3-decimal values as published. All dates were Mondays [S24].
- Prices in this window are all above $4.40. The price band the later memo covers, $3.00 to $5.00, may not span the maximum of 6.680 [S24], so later steps should check this.
- NEXT STEP (about 2 turns): rerun the parse on sources/S4_Weekly_Midwest_No_2_Diesel_Retail_Prices.txt with de-duplication by date, take the last 52 distinct Mondays, confirm 52 rows with 7-day spacing and prices between 1 and 10, rewrite eia_weekly.csv, and re-check S1 for "Indiana".
BLOCKED: local:Bash — no turns were left to rerun the extraction with de-duplication, so eia_weekly.csv still holds duplicated date rows (about 26 distinct weeks) instead of 52 distinct weeks
MISSING DATA: Distinct weekly Midwest (PADD 2) prices for 2025-09-29 to 2026-03-23 and 2026-08-17 to 2026-09-21 — saved EIA history page sources/S4 (fetched, printed output cut off, not re-parsed)
MISSING DATA: Confirmation that EIA has no Indiana state diesel series — EIA page [S1] areas list (output cut off before any state names)
MISSING DATA: Any Midwest weekly price after 2026-09-21 (Mondays 2026-09-28, 10-05, 10-12) — saved page [S4] released 9/22/2026; no newer-release search done
