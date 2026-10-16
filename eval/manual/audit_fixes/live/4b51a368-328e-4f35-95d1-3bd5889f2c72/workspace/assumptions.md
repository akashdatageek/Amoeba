# Assumptions and derived numbers (step 1 register)
Run date: 2026-10-16 (Friday). No EIA or ATRI figure has been fetched in this step; none is stated here.

## Fleet inputs (given in the task)
- Tractors: 35
- Miles per tractor per week: 2,300
- Fuel economy: 6.2 mpg
- Base (peg) price: $1.25 per gallon
- Weeks in window: 52
- Band step: $0.05 (bands from $3.00 to $5.00)

## Derived numbers (arithmetic shown)
- Fleet miles per week = 35 x 2,300 = 80,500 miles
- Fleet gallons per week = 80,500 / 6.2 = 12,983.87 gallons (12,983.871 unrounded)
- Fleet fuel cost per week = 12,983.871 x weekly price (e.g. at $3.00 = $38,951.61; at $5.00 = $64,919.35)
- Fuel cost per mile = price / 6.2 (e.g. at $3.00 = 3.00/6.2 = $0.4839)
- Example surcharges, ROUND((price - 1.25)/6.2, 2), half-up:
  - $3.00: (3.00 - 1.25)/6.2 = 1.75/6.2 = 0.282258 -> $0.28 per mile
  - $3.05: (3.05 - 1.25)/6.2 = 1.80/6.2 = 0.290323 -> $0.29 per mile
  - $3.10: (3.10 - 1.25)/6.2 = 1.85/6.2 = 0.298387 -> $0.30 per mile
  - $5.00: (5.00 - 1.25)/6.2 = 3.75/6.2 = 0.604839 -> $0.60 per mile
- Band table rows = (5.00 - 3.00)/0.05 + 1 = 41 rows; lower bounds 3.00, 3.05, ..., 5.00; first label '$3.00-3.049', last row '$5.00 and above'

## Assumptions (each is an assumption, not a verified fact)
- ASSUMPTION 1 (proxy): the "Indiana" weekly price is the EIA weekly retail on-highway diesel price, all types, for the Midwest (PADD 2) region, used as a proxy for Indiana. Whether EIA publishes a true Indiana state series is for the researcher to confirm; nothing is claimed here.
- ASSUMPTION 2 (bands): each 5-cent band such as $3.00-3.049 and $3.05-3.099 is priced at its lower-bound price; 41 rows, last row '$5.00 and above'.
- ASSUMPTION 3 (rounding): surcharge is rounded to the cent half-up (Excel ROUND and Python ROUND_HALF_UP agree; Python's round() is not used because of binary floats and banker's rounding).
- ASSUMPTION 4 (window): the 52 weekly EIA points end at the latest published Monday price as of 2026-10-16.
- ASSUMPTION 5 (fleet cost): all 35 tractors run 2,300 miles per week at 6.2 mpg every week, with no discounts, no idling and no seasonality.
- ASSUMPTION 6 (ATRI): the latest ATRI "Operational Costs of Trucking" average marginal cost per mile, total and fuel component, is used as published, on ATRI's own diesel price and mpg basis.

## Risks
- Midwest PADD 2 price may differ from Indiana's actual price; the gap is unverified.
- A week may be missing or revised in the EIA series; the 52-week count must be checked.
- ATRI's fuel price and mpg basis differ from the carrier's 6.2 mpg, so the comparison is indicative only.
- The latest ATRI edition may be older than 2026; its year must be stated.
- No price or cost figure may be invented; any figure not found is listed as missing with the substitute named.
- The memo must fit 2 pages with the 41-row band table (3 side-by-side blocks).

## Checks planned
- Weekly sheet has exactly 52 data rows; dates are consecutive Mondays.
- Python surcharge (ROUND_HALF_UP) equals the workbook ROUND formula on every row (recalculate with LibreOffice).
- Fleet gallons = 12,983.87 each week; fleet cost = gallons x price; totals row = sum of weeks.
- Fleet inputs sit in named cells; no constants inside formulas.
- Band table has 41 rows; first label '$3.00-3.049', last '$5.00 and above'.
- Chart: dual axis, labelled, legend, date range, at least 1200 px wide.
- Memo: at most 2 pages, opens with the required interpretation line, every figure has source and date.
