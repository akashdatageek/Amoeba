I read "between 2015 and 2023" as Endpoints only (2015 and 2023), with percentage change computed between them; if you meant Every year from 2015 to 2023, with percentage change from 2015 to 2023, the answer below may not apply.

**Status: partial.** The CPI-U factors are computed. figures.csv exists, but every ACS income cell is empty. real_income_chart.png exists only as a CPI-U placeholder chart, not the Indiana vs United States real-income chart. Steps 1 and 2 delivered no Indiana or United States B19013 estimate or MOE for 2015 or 2023. The Census Reporter page fetched in this step [S59] gave no usable values either. The Census Reporter API call for 2023 failed. I used no figure from memory. I did not use the unverified "about $70K / $78.5K" snippet from Step 2. I did not use the 55,775 from Step 1 [S20], because its geography is unconfirmed and it is only one of four needed values.

## Computed (script ran; the exit code 2 came only from the final `ls`)
- CPI-U annual averages (Step 3): 2015 = 237.017 and 2023 = 304.702 [S55], series CUUR0000SA0 [S56]. Retrieved 2026-10-23; the BLS publication date is not shown in the API response [S53].
- factor_2015 = 304.702 / 237.017 = 1.2855702333587886, about 1.2856. factor_2023 = 304.702 / 304.702 = 1.0 exactly. These are the script's printed values.
- CPI-U change 2015 to 2023 = 304.702 / 237.017 - 1 = 0.2855702, i.e. 28.557%, about 28.6%.

## figures.csv
- The file is 2,355 bytes [S60]. It has the header plus 6 rows.
- Columns: geography, year, nominal_income_usd, income_moe_usd, cpi_u, adjustment_factor, adjusted_2023_usd, pct_change_nominal, pct_change_real, income_source, cpi_source, retrieved_date.
- The listing below abbreviates the two source columns. In the file they hold the full source text.
```
geography,year,nominal_income_usd,income_moe_usd,cpi_u,adjustment_factor,adjusted_2023_usd,pct_change_nominal,pct_change_real,income_source,cpi_source,retrieved_date
Indiana,2015,,,237.017,1.2855702333587886,,,,<income_source>,<cpi_source>,2026-10-23
Indiana,2023,,,304.702,1.0,,,,<income_source>,<cpi_source>,2026-10-23
Indiana,2015-2023 change,,,,,,,,<income_source>,<cpi_source>,2026-10-23
United States,2015,,,237.017,1.2855702333587886,,,,<income_source>,<cpi_source>,2026-10-23
United States,2023,,,304.702,1.0,,,,<income_source>,<cpi_source>,2026-10-23
United States,2015-2023 change,,,,,,,,<income_source>,<cpi_source>,2026-10-23
```
- income_source: "ACS 1-year B19013 (data.census.gov ACSDT1Y2023.B19013 [S42]; 2015 B19013 [S20]); value NOT FETCHED because the Census API returned Missing Key [S1][S41]".
- cpi_source: "BLS CUUR0000SA0 annual average (M13), https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true [S53][S55]; release date not shown".
- The empty income cells are deliberate. They are not zeros.

## Script (make_figures.py, as run)
```python
import csv
CPI={2015:237.017,2023:304.702}
ACS={('Indiana',2015):(None,None),('Indiana',2023):(None,None),
     ('United States',2015):(None,None),('United States',2023):(None,None)}  # NOT FETCHED
f={y:CPI[2023]/CPI[y] for y in CPI}
# adjusted = nominal*f[y]; pct_nominal = n2023/n2015-1; pct_real = a2023/a2015-1
# writes figures.csv (None -> empty cell); the chart block runs only if all 4 estimates exist
```
- When the four estimates are filled in, the chart block draws a grouped bar chart.
- It uses figsize (9,6) and dpi 150, per the role card.
- Bars: Indiana and United States on the x-axis, 2015 and 2023 bars in 2023 dollars, with $ value labels, axis titles and a dated source caption.
- Title: "Real median household income, 2015 vs 2023 (2023 dollars)".

## real_income_chart.png (PLACEHOLDER)
- Pixel shape is (900, 1350, 4), i.e. 1350 px wide by 900 px high [S60]. The file is 59,833 bytes [S60].
- It shows only the two CPI-U bars, 237.017 and 304.702. The title says that the ACS values are NOT FETCHED.
- The caption cites BLS CUUR0000SA0 via api.bls.gov, retrieved 2026-10-23.
- It is not the requested Indiana vs United States chart. Do not present it as one.

## Computation note
- **Formulas:** factor_y = CPI_2023 / CPI_y. adjusted = nominal × factor_y. Real % = adjusted_2023 / adjusted_2015 - 1. Nominal % = nominal_2023 / nominal_2015 - 1.
- **Rounding:** compute from unrounded values. Round only for presentation: dollars to whole numbers, percentages to 0.1 point, factors to 4 decimals.
- **Indiana vs United States:** this cannot be compared yet. There are no sourced incomes. So I cannot say which grew more, give the gap in percentage points, or test either real change against the combined MOE.
- **What the CPI implies:** the same national factor of about 1.2856 applies to both geographies. Each area's real change is (1 + nominal change) × 1.2856 - 1. For example, a nominal rise of 28.6% would give roughly zero real change. This is arithmetic, not a finding.
- **Caveats:**
  - National CPI-U is applied to a state, so it misses Indiana-specific prices.
  - ACS values are sample estimates with sampling error, so small changes may not be significant.
  - There is no standard 2020 1-year release, but this does not affect an endpoints-only comparison.
  - Apply the CPI factor once, to the nominal values, so there is no double adjustment.
  - The BLS publication date and the series metadata are unconfirmed (Step 3).
  - The ACS release dates are unconfirmed (Steps 1 and 2).

## To finish
Supply B19013_001E and B19013_001M for Indiana and the United States for 2015 and 2023, with release dates. Use a Census API key or a readable table. Then fill the ACS dict and rerun the script. That produces the full CSV and the real chart.
BLOCKED: Census API access with a key — the 2015 and 2023 ACS 1-year B19013 queries returned Missing Key, so no Indiana or United States estimates or MOEs could be retrieved
BLOCKED: Rendering of JavaScript data tables (data.census.gov, Census Reporter) — the fetched pages held no Indiana or United States B19013 values, so the real-income bar chart could not be drawn
MISSING DATA: Indiana ACS 1-year B19013_001E and _001M, 2015 and 2023 — Census API (Missing Key), data.census.gov [S20][S42], Census Reporter [S28][S59]
MISSING DATA: United States ACS 1-year B19013_001E and _001M, 2015 and 2023 — same sources; 55,775 [S20] has an unconfirmed geography and no MOE
MISSING DATA: ACS 2015 and 2023 release dates — no fetched page stated them
MISSING DATA: BLS publication date of the CPI-U annual averages — not in the API response [S53]
MISSING INPUT: Indiana and United States 2015 B19013 estimates and MOEs — step 1 (partial, none delivered)
MISSING INPUT: Indiana and United States 2023 B19013 estimates and MOEs — step 2 (partial, none delivered)
