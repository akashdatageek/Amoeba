I read "weekly retail on-highway diesel price for Indiana" as EIA weekly Midwest (PADD 2) on-highway diesel price used as a proxy for Indiana; if you meant EIA weekly retail on-highway diesel price, Indiana, all types (PADD 2 Midwest state series, if published) or EIA weekly U.S. national average on-highway diesel price as a fallback, the answer below may not apply.

**Step 1 result: EIA weekly Midwest (PADD 2) No. 2 diesel retail price, 52 latest weeks**

- Series: EMD_EPD2D_PTE_R20_DPG, "Weekly Midwest No. 2 Diesel Retail Prices", $/gal. The ID matches the page URL parameter s=emd_epd2d_pte_r20_dpg [S6][S20]. Midwest (PADD 2) is a proxy for Indiana, not an Indiana price.
- Source URL (public EIA weekly history page): https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=emd_epd2d_pte_r20_dpg&f=W [S6]
- Retrieved: 2026-10-22 (America/Chicago). This date is in the retrieved_date column of every row [S20].
- File: eia_weekly_diesel.csv, header plus 52 data rows, columns week_date, price_usd_per_gal, series_id, source_url, retrieved_date [S21].
- Range: oldest row week of 2025-10-20 at $3.564/gal. Newest published week on the page is **2026-10-12 at $6.259/gal, as of 2026-10-12** [S20][S21].
- Spacing check, done by code on the saved CSV: 52 rows, 52 unique dates, every gap is 7 days, every date is a Monday [S20]. No week is missing inside the 52 rows.
- Duplicates: the first parse gave duplicate dates (3,400 values, 1,700 after de-duplication) because the page text repeats its data. They were removed, and 52 unique weeks remain [S19][S20].

**Flag: newest release.** Today is Thursday 2026-10-22. The fetched page's last row is the week of 2026-10-12. The Monday 2026-10-19 price is not in the file. A final grep of the page for "10/19" found only rows from other years, so the page does not hold it [S21]. No newer-value search was completed because I ran out of turns. The week of 2026-10-19 may already be published on EIA; if it is, the CSV's newest row is not the latest release.

**Prices visible in tool output (week date, $/gal; all from the EIA page fetched 2026-10-22; series EMD_EPD2D_PTE_R20_DPG; URL above)** [S21]:

| week_date | price_usd_per_gal | week_date | price_usd_per_gal |
|---|---|---|---|
| 2025-10-20 | 3.564 | 2026-03-23 | 5.160 |
| 2025-10-27 | 3.715 | 2026-03-30 | 5.105 |
| 2025-11-03 | 3.773 | 2026-04-06 | 5.304 |
| 2025-11-10 | 3.891 | 2026-04-13 | 5.382 |
| 2025-11-17 | 3.913 | 2026-04-20 | 5.165 |
| 2025-11-24 | 3.850 | 2026-04-27 | 5.131 |
| 2025-12-01 | 3.755 | 2026-05-04 | 5.742 |
| 2025-12-08 | 3.635 | 2026-05-11 | 5.815 |
| 2025-12-15 | 3.567 | 2026-05-18 to 2026-07-06 (8 weeks) | in the CSV only, not visible to me |
| 2025-12-22 | 3.483 | 2026-07-13 | 4.659 [S20] |
| 2025-12-29 | 3.424 | 2026-07-20 | 4.988 [S20] |
| 2026-01-05 | 3.387 | 2026-07-27 | 5.196 [S20] |
| 2026-01-12 | 3.365 | 2026-08-03 | 5.262 [S20] |
| 2026-01-19 | 3.445 | 2026-08-10 | 5.181 [S20] |
| 2026-01-26 | 3.579 | 2026-08-17 | 5.435 [S20] |
| 2026-02-02 | 3.625 | 2026-08-24 | 5.636 [S20] |
| 2026-02-09 | 3.636 | 2026-08-31 | 5.571 [S20] |
| 2026-02-16 | 3.664 | 2026-09-07 | 5.946 [S20] |
| 2026-02-23 | 3.798 | 2026-09-14 | 6.250 [S20] |
| 2026-03-02 | 3.888 | 2026-09-21 | 6.680 [S20] |
| 2026-03-09 | 4.801 | 2026-09-28 | 6.526 [S20] |
| 2026-03-16 | 4.970 | 2026-10-05 | 6.286 [S20] |
| | | 2026-10-12 | 6.259 [S20] |

That is 44 of the 52 rows. The 8 weeks from 2026-05-18 to 2026-07-06 (05-18, 05-25, 06-01, 06-08, 06-15, 06-22, 06-29, 07-06) are in eia_weekly_diesel.csv, but their prices did not appear in the output I saw. I have not filled them from memory or by estimate. Later steps must read them from the CSV.

**Note for later steps.** Prices from March 2026 onward are mostly above $5.00, the top of the memo's $3.00–$5.00 band range. Use the CSV values as fetched.

- Any value newer than the page's last row (2026-10-12), or a later revision to a past week.
- An independent cross-check against the API or against the other saved pages (S1–S3), which I did not use for any value.
- An Indiana-specific price.
MISSING DATA: EIA Midwest diesel price for the week of 2026-10-19 — not on the fetched EIA history page (last row 2026-10-12); no newer-value search completed
MISSING DATA: Prices for the 8 weeks 2026-05-18 to 2026-07-06 in this text — not visible in tool output; present only in eia_weekly_diesel.csv
