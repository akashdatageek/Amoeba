Verdict: FAIL
I read "between 2015 and 2023" as Endpoints only: 2015 and 2023; if you meant Every year from 2015 through 2023, with change from 2015 to 2023, the answer below may not apply.

Verdict: FAIL

## File checks (Job C: chart and CSV)
- Re-check 1 (Python os.path.exists and glob for *.png in the workspace): "png exists: False", "any png: []" [S135][S136]. A shell `ls` of real_median_household_income.png also returned "No such file or directory". The PNG was not produced, so I could not check its pixel size (the 600 px minimum), readability or labelled numbers.
- Step 4 says the same: no plotting code was run, no file exists, and the chart has no labelled values or footnote (step 4 output).
- Chart vs CSV: not performed, because there is no chart.
- figures.csv exists with 4 data rows and 11 columns [S135]. The nominal, adjusted and percent-change cells for Indiana and the United States hold "NOT RETRIEVED" or "NOT COMPUTED". Python counted 8 "NOT RETRIEVED" cells [S136]. Those 8 cells match the 4 geography-year rows times two columns. The 2015 and 2023 rows therefore hold no ACS numbers for either Indiana or the United States, and the CSV is only a skeleton. Step 3 is also stale (step 3 output).
- Recompute (calc): 304.702 / 237.017 = 1.2855702333587886. This matches the factor in step 3 and step 4. The two CPI-U values 237.017 and 304.702 both appear in the saved BLS sources S44 and S46 [S136].

## Citation check
- CPI-U 2015 = 237.017 and 2023 = 304.702 (series CUUR0000SA0, annual average): present in the BLS API result [S44] and the BLS table [S46] [S136]. The CSV cpi_source column names the BLS API with the retrieval date 2026-10-22 (step 3 output). I did not check the CSV cell text for this.
- ACS figures: there are none to cite. The Census API returned "Missing Key" for the 2015 and 2023 queries [S1][S2]. The data.census.gov page for Indiana 2023 (ACSDT1Y2023.B19013, S100) was fetched, but no median value could be read from it (step 1 and step 4 outputs). The acs_source cells only record the failed attempt.
- Chart footnote: cannot be checked, because no chart exists.
- Therefore "every figure carries a source and date" cannot be confirmed for the ACS values, the adjusted values or the percentage changes.

## Corrections
1. Step 1: obtain the four ACS 1-year B19013 values (Indiana and the United States, 2015 and 2023). Use a Census API key, or the data.census.gov tables ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013. Record the release year, source URL and retrieval date for each.
2. Step 3: rebuild figures.csv. Use adjusted = nominal × 304.702 / CPIyear (the 2023 adjusted value must equal nominal) and fill the nominal and real percentage changes. Then re-run calc.py.
3. Step 4: produce real_median_household_income.png, at least 600 px wide. It needs four bars in 2023 dollars, the value labels, the real % change per geography, and a footnote citing ACS B19013 1-year (release year and retrieval date) and BLS CUUR0000SA0.
4. Do not use the FRED series MEHOINUSA672N (S119, a CPS series with 84,730 for 2023) as a substitute. It is not ACS B19013 and has no Indiana figure.

Not confirmed: all ACS inputs, the chart, the footnote, and the chart-to-CSV match. The result is FAIL, not PASS.
BLOCKED: Census ACS data access — the four ACS B19013 1-year values could not be obtained upstream, so the chart and CSV figures could not be verified
MISSING DATA: real_median_household_income.png — does not exist in the workspace
MISSING DATA: ACS B19013 1-year values for Indiana and the United States, 2015 and 2023 — saved sources S1, S2, S100 and others, and figures.csv (placeholders only)
MISSING INPUT: real_median_household_income.png — step 4
MISSING INPUT: ACS B19013 values filled into figures.csv — step 3 (stale) and step 1
Issues:
1. Step 4: real_median_household_income.png does not exist [S135][S136]; PNG size, readability, labelled numbers and footnote could not be checked. Fix: produce the bar chart (>=600 px) after the ACS values are available.
2. Step 3: figures.csv has 4 rows and 11 columns but the nominal, adjusted and percent-change cells hold 'NOT RETRIEVED' or 'NOT COMPUTED' (8 NOT RETRIEVED cells) [S135][S136]. Fix: fill from the four ACS values with adjusted = nominal*304.702/CPIyear and re-run calc.py.
3. Step 1: the four ACS 1-year B19013 values (Indiana and the United States, 2015 and 2023) were never obtained (Census API Missing Key [S1][S2]). Fix: use a Census API key or the data.census.gov tables ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013, and cite each with release year and retrieval date.
4. Citations: no ACS figure has a source and date in the CSV or the footnote, and the footnote does not exist. Fix: add source URL, release year and retrieval date for every ACS value in the CSV and the chart footnote.
5. Step 3 is stale (built before the rework of steps 1 and 2). Fix: rebuild it on the current inputs.
