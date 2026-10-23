I read "between 2015 and 2023" as Endpoints only (2015 and 2023), with percentage change computed between them; if you meant Every year from 2015 to 2023, with percentage change from 2015 to 2023, the answer below may not apply.

**Status: partial.** figures.csv and real_income_chart.png exist and are computed from the script. Steps 1 and 2 delivered no Census-confirmed ACS values, so the four income inputs below are NOT confirmed against a Census page. No MOE was obtained. The CPI-U inputs are sourced.

## Input status
- US 2015 = 55,775 [S20]. This is the data.census.gov B19013 page, titled "Median household income in the past 12 months (in 2015 inflation-adjusted dollars)". The page text does not label the geography, so it is unconfirmed as the US figure.
- Indiana 2015 = 50,532. It is from my own knowledge, and no fetched page shows it.
- Indiana 2023 = 70,051 and US 2023 = 78,538. Both came from a third-party web-search snippet that quoted the ACS "in 2023 inflation-adjusted dollars". The snippet has no [S#] and I could not read the page. They are [unverified] against Census. The Step 2 snippet gave only rounded figures of about $70K and $78.5K, and these two values are consistent with that.
- The Census API returned "Missing Key" for 2015 [S1] and for 2023 [S41]. The 2023 table page [S42] and the Census Reporter pages [S28][S59] held no values.
- MOE (B19013_001M): NOT FETCHED, so income_moe_usd is empty.
- ACS release dates: not stated on any fetched page. BLS publication date: not in the API response [S53].
- CPI-U annual average (M13), series CUUR0000SA0: 2015 = 237.017 and 2023 = 304.702 [S55][S56]. URL: https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true [S53]. Retrieved 2026-10-23. Step 5 checked these two values against a BLS historical table, as reported in the rework notes.

## Computed results (script output [S72])
factor_2015 = 304.702 / 237.017 = 1.2855702333587886 (about 1.2856). factor_2023 = 304.702 / 304.702 = 1.0.

| Geography | Nominal 2015 | Nominal 2023 | Adjusted 2015 (2023 $) | Adjusted 2023 (2023 $) | Nominal change | Real change |
|---|---|---|---|---|---|---|
| Indiana | 50,532 | 70,051 | 64,962.435 | 70,051.0 | 38.627% | 7.833% |
| United States | 55,775 [S20] | 78,538 | 71,702.680 | 78,538.0 | 40.812% | 9.533% |

Check: 50,532 x 1.2855702 = 64,962.4, and 55,775 x 1.2855702 = 71,702.7. The CPI-U rise is 304.702 / 237.017 - 1 = 28.557%.

## figures.csv
The file has 6 data rows and 12 columns. The reread matched the printed intermediates [S72]. The pct_* columns are percentages, so 7.833 means 7.833%. The listing below abbreviates the source text, which is written out in full in the file.
```
geography,year,nominal_income_usd,income_moe_usd,cpi_u,adjustment_factor,adjusted_2023_usd,pct_change_nominal,pct_change_real,income_source,cpi_source,retrieved_date
Indiana,2015,50532,,237.017,1.2855702333587886,64962.43503208631,,,"ACS 2015 1-yr B19013_001E Indiana; NOT confirmed (API Missing Key [S1]); analyst memory [unverified]; table ACSDT1Y2015.B19013; release date not confirmed","BLS CUUR0000SA0 annual avg (M13); https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true [S53][S55][S56]; pub. date not shown; retrieved 2026-10-23",2026-10-23
Indiana,2023,70051,,304.702,1.0,70051.0,,,"ACS 2023 1-yr B19013_001E Indiana; third-party snippet quoting ACS [unverified vs Census]; ACSDT1Y2023.B19013 [S42] showed no values; release date not confirmed",(same BLS text),2026-10-23
Indiana,2015-2023 change,,,,,,38.627008628195995,7.833088407785738,pct from rows above,(same BLS text),2026-10-23
United States,2015,55775,,237.017,1.2855702333587886,71702.67976558644,,,"ACS 2015 1-yr B19013_001E; 55,775 on data.census.gov page [S20]; geography label not shown; release date not confirmed",(same BLS text),2026-10-23
United States,2023,78538,,304.702,1.0,78538.0,,,"ACS 2023 1-yr B19013_001E US; third-party snippet quoting ACS [unverified vs Census]; [S42] showed no values",(same BLS text),2026-10-23
United States,2015-2023 change,,,,,,40.81219184222322,9.532865796313184,pct from rows above,(same BLS text),2026-10-23
```

## real_income_chart.png
- The image is 1500 px wide x 1050 px high [S72]. That is figsize (10,7) at dpi 150, so 10 x 150 = 1500 and 7 x 150 = 1050. This clears the 1000 px minimum width.
- It is a grouped bar chart. Indiana and United States are on the x-axis, with 2015 and 2023 bars in 2023 dollars.
- The value labels are $64,962 and $70,051 for Indiana, and $71,703 and $78,538 for the US. They are the same numbers as the CSV, from the same script run.
- It has axis titles and the title "Real median household income, 2015 vs 2023 (2023 dollars)".
- The caption names ACS 1-year B19013 and BLS CUUR0000SA0 (237.017 and 304.702), retrieved 2026-10-23, and flags the ACS values as partly unverified.
- I checked the pixel size but did not view the image.

## Script (make_figures.py, as run [S72])
```python
import csv, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
CPI={2015:237.017,2023:304.702}
N={('Indiana',2015):50532,('Indiana',2023):70051,('United States',2015):55775,('United States',2023):78538}
MOE={k:None for k in N}
f={y:CPI[2023]/CPI[y] for y in CPI}
adj={k:v*f[k[1]] for k,v in N.items()}
# per geography: pn = N23/N15-1 ; pr = adj23/adj15-1 ; written unrounded, pct x100
# CSV via csv.DictWriter: 12 columns, 4 year rows + 2 change rows, full source strings
# chart: figsize (10,7), dpi 150, two bars per geography, "${:,.0f}" labels,
# title "Real median household income, 2015 vs 2023 (2023 dollars)", source caption via fig.text
```
To use Census-confirmed values, replace the four entries in N and the MOE dictionary, then rerun.

## Computation note
- **Formulas:** factor_y = CPI_2023 / CPI_y. Adjusted = nominal x factor_y. Nominal % = N2023 / N2015 - 1. Real % = adjusted_2023 / adjusted_2015 - 1. The CPI factor is applied once, to the nominal values.
- **Rounding:** all calculations use unrounded values, and the CSV holds unrounded values. For presentation, round dollars to whole numbers, percentages to one decimal place, and factors to four decimals.
- **Comparison (conditional on the unconfirmed inputs):** the US grew more in real terms, +9.5% against +7.8% for Indiana. The gap is 9.5329 - 7.8331 = 1.70 percentage points in the US's favour. Both nominal rises (38.6% Indiana, +7.8% real, +38.6% nominal US) exceed the 28.6% CPI-U rise, so both real changes are positive. I cannot say whether either real change exceeds the combined MOE, because no MOEs were obtained. The 1.7-point gap between the two growth rates may not be statistically significant.
- **Caveats:**
  - Three of the four incomes are not Census-confirmed, and the US 2015 geography is unlabeled.
  - The Indiana 2015 value comes from memory.
  - The third-party 2023 values may not be the standard 1-year estimates.
  - National CPI-U is applied to a state, so it misses Indiana-specific prices.
  - ACS values carry sampling error.
  - There is no standard 2020 1-year release, which does not affect an endpoints-only comparison.
  - ACS release dates and the BLS publication date are not confirmed.
  - The BLS series meaning (all items, U.S. city average, not seasonally adjusted) is read from series-ID conventions [unverified].

Files: figures.csv and real_income_chart.png are in the workspace.
BLOCKED: Census API access with a key — 2015 and 2023 ACS 1-year B19013 queries returned Missing Key, so no confirmed estimates or MOEs could be retrieved
BLOCKED: Rendering of JavaScript data tables (data.census.gov, Census Reporter) — fetched pages held no Indiana or US B19013 values
MISSING DATA: Census-confirmed Indiana B19013_001E and _001M, 2015 and 2023 — Census API (Missing Key), data.census.gov [S20][S42], Census Reporter [S28][S59]
MISSING DATA: Census-confirmed United States B19013_001E and _001M, 2015 and 2023 — same sources; 55,775 [S20] has an unlabeled geography
MISSING DATA: ACS 2015 and 2023 release dates — no fetched page stated them
MISSING DATA: BLS publication date of the CPI-U annual averages — not in the API response [S53]
MISSING INPUT: Indiana and United States 2015 B19013 estimates and MOEs — step 1 (partial, only an unlabeled 55,775 delivered)
MISSING INPUT: Indiana and United States 2023 B19013 estimates and MOEs — step 2 (partial, none delivered)