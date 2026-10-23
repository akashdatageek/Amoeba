Verdict: FAIL
VERIFICATION MEMO (Step 5, Figures Verifier). Run date 2026-10-23.

VERDICT: FAIL. The arithmetic in the CSV is correct, but the United States 2023 income input (78,538) is likely the 5-year estimate rather than the standard ACS 1-year B19013 value. This error changes the US percentage changes and the relative growth conclusion between Indiana and the US. Additionally, Indiana's figures remain unconfirmed against Census sources.

RE-CHECKS I RAN
1. Read figures.csv [S92]. It has 6 data rows, with the CPI inputs and nominal inputs shown in the table below.
2. Python recomputation from the CSV nominal and CPI columns [S94]. factor = CPI_2023 / CPI_year, adjusted = nominal x factor. All CSV factors, adjusted values and percentage changes match to rounding (Indiana 2015: factor 1.28557, adjusted 64,962.435).
3. PNG check with PIL [S93]: real_income_chart.png is 1500 x 1050 px, which clears the 1000 px minimum. I did not render or view the image, so I did not check its bar labels against the CSV. Label match is UNCHECKED.
4. Source greps over the saved sources [S95][S96], to test the nominal inputs against independent pages.

RECOMPUTED vs REPORTED (CPI-U series CUUR0000SA0; CPI 2015 = 237.017 and 2023 = 304.702; BLS API fetched 2026-10-23 [S53])

| Item | Reported in CSV | Recomputed | Match | Source / date |
|---|---|---|---|---|
| Factor 2015 | 1.28557023 | 304.702 / 237.017 = 1.28557 | yes | CPI [S53], 2026-10-23 |
| Factor 2023 | 1.0 | 1.0 | yes | [S53] |
| Indiana 2015 nominal 50,532, adjusted | 64,962.435 | 50,532 x 1.28557 = 64,962.4 | yes | nominal [unverified] (no fetched page shows it) |
| Indiana 2023 (nominal = adjusted) | 70,051 | 70,051 x 1.0 = 70,051 | yes | nominal [unverified] (third-party snippet, no [S#]) |
| Indiana nominal change | 38.627% | 70,051 / 50,532 - 1 = 38.627% | yes | derived |
| Indiana real change | 7.833% | 70,051 / 64,962.4 - 1 = 7.833% | yes | derived |
| US 2015 nominal 55,775, adjusted | 71,702.680 | 55,775 x 1.28557 = 71,702.7 | yes | nominal 55,775 ±85 on the data.census.gov B19013 2015 page [S20], fetched 2026-10-23. The page does not label its geography. |
| US 2023 (nominal = adjusted) | 78,538 | arithmetic 78,538 x 1.0 = 78,538 | arithmetic yes, INPUT DISPUTED | see spot-checks |
| US nominal change (as reported) | 40.812% | 78,538 / 55,775 - 1 = 40.812% | arithmetic yes | derived |
| US real change (as reported) | 9.533% | 78,538 / 71,702.68 - 1 = 9.533% | arithmetic yes | derived |
| US nominal change, if 2023 = 77,719 | n/a | 77,719 / 55,775 - 1 = 39.34% | n/a | 77,719 from [S85] |
| US real change, if 2023 = 77,719 | n/a | 77,719 / 71,702.68 - 1 = 8.39% | n/a | derived |

SOURCE SPOT-CHECKS
- CPI-U CUUR0000SA0 2023 annual average 304.702: BLS API https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true, fetched 2026-10-23 [S53]. This is the same source the producer used, so it is not independent. CONFIRMED only against BLS itself. My attempt to read a second BLS table (the December 2023 CPI release [S67]) showed nothing I can cite, so the independent second-source check on CPI is UNCONFIRMABLE. The 2015 value 237.017 is in the saved BLS response [S53][S55]. It matches my recollection of the BLS annual average [unverified]. The step-4 note says step 5 checked CPI against a historical table, but I did not do that check.
- US 2023 median household income, standard ACS 1-year B19013: The Census-hosted Michigan takeaways page, fetched 2026-10-23, states \"The median household income was $77,719 in the United States in 2023 compared to $69,183 for Michigan households\" [S85]. The comparison is of the 2023 ACS estimates. The page says the data are adjusted to 2023 dollars, which for the survey year 2023 equals the nominal value. This conflicts with the CSV value of 78,538. A third-party page [S77] gives 78,538 for 2023, and that page also discusses 2019-2023 5-year data [S95][S96]. My reading, not confirmed: 78,538 is the 2019-2023 5-year figure (consistent with my recollection [unverified]), not the 1-year one. The CSV's US 2023 input is therefore probably the wrong product, and step 4 itself flagged it as possibly not the standard 1-year estimate. Treat 77,719 as the likely correct standard 1-year value [S85]. This matches my independent pre-step result (US real change about +8.4%).
- Indiana 2023 = 70,051: not found in any fetched Census source. CSV cites only a third-party snippet. UNCONFIRMABLE. It could be the 1-year or the 5-year figure, so it is also at risk.
- Indiana 2015 = 50,532: from memory, no fetched page [unverified]. UNCONFIRMABLE.
- US 2015 = 55,775: matches the data.census.gov ACSDT1Y2015.B19013 page [S20]. The page's title says \"in 2015 inflation-adjusted dollars\", so the value is survey-year dollars (standard), not a 2023-dollar restatement. The geography label is missing, but the value matches my recollection of the US 2015 1-year figure [unverified].
- Standard-vs-restated check: the 2015 values are in 2015 dollars [S20]. The 2023 values need no restatement, since the factor is 1. The only concern is 1-year vs 5-year, as above.
- ACS release dates and BLS publication date: not stated on any fetched page. UNCONFIRMABLE.
- Margins of error: none in the CSV (income_moe_usd empty). The US 2015 MOE of ±85 is shown on [S20]. No MOEs for the other values.

DISCREPANCIES AND FIXES
1. US 2023 nominal (CSV 78,538) conflicts with 77,719 from the Census-hosted page [S85]. 78,538 is probably the 5-year product. Fix: replace it with the confirmed standard ACS 1-year value for 2023 (likely 77,719), then recompute. US nominal change becomes about 39.34% and real change about 8.39%, against 40.81% and 9.53% reported. The US-vs-Indiana real gap shrinks from about 1.70 points to about 0.56 points (8.39% - 7.83%). The conclusion that the US grew faster still holds in point estimates, but the size of the gap changes. Without MOEs, no significance can be claimed.
2. Indiana 2023 (70,051) and Indiana 2015 (50,532) have no Census source. Fix: confirm from data.census.gov ACSDT1Y2023.B19013 and ACSDT1Y2015.B19013 or the Census API with a key. Confirm that the 2023 value is the 1-year estimate.
3. Add MOEs (B19013_001M) and the ACS release dates, or state that they are not available.
4. The chart's bar labels were not checked against the CSV. Rerun the chart after fixing the US 2023 value.
5. The CSV and chart must carry the corrected US 2023 and the recomputed percentages. The final answer must keep the required opening line on the endpoints-only interpretation.

WHAT PASSED: factor, adjusted values and percentage changes are arithmetically correct; the PNG is 1500 px wide [S93]; CPI-U inputs agree with BLS [S53].
BLOCKED: Image content analysis — could not verify if bar labels match CSV
MISSING DATA: Independent second-source CPI-U annual averages for 2015 and 2023 — BLS historical table
MISSING DATA: Census-confirmed Indiana B19013 1-year estimates for 2015 and 2023 — saved sources S75-S85
MISSING DATA: Margins of error and ACS/BLS release dates — not on any fetched page
MISSING INPUT: Census-confirmed ACS 1-year B19013 values for Indiana and the United States, 2015 and 2023 — steps 1, 2 and 4
Issues:
1. Step 4 figures.csv, United States 2023 nominal: 78,538 conflicts with 77,719 stated for the 2023 US ACS estimate on a Census-hosted page [S85]. 78,538 is probably the 5-year figure. Fix: use the confirmed 1-year value (likely 77,719) and recompute. US nominal change becomes about 39.34% (not 40.81%) and real change about 8.39% (not 9.53%).
2. Step 4 figures.csv, Indiana 2023 = 70,051: sourced only from a third-party snippet with no [S#]. Not confirmed against Census and may be a 5-year figure. Fix: confirm from data.census.gov ACSDT1Y2023.B19013 or the Census API with a key.
3. Step 4 figures.csv, Indiana 2015 = 50,532: from memory, no fetched source. Fix: confirm from the ACS 2015 1-year B19013 table.
4. Step 4 figures.csv: no margins of error and no ACS release dates. Fix: add B19013_001M values and release dates, or state that they are unavailable.
5. Step 4 real_income_chart.png: the file is 1500 x 1050 px [S93], but the bar labels were not checked against the CSV. Regenerate it after correcting the US 2023 value.
6. CPI-U 2015 and 2023 values come from a BLS API call, not an independent second table. Fix: cross-check against the BLS CPI-U historical table.
