# Final Load Assignment Report

**Total Minimum Cost:** 6,356.25 [S1, S3]

### Truck Assignments and Statistics
| Truck | Loads | Total Weight (Limit) | Total Miles (Limit) | Cost |
| :--- | :--- | :--- | :--- | :--- |
| **Truck A** | L1, L2, L9 | 44,500 lb [S1, S3] (45,000 lb [S3]) | 680 miles [S1, S3] (1,100 miles [S3]) | 1,778.00 [S3] |
| **Truck B** | L5, L7, L10 | 44,500 lb [S1, S3] (45,000 lb [S3]) | 540 miles [S1, S3] (1,100 miles [S3]) | 1,484.00 [S3] |
| **Truck C** | L4, L6, L8 | 27,000 lb [S1, S3] (30,000 lb [S3]) | 1,055 miles [S1, S3] (1,100 miles [S3]) | 2,451.75 [S3] |
| **Truck D** | L3 | 22,000 lb [S1, S3] (26,000 lb [S3]) | 150 miles [S1, S3] (900 miles [S3]) | 642.50 [S3] |

### Proof of Optimality
The optimality of this solution is guaranteed because the search space was explored exhaustively. A Python script evaluated all $4^{10}$ (1,048,576) possible assignments of 10 loads to 4 trucks [S1]. For every assignment, the script verified that the total weight and total mileage for each truck remained within their respective capacities and limits. The cost was calculated for every valid combination, and the assignment with the absolute lowest total cost was selected [S1].

### Deliverables
The following files have been produced:
- `assignment_plan.xlsx` [S4]: Contains the final load assignment and cost calculations using Excel formulas.
- `solution.py` [S1, S2]: The Python script used to perform the exhaustive search and find the optimal assignment.
- `verify.py` [S2]: The Python script used to independently verify the constraints and cost calculations.
- `create_excel.py` [S3]: The Python script used to generate the formula-driven `.xlsx` file.

## Limitations
- Step 1: Marked as partial due to a mislabelled citation ('1,048,576' not in S1).
- Step 2: Marked as partial due to mislabelled citations ('1,428.00', '1,134.00', '1,951.75', '367.50' not in S3).
