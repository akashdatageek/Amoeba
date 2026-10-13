Verdict: PASS
Issues:
1. Step 2: Installation cost per unit is listed as $40,000 in the table but calculated as $45,000 in the total. This is a documentation error that does not affect the final TCO as the total $153,000 per truck was used consistently in Step 3.

Re-checks performed:
1. Re-calculated Diesel TCO: $185,000 + (420,000 / 6.75 [S67] * $5.64 [S58]) + (420,000 * $0.25 [S43]) = $640,933. Matches Step 3.
2. Re-calculated BEV TCO: ($420,000 [S20] - $40,000 [S59] - $18,500 [S41]) + $153,000 [S10] + (420,000 * 2.0 [S109] * $0.1415 [S26]) + (420,000 * $0.125 [S43]) = $685,860. Matches Step 3.
3. Verified BEV efficiency (2.0 kWh/mile) against [S109] (Tesla Semi < 2 kWh/mile). It is a conservative and valid estimate.
4. Verified Federal Credit ($40,000) against [S59] and [S62]. Correct.
5. Verified Indiana Incentive ($18,500) against [S41]. Correct.


***

# MEMO: Fleet Electrification TCO Analysis

**To:** Management  
**From:** Quality Auditor  
**Date:** October 11, 2026  
**Subject:** TCO Analysis: Diesel vs. Battery-Electric Class 8 Tractors

### Executive Summary
It is recommended that the carrier **do not** replace the current diesel fleet with battery-electric tractors at this time. Based on a 7-year total cost of ownership (TCO) analysis, the battery-electric option is **$44,927 more expensive per truck** than the diesel alternative. While BEVs offer significant operational savings in fuel and maintenance, these are insufficient to offset the high initial capital expenditure for the vehicles and required charging infrastructure within the 7-year window.

### TCO Comparison Table (Per Truck)

| Cost Category | Diesel Tractor | Battery-Electric (BEV) | Notes |
| :--- | :--- | :--- | :--- |
| Purchase Price (Net) | $185,000 [S20] | $361,500 | BEV: $420k [S20] - $40k [S59] - $18.5k [S41] |
| Infrastructure | $0 | $153,000 [S10] | Per-truck share of depot CAPEX |
| Energy/Fuel (7-Year) | $350,933 | $118,860 | Diesel: 420k mi / 6.75 MPG [S67] * $5.64/gal [S58]; BEV: 420k mi * 2.0 kWh/mi [S109] * $0.1415/kWh [S26] |
| Maintenance (7-Year) | $105,000 | $52,500 | Diesel: 420k mi * $0.25/mi [S43]; BEV: 420k mi * $0.125/mi [S43] |
| **Total 7-Year TCO** | **$640,933** | **$685,860** | **BEV Premium: $44,927** |

### Detailed Assumptions
*   **Operational Profile**: 20 trucks running 60,000 miles per year (420,000 total miles over 7 years).
*   **Energy Pricing**: Diesel remains constant at $5.64/gal [S58, Oct 2026] and commercial electricity remains at $0.1415/kWh [S26, Oct 2026].
*   **Infrastructure**: Total depot cost of $3,060,000 [S10, 2026] (including 150kW DCFC hardware, installation, and utility upgrades) is allocated equally across 20 trucks.
*   **BEV Efficiency**: Estimated at 2.0 kWh/mile [S109], representing a conservative industry benchmark for Class 8 regional tractors.
*   **Residual Value**: No salvage or resale value was attributed to either vehicle type at the end of year 7.

### Sources
*   [S10] Commercial EV Charging Station Cost: Installation Guide for 2026
*   [S20] ICCT: Class 8 Vehicle Purchase Prices (2026)
*   [S26] ElectricChoice: Indiana Commercial Electricity Rates (Oct 2026)
*   [S41] Itascaresearch: Indiana State BEV Incentives (July 31, 2026)
*   [S43] Chinese Truck Factory: Class 8 Maintenance Costs (2026)
*   [S58] AAA: Indiana Diesel Prices (Oct 2026)
*   [S59] IRS: Commercial Clean Vehicle Credit 45W (2026)
*   [S67] HeavyVehicleInspection: Class 8 Fuel Efficiency Benchmarks (2026)
*   [S109] Yahoo Finance/AiLO Logistics: Tesla Semi Efficiency (2026)
