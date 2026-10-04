The formula-driven Excel file `assignment_plan.xlsx` has been generated [S4]. 

**File Details:**
- **Loads Table:** Contains all 10 loads with their weights and miles.
- **Trucks Table:** Contains properties for Trucks A, B, C, and D (Capacity, Mileage Limit, Fixed Cost, Rate).
- **Assignment Table:** Maps loads to trucks:
    - Truck A: L1, L2, L9 (44,500 lb, 680 mi) [S1, S3]
    - Truck B: L5, L7, L10 (44,500 lb, 540 mi) [S1, S3]
    - Truck C: L4, L6, L8 (27,000 lb, 1,055 mi) [S1, S3]
    - Truck D: L3 (22,000 lb, 150 mi) [S1, S3]
- **Cost Calculation Section:** Uses Excel formulas to calculate costs per truck and the total cost:
    - Individual Truck Cost Formula: `=FixedCost + (Rate * TotalMiles)`
    - Total Cost Formula: `=SUM(TruckCosts)`
    - Calculated Total Cost: 6,356.25 [S1, S3]

xlsx: assignment_plan.xlsx
