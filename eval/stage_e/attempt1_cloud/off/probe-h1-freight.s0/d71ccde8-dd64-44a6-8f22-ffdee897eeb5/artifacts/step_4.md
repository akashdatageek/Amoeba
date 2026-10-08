# Final Delivery: Load Assignment Optimization

**Minimum Total Cost: $6,356.25 [S1]**

### Assignment Table
| Truck | Loads | Total Weight (lb) | Total Miles |
| :--- | :--- | :--- | :--- |
| A | L1, L2, L9 | 44,500 | 680 |
| B | L5, L7, L10 | 44,500 | 540 |
| C | L4, L6, L8 | 27,000 | 1,055 |
| D | L3 | 22,000 | 150 |

### Optimality Proof
The load-assignment problem was modeled as an Integer Linear Programming (ILP) problem. Due to the absence of the `pulp` library in the execution environment, the problem was solved using a custom-implemented recursive backtracking algorithm with cost-based pruning.

**Methodology:**
1. **Search Space**: The algorithm explores all possible assignments of the 10 loads to the 4 available trucks.
2. **Constraint Validation**: At each step of the recursion, the algorithm validates that the truck's weight capacity and mileage limit are not exceeded.
3. **Pruning (Branch-and-Bound)**: The solver maintains the `best_cost` found so far. If the current partial assignment's cost already equals or exceeds the `best_cost`, the entire branch is pruned, as further assignments can only increase the cost.
4. **Exhaustive Search**: By exploring all feasible combinations (or proving them suboptimal via pruning), the algorithm ensures that the final result is the global minimum.

**Result:**
The solver converged to a minimum cost of 6,356.25 [S1]. Because the search space is finite and the pruning logic is sound, the gap between the best integer solution and the theoretical lower bound is 0%.

### QA Verification
The solution has been verified by the QA Engineer. The verification process included:
- Independent recalculation of weights and miles for each truck to ensure they are within limits.
- Independent calculation of costs using the provided fixed costs and per-mile rates.
- Confirmation that the total cost is exactly $6,356.25 [S3].
- Verification that the `.xlsx` file exists and contains the required data [S3].

**Verdict: PASS**

### Deliverables
The following files were produced during the process:
- `cost_plan_xlsx.xlsx`: The final deliverable containing the load assignment plan and cost calculations implemented as Excel formulas.
- `solver.py`: The Python script used to find the optimal assignment via a recursive backtracking algorithm with cost-based pruning.
- `create_xlsx.py`: The Python script used to generate the `cost_plan_xlsx.xlsx` file.
- `qa_verify.py`: The Python script used to independently verify that all constraints were met and costs were calculated correctly.

xlsx: cost_plan_xlsx.xlsx

## Limitations
- **Step 2**: Marked as partial due to internal citation mislabeling of individual truck costs and the `recalc.py` (xlsx skill) being blocked because `soffice` was not found on the system PATH. However, all final figures were independently verified by the QA Engineer in Step 3.

- NOT USED: skill xlsx, xlsx, xlsx (local:Read, local:Bash, local:Write, local:Edit) (given to the team for step 2 but never used; added by plain code)

