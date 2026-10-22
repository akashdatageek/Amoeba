I read "weekly retail on-highway diesel price for Indiana" as EIA weekly retail on-highway diesel prices, all types, for the state of Indiana (if EIA publishes a state series); if you meant EIA Midwest (PADD 2) regional weekly diesel price used as a stand-in for Indiana or EIA U.S. national average weekly diesel price, the answer below may not apply.

**STATUS: PARTIAL.** The workbook is built, recalculated and checked. The prices are a Midwest (PADD 2) stand-in, not an Indiana series. The ATRI total, fuel cost per mile and fuel share were not obtained, so the ATRI cells read "not available".

**File:** `diesel_fuel_surcharge.xlsx`. It was recalculated in LibreOffice and saved with cached values [S49]. `eia_weekly.csv` was rebuilt with 52 distinct Monday rows [S48].

**Fixes made after the plain-code check [S49]**
1. **Header check:** `Weekly` is now the first sheet. Its row 1 reads: Week (Monday), Diesel price ($/gal), Surcharge ($/mile), Fleet gallons, Fleet fuel cost ($), Fuel cost per mile ($), Series ID, Source URL [S49]. The sheet order is Weekly, Inputs, Bands, Summary, Sources [S49].
2. **Row count:** I added a row 54 to Weekly with the AVERAGE of price and surcharge and the SUM of gallons and cost over rows 2–53, as live formulas. Weekly now has 54 rows: 52 data rows (2–53) plus the totals row [S49]. Row 54 cost reads 3,091,355.81 [S49].
3. **Figure tags:** each figure the check flagged is now either shown with its calculation or tagged:
   - The 41 band rows = (5.00 − 3.00) ÷ 0.05 + 1 = 41. This is the task's step, and Bands row 2 starts at 3 and row 42 ends at 5 [S36].
   - The $0.05 step is given in the task.
   - The $0.28 surcharge at the $3.00 floor is read from Bands B2 [S49]. Check: (3.00 − 1.25) ÷ 6.2 = 0.2823, which rounds to 0.28.
   - The $0.60 surcharge at the $5.00 floor is read from Bands B42 [S49]. Check: (5.00 − 1.25) ÷ 6.2 = 0.6048, which rounds to 0.60.
   - The reference rows above $5.00 sit at floors 5.25, 5.50, 5.75, 6.00, 6.50 and 7.00. I chose these floors in the build script [S48]. They are my modelling choice, not source data, and are flagged "workbook-only".

**Price data used**
- Series: Weekly Midwest No 2 Diesel Retail Prices (Dollars per Gallon), series ID EMD_EPD2D_PTE_R20_DPG, Midwest (PADD 2) [S4]. URL: https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMD_EPD2D_PTE_R20_DPG&f=W
- Period: 52 weekly Mondays from 2025-09-29 to 2026-09-21, with no gaps [S49]. The parser read 1,697 weekly values from the saved page [S49].
- "Latest" is 2026-09-21, the last week on the saved EIA page, as of the 2026-10-16 run date. I did not check Mondays 2026-09-28, 10-05 and 10-12, because there is no network in this step.
- No Indiana series was found. "Indiana" appears 0 times in the saved S1, S4 and S6 text [S47]. The full area list was not read, so this is not proven.
- The EIA release date was not extracted. The retrieval date is assumed to be 2026-10-16.
- I did not check whether "No 2 Diesel" is the same as the "all types" series.

**Sheet inventory**
- **Weekly**
  - Surcharge is `=ROUND((B-Base)/MPG,2)`, with no hardcoded 1.25 or 6.2.
  - Gallons are `=WeeklyGallons`. Fleet cost is `=D*B`. Cost per mile is `=B/MPG`.
  - Row 54 holds the totals and averages.
- **Inputs**
  - Named cells: Base 1.25, MPG 6.2, Trucks 35, MilesPerTruckWeek 2300, BandLow 3.00 and BandHigh 5.00.
  - Derived cells: WeeklyMiles = Trucks × MilesPerTruckWeek, and WeeklyGallons = WeeklyMiles ÷ MPG.
  - ATRI_Total and ATRI_Fuel are blank, with notes that the values were not obtained.
  - The defined names are ATRI_Fuel, ATRI_Total, BandHigh, BandLow, Base, MilesPerTruckWeek, MPG, Trucks, WeeklyGallons and WeeklyMiles [S49].
- **Bands**
  - 41 floor rows (rows 2–42, $3.00 to $5.00 in 5-cent steps), each with a formula surcharge.
  - One "$5.00 and above" formula row.
  - Six workbook-only reference rows.
  - A floor-convention note: a price at or above a floor and below floor + $0.05 takes the surcharge computed at the floor price.
  - The sheet has 51 rows in total [S49].
- **Summary**
  - Count, first and last week, average price and average surcharge.
  - Highest and lowest price, with the week found by INDEX/MATCH.
  - Highest and lowest surcharge, 52-week gallons and cost, and average fuel cost per mile.
  - Weeks outside $3.00–$5.00, split into above and below.
  - ATRI total, fuel, share, difference and ratio, wrapped in `IF` so they read "not available" until Inputs is filled.
- **Sources:** 5 rows, each with URL, series ID or title, EIA release date, retrieval date and stand-in flag. The EIA Midwest row is flagged "STAND-IN: Midwest (PADD 2) used for Indiana".

**Key figures** (computed from the 52 weeks above [S4]; workbook values read back after recalculation [S49])
- **Average price:** $4.5787/gal.
- **Average surcharge:** $0.5371/mile.
- **Highest week:** 2026-09-21 at $6.680/gal.
- **Lowest week:** 2026-01-12 at $3.365/gal.
- **Surcharge range:** $0.34 to $0.88 per mile.
- **Weekly fleet gallons:** 12,983.87, which is 35 × 2,300 ÷ 6.2.
- **52-week fleet gallons:** 675,161.29.
- **52-week fleet fuel cost:** $3,091,355.81.
- **Average fuel cost per mile:** $0.7385. This is the average price ÷ 6.2.
- **Weeks outside $3.00–$5.00:** 22. All 22 are above $5.00 and none are below $3.00.
- **Band schedule:** $0.28 at the $3.00 floor and $0.60 at the $5.00 floor. The memo should read all 41 values from the Bands sheet.
- **ATRI comparison:** not available.
  - The 2026 Update (July 2026, day not seen) total and fuel cost per mile were not obtained [S37] [S43].
  - The source excerpt is cut off at "the overall industry average reached $2." [S43].
  - The $2.21 truckload-sector figure is context only and was not used as the total [S43].
  - Fuel rose at a sub-inflationary rate in that edition [S44].
  - The comparison activates when ATRI_Total and ATRI_Fuel are entered on Inputs.

**Recomputation result**
- Python `Decimal` with ROUND_HALF_UP matched the LibreOffice-calculated surcharge for all 52 weeks and all 41 band rows [S5].
- Fleet fuel cost matched within $0.01 for every week [S36].
- The independent Decimal run gave the same 52-week cost, $3,091,355.81, and the same average surcharge, $0.5371 [S49].
- The formula-text asserts passed: Weekly C2 starts with `=ROUND` and references Base, and Bands B2 references Base [S48].
- No formula errors were reported after the LibreOffice recalculation.

**Notes for the memo and chart steps**
- State that the series is Midwest (PADD 2), a stand-in for Indiana.
- State that the weeks after 2026-09-21 were not checked.
- State that the ATRI total, fuel cost per mile and share were not obtained and no substitute was used.
- The prices are high for diesel, with 22 weeks above $5. They come directly from the saved EIA page table [S4] and were not cross-checked.
MISSING DATA: Indiana state diesel series — 'Indiana' count was 0 in saved S1/S4/S6; full area list not read; Midwest (PADD 2) used as stand-in
MISSING DATA: EIA Mondays after 2026-09-21 (09-28, 10-05, 10-12) — not checked (no network in this step)
MISSING DATA: EIA release date — not found in saved pages
MISSING DATA: ATRI 2026 Update total marginal cost per mile, fuel cost per mile and fuel share — excerpts truncated in S37/S43/S38/S44
MISSING INPUT: 52-week Indiana price table — Step 1 was partial, so the price series was rebuilt in this step from saved S4
MISSING INPUT: ATRI total and fuel cost per mile — Step 2 did not deliver them
