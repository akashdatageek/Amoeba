### optimal_assignment
| Truck | Loads | Weight (lb) | Miles |
| :--- | :--- | :--- | :--- |
| A | L1, L2, L9 | 44,500 | 680 |
| B | L5, L7, L10 | 44,500 | 540 |
| C | L4, L6, L8 | 27,000 | 1,055 |
| D | L3 | 22,000 | 150 |
**Total Cost: 6,356.25 [S1]**

### optimality_proof
**Memo: Optimality Proof**
The load-assignment problem was modeled as an Integer Linear Programming (ILP) problem. Due to the absence of the `pulp` library in the execution environment, the problem was solved using a custom-implemented recursive backtracking algorithm with cost-based pruning.

**Methodology:**
1. **Search Space**: The algorithm explores all possible assignments of the 10 loads to the 4 available trucks.
2. **Constraint Validation**: At each step of the recursion, the algorithm validates that the truck's weight capacity and mileage limit are not exceeded.
3. **Pruning (Branch-and-Bound)**: The solver maintains the `best_cost` found so far. If the current partial assignment's cost already equals or exceeds the `best_cost`, the entire branch is pruned, as further assignments can only increase the cost.
4. **Exhaustive Search**: By exploring all feasible combinations (or proving them suboptimal via pruning), the algorithm ensures that the final result is the global minimum.

**Result:**
The solver converged to a minimum cost of 6,356.25 [S1]. Because the search space is finite and the pruning logic is sound, the gap between the best integer solution and the theoretical lower bound is 0%.
