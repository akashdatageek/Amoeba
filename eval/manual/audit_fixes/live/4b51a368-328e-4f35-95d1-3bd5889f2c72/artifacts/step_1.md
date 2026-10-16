I read "weekly retail on-highway diesel price for Indiana" as EIA weekly retail on-highway diesel prices, all types, for the Midwest PADD 2 region, used as a proxy for Indiana; if you meant A true Indiana state-level EIA weekly series, if one exists or Indianapolis city or Midwest regional price used in place of the state, the answer below may not apply. I read "each 5-cent price band from $3.00 to $5.00" as Bands such as $3.00–3.049, $3.05–3.099, and so on up to $5.00, with the surcharge computed at the band's price; if you meant Bands stepping from $3.00 by $0.05 to $5.00 as 41 price points, with the surcharge at each point, the answer below may not apply.

Files written and re-opened to confirm: inputs.json (18 lines, read back [S4]) and assumptions.md (48 lines, read back [S3]). Run date is Friday 2026-10-16. No EIA or ATRI figure was fetched in this step, so none is stated here. The EIA prices and the ATRI cost figures are left to the research steps.

**Fleet inputs (given in the task; stored in inputs.json)**
1. Tractors: 35
2. Miles per tractor per week: 2,300
3. Fuel economy: 6.2 mpg
4. Base (peg) price: $1.25 per gallon
5. Weeks in window: 52
6. Band step: $0.05, with 41 band rows from $3.00 to $5.00 inclusive
(inputs.json also holds the rule strings: surcharge ROUND((price-1.25)/6.2,2) with ROUND_HALF_UP in Python; fleet cost 35*2300/6.2*price; fuel cost per mile price/6.2.)

**Derived numbers (arithmetic)**
7. Fleet miles per week = 35 × 2,300 = 80,500 miles.
8. Fleet gallons per week = 80,500 ÷ 6.2 = 12,983.87 gallons (12,983.871 unrounded).
9. Fleet fuel cost per week = 12,983.871 × weekly price. Each $1.00 of price adds $12,983.87 a week.
10. Annual gallons over 52 weeks = 52 × 12,983.871 = 675,161.29 gallons.
11. Fuel cost per mile = price ÷ 6.2. For example, $4.00 ÷ 6.2 = $0.645 per mile.
12. Example surcharges, ROUND_HALF_UP, in $ per mile:
   - $3.00: (3.00 − 1.25) ÷ 6.2 = 1.75 ÷ 6.2 = 0.28226, so $0.28.
   - $3.05: 1.80 ÷ 6.2 = 0.29032, so $0.29.
   - $3.10: 1.85 ÷ 6.2 = 0.29839, so $0.30.
   - $5.00: 3.75 ÷ 6.2 = 0.60484, so $0.60.

**Assumptions (each is an assumption)**
13. Assumption: the price series is EIA weekly retail on-highway diesel, all types, Midwest (PADD 2), used as a proxy for Indiana.
14. Assumption: "most recent 52 weeks" means the last 52 weekly EIA points ending at the latest published Monday price. The settled "as of" date goes next to it once the research step finds it.
15. Assumption: the band table has 41 rows, with lower bounds $3.00 to $5.00 in $0.05 steps. Labels run '$3.00-3.049' and so on, and the last row is '$5.00 and above'. The surcharge is computed at the band's lower-bound price.
16. Assumption: surcharge rounding is to the cent, ROUND_HALF_UP in Python and ROUND() in Excel. Fleet cost uses no discounts.
17. Assumption: every tractor runs 2,300 miles a week at 6.2 mpg in all 52 weeks, with no seasonal variation.
18. Assumption: ATRI means the latest 'Operational Costs of Trucking' average marginal cost per mile, total and fuel component.

**Risks**
19. PADD 2 is a regional price, not Indiana's. It may differ from the Indiana or Indianapolis price, so the surcharge and fuel cost are approximate.
20. The latest EIA week may lag today (2026-10-16). Check for a newer point before settling on the end date.
21. ATRI uses its own diesel price and mpg basis, which differ from 6.2 mpg, so the comparison needs a caveat. The ATRI edition may also be dated before 2026.
22. If any EIA or ATRI figure cannot be retrieved, mark it MISSING and name the substitute. Never invent a figure.
23. Python rounding differs from float rounding at half-cent cases, so use Decimal ROUND_HALF_UP.

**Checks planned**
24. The Weekly sheet has exactly 52 data rows with formulas for surcharge, gallons and fleet cost. The totals row equals the sum of the weeks.
25. The fleet inputs sit in named cells, with no constants inside formulas.
26. Python values equal the recalculated Excel values. Recalculate with LibreOffice and expect zero formula errors.
27. The band table has 41 rows, first label '$3.00-3.049', last '$5.00 and above'.
28. The chart is dual axis with labelled axes, a legend and the date range, and is at least 1200 px wide.
29. The memo is at most 2 pages, opens with the interpretation line, and gives a source and date for every figure.
