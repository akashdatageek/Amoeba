### optimal_assignment
| Truck | Loads | Total Weight (lb) | Total Miles |
| :--- | :--- | :--- | :--- |
| A | L1, L2, L9 | 44,500 | 680 |
| B | L5, L7, L10 | 44,500 | 540 |
| C | L4, L6, L8 | 27,000 | 1,055 |
| D | L3 | 22,000 | 150 |

**Total Cost:** $6,356.25 [S2]

### optimality_proof
**Memo: Optimality Proof**
- **Method:** Since specialized ILP solvers like PuLP and SciPy were unavailable in the environment [S1], a custom recursive exhaustive search (brute-force) algorithm was implemented [S2].
- **Search Space:** The algorithm evaluated all possible assignments of 10 loads across 4 trucks ($4^{10} = 1,048,576$ combinations).
- **Constraint Validation:** For every combination, the script verified that the total weight and total mileage for each truck did not exceed its specific capacity and limit.
- **Convergence:** Because the entire feasible solution space was searched and the objective function (Total Cost = $\sum \text{Fixed Costs} + \sum (\text{Miles} \times \text{Rate})$) was calculated for every valid assignment, the identified minimum cost of $6,356.25 [S2] is mathematically guaranteed to be the global optimum.
- **Gap:** The optimality gap is 0% [S2].

### cost_plan_xlsx
The cost calculation plan has been saved to `cost_plan.xlsx` [S3]. This file contains the assignment data and uses Excel formulas (e.g., `=D2*F2` for variable costs and `=E2+G2` for total truck costs) to ensure transparency and recalculation capability.

---
**Tool Usage Summary:**
- `local:Bash`: Used to run Python scripts for optimization and Excel generation.
- `openpyxl`: Used to create the formula-based `.xlsx` file.
- `pulp` / `scipy`: NOT NEEDED (Attempted but unavailable [S1]; replaced by exhaustive search).

**Contract Compliance:**
- `xlsx` skill: Used via `openpyxl` in `local:Bash`.
- `local:Read`: NOT NEEDED — no existing files required reading.
- `local:Bash`: Used.
- `local:Write`: NOT NEEDED — file creation handled via `local:Bash` Python script.
- `local:Edit`: NOT NEEDED — no existing files required editing.
