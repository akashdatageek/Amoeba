Verdict: FAIL
Verdict: FAIL

Job B (math and CSV) cannot pass. figures.csv has no income data. The four ACS B19013 nominal values were never retrieved, so no adjusted value or percentage change exists to check.

## Recalculation
- I ran calc on 304.702 / 237.017. It returned 1.2855702333587886 (calc, this step).
- That matches the step 2 and step 3 factor (1.2855702333587886) [S65]. The 2023 factor is 304.702 / 304.702 = 1.
- The CPI inputs 237.017 (2015) and 304.702 (2023) are the values step 2 recorded [S44][S46]. This step did not re-fetch them from BLS; that is Job A. Step 2 reports that the BLS API and the BLS annual table agree.
- I could not recompute these items, because no verified ACS nominal value exists for any of them:
  - adjusted 2015 values for Indiana and the United States
  - nominal % change
  - real % change
  - the Indiana-versus-US comparison
- I did not substitute remembered values. My own pre-step recall (US 55,775 and 77,719; Indiana 50,532 and 70,051) is [unverified]. I searched the saved sources for those numbers and for MEHOINUSA. Source S108 (data.census.gov B19013 page) and S119 (a "Real Median Household Income in the United States" page) returned no match. Those numbers are not usable.

## File checks
I read figures.csv with Bash and Python [S121][S122].
- **Rows:** there are 4 data rows. They are Indiana 2015, Indiana 2023, United States 2015 and United States 2023.
- **Columns:** all 11 required columns are present:
  - geography, year, nominal_median_household_income, cpi_u_annual_avg, cpi_base_2023
  - adjusted_2023_dollars, nominal_pct_change_2015_2023, real_pct_change_2015_2023
  - acs_source, cpi_source, retrieval_date
- **CPI columns:** cpi_u_annual_avg is 237.017 for 2015 and 304.702 for 2023, on all four rows. cpi_base_2023 is 304.702 on all four rows. These match my recomputation inputs.
- **Income columns:** nominal_median_household_income is "NOT RETRIEVED" on all 4 rows. adjusted_2023_dollars and both percentage-change columns are "NOT COMPUTED" on all 4 rows.
- **Check that 2023 adjusted equals nominal:** this fails. Both 2023 rows hold "NOT COMPUTED" instead of a number equal to the nominal value.
- **ACS source column:** it holds an API URL marked "NOT RETRIEVED (Missing Key)". It cites no actual figure.
- **Retrieval date:** retrieval_date is 2026-10-22 on all four rows.
- **Release date in cpi_source:** the cpi_source text says "BLS cross-check table (released 2026)". Step 2 says the release year is not shown on the BLS pages [S46]. That is an unsupported detail. Remove it, or state "release year not shown".
- **Verdict on the file:** the file is a skeleton, not a data table. It cannot support the requested comparison, and the chart cannot be built from it.

## Corrections
1. Step 1: supply the four ACS 1-year B19013_001E values. They are Indiana 2015, Indiana 2023, US 2015 and US 2023. Each needs a source URL or ID, release year and retrieval date. Use a Census API key, or a rendered data.census.gov page (ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013). No correct number can be named here, because none was verified.
2. Step 3: re-run calc.py once those values exist. The formulas are:
   - adjusted = nominal × 304.702 / CPIyear
   - nominal % change = nominal2023 / nominal2015 − 1
   - real % change = adjusted2023 / adjusted2015 − 1
   Fill the cells and make the 2023 adjusted value equal the 2023 nominal value.
3. Step 3: fix the cpi_source text. Drop "released 2026", or replace it with "release year not shown on the BLS page".
4. The final deliverable must open with the required line: I read "between 2015 and 2023" as Endpoints only: 2015 and 2023; if you meant Every year from 2015 through 2023, with change from 2015 to 2023, the answer below may not apply.
5. Step 3 is marked stale, so it must be re-verified after the rework.
MISSING DATA: ACS B19013 1-year nominal median household income, Indiana 2015 — api.census.gov (Missing Key), saved sources S108 and S119
MISSING DATA: ACS B19013 1-year nominal median household income, Indiana 2023 — same
MISSING DATA: ACS B19013 1-year nominal median household income, United States 2015 — same
MISSING DATA: ACS B19013 1-year nominal median household income, United States 2023 — same
MISSING INPUT: ACS B19013 1-year values for Indiana and United States, 2015 and 2023 — step 1
MISSING INPUT: Computed adjusted values and percentage changes in figures.csv — step 3
Issues:
1. Step 1: none of the four ACS B19013 1-year values (Indiana and United States, 2015 and 2023) were retrieved. The Census API returned 'Missing Key' [S1][S2]. Fix: obtain them from the API with a key or from data.census.gov ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013, each with source URL, release year and retrieval date.
2. Step 3: figures.csv has 4 rows and 11 columns, but nominal income is 'NOT RETRIEVED' and adjusted values and percentage changes are 'NOT COMPUTED' in all 4 rows. The 2023 adjusted value cannot equal nominal. Fix: re-run calc.py after step 1 delivers values.
3. Step 3: the cpi_source cell says 'BLS cross-check table (released 2026)', but step 2 says the BLS pages show no release year [S46]. Fix: remove the claim or say the release year is not shown.
4. Job B recalculation: only the factor 1.2855702333587886 was verified (calc). The adjusted values and the nominal and real percentage changes could not be recomputed. Step 3 is also stale relative to the reworked steps 1 and 2.
