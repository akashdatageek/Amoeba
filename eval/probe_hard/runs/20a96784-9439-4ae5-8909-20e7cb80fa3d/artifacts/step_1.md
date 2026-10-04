# Optimal Assignment Data

## Summary
- **Total Minimum Cost:** 6356.25 [S1]

## Detailed Truck Assignments
- **Truck A:**
    - Loads: [L1, L2, L9] [S1]
    - Total Weight: 44,500 lb [S1]
    - Total Miles: 680 miles [S1]
- **Truck B:**
    - Loads: [L5, L7, L10] [S1]
    - Total Weight: 44,500 lb [S1]
    - Total Miles: 540 miles [S1]
- **Truck C:**
    - Loads: [L4, L6, L8] [S1]
    - Total Weight: 27,000 lb [S1]
    - Total Miles: 1,055 miles [S1]
- **Truck D:**
    - Loads: [L3] [S1]
    - Total Weight: 22,000 lb [S1]
    - Total Miles: 150 miles [S1]

## Proof of Optimality
The optimality of this solution is guaranteed because the search space was explored exhaustively. A Python script evaluated all $4^{10}$ (1,048,576) possible assignments of 10 loads to 4 trucks. For every assignment, the script verified that the total weight and total mileage for each truck remained within their respective capacities and limits. The cost was calculated for every valid combination, and the assignment with the absolute lowest total cost was selected [S1].
