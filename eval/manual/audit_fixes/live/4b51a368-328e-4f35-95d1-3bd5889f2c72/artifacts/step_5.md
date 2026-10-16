I read "weekly retail on-highway diesel price for Indiana" as EIA weekly retail on-highway diesel prices, all types, for the Midwest PADD 2 region, used as a proxy for Indiana; if you meant A true Indiana state-level EIA weekly series, if one exists or Indianapolis city or Midwest regional price used in place of the state, the answer below may not apply. I read "each 5-cent price band from $3.00 to $5.00" as Bands such as $3.00–3.049, $3.05–3.099, and so on up to $5.00, with the surcharge computed at the band's price; if you meant Bands stepping from $3.00 by $0.05 to $5.00 as 41 price points, with the surcharge at each point, the answer below may not apply.

File stats.json is written and was re-opened: it holds 41 bands and 52 weekly rows, 11,469 bytes [S54]. Python used Decimal ROUND_HALF_UP: surcharge = ROUND((price − 1.25) ÷ 6.2, 2); fleet cost = 35 × 2,300 ÷ 6.2 × price; fuel cost per mile = price ÷ 6.2 [S52][S53]. stats.json keys: window, avg_price, avg_price_week_surcharge, highest, lowest, fleet_gallons_per_week, annual_gallons, annual_fleet_fuel_cost, avg_weekly_fleet_fuel_cost, avg_fuel_cost_per_mile, atri, missing, weekly, bands [S55].

Prices come from eia_prices.csv: EIA series EMD_EPD2D_PTE_R20_DPG, Weekly Midwest No 2 Diesel Retail Prices, a PADD 2 proxy for Indiana, EIA page released 9/22/2026, retrieved 2026-10-16 [S10][S27]. Window: Monday 2025-09-29 to Monday 2026-09-21, 52 weeks. Latest week in the window, as of 2026-09-21: $6.680 per gallon [S27].

**Band table: 41 rows. Surcharge in $ per mile, computed at the band's lower-bound price as ROUND((price − 1.25) ÷ 6.2, 2). Every row is from stats.json [S55].**

| Band | Surcharge $/mile | Source |
|---|---|---|
| $3.00-3.049 | 0.28 | [S55] |
| $3.05-3.099 | 0.29 | [S55] |
| $3.10-3.149 | 0.30 | [S55] |
| $3.15-3.199 | 0.31 | [S55] |
| $3.20-3.249 | 0.31 | [S55] |
| $3.25-3.299 | 0.32 | [S55] |
| $3.30-3.349 | 0.33 | [S55] |
| $3.35-3.399 | 0.34 | [S55] |
| $3.40-3.449 | 0.35 | [S55] |
| $3.45-3.499 | 0.35 | [S55] |
| $3.50-3.549 | 0.36 | [S55] |
| $3.55-3.599 | 0.37 | [S55] |
| $3.60-3.649 | 0.38 | [S55] |
| $3.65-3.699 | 0.39 | [S55] |
| $3.70-3.749 | 0.40 | [S55] |
| $3.75-3.799 | 0.40 | [S55] |
| $3.80-3.849 | 0.41 | [S55] |
| $3.85-3.899 | 0.42 | [S55] |
| $3.90-3.949 | 0.43 | [S55] |
| $3.95-3.999 | 0.44 | [S55] |
| $4.00-4.049 | 0.44 | [S55] |
| $4.05-4.099 | 0.45 | [S55] |
| $4.10-4.149 | 0.46 | [S55] |
| $4.15-4.199 | 0.47 | [S55] |
| $4.20-4.249 | 0.48 | [S55] |
| $4.25-4.299 | 0.48 | [S55] |
| $4.30-4.349 | 0.49 | [S55] |
| $4.35-4.399 | 0.50 | [S55] |
| $4.40-4.449 | 0.51 | [S55] |
| $4.45-4.499 | 0.52 | [S55] |
| $4.50-4.549 | 0.52 | [S55] |
| $4.55-4.599 | 0.53 | [S55] |
| $4.60-4.649 | 0.54 | [S55] |
| $4.65-4.699 | 0.55 | [S55] |
| $4.70-4.749 | 0.56 | [S55] |
| $4.75-4.799 | 0.56 | [S55] |
| $4.80-4.849 | 0.57 | [S55] |
| $4.85-4.899 | 0.58 | [S55] |
| $4.90-4.949 | 0.59 | [S55] |
| $4.95-4.999 | 0.60 | [S55] |
| $5.00 and above | 0.60 | [S55] |

Spot checks: $3.00 gives 1.75 ÷ 6.2 = 0.28226, so 0.28. $3.10 gives 1.85 ÷ 6.2 = 0.29839, so 0.30. $5.00 gives 3.75 ÷ 6.2 = 0.60484, so 0.60.

**Summary table (52 weeks, 2025-09-29 to 2026-09-21; EIA series [S10][S27]; fleet inputs from the task) [S54][S55]**

| Item | Value |
|---|---|
| Average weekly price | $4.5787 per gallon |
| Surcharge at the average price | $0.54 per mile |
| Highest week | 2026-09-21: price $6.680, surcharge $0.88, fleet cost $86,732.26 |
| Lowest week | 2026-01-12: price $3.365, surcharge $0.34, fleet cost $43,690.73 |
| First week | 2025-09-29: price $3.731, surcharge $0.40, fleet cost $48,442.82 |
| Fleet gallons per week | 12,983.87 (35 × 2,300 ÷ 6.2) |
| Average weekly fleet fuel cost | $59,449.15 |
| Annual fleet fuel cost (sum of 52 weeks) | $3,091,355.81 |
| Average fuel cost per mile | $0.7385 (4.5787 ÷ 6.2) |

Check: 59,449.15 × 52 = 3,091,355.8, which matches the annual figure.

**ATRI comparison [S54]**
- Edition: ATRI "An Analysis of the Operational Costs of Trucking: 2026 Update", cost year 2025, released 15 July 2026, retrieved 16 Oct 2026 [S29][S30][S36].
- ATRI total average marginal cost: $2.336 per mile. ATRI fuel cost: $0.482 per mile, 48.2 cents [S36][S30].
- ATRI fuel share: 0.482 ÷ 2.336 = 20.6%.
- Carrier average fuel cost per mile $0.7385 minus ATRI $0.482 = $0.2565 above, or 0.2565 ÷ 0.482 = 53.2% higher.
- Carrier fuel cost as a share of ATRI total: 0.7385 ÷ 2.336 = 31.6%.
- Caveat: ATRI uses its own survey fuel price and fleet mpg, not 6.2 mpg and not Midwest PADD 2 prices. ATRI covers the 2025 cost year. The carrier figure covers the 52 weeks to 2026-09-21. I did not read the full ATRI PDF; figures are from the abstract and the ATRI page [S36][S30].
- Nothing ATRI-related is MISSING.

**Not confirmed or missing (carried in stats.json "missing")**
- EIA weeks after 2026-09-21 were not fetched. [S5] shows newer releases on 9/29/2026 and 10/6/2026. The window may be 2–3 weeks behind the latest published Monday, as of 2026-10-16. Substitute: the window ending 2026-09-21.
- No Indiana state-level EIA weekly series was found on the pages read. Substitute: Midwest PADD 2.
- The 2026 prices of $6.250 (2026-09-14) and $6.680 (2026-09-21) are far above the 2025 prices of about $3.6 [S27]. They were not cross-checked against a second source. They drive the highest week and the average, so treat them with caution.
- Only the first, last, highest and lowest weeks and the averages are printed here. The other weekly rows are in stats.json and eia_prices.csv.
BLOCKED: web fetch — EIA releases after 9/22/2026 (9/29 and 10/6) were not fetched, so the latest published Monday is unconfirmed
MISSING DATA: Latest published EIA weekly price after 2026-09-21 — saved S10 page released 9/22/2026; S5 lists later releases not fetched
MISSING DATA: Indiana state-level weekly EIA diesel series — not on S5, S6, S7 or S10; Midwest PADD 2 used instead
MISSING DATA: Second-source check of the 2026 prices of $6.250 and $6.680 — not run
