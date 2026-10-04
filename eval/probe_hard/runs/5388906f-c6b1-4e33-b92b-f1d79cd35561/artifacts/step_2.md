# TCO Analysis Package

## TCO Table (Per Truck)

| Component | Diesel | Battery-Electric (BEV) | Source/Date |
| :--- | :--- | :--- | :--- |
| Purchase Price | $185,000 [S2] | $420,000 [S2] | [S2] Oct 2026 |
| Federal Incentives (IRA 45W) | $0 [S2] | $0 [S2] | [S2] Oct 2026 |
| Indiana State Incentives | $0 [unverified] | $0 [unverified] | [unverified] Oct 2026 |
| Energy/Fuel Cost (7-yr) | $228,000 (calc) | $100,800 (calc) | [S24] Oct 2026 |
| Maintenance Cost (7-yr) | $63,000 (calc) | $37,800 (calc) | [S24] Oct 2026 |
| Charging Infrastructure | $0 [unverified] | $50,000 [unverified] | [unverified] Oct 2026 |
| **Total 7-Year TCO** | **$476,000 (calc)** | **$608,600 (calc)** | **[S24] Oct 2026** |

## Assumptions List
- **Annual Mileage:** 60,000 miles per truck (Task).
- **Analysis Period:** 7 years (Task).
- **Total Mileage:** 60,000 * 7 = 420,000 miles.
- **Diesel Fuel Economy:** 7.0 MPG [S1] (Conservative estimate based on 7–11.5 MPG range).
- **Diesel Price:** $3.80 per gallon (Indiana average estimate) [unverified].
- **BEV Energy Consumption:** 2.0 kWh per mile [S1].
- **Electricity Rate:** $0.12 per kWh (Indiana commercial rate estimate) [unverified].
- **Maintenance (Diesel):** $0.15 per mile [unverified].
- **Maintenance (BEV):** $0.09 per mile [unverified].
- **Infrastructure:** Total fleet cost of $1,000,000 for 20 trucks, allocated at $50,000 per truck [unverified].
- **Incentives:** Federal IRA 45W credit is $0 as it was canceled [S2]; no specific Indiana state-level purchase vouchers identified [unverified].

## Calculations
- **Diesel Energy Cost:** (420,000 miles / 7.0 [S1] MPG) * $3.80 [unverified]/gal = $228,000 [S24]
- **BEV Energy Cost:** 420,000 miles * 2.0 [S1] kWh/mi * $0.12 [unverified]/kWh = $100,800 [S24]
- **Diesel Maintenance:** 420,000 miles * $0.15 [unverified]/mi = $63,000 [S24]
- **BEV Maintenance:** 420,000 miles * $0.09 [unverified]/mi = $37,800 [S24]
- **Diesel TCO:** $185,000 [S2] + $228,000 + $63,000 = $476,000 [S24]
- **BEV TCO:** $420,000 [S2] - $0 [S2] + $100,800 + $37,800 + $50,000 [unverified] = $608,600 [S24]

## Citations List
- **[S1] Energy Consumption & Fuel Economy:** Electric Truck vs Diesel Truck: Complete Comparison - BOSA lithium battery (Energy consumption 1.55–2.1 kWh per mile; Diesel MPG 7–11.5).
- **[S2] Purchase Prices & Incentives:** California’s new incentive program could cause battery electric tractor-truck sales to skyrocket - International Council on Clean Transportation (Diesel: $185,000; BEV: $420,000; IRA 45W credit canceled).
- **[S24] TCO Calculations:** Local Bash execution results (Oct 2026).

## Draft Memo Text

**MEMORANDUM**

**TO:** Fleet Management
**FROM:** Fleet Cost Analyst
**DATE:** October 4, 2026
**SUBJECT:** TCO Analysis: Diesel vs. Battery-Electric Class 8 Tractors

**Executive Summary**
This analysis evaluates the 7-year Total Cost of Ownership (TCO) for replacing 20 Class 8 tractors with battery-electric vehicles (BEVs) for regional routes in Indiana. While BEVs offer significant operational savings in energy and maintenance, the high initial purchase price, the cancellation of federal tax credits, and the cost of charging infrastructure result in a BEV TCO that is $132,600 ($608,600 - $476,000) higher per truck than diesel over a 7-year period ($608,600 [S24] vs $476,000 [S24]).

**TCO Comparison (Per Truck)**
| Component | Diesel | BEV |
| :--- | :--- | :--- |
| Net Purchase Price | $185,000 [S2] | $420,000 [S2] |
| 7-Year Energy Cost | $228,000 [S24] | $100,800 [S24] |
| 7-Year Maintenance | $63,000 [S24] | $37,800 [S24] |
| Infrastructure | $0 [unverified] | $50,000 [unverified] |
| **Total TCO** | **$476,000 [S24]** | **$608,600 [S24]** |

**Key Drivers**
1. **Capital Expenditure:** The BEV purchase price is the primary cost driver. With the cancellation of the IRA 45W federal tax credit [S2], the net capital cost for a BEV is more than double that of a diesel tractor.
2. **Energy Savings:** BEVs provide a substantial operational advantage, reducing energy costs by approximately 56% (($228,000 - $100,800) / $228,000) ($127,200 ($228,000 - $100,800) savings per truck over 7 years) based on Indiana commercial electricity rates.
3. **Maintenance:** Reduced mechanical complexity in BEVs leads to an estimated 40% reduction in maintenance expenses.
4. **Infrastructure:** The requirement for DC fast charging and grid upgrades adds a significant upfront cost of $50,000 [unverified] per vehicle.

**Recommendation**
Based on the current financial modeling, **I recommend continuing with Diesel tractors for the 2026 procurement cycle.** 

The BEV option does not achieve TCO parity under current Indiana energy rates and purchase prices. The transition to BEV would only be financially viable if the company secures significant new state-level incentives or if diesel prices increase drastically.

***
