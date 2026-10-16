I read "weekly retail on-highway diesel price for Indiana" as EIA weekly retail on-highway diesel prices, all types, for the state of Indiana (if EIA publishes a state series); if you meant EIA Midwest (PADD 2) regional weekly diesel price used as a stand-in for Indiana or EIA U.S. national average weekly diesel price, the answer below may not apply.

STATUS: PARTIAL. eia_weekly.csv is now correct with 52 rows. Unresolved: no Indiana series (Midwest PADD 2 stand-in used), the newest saved week is 2026-09-21 and may be stale, and the release date is ambiguous.

CHECKS ON eia_weekly.csv (re-parsed with duplicates removed) [S14]
- 52 unique Monday dates, 2025-09-29 to 2026-09-21, all gaps exactly 7 days.
- 3-decimal prices, no blanks, low 3.365 (week of 2026-01-12), high 6.680 (week of 2026-09-21).
- The earlier file had duplicate rows. The new parse gives 1,697 distinct dated prices in the saved page [S14].

WEEKLY TABLE (saved as eia_weekly.csv)
All prices are EIA figures from the saved history page [S4], as parsed in [S14]; each is the Monday price for the date shown.
Series name for every row: Midwest (PADD 2) No 2 Diesel Retail Prices (Weekly, Dollars per Gallon). Series ID: EMD_EPD2D_PTE_R20_DPG. Area: Midwest (PADD 2), a stand-in for Indiana. Source URL: https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMD_EPD2D_PTE_R20_DPG&f=W

| week_date | price_usd_per_gal | series_name | series_id | area | source_url |
|---|---|---|---|---|---|
| 2025-09-29 | 3.731 | Midwest (PADD 2) No 2 Diesel Retail Prices (Weekly, $/gal) | EMD_EPD2D_PTE_R20_DPG | Midwest (PADD 2) | URL above |
| 2025-10-06 | 3.670 | same | same | same | URL above |
| 2025-10-13 | 3.606 | same | same | same | URL above |
| 2025-10-20 | 3.564 | same | same | same | URL above |
| 2025-10-27 | 3.715 | same | same | same | URL above |
| 2025-11-03 | 3.773 | same | same | same | URL above |
| 2025-11-10 | 3.891 | same | same | same | URL above |
| 2025-11-17 | 3.913 | same | same | same | URL above |
| 2025-11-24 | 3.850 | same | same | same | URL above |
| 2025-12-01 | 3.755 | same | same | same | URL above |
| 2025-12-08 | 3.635 | same | same | same | URL above |
| 2025-12-15 | 3.567 | same | same | same | URL above |
| 2025-12-22 | 3.483 | same | same | same | URL above |
| 2025-12-29 | 3.424 | same | same | same | URL above |
| 2026-01-05 | 3.387 | same | same | same | URL above |
| 2026-01-12 | 3.365 | same | same | same | URL above |
| 2026-01-19 | 3.445 | same | same | same | URL above |
| 2026-01-26 | 3.579 | same | same | same | URL above |
| 2026-02-02 | 3.625 | same | same | same | URL above |
| 2026-02-09 | 3.636 | same | same | same | URL above |
| 2026-02-16 | 3.664 | same | same | same | URL above |
| 2026-02-23 | 3.798 | same | same | same | URL above |
| 2026-03-02 | 3.888 | same | same | same | URL above |
| 2026-03-09 | 4.801 | same | same | same | URL above |
| 2026-03-16 | 4.970 | same | same | same | URL above |
| 2026-03-23 | 5.160 | same | same | same | URL above |
| 2026-03-30 | 5.105 | same | same | same | URL above |
| 2026-04-06 | 5.304 | same | same | same | URL above |
| 2026-04-13 | 5.382 | same | same | same | URL above |
| 2026-04-20 | 5.165 | same | same | same | URL above |
| 2026-04-27 | 5.131 | same | same | same | URL above |
| 2026-05-04 | 5.742 | same | same | same | URL above |
| 2026-05-11 | 5.815 | same | same | same | URL above |
| 2026-05-18 | 5.749 | same | same | same | URL above |
| 2026-05-25 | 5.623 | same | same | same | URL above |
| 2026-06-01 | 5.392 | same | same | same | URL above |
| 2026-06-08 | 5.182 | same | same | same | URL above |
| 2026-06-15 | 5.011 | same | same | same | URL above |
| 2026-06-22 | 4.751 | same | same | same | URL above |
| 2026-06-29 | 4.583 | same | same | same | URL above |
| 2026-07-06 | 4.458 | same | same | same | URL above |
| 2026-07-13 | 4.659 | same | same | same | URL above |
| 2026-07-20 | 4.988 | same | same | same | URL above |
| 2026-07-27 | 5.196 | same | same | same | URL above |
| 2026-08-03 | 5.262 | same | same | same | URL above |
| 2026-08-10 | 5.181 | same | same | same | URL above |
| 2026-08-17 | 5.435 | same | same | same | URL above |
| 2026-08-24 | 5.636 | same | same | same | URL above |
| 2026-08-31 | 5.571 | same | same | same | URL above |
| 2026-09-07 | 5.946 | same | same | same | URL above |
| 2026-09-14 | 6.250 | same | same | same | URL above |
| 2026-09-21 | 6.680 | same | same | same | URL above |

In the CSV file itself each row carries the full series name, series ID EMD_EPD2D_PTE_R20_DPG, area "Midwest (PADD 2)" and the full URL; the table abbreviates these only to save space.

DATA NOTE
- Indiana series: NO. The text of EIA's weekly retail gasoline and diesel page, https://www.eia.gov/dnav/pet/pet_pri_gnd_dcus_nus_w.htm (retrieved 2026-10-16), has zero occurrences of "Indiana" [S1]. The areas I saw were U.S., the PADD regions and Midwest (PADD 2). I only saw a truncated print of the full area list, so I cannot fully rule out other state names.
- Series used (stand-in, not Indiana): "Midwest (PADD 2) No 2 Diesel Retail Prices (Weekly, Dollars per Gallon)", ID EMD_EPD2D_PTE_R20_DPG [S4]. I could not confirm that it is the "all types" series; the page title says "No 2 Diesel".
- First and last week: 2025-09-29 to 2026-09-21 [S14]. Last price 6.680 $/gal, as of 2026-09-21.
- Possibly stale: the newest saved week is 25 days before today, 2026-10-16. Weeks 2026-09-28, 10-05 and 10-12 are not in the saved page. I had no web access in my last turns, so I could not search for newer data. If EIA has published them, the 52-week window should shift forward by up to 3 weeks.
- Release dates are inconsistent. The history page [S4] shows both "Release Date 9/22/2026" and "10/6/2026". The 9/22 date matches the last data week of 2026-09-21. The Excel download of the same series, [S6] (https://www.eia.gov/dnav/pet/hist_xls/EMD_EPD2D_PTE_R20_DPGw.xls), contains the dates 10/14/2026 and 10/20/2026. I did not parse that file's data, so I do not know which date applies to this table. I settled on 2026-09-21 as the latest week, but the release date stays unconfirmed.
- Retrieval date: 2026-10-16 (the run date). The sources index did not show a fetch timestamp.
- Anomaly: the price jumps from 3.888 (2026-03-02) to 4.801 (2026-03-09), up 0.913 in one week [S14]. It is an EIA-published value and I did not alter it.
- No week inside the 52-week window is missing, and I did not estimate or interpolate any value.

MISSING DATA
- Indiana state diesel series: not listed on EIA's weekly page [S1]; Midwest PADD 2 used instead.
- Weeks after 2026-09-21 (2026-09-28, 10-05, 10-12): not retrieved or checked.
- Release date for the table: ambiguous between 9/22/2026, 10/6/2026 and 10/14/2026 [S4][S6].
MISSING DATA: Indiana state diesel series — not listed on EIA weekly retail page (S1); Midwest PADD 2 used as stand-in
MISSING DATA: Weekly prices after 2026-09-21 (2026-09-28, 10-05, 10-12) — not searched; saved history page ends 2026-09-21
MISSING DATA: Unambiguous EIA release date for the table — page shows 9/22/2026 and 10/6/2026; xls shows 10/14/2026 and 10/20/2026
