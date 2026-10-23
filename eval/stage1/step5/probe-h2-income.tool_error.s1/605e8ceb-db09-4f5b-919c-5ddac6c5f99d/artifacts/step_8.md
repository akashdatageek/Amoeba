I read "between 2015 and 2023" as Every year from 2015 through 2023, inclusive; if you meant Only the two endpoint years, 2015 and 2023, the answer below may not apply.

## Chart report: real_income_indiana_vs_us.png (rendered, but it contains no income bars)

- File: real_income_indiana_vs_us.png, in the workspace, 145,897 bytes [S68]. Pixel size: 1800 x 1050 px, saved at dpi=150 [S68]. It was drawn by chart.py. The width meets the task's minimum width.
- Plotted values: 0 of 18 [S68]. chart.py read the `adjusted_2023_usd` column of income_cpi_adjusted.csv [S67]. Every ACS income and adjusted cell in that file is blank [S67]. The blanks come from step 7, where the Census API returned "Missing Key" and no B19013 value was retrieved. I did not fill, estimate or recall any value, so no bars are drawn.

## Chart elements (one paragraph)

The title is "Real median household income, Indiana vs United States, 2015-2023 (2023 dollars)". The x-axis is labelled "Year (ACS 1-year estimate)". The y-axis is labelled "Real median household income (2023 dollars)". The y-axis range is a fixed setting in chart.py, running from zero up to a hard-coded upper limit of 100k dollars. It is not a data value. The x-axis has nine year groups, 2015 to 2023, with 2020 marked "2020*". The layout is two bars per year, Indiana in blue and United States in orange. The 2020 group is covered by a hatched band, and its bars would be hatched if values existed. The legend lists Indiana, United States and "2020: experimental ACS only (hatched)". A red box in the plot area reads "NO DATA PLOTTED: ACS B19013 values are blank in income_cpi_adjusted.csv (Census API returned "Missing Key"); nothing was estimated or filled in." The source footnote explains the 2020 asterisk (no standard ACS 1-year release because of pandemic nonresponse; only experimental estimates exist, shown hatched). It cites U.S. Census Bureau ACS 1-year table B19013 (api.census.gov) and BLS CPI-U series CUUR0000SA0 annual average (api.bls.gov). It gives the formula adjusted = nominal x CPI_2023 / CPI_year, says the values were read from income_cpi_adjusted.csv, and gives "Retrieved 2026-10-23" [S68].

## Done_when check and next step

- The PNG exists and is wider than the task's minimum width. The title contains "2023 dollars". The axes are labelled, and the legend, the 2020 hatching, the 2020 footnote and the dated source footnote are present.
- The condition that the plotted values come from the CSV is met in method only, because the CSV has no values.
- To finish: get the 18 ACS B19013 values with a free Census API key or from data.census.gov. Put them in `nom` in build.py and rerun it to refill the CSV. Then rerun chart.py, which will draw the real bars with no other edits. Until then the chart is not a usable comparison.

BLOCKED: Census API key — ACS 1-year B19013 values for Indiana and the U.S., 2015–2023, could not be retrieved upstream, so the bars could not be plotted
MISSING DATA: ACS 1-year B19013_001E, Indiana and United States, 2015–2019 and 2021–2023 — api.census.gov (Missing Key), blank in income_cpi_adjusted.csv [S67]
MISSING DATA: ACS 2020 experimental B19013, Indiana and United States — blank in income_cpi_adjusted.csv [S67]
MISSING INPUT: ACS B19013 nominal values and adjusted_2023_usd for all 18 year-geography pairs — step 7 (blank)
BLOCKED: Census API key — ACS 1-year B19013 values for Indiana and the U.S., 2015–2023, could not be retrieved upstream, so the bars could not be plotted
MISSING DATA: ACS 1-year B19013_001E, Indiana and United States, 2015–2019 and 2021–2023 — api.census.gov (Missing Key), blank in income_cpi_adjusted.csv [S67]
MISSING DATA: ACS 2020 experimental B19013, Indiana and United States — blank in income_cpi_adjusted.csv [S67]
MISSING INPUT: ACS B19013 nominal values and adjusted_2023_usd for all 18 year-geography pairs — step 7 (blank)
