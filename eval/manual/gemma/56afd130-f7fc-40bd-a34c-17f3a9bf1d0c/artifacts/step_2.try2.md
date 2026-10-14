### TCO Comparison Table

| Cost Category | Diesel (Per Truck) | BEV (Per Truck) | Notes |
| :--- | :--- | :--- | :--- |
| Net Purchase Price | $159,500 | $360,000 | Diesel: Avg of $139k-$180k [S6, S12]; BEV: $400k minus $40k Fed credit [S12, S26, S28] |
| 7-Year Energy Cost | $338,400 [S36] | $118,860 [S36] | Based on 60k miles/year for 7 years [S36] |
| 7-Year Maintenance | BLOCKED | BLOCKED | Data not available in sources |
| Infrastructure Cost | $0 | BLOCKED | Data not available in sources |
| **Total 7-Year TCO** | **$497,900** | **$478,860** | Diesel: $159,500 + $338,400; BEV: $360,000 + $118,860 |

### Assumption List
- **Annual Mileage:** 60,000 miles per truck (as specified in task).
- **Analysis Period:** 7 years (as specified in task).
- **Fleet Size:** 20 trucks (as specified in task).
- **Diesel Fuel Price:** $5.64 per gallon [S25].
- **Diesel Efficiency:** 7.0 MPG (average of 6.0 - 8.0 MPG range) [S1, S4, S6].
- **Electricity Rate:** 14.15 ¢/kWh [S20].
- **BEV Efficiency:** 2.0 kWh/mile (average of 1.8 - 2.2 kWh/mile range) [S1, S4].
- **Diesel Purchase Price:** $159,500 (average of $139,000 and $180,000) [S6, S12].
- **BEV Purchase Price:** $400,000 [S12].
- **Federal Incentive:** $40,000 (IRA 45W) [S26, S28].
- **Indiana State Incentive:** $0 [S31].

***

**Plain Code Checks:**
- BLOCKED: Charging Infrastructure — No total installation cost for 20 trucks was found in the sources to amortize.
- BLOCKED: Maintenance Cost — No quantitative cost-per-mile figures for Class 8 diesel or BEV maintenance were found in the sources.
- local tools: Used local:Bash to perform arithmetic.
