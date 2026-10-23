I read "weekly retail on-highway diesel price for Indiana" as EIA weekly Midwest (PADD 2) on-highway diesel price used as a proxy for Indiana; if you meant EIA weekly retail on-highway diesel price, Indiana, all types (PADD 2 Midwest state series, if published) or EIA weekly U.S. national average on-highway diesel price as a fallback, the answer below may not apply.

**STATUS: DONE.** raw_eia_extract.txt and eia_weekly_diesel.csv were written in the workspace by the run in [S27]. The run printed no errors. I did not open the files again to check them.

**Series and sources**
- **Series:** Weekly Midwest No 2 Diesel Retail Prices, on-highway, all types, in $/gal including taxes. The series ID is EMD_EPD2D_PTE_R20_DPG [S25].
- **Proxy:** Midwest PADD 2 is a regional proxy for Indiana. It is not an Indiana price.
- **History page (S6):** https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=emd_epd2d_pte_r20_dpg&f=W [S26]. It shows 1,700 weekly values, from 1994-03-21 to 2026-10-12. Its last release was 2026-10-14 [S25, S26].
- **Summary page (S1):** https://www.eia.gov/dnav/pet/pet_pri_gnd_dcus_r20_w.htm. It was fetched 2026-10-23T00:59:22 UTC, which is 22 Oct 2026 in Chicago [S23]. Its release date is 2026-10-20, and the next release is 2026-10-27 [S25]. The 10/27 release is after today (22 Oct), so it cannot be used.
- **Retrieved date:** I used 2026-10-22 (America/Chicago) on every row. The exact fetch time of S6 was not confirmed.

**Newest week versus latest release**
- The newest week, 2026-10-19 (6.352), matches the latest release of 2026-10-20 [S25, S27]. I settled on this week as of 2026-10-20.
- The history page (S6) stops at 2026-10-12. The 2026-10-19 row therefore comes from the summary page (S1) and carries that page's URL in the CSV.
- The 10/12 value, 6.259, is the same on both pages [S25, S26].

**Window and checks (automated, in code, not by hand)**
- There are 52 rows, from Monday 2025-10-27 to Monday 2026-10-19 [S27].
- The start date is 51 weeks × 7 days = 357 days before 2026-10-19. The run confirmed 2025-10-27 as the first row [S27].
- Every consecutive gap is 7 days, so no week is missing. The gap list is empty and all dates are Mondays [S27].
- Summary of the 52 prices [S27]:
  - Minimum 3.365 (week of 2026-01-12).
  - Maximum 6.680 (week of 2026-09-21).
  - Simple mean 4.7874.

**All 52 values (week_date: $/gal)** [S27]
- 2025-10-27: 3.715
- 2025-11-03: 3.773
- 2025-11-10: 3.891
- 2025-11-17: 3.913
- 2025-11-24: 3.850
- 2025-12-01: 3.755
- 2025-12-08: 3.635
- 2025-12-15: 3.567
- 2025-12-22: 3.483
- 2025-12-29: 3.424
- 2026-01-05: 3.387
- 2026-01-12: 3.365
- 2026-01-19: 3.445
- 2026-01-26: 3.579
- 2026-02-02: 3.625
- 2026-02-09: 3.636
- 2026-02-16: 3.664
- 2026-02-23: 3.798
- 2026-03-02: 3.888
- 2026-03-09: 4.801
- 2026-03-16: 4.970
- 2026-03-23: 5.160
- 2026-03-30: 5.105
- 2026-04-06: 5.304
- 2026-04-13: 5.382
- 2026-04-20: 5.165
- 2026-04-27: 5.131
- 2026-05-04: 5.742
- 2026-05-11: 5.815
- 2026-05-18: 5.749
- 2026-05-25: 5.623
- 2026-06-01: 5.392
- 2026-06-08: 5.182
- 2026-06-15: 5.011
- 2026-06-22: 4.751
- 2026-06-29: 4.583
- 2026-07-06: 4.458
- 2026-07-13: 4.659
- 2026-07-20: 4.988
- 2026-07-27: 5.196
- 2026-08-03: 5.262
- 2026-08-10: 5.181
- 2026-08-17: 5.435
- 2026-08-24: 5.636
- 2026-08-31: 5.571
- 2026-09-07: 5.946
- 2026-09-14: 6.250
- 2026-09-21: 6.680
- 2026-09-28: 6.526
- 2026-10-05: 6.286
- 2026-10-12: 6.259
- 2026-10-19: 6.352

**Files**
- raw_eia_extract.txt lists the series ID, units, proxy note, retrieved date, release dates, both source URLs, the spacing result and the 52 dated values.
- eia_weekly_diesel.csv has the columns week_date, price_usd_per_gal, series_id, source_url and retrieved_date, with 52 rows.

**Notes for later steps**
- Prices have been above $5.00 since 2026-03-30 in most weeks, and as high as 6.680 [S27]. The task's $3.00–$5.00 band table will not cover those weeks, so the memo should say so. Extending the table above $5.00 is a separate decision.
- The surcharge calculation, ATRI comparison and deliverables are not part of this step.
