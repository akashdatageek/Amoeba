### Real Median Household Income Comparison (2015-2023)

**Summary Table (Adjusted to 2023 Dollars)**
| Year | US Nominal Income | US Real Income | IN Nominal Income | IN Real Income |
| :--- | :--- | :--- | :--- | :--- |
| 2015 | $55,775 [S29] | $71,702.68 [S42] | NaN | NaN |
| 2016 | NaN | NaN | NaN | NaN |
| 2017 | NaN | NaN | NaN | NaN |
| 2018 | NaN | NaN | NaN | NaN |
| 2019 | $69,560 [S28] | $82,904.33 [S42] | NaN | NaN |
| 2020 | $67,521 [S28] | $79,493.47 [S42] | NaN | NaN |
| 2021 | NaN | NaN | NaN | NaN |
| 2022 | $77,719 [S24] | $80,918.26 [S42] | NaN | NaN |
| 2023 | $80,610 [S25] | $80,610.00 [S42] | NaN | NaN |

**Real Income Percentage Change (2015-2023)**
- **United States:** 12.42% [S42]
- **Indiana:** N/A (Insufficient data)

**Artifacts Generated**
- **CSV File:** `income_comparison.csv` (Contains Year, US_Nominal, US_Real, IN_Nominal, IN_Real)
- **Bar Chart:** `income_chart.png` (Comparing US vs Indiana Real Median Household Income)

**Missing Inputs**
- MISSING INPUT: Nominal Median Household Income for Indiana (2015-2023) — Step 2
- MISSING INPUT: Nominal Median Household Income for US (2016, 2017, 2018, 2021) — Step 2

**Tool Usage**
- `local:Bash`: Used to execute the Python analysis script for calculations and visualization.
- `local:Write`: NOT NEEDED — File writing was performed via pandas `to_csv` and matplotlib `savefig` within the Python script executed via `local:Bash`.
