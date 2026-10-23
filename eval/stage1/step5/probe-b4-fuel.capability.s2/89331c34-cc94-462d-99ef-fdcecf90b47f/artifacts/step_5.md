I read "weekly retail on-highway diesel price for Indiana" as EIA weekly Midwest (PADD 2) retail diesel price, used as a proxy because EIA publishes no Indiana-only weekly series; if you meant EIA weekly Indiana-specific retail diesel price, if such a series exists or EIA weekly Midwest regional price, with Indianapolis or a nearby metro as a cross-check or EIA weekly US national average diesel price, as the fallback, the answer below may not apply.

Step 5 result: I recomputed every weekly surcharge, fleet cost and statistic in Python with Decimal ROUND_HALF_UP and drew the chart. The Decimal logic mirrors the workbook formulas: surcharge = ROUND((price − 1.25) ÷ 3,232,256.77 USD (52-week total fleet fuel cost), 2), gallons = 35 × 2,300 ÷ 6.2 = 12,983.8710 per week, fleet cost = price × gallons, fuel $/mi = price ÷ 6.2. The values match the workbook's recalculated Summary sheet (total 3,232,256.77; average $/mi 0.7722) [S94][S92]. The Python script is step5.py.

File created: price_surcharge_chart.png. It is 2,400 px wide by 1,360 px high at dpi 200 [S78]. The price line is on the left axis ($ per gallon) and the surcharge line on the right axis ($ per mile). Each line has 52 points [S94]. The chart has a title, titled axes, a legend and dates every 4 weeks. The source note reads "Source: EIA, Midwest (PADD 2) weekly retail diesel (EMD_EPD2D_PTE_R20_DPG), retrieved 2026-10-23". The caption reads "the two lines look alike because the surcharge is linear in price (slope 1/6.2 per $)". I did not open the PNG to inspect it visually.

Period: 52 weekly EIA releases, weeks ending 2025-10-27 to 2026-10-19; the latest week is as of 2026-10-19; retrieved 2026-10-23 [S94][S58].

Table 1: Stats summary (52 weeks)

| Metric | Value | Source / date |
|---|---|---|
| Average price ($/gal) | 4.78738 | EIA PADD 2 weekly, retrieved 2026-10-23 [S94] |
| Average surcharge ($/mi, mean of the rounded weekly values) | 0.5708 | computed [S94] |
| Highest week | week ending 2026-09-21: price 6.68 $/gal, surcharge 0.88 $/mi | EIA [S94] |
| Lowest week | week ending 2026-01-12: price 3.365 $/gal, surcharge 0.34 $/mi | EIA [S94] |
| 52-week total fleet fuel cost ($) | 3,232,256.77 | computed [S94] |
| Average weekly fleet fuel cost ($) | 62,158.78 | computed [S94] |
| Carrier average fuel cost per mile ($/mi) | 0.7722 | computed (price ÷ 6.2, averaged) [S94] |
| ATRI total marginal cost per mile, 2025 data (released 2026-07-15) | 2.336 $/mi | ATRI, An Analysis of the Operational Costs of Trucking [S46][S47] |
| ATRI cost per mile excluding fuel | 1.854 $/mi | ATRI [S46] |
| ATRI fuel cost per mile, SUBSTITUTE (2.336 − 1.854) | 0.482 $/mi | derived; ATRI's own stated fuel figure was not found |
| ATRI fuel share of total | 20.6% (0.482 ÷ 2.336) | derived [S94] |
| Gap, carrier minus ATRI fuel $/mi | +0.2902 $/mi, i.e. 60.2% of ATRI fuel (0.2902 ÷ 0.482) | derived [S94] |

Caveats:
- The ATRI comparison is not like-for-like. ATRI is an industry-wide average built on 2025 data. The carrier figure uses 2025–26 Midwest prices at 6.2 mpg.
- The 52-week high of 6.68 and the latest week (6.352) are above the $3.00–$5.00 band grid. The base formula still applies above $5.00; for example, 6.68 gives 0.88 $/mi.

Table 2: 40-band surcharge schedule ($3.00–$5.00, 5-cent bands). Surcharge = ROUND((midpoint − 1.25) ÷ 6.2, 2) on the band midpoint, half-up [S95].

| # | Band low | Band high | Midpoint | Surcharge $/mi |
|---|---|---|---|---|
| 1 | 3.00 | 3.05 | 3.025 | 0.29 |
| 2 | 3.05 | 3.10 | 3.075 | 0.29 |
| 3 | 3.10 | 3.15 | 3.125 | 0.30 |
| 4 | 3.15 | 3.20 | 3.175 | 0.31 |
| 5 | 3.20 | 3.25 | 3.225 | 0.32 |
| 6 | 3.25 | 3.30 | 3.275 | 0.33 |
| 7 | 3.30 | 3.35 | 3.325 | 0.33 |
| 8 | 3.35 | 3.40 | 3.375 | 0.34 |
| 9 | 3.40 | 3.45 | 3.425 | 0.35 |
| 10 | 3.45 | 3.50 | 3.475 | 0.36 |
| 11 | 3.50 | 3.55 | 3.525 | 0.37 |
| 12 | 3.55 | 3.60 | 3.575 | 0.38 |
| 13 | 3.60 | 3.65 | 3.625 | 0.38 |
| 14 | 3.65 | 3.70 | 3.675 | 0.39 |
| 15 | 3.70 | 3.75 | 3.725 | 0.40 |
| 16 | 3.75 | 3.80 | 3.775 | 0.41 |
| 17 | 3.80 | 3.85 | 3.825 | 0.42 |
| 18 | 3.85 | 3.90 | 3.875 | 0.42 |
| 19 | 3.90 | 3.95 | 3.925 | 0.43 |
| 20 | 3.95 | 4.00 | 3.975 | 0.44 |
| 21 | 4.00 | 4.05 | 4.025 | 0.45 |
| 22 | 4.05 | 4.10 | 4.075 | 0.46 |
| 23 | 4.10 | 4.15 | 4.125 | 0.46 |
| 24 | 4.15 | 4.20 | 4.175 | 0.47 |
| 25 | 4.20 | 4.25 | 4.225 | 0.48 |
| 26 | 4.25 | 4.30 | 4.275 | 0.49 |
| 27 | 4.30 | 4.35 | 4.325 | 0.50 |
| 28 | 4.35 | 4.40 | 4.375 | 0.50 |
| 29 | 4.40 | 4.45 | 4.425 | 0.51 |
| 30 | 4.45 | 4.50 | 4.475 | 0.52 |
| 31 | 4.50 | 4.55 | 4.525 | 0.53 |
| 32 | 4.55 | 4.60 | 4.575 | 0.54 |
| 33 | 4.60 | 4.65 | 4.625 | 0.54 |
| 34 | 4.65 | 4.70 | 4.675 | 0.55 |
| 35 | 4.70 | 4.75 | 4.725 | 0.56 |
| 36 | 4.75 | 4.80 | 4.775 | 0.57 |
| 37 | 4.80 | 4.85 | 4.825 | 0.58 |
| 38 | 4.85 | 4.90 | 4.875 | 0.58 |
| 39 | 4.90 | 4.95 | 4.925 | 0.59 |
| 40 | 4.95 | 5.00 | 4.975 | 0.60 |

Figures not found or substituted:
- ATRI's stated fuel cost per mile was not found. I read only the press release and summary page, not the full PDF. I used 2.336 − 1.854 = 0.482 $/mi as the substitute, and it is marked as a substitute.
- I did not confirm that no ATRI edition is newer than July 2026. Only search snippets were checked.
- The Indiana-only weekly series does not exist at EIA, so the Midwest (PADD 2) price is used as the proxy.
MISSING DATA: ATRI fuel cost per mile as a stated table value — looked in ATRI press release and summary page [S35][S46]; substituted 2.336 − 1.854 = 0.482 $/mi
MISSING DATA: Confirmation that no ATRI edition newer than July 2026 exists — only search snippets checked
