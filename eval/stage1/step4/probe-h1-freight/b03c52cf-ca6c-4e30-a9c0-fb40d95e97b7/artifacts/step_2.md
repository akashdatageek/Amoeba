# Memo: truck_assignment_plan.xlsx

## Summary
- **File:** truck_assignment_plan.xlsx, in the workspace root. build.py created it from solution.json [S3].
- **Total cost cell:** Cost!B8, which is =J6. Cost!J6 is =SUM(J2:J5).
- **Computed total:** $6,356.25. This equals the solver optimum of $6,356.25 from step 1 [S2].
- **Recalculation:** LibreOffice recalc.py reported status success, 148 formulas and 0 errors [S5].
- **Formulas confirmed:** I reloaded the file with openpyxl. Examples are Cost!B8 = "=J6" [S5] and Cost!B2 = SUMIF(Assignment!$B$2:$B$11,$A2,Assignment!$C$2:$C$11) [S4].
- **Cached values:** After recalculation, Cost!C17 (all checks) = OK and Cost!C18 (total matches solver) = OK [S5].

## Sheets
The sheet order is Assignment, Inputs, Cost, Optimality [S5]. I moved Assignment to the front. Its header row is Load, Truck, Weight, Miles [S5], which satisfies the required column names Truck, Weight, Miles.

### Assignment
- **Rows:** one row per load, rows 2–11 (10 rows).
- **Column A:** Load ID, pulled by formula from Inputs.
- **Column B:** Truck letter. These are the input cells B2:B11, shaded yellow, with an A/B/C/D dropdown. They hold the optimal plan:
  - A: L1, L2, L9
  - B: L5, L7, L10
  - C: L4, L6, L8
  - D: L3
- **Columns C and D:** Weight and Miles, pulled by INDEX/MATCH on Inputs.
- **Helper columns G1:J11:** =IF($B2=G$1,", "&$A2,""). They build the load lists without TEXTJOIN, so older Excel works.

### Inputs
- **Load table:** A4:C14 (ID, Weight (lb), Miles).
- **Truck table:** A18:E22 (Truck, Capacity, Mileage limit, Fixed $/day, Rate $/mile).
- **Hard-coded data:** these are the only hard-coded data, shown in blue. A1 notes that the source is the task statement.

### Cost
Truck rows 2–5 hold A–D. The columns are:
- Weight (SUMIF)
- Miles (SUMIF)
- Loads count (COUNTIF)
- Used (=IF(count>0,"Yes","No"))
- Weight OK
- Miles OK
- Fixed (=IF(used,fixed,0))
- Variable (=rate*miles)
- Truck cost (Fixed+Variable)
- Loads (MID of the concatenated helpers)

Row 6 holds the totals: weight 138,000 lb, miles 2,425, loads 10, fixed $1,475.00, variable $4,881.25, cost $6,356.25.

Checks are in rows 11–17, with the overall result in C17:
- COUNTA of assignments = 10.
- Every letter is valid, via SUMPRODUCT(COUNTIF(...)) = 10.
- The per-truck counts sum to 10, so each load is assigned exactly once.
- Assigned weight equals total load weight.
- All four weight limits are OK.
- All four mileage limits are OK.

C18 compares the total with Optimality!B5.

### Optimality
Hard-coded solver output is labelled as such in A1 [S2]:
- **Method:** exhaustive enumeration of 4^10 = 1,048,576 assignments, with no pruning.
- **B4:** 452 feasible assignments.
- **B5:** optimal cost $6,356.25.
- **B6:** 2 optimal assignments. They are the A/B mirror pair, so the optimum is unique up to the A/B swap.
- **B7 and B8:** next-best distinct cost $6,362.50, reached by 6 assignments.
- **A15:B19:** the top-5 distinct cost levels.

Formulas on this sheet:
- **B9:** margin = B7−B5 = $6.25.
- **B10:** =Cost!B8.
- **B11:** shows OK when the workbook total matches the solver.

The all-four-trucks-needed argument is built by formula:
- **B22:** total load weight = 138,000 lb.
- **B23:** three largest capacities = 45,000 + 45,000 + 30,000 = 120,000 lb.
- **B24:** "No – all 4 trucks required", because 120,000 < 138,000.
- **B25:** fixed cost of all four trucks = $1,475.00.

Rows 28–30 hold text notes.

## Recalculated per-truck results
All weight and mileage checks show OK.

| Truck | Loads | Weight (lb) | Miles | Cost |
|---|---|---|---|---|
| A | L1, L2, L9 | 44,500 | 680 | $1,778.00 |
| B | L5, L7, L10 | 44,500 | 540 | $1,484.00 |
| C | L4, L6, L8 | 27,000 | 1,055 | $2,451.75 |
| D | L3 | 22,000 | 150 | $642.50 |

Total = 1,778.00 + 1,484.00 + 2,451.75 + 642.50 = $6,356.25, which matches the solver.

## Formatting and dates
- **Formatting:** Arial font, currency and thousands-separator number formats, and set column widths.
- **Research:** No web research was needed. The task's "today" date (22 October 2026) is not used in any figure.
