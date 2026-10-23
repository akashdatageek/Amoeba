Verdict: FAIL
I read "between 2015 and 2023" as Endpoints only (2015 and 2023), with percentage change computed between them; if you meant Every year from 2015 to 2023, with percentage change from 2015 to 2023, the answer below may not apply.

# Verification memo: Figures Verifier, step 5
Date of checks: 2026-10-23.

**VERDICT: FAIL.** The CPI-U half of figures.csv is correct. The income half is empty. No Indiana or United States B19013 value, adjusted value or percentage change exists to verify. The chart is a CPI-U placeholder, not the Indiana vs United States real-income chart. Both gaps change the deliverable.

## Re-checks I ran
1. **Read figures.csv, then recomputed it with Python** [S65][S66]. There are 6 rows. Every nominal_income_usd, income_moe_usd, adjusted_2023_usd, pct_change_nominal and pct_change_real cell is empty. Only cpi_u and adjustment_factor are filled. The two source columns hold the literal placeholder text `<income_source>` and `<cpi_source>` in the rows shown in step 4's listing.
2. **calc: 304.702 / 237.017 = 1.2855702333587886.** This matches the CSV factor for 2015 exactly.
3. **Independent CPI-U check.** I fetched the BLS historical CPI-U table, https://www.bls.gov/cpi/tables/supplemental-files/historical-cpi-u-202312.pdf, on 2026-10-23 [S67]. I averaged its 12 monthly values with Python [S68].
   - 2015: the monthly values average 237.017 [S68]. This matches the CSV's 237.017.
   - 2023: the monthly values average 304.7016 [S68]. This matches the CSV's 304.702 to rounding. BLS publishes 304.702 as the annual average [S53].
   - The table's December 2023 value, 306.746 [S68], was correctly not used.
4. **Chart.** In step 4's own check the image shape was (900, 1350, 4) [S60], so it is 1350 px wide and passes the 1000 px test. I did not re-measure it with my own tool call. Its content is a CPI-U placeholder, so its labels cannot match any CSV income values. Verdict on the chart: **FAIL (content)**.

## Recomputed vs reported
| Item | Recomputed | Reported in CSV | Source and date | Result |
|---|---|---|---|---|
| CPI-U 2015 annual average, CUUR0000SA0 | 237.017 | 237.017 | [S68] from BLS table [S67], 2026-10-23 | MATCH |
| CPI-U 2023 annual average, CUUR0000SA0 | 304.7016 (monthly mean) | 304.702 | [S68], [S53], 2026-10-23 | MATCH (rounding) |
| Factor 2015 = CPI_2023 / CPI_2015 | 1.2855702 | 1.2855702333587886 | calc, 2026-10-23 | MATCH |
| Factor 2023 | 1.0 | 1.0 | calc | MATCH |
| CPI-U change 2015 to 2023 | +28.557% | not in CSV | calc | n/a |
| Indiana nominal 2015 and 2023 | cannot compute | empty | none fetched | MISSING |
| Indiana adjusted 2015 (nominal x 1.2856) and 2023 | cannot compute | empty | none fetched | MISSING |
| Indiana nominal % and real % change | cannot compute | empty | none fetched | MISSING |
| US nominal 2015 and 2023 | cannot compute | empty | none fetched | MISSING |
| US adjusted 2015 and 2023 | cannot compute | empty | none fetched | MISSING |
| US nominal % and real % change | cannot compute | empty | none fetched | MISSING |

For every income row, adjusted_2023 = nominal × factor, and the 2023 adjusted value must equal the 2023 nominal value because the factor is 1.0. Both rules were untestable on empty cells.

## Source spot-checks
| Input | Second source | Status |
|---|---|---|
| CPI-U 2015 annual average 237.017 | BLS historical CPI-U table, https://www.bls.gov/cpi/tables/supplemental-files/historical-cpi-u-202312.pdf, fetched 2026-10-23 [S67][S68] | CONFIRMED. The BLS API [S53] was fetched the same day as the first source. |
| CPI-U 2023 annual average 304.702 | same BLS table [S67][S68] | CONFIRMED to rounding (304.7016 vs 304.702) |
| US B19013 2015 | Step 1 saw 55,775 ±85, labelled "in 2015 inflation-adjusted dollars", on a data.census.gov page [S20]. The page does not label the geography. | UNCONFIRMABLE. It is not in the CSV and has no geography label. |
| US B19013 2023 | none fetched | UNCONFIRMABLE |
| Indiana B19013 2015 and 2023 | none fetched. The Census API returned "Missing Key" [S1][S3]. Census Reporter showed no values [S28][S59]. | UNCONFIRMABLE |
| Nominal values are standard 1-year survey-year dollars | The CSV has no nominal values. | UNCONFIRMABLE. The 2015 label "2015 Inflation-adjusted dollars" [S21] is the standard survey-year dollar wording. |

I used the figures 77,719, 50,532 and 70,051 from earlier steps' memory only as leads. They are [unverified] and I did not use them as confirmed values.

## Discrepancies and fixes
1. **Step 4: income cells empty.** Fix: obtain B19013_001E and B19013_001M for Indiana (state 18) and the US (us:1) for the 2015 and 2023 standard ACS 1-year releases. Use a Census API key, a data.census.gov export or a readable Census Reporter table. Enter them in survey-year dollars (2015 dollars for 2015, 2023 dollars for 2023). Then rerun make_figures.py.
2. **Step 4: placeholder source columns.** `<income_source>` and `<cpi_source>` must be replaced by full citations with URL and date.
3. **Step 4: chart.** real_income_chart.png is a CPI-U placeholder. Regenerate it as an Indiana vs US bar chart of 2015 and 2023 adjusted values, with labels taken from the CSV.
4. **ACS release dates and BLS publication date** are missing. Add them, or state them as unavailable.
5. **MOE significance.** Once the values exist, compare the real change against the margins of error.

What passes: CPI-U values, factors, and the formula factor = CPI_2023 / CPI_year. What fails: every ACS-derived figure and the chart content.
BLOCKED: Census API key — ACS 1-year B19013 values for Indiana and the United States could not be fetched for the independent spot-check (Missing Key)
BLOCKED: Rendering of JavaScript data tables (data.census.gov, Census Reporter) — no Indiana or US B19013 values could be read to compare with the CSV
MISSING DATA: Indiana B19013 2015 and 2023 estimates and MOEs — Census API (Missing Key), Census Reporter [S28][S59], data.census.gov [S20]
MISSING DATA: United States B19013 2023 estimate, and MOEs for both years — same sources
MISSING DATA: ACS release dates for 2015 and 2023 — no fetched page stated them
MISSING DATA: BLS publication date of the CPI-U annual averages — BLS API response [S53]
MISSING INPUT: Indiana and United States B19013 estimates for 2015 and 2023 — step 4 (CSV income cells empty; steps 1 and 2 delivered none)
Issues:
1. Step 4 figures.csv: every nominal_income_usd, income_moe_usd, adjusted_2023_usd, pct_change_nominal and pct_change_real cell is empty, so no real-income comparison exists. Fix: fetch the four B19013_001E/001M values (Indiana and US, 2015 and 2023, standard 1-year, survey-year dollars) and rerun the script.
2. Step 4 figures.csv: income_source and cpi_source hold placeholder text <income_source> and <cpi_source> instead of citations with URL and date. Fix: write full citations.
3. Step 4 real_income_chart.png: it is a CPI-U placeholder, not the Indiana vs United States real-income bar chart. Fix: regenerate from the completed CSV.
4. Steps 1-2: no ACS value was independently confirmed. The US 2015 value 55,775 [S20] has no geography label and is not in the CSV. Standard 1-year survey-year dollars could not be verified because the CSV has no nominal values.
5. Verified OK: CPI-U 2015 = 237.017 and 2023 = 304.702 match the BLS historical table [S67][S68]. Factor 1.2855702 matches by calc.
