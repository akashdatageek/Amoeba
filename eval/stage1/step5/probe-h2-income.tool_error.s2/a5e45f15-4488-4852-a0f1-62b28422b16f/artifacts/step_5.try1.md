Verdict: FAIL
# Verification memo, step 5 (re-check after the earlier FAIL), run 2026-10-23

I read "between 2015 and 2023" as Endpoints only (2015 and 2023), with percentage change computed between them; if you meant Every year from 2015 to 2023, with percentage change from 2015 to 2023, the answer below may not apply.

## Verdict: FAIL

The rework filled the empty cells in figures.csv [S73], and the placeholder text is gone. The earlier issues 1 to 3 are therefore partly fixed. Three problems remain, and the first changes a number and the conclusion.
- The US 2023 nominal value in the CSV is 78,538. The Census Bureau ACS brief "Household Income in States and Metropolitan Areas: 2023" gives 77,719 [S84]. The Michigan state page, which uses the same ACS 1-year data, also gives 77,719 [S85].
- The Indiana values and the US 2015 value cannot be confirmed.
- The PNG could not be checked by me.

## Re-checks run
1. **Read figures.csv** [S73] and recomputed from its nominal and CPI columns with a Python script [S74]. Output lines such as "Indiana Nominal Change: Reported=38.627008628195995, Recomputed=38.62701%" [S74] show the arithmetic inside the CSV is consistent. Factor = 304.702 / 237.017 = 1.2855702, and adjusted = nominal x factor.
2. **US 2023 B19013 search.** The Census Bureau brief says "The U.S. median household income was $77,719, according to the ACS (Table 1)" [S84]. URL: https://www2.census.gov/library/publications/2024/demo/acsbr-023.pdf (2024 publication, fetched 2026-10-23). The CSV's 78,538 came from a third-party snippet with no [S#] in step 4, so [S84] is the better source.
3. **calc:** (77719/55775 - 1) x 100 = 39.3438% for the US nominal change. The CSV has 40.812% [S73].
4. **CPI-U, series CUUR0000SA0** (all items, U.S. city average, not seasonally adjusted, annual average): 2015 = 237.017 and 2023 = 304.702 in the BLS historical CPI-U table [S67][S68]. The BLS API, retrieved 2026-10-23, also gives 304.702 for 2023 [S53]. CPI-U is confirmed.

## Recomputed vs reported
All values are in survey-year dollars. Factor = 304.702 / CPI of the year.

| Item | CSV reports [S73] | Recomputed or corrected | Status |
|---|---|---|---|
| CPI-U 2015 (CUUR0000SA0) | 237.017 | 237.017 [S67][S68] | OK |
| CPI-U 2023 (CUUR0000SA0) | 304.702 | 304.702 [S53] | OK |
| Factor 2015 to 2023 dollars | 1.28557023 | 304.702 / 237.017 = 1.28557023 (calc) | OK |
| Indiana 2015 nominal | 50,532 | cannot confirm; no fetched page shows it | UNCONFIRMABLE |
| Indiana 2023 nominal | 70,051 | cannot confirm; no fetched page shows it | UNCONFIRMABLE |
| US 2015 nominal | 55,775 [S20] | the page does not label the geography | UNCONFIRMABLE |
| US 2023 nominal | 78,538 | 77,719 [S84][S85] | WRONG |
| Indiana adjusted 2015 (2023 $) | 64,962.44 | 50,532 x 1.28557 = 64,962.4 | arithmetic OK; input unconfirmed |
| Indiana adjusted 2023 (2023 $) | 70,051 | 70,051 x 1 = 70,051 | arithmetic OK; input unconfirmed |
| Indiana nominal change | 38.627% | 70,051 / 50,532 - 1 = 38.627% | arithmetic OK |
| Indiana real change | 7.833% | 70,051 / 64,962.44 - 1 = 7.833% | arithmetic OK; inputs unconfirmed |
| US adjusted 2015 (2023 $) | 71,702.68 | 55,775 x 1.28557 = 71,702.7 | arithmetic OK; input unconfirmed |
| US adjusted 2023 (2023 $) | 78,538 | 77,719 [S84] | WRONG |
| US nominal change | 40.812% | 39.344% (calc: 77,719 / 55,775 - 1) | WRONG |
| US real change | 9.533% | 77,719 / 71,702.68 - 1 = 8.39% (about 8.39%, derived) | WRONG |

## Source spot-checks (dates are retrieval dates, 2026-10-23)
- **CPI-U 2015 and 2023:** confirmed against the BLS historical table [S67][S68] and the BLS API https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true [S53].
- **US 2023 B19013:** contradicted. The Census ACS brief gives 77,719 [S84], and [S85] agrees. The CSV's 78,538 is unsupported.
- **US 2015 B19013 = 55,775:** shown on the data.census.gov table page [S20] with no geography label. It is probably the US figure but is unconfirmed.
- **Indiana 2015 = 50,532 and 2023 = 70,051:** not confirmed against any independent source. The Census API returned "Missing Key" [S1][S41].
- **Standard 1-year survey-year dollars:** the US 2023 figure of 77,719 is the standard ACS 1-year value, not a 2023-dollar restatement of an earlier year [S84]. For 2015, the page [S20] is titled "in 2015 inflation-adjusted dollars", which is survey-year dollars. For Indiana the basis is UNCONFIRMABLE, because the 2023 value came from a third-party snippet.
- **MOEs (B19013_001M):** none in the CSV (income_moe_usd is empty) [S73]. ACS release dates are not documented.

## PNG check
Step 4 reports 1500 x 1050 px [S72], which clears the 1000 px minimum. My own check output [S74] was cut off in what I saw, so I could not confirm the width or that the labels match the CSV. I report the PNG as UNCHECKED by me. It is built from the wrong US 2023 value, so it must be regenerated in any case.

## Discrepancies and fixes
1. **US 2023 nominal is wrong.** Change 78,538 to 77,719 [S84]. Then the US adjusted 2023 value is 77,719, the US nominal change is about 39.34% (CSV 40.81%), and the US real change is about 8.39% (CSV 9.53%). Rerun make_figures.py and regenerate the chart.
2. **The US-versus-Indiana real gap shrinks.** It was 9.533 - 7.833 = 1.70 percentage points. It becomes 8.39 - 7.833 = 0.56 percentage points. Any narrative built on the 9.5% figure is wrong. With no MOEs, it cannot be said whether a 0.56-point gap is meaningful.
3. **Unconfirmed inputs.** Indiana 2015 (50,532), Indiana 2023 (70,051) and US 2015 (55,775) need confirming from Census tables (data.census.gov ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013, or the ACS brief). Label each with its geography and add the MOEs.
4. **Source columns.** They still say "unverified" and "third-party snippet". After the fixes, cite the Census page and release date for each figure.
5. **Caveats.** The caveats in step 4 that flag unconfirmed inputs are accurate and should stay.
BLOCKED: Census API with a key — Indiana and US ACS 1-year B19013 estimates and MOEs for 2015 and 2023 could not be retrieved, so Indiana values and the US 2015 geography stay unconfirmed
BLOCKED: Image inspection — I could not read my own PNG-check output [S74], so I could not confirm the chart width and labels against the CSV
MISSING DATA: Indiana B19013_001E 2015 (50,532) and 2023 (70,051) confirmation — Census API (Missing Key), data.census.gov pages, web searches
MISSING DATA: US 2015 geography label for 55,775 — data.census.gov page [S20]
MISSING DATA: B19013_001M margins of error for all four values — not fetched
MISSING DATA: ACS 1-year release dates for 2015 and 2023 — no fetched page states them
Issues:
1. Step 4 figures.csv: US 2023 nominal income is 78,538 but the Census ACS brief says 77,719 [S84][S85]. Fix: use 77,719; then US adjusted 2023 = 77,719, nominal change about 39.34% (CSV 40.81%), real change about 8.39% (CSV 9.53%). Rerun make_figures.py.
2. Step 4 real_income_chart.png: built from the wrong US 2023 value, so US bars and percentage labels are wrong. Fix: regenerate after correcting the CSV. I could not confirm its labels against the CSV.
3. Step 4 / Steps 1-2: Indiana 2015 (50,532) and Indiana 2023 (70,051) are not confirmed against any Census page. Fix: confirm from data.census.gov ACSDT1Y2015.B19013 and ACSDT1Y2023.B19013 or the ACS brief, and record the Census URL and release date.
4. Step 4 figures.csv: US 2015 value 55,775 [S20] has no geography label on the page. Fix: confirm it is the US 1-year estimate for 2015.
5. Step 4 figures.csv: income_moe_usd is empty and the source columns say unverified or third-party snippet. Fix: add B19013_001M values and full Census citations with URL and date.
