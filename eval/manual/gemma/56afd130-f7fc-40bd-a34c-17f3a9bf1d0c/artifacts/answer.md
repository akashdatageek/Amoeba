## Step 1: Data Gathering

### Market Data Sheet

| Item | Value | Unit | Source | Date |
| :--- | :--- | :--- | :--- | :--- |
| Class 8 Diesel Purchase Price (Day Cab/Sleeper) | 139,000 - 180,000 | USD | [S6], [S12] | 2026 |
| Class 8 BEV Purchase Price (eCascadia) | 400,000 | USD | [S12] | 2026 |
| Indiana Commercial Electricity Rate | 14.15 | ¢/kWh | [S20] | Oct 2026 |
| Indiana Diesel Price (Average) | 5.64 | USD/gal | [S25] | Oct 2026 |
| Federal Commercial Clean Vehicle Credit (IRA 45W) | 40,000 | USD | [S26], [S28] | 2026 |
| Indiana State EV Purchase Incentives | 0 | USD | [S31] | July 2026 |
| Class 8 Diesel Efficiency | 6.0 - 8.0 | MPG | [S1], [S4], [S6] | 2026 |
| Class 8 BEV Efficiency | 1.8 - 2.2 | kWh/mile | [S1], [S4] | 2026 |
| Maintenance Cost (Diesel) | BLOCKED | USD/mile | N/A | N/A |
| Maintenance Cost (BEV) | BLOCKED | USD/mile | N/A | N/A |
| Charging Infrastructure (20 Trucks) | BLOCKED | USD | N/A | N/A |

**Notes on Blocked Data:**
- **Maintenance Costs:** While sources [S1] and [S12] indicate that BEV maintenance is lower than diesel, no specific quantitative "cost per mile" figures were found in the search results.
- **Infrastructure Costs:** No specific total cost for a 20-truck depot installation (including utility upgrades) was found. Source [S31] mentions utility rebates exist but does not provide the base installation cost.

## Step 2: Financial Modeling

### TCO Comparison Table

| Cost Category | Diesel (Per Truck) | BEV (Per Truck) | Notes |
| :--- | :--- | :--- | :--- |
| Net Purchase Price | $159,500 | $360,000 | Diesel: (139,000 + 180,000) / 2 [S6, S12]; BEV: 400,000 [S12] - 40,000 [S26, S28] |
| 7-Year Energy Cost | $338,400 | $118,860 | Diesel: ($5.64 [S25] / 7.0) * 60,000 * 7; BEV: ($0.1415 [S20] * 2.0) * 60,000 * 7 |
| 7-Year Maintenance | $90,300 | $70,560 | Diesel: $0.215 [S39] * 60,000 * 7; BEV: ($0.215 [S39] - $0.047 [S46]) * 60,000 * 7 |
| Infrastructure | $0 | $82,500 | BEV: (10 chargers * $165,000 [S53 midpoint]) / 20 trucks |
| **Total 7-Year TCO** | **$588,200** | **$631,920** | **Sum of above categories** |

### Assumption List
*   **Annual Mileage:** 60,000 miles per truck (as specified in task).
*   **Analysis Period:** 7 years (as specified in task).
*   **Fleet Size:** 20 trucks (as specified in task).
*   **Diesel Purchase Price:** $159,500 (midpoint of $139,000 - $180,000 range) [S6, S12].
*   **BEV Purchase Price:** $400,000 [S12].
*   **Federal Incentive:** $40,000 (IRA 45W credit) [S26, S28].
*   **Indiana State Incentive:** $0 [S31].
*   **Diesel Fuel Price:** $5.64 per gallon [S25].
*   **Diesel Efficiency:** 7.0 MPG (midpoint of 6.0 - 8.0 range) [S1, S4, S6].
*   **Diesel Cost per Mile:** $0.8057/mile (calculated as $5.64 [S25] / 7.0 MPG).
*   **Electricity Rate:** $0.1415 per kWh [S20].
*   **BEV Efficiency:** 2.0 kWh/mile (midpoint of 1.8 - 2.2 range) [S1, S4].
*   **BEV Cost per Mile:** $0.283/mile (calculated as $0.1415 [S20] * 2.0 kWh/mi).
*   **Diesel Maintenance Cost:** $0.215 per mile (industry average) [S39].
*   **BEV Maintenance Cost:** $0.168 per mile (calculated as $0.215 [S39] minus $0.047/mile savings [S46]).
*   **Charging Infrastructure:** $1,650,000 total depot cost, amortized to $82,500 per truck. This assumes 10 DC fast chargers for 20 trucks at an average cost of $165,000 per charger (midpoint of $80,000 - $250,000) [S53].

**Recommendation:**
The freight carrier should **not** replace the diesel tractors with battery-electric tractors at this time. Based on the 7-year TCO analysis, the diesel tractors are more cost-effective, with a total cost of $588,200 per truck compared to $631,920 for the BEV, resulting in a savings of approximately **$43,720 per truck** ($631,920 - $588,200).

***

**Contract Check:**

## Files made
- calculations.py (1,381 bytes, made in step 2; listed by plain code)

## Limitations
- Mislabelled citation: step 1 cites S6 for '180,000', which S6 does not contain; it is in S1, S11, S12 (added by plain code)
- Mislabelled citation: step 1 cites S31 for '0', which S31 does not contain; it is in S1, S2, S3 (added by plain code)
- Mislabelled citation: step 2 cites S6,S12 for '$159,500', which S6,S12 does not contain; it is in S36 (added by plain code)
- Mislabelled citation: step 2 cites S6,S12 for '$360,000', which S6,S12 does not contain; it is in S36 (added by plain code)
- Mislabelled citation: step 2 cites S25 for '$338,400', which S25 does not contain; it is in S36 (added by plain code)
- Mislabelled citation: step 2 cites S25 for '$118,860', which S25 does not contain; it is in S36 (added by plain code)
- Mislabelled citation: step 2 cites S20 for '7.0', which S20 does not contain; it is in S2, S3, S4 (added by plain code)

