# Final Load Assignment Solution

**Minimum Total Cost:** $6,356.25 [S2]

### Assignment Table
| Truck | Loads | Total Weight (lb) | Total Miles |
| :--- | :--- | :--- | :--- |
| A | L1, L2, L9 | 44,500 [S2] | 680 [S2] |
| B | L5, L7, L10 | 44,500 [S2] | 540 [S2] |
| C | L4, L6, L8 | 27,000 [S2] | 1,055 [S2] |
| D | L3 | 22,000 [S2] | 150 [S2] |

### Optimality Proof
The solution was determined using a custom recursive exhaustive search (brute-force) algorithm [S2]. The algorithm evaluated all possible assignments of 10 loads across 4 trucks ($4^{10} = 1,048,576$ combinations) [S2]. For every combination, the script verified that the total weight and total mileage for each truck did not exceed its specific capacity and limit. Because the entire feasible solution space was searched and the objective function (Total Cost = $\sum \text{Fixed Costs} + \sum (\text{Miles} \times \text{Rate})$) was calculated for every valid assignment, the identified minimum cost of $6,356.25 [S2] is mathematically guaranteed to be the global optimum. The optimality gap is 0% [S2].

### QA Verification
The solution has been verified by the QA Engineer with a verdict of **PASS**. Verification included:
- Manual summation of weights and miles for all trucks against task constraints.
- Manual recalculation of costs for each truck and the total cost.
- Inspection of the `cost_plan.xlsx` file to confirm correct data and formula-based calculations.

### Deliverables
The detailed plan and cost calculations are provided in the attached file: `cost_plan.xlsx` [S3].

## Limitations
- Step 1: Partial (mislabelled citation: '0%' not in S2).
- Step 3: Partial (mislabelled citations: '1,778.00', '1,484.00', '2,451.75', '642.50' not in S2).
