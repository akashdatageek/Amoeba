CPI-U annual averages, series CUUR0000SA0. Fetched from the BLS Public API v2 with annualaverage=true. The annual average is period M13, periodName "Annual".

| year | CPI-U annual average | series ID | source URL | publication date | retrieved date |
|---|---|---|---|---|---|
| 2015 | 237.017 [S55] | CUUR0000SA0 [S56] | https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true [S53] | Not shown in the API response. The response gives only the reference year 2015 [S55]. | 2026-10-23 (run date) |
| 2023 | 304.702 [S55] | CUUR0000SA0 [S56] | same URL [S53] | Not shown in the API response. The response gives only the reference year 2023 [S55]. | 2026-10-23 (run date) |

Evidence: The API returned status REQUEST_SUCCEEDED for seriesID CUUR0000SA0 [S56]. The M13 / "Annual" rows give 237.017 for 2015 and 304.702 for 2023 [S55]. The December 2023 monthly value in the same response is 306.746 [S56]. I did not use it, because the task asks for the annual average.

Series definition: The response confirms the series ID CUUR0000SA0 [S56]. It returns no descriptive metadata, because the catalog was not requested. The reading CU = CPI for All Urban Consumers, U = not seasonally adjusted, R = periodicity code, 0000 = U.S. city average and SA0 = all items comes from BLS series-ID conventions [unverified]. It matches the working interpretation, but I did not confirm it on a fetched BLS page. The index base period (1982-84 = 100) is also from my own knowledge [unverified] and does not affect the ratios.

Derived (calc result): the factor to convert 2015 dollars to 2023 dollars is CPI_2023 / CPI_2015 = 304.702 / 237.017 = 1.2855702 (calc). That is about 1.2856. The CPI-U rose (304.702 / 237.017 - 1) x 100 = 28.557%, about 28.6% (calc), between 2015 and 2023. Later steps should recompute this from the table values.

Fit note: The CPI-U annual average is the standard all-items price index for U.S. urban consumers. One national deflator applies the same way to Indiana and U.S. incomes. The 2023 annual average gives a consistent 2023-dollar base (factor = CPI_2023 / CPI_year). Limits: it is a national index, so it does not capture Indiana-specific price changes. It covers urban consumers only. It is an average-basket measure, so it may not match any one household's inflation. Census's "inflation-adjusted dollars" label in B19013 refers to the survey year's own dollars. To avoid double adjustment, apply the CPI-U factor to the nominal values.

Gaps: (1) The BLS publication (release) date of the annual averages is not in the fetched API response (S53), and I did not fill it from memory. (2) The series definition (all items, U.S. city average, NSA) is not confirmed by a fetched descriptive page.
MISSING DATA: BLS publication (release) date of the 2015 and 2023 annual averages — not in the API response fetched at api.bls.gov (S53); no BLS release page was fetched
MISSING DATA: Descriptive series metadata confirming 'all items, U.S. city average, NSA' — API response (S53) returned only the series ID; no catalog data was requested
