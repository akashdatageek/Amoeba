```json
{
  "optimal_assignment": {
    "A": {"loads": ["L1","L2","L9"],  "weight_lb": 44500, "miles": 680,  "fixed": "350.00", "variable": "1428.00", "cost": "1778.00", "cap": 45000, "limit": 1100},
    "B": {"loads": ["L5","L7","L10"], "weight_lb": 44500, "miles": 540,  "fixed": "350.00", "variable": "1134.00", "cost": "1484.00", "cap": 45000, "limit": 1100},
    "C": {"loads": ["L4","L6","L8"],  "weight_lb": 27000, "miles": 1055, "fixed": "500.00", "variable": "1951.75", "cost": "2451.75", "cap": 30000, "limit": 1100},
    "D": {"loads": ["L3"],            "weight_lb": 22000, "miles": 150,  "fixed": "275.00", "variable": "367.50",  "cost": "642.50",  "cap": 26000, "limit": 900}
  },
  "total_cost": "6356.25",
  "feasible_count": 452,
  "optimal_count": 2,
  "top5_distinct_costs": [
    {"cost": "6356.25", "num_assignments": 2},
    {"cost": "6362.50", "num_assignments": 6},
    {"cost": "6368.75", "num_assignments": 4},
    {"cost": "6376.50", "num_assignments": 4},
    {"cost": "6382.75", "num_assignments": 4}
  ],
  "total_weight": 138000,
  "sum_capacity": 146000,
  "fixed_all_four": "1475.00"
}
```
(Source for all figures above: the enumeration run saved in solution.json [S2]. The file also holds the list of both optimal assignments. Costs were computed with exact Fractions, so there is no rounding.)

Optimality evidence:
- **Exhaustive search:** the script enumerated all 4^10 = 1,048,576 assignments of loads to trucks. It rejected any assignment that broke a weight or mileage limit. It found 452 feasible assignments [S2]. The minimum total cost is $6,356.25, reached by exactly 2 assignments [S2]. There was no pruning, so nothing was skipped.
- **All four trucks are needed:** total load weight is 138,000 lb. The three largest capacities sum to 45,000 + 45,000 + 30,000 = 120,000 lb, which is below 138,000. All four trucks must therefore carry loads (total capacity 146,000 lb). Fixed cost is fixed at 350 + 350 + 500 + 275 = $1,475.00 for every feasible plan. Only the variable cost, at 2.10, 2.10, 1.85 and 2.45 $/mile, is being optimised.
- **Recomputation with calc:** (350 + 2.10×680) + (350 + 2.10×540) + (500 + 1.85×1055) + (275 + 2.45×150) = 6356.25. This matches the script's total.
- **Constraint check on the optimum:**
  - Every load appears on exactly one truck: A has L1, L2, L9; B has L5, L7, L10; C has L4, L6, L8; D has L3. That is 10 loads in total.
  - A: 44,500 lb ≤ 45,000 and 680 mi ≤ 1,100.
  - B: 44,500 lb ≤ 45,000 and 540 mi ≤ 1,100.
  - C: 27,000 lb ≤ 30,000 and 1,055 mi ≤ 1,100.
  - D: 22,000 lb ≤ 26,000 and 150 mi ≤ 900.
- **A/B symmetry:** trucks A and B have identical parameters, so swapping their load sets gives the other optimal assignment. The 2 optimal assignments are this mirror pair: A and B swapped, with C = {L4, L6, L8} and D = {L3} unchanged. Up to the A/B swap the optimum is unique.
- **Margin:** the next-best distinct cost is $6,362.50 (6 assignments), which is $6.25 above the optimum. The next ones are $6,368.75, $6,376.50 and $6,382.75 [S2].
- **Files:** solution.json is saved in the workspace. The .xlsx deliverable with formula-based cost cells has not been built in this step. A later step should build it from these assignments.
