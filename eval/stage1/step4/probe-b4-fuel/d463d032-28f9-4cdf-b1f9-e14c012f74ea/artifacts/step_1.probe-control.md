I read "weekly retail on-highway diesel price for Indiana" as EIA weekly Midwest (PADD 2) on-highway diesel price used as a proxy for Indiana; if you meant EIA weekly retail on-highway diesel price, Indiana, all types (PADD 2 Midwest state series, if published) or EIA weekly U.S. national average on-highway diesel price as a fallback, the answer below may not apply.

STEP 1 RESULT: raw_eia_extract.txt (written in the workspace by a Python script; the 52 rows are listed in full below)

Series: EIA Weekly Midwest (PADD 2) No. 2 Diesel Retail Prices, On-Highway, All Types. Series ID EMD_EPD2D_PTE_R20_DPG. Units: dollars per gallon including taxes [S1][S6].
Proxy note: Midwest PADD 2 is a proxy for Indiana. This is an assumption. Indiana-specific prices were not fetched.

Source URLs:
- History page: https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMD_EPD2D_PTE_R20_DPG&f=W [S6]
- Current-week table: https://www.eia.gov/dnav/pet/pet_pri_gnd_dcus_r20_w.htm [S1]

Release dates and retrieval:
- The history page shows "Release Date: 10/14/2026" and "Next Release Date: 10/20/2026" [S6].
- The current-week table shows the 10/19/26 price [S1]. It is therefore the 10/20/2026 release.
- retrieved_date: 2026-10-22 (today).

Coverage (script check [S32]):
- 52 rows, from 2025-10-27 to 2026-10-19.
- Every row is a Monday.
- Spacing is exactly 7 days between all rows, so no week is missing. A script did this check, not a manual one.
- The newest week is 2026-10-19, $6.352/gal, as of 2026-10-19 [S1].
- The newest week matches the latest EIA release I fetched. The next Monday, 2026-10-26, is after today (2026-10-22), so no newer week can exist. I ran no separate search for a newer value.
- The history page [S6] ends at 2026-09-07 ($5.946 [S32]). The six weeks 2026-09-14 to 2026-10-19 come from the current-week table [S1].
- For 09-14 to 10-12, [S1] and [S6] match exactly [S32].
- 2026-10-19 rests on [S1] alone.

All 52 values (week_date, $/gal), from the script output [S33]:
Source S6 (history page), 46 rows:
2025-10-27 3.715; 2025-11-03 3.773; 2025-11-10 3.891; 2025-11-17 3.913; 2025-11-24 3.850; 2025-12-01 3.755; 2025-12-08 3.635; 2025-12-15 3.567; 2025-12-22 3.483; 2025-12-29 3.424; 2026-01-05 3.387; 2026-01-12 3.365; 2026-01-19 3.445; 2026-01-26 3.579; 2026-02-02 3.625; 2026-02-09 3.636; 2026-02-16 3.664; 2026-02-23 3.798; 2026-03-02 3.888; 2026-03-09 4.801; 2026-03-16 4.970; 2026-03-23 5.160; 2026-03-30 5.105; 2026-04-06 5.304; 2026-04-13 5.382; 2026-04-20 5.165; 2026-04-27 5.131; 2026-05-04 5.742; 2026-05-11 5.815; 2026-05-18 5.749; 2026-05-25 5.623; 2026-06-01 5.392; 2026-06-08 5.182; 2026-06-15 5.011; 2026-06-22 4.751; 2026-06-29 4.583; 2026-07-06 4.458; 2026-07-13 4.659; 2026-07-20 4.988; 2026-07-27 5.196; 2026-08-03 5.262; 2026-08-10 5.181; 2026-08-17 5.435; 2026-08-24 5.636; 2026-08-31 5.571; 2026-09-07 5.946 [all S33, source page S6]
Source S1 (current-week table), 6 rows:
2026-09-14 6.250; 2026-09-21 6.680; 2026-09-28 6.526; 2026-10-05 6.286; 2026-10-12 6.259; 2026-10-19 6.352 [all S33, source page S1]

File row format: week_date, price, EMD_EPD2D_PTE_R20_DPG, source label ("S6 history" or "S1 page"), 2026-10-22. The source label is not yet the full URL. The final eia_weekly_diesel.csv must put the matching full URL above in source_url: the history URL for the 46 S6 rows, the current-week URL for the 6 S1 rows.

Not confirmed:
- Indiana-specific weekly diesel prices were not fetched. The settled interpretation uses the Midwest proxy.
- Full-year data from the EIA API was not used. The values come from the public pages only.
MISSING DATA: Indiana-specific weekly diesel series — not fetched; the settled interpretation uses Midwest PADD 2 as the proxy
