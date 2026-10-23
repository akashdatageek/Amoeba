# Final answer: minimum-cost assignment of 10 loads to 4 trucks

## 1) Result
The minimum total cost is **$6,356.25** [S2]. The independent verifier recomputed it and got the same figure [S7]. All four trucks are used. Truck A takes L1, L2 and L9. Truck B takes L5, L7 and L10. Truck C takes L4, L6 and L8. Truck D takes L3. Every load is on exactly one truck, and every weight and mileage limit is met.

## 2) Per-truck plan
| Truck | Loads | Total weight (lb) | Capacity (lb) | Total miles | Mileage limit | Fixed ($) | Variable ($) | Cost ($) |
|---|---|---|---|---|---|---|---|---|
| A | L1, L2, L9 | 44,500 | 45,000 | 680 | 1,100 | 350.00 | 1,428.00 | 1,778.00 |
| B | L5, L7, L10 | 44,500 | 45,000 | 540 | 1,100 | 350.00 | 1,134.00 | 1,484.00 |
| C | L4, L6, L8 | 27,000 | 30,000 | 1,055 | 1,100 | 500.00 | 1,951.75 | 2,451.75 |
| D | L3 | 22,000 | 26,000 | 150 | 900 | 275.00 | 367.50 | 642.50 |
| **Total** | 10 loads | 138,000 | 146,000 | 2,425 | – | 1,475.00 | 4,881.25 | **6,356.25** |

Sources: truck rows [S2]. Totals for weight, miles, fixed, variable and cost [S2][S5]. Total capacity 146,000 lb [S2].

Calculation: (350 + 2.10×680) + (350 + 2.10×540) + (500 + 1.85×1,055) + (275 + 2.45×150) = 6,356.25 [S2].

## 3) Why it is optimal
- **All four trucks are forced.** Total load weight is 138,000 lb. The three largest capacities sum to 45,000 + 45,000 + 30,000 = 120,000 lb, which is below 138,000. So every feasible plan uses all four trucks. The fixed cost is therefore always 350 + 350 + 500 + 275 = **$1,475.00**, and only the variable cost can be reduced [S2].
- **Exhaustive enumeration.** All 4^10 = 1,048,576 assignments were enumerated with no pruning. Of these, **452 are feasible** and **2 are optimal**, both at $6,356.25 [S2].
- **A/B symmetry.** Trucks A and B have identical parameters. The 2 optimal assignments are a mirror pair: the L1/L2/L9 and L5/L7/L10 sets swapped between A and B. C = {L4, L6, L8} and D = {L3} are the same in both. Up to the A/B swap, the optimum is unique [S2].
- **Margin.** The next-best distinct cost is $6,362.50, reached by 6 assignments. That is $6.25 above the optimum [S4]. The next levels are $6,368.75, $6,376.50 and $6,382.75 [S2].
- **Independent verification.** The verifier used a different method: a subset-based dynamic program over feasible load subsets per truck (verify_solve.py) [S7]. It found the same minimum, $6,356.25. It recomputed every truck's weight, miles and cost and checked all limits. **Verifier verdict: "PASS". Discrepancies: "None."** [S7][S9]

## 4) Workbook: truck_assignment_plan.xlsx
Sheets, in order: **Assignment, Inputs, Cost, Optimality** [S5].
- **Assignment:** one row per load, with columns Load, Truck, Weight and Miles. The truck letters in B2:B11 are the editable inputs, with an A/B/C/D dropdown. Weight and Miles are looked up by formula.
- **Inputs:** the load table and truck table from the task statement. This is the only hard-coded data.
- **Cost:** per-truck weight, miles, count, used flag, weight and mileage checks, fixed cost, variable cost, truck cost and load list, all as formulas. It also has the exactly-once and limit checks in rows 11–17, with the overall result in C17.
- **Total-cost formula:** the total sits in **Cost!B8**, which is `=J6`. Cost!J6 is `=SUM(J2:J5)` [S2][S5]. Per-truck weight and miles use SUMIF, for example Cost!B2 = `SUMIF(Assignment!$B$2:$B$11,$A2,Assignment!$C$2:$C$11)` [S4].
- **Optimality:** the solver results are hard-coded and labelled as such: 452 feasible, 2 optimal, next-best $6,362.50. The margin and the all-four-trucks-needed argument are formulas.
- **Recalculation:** LibreOffice recalculation reported success, 148 formulas and 0 errors. Cost!C17 (all checks) and Cost!C18 (total matches solver) both show OK [S5].
- **Audit:** the verifier audited the workbook. It confirmed the Inputs data, the plan on the Assignment sheet, the formulas, and that the evaluated values match the recomputation (A 1778, B 1484, C 2451.75, D 642.5, total 6356.25) [S9].

### Files produced by the team
- **truck_assignment_plan.xlsx** (step 2): the deliverable workbook described above, with the plan, live cost formulas, constraint checks and the optimality sheet.
- **solution.json** (step 1): the solver output: the optimal assignment per truck, total cost 6356.25, 452 feasible and 2 optimal assignments, the top-5 distinct costs, and both optimal assignments.
- **solve.py** (step 1): the exhaustive enumeration script over all 4^10 assignments that produced solution.json.
- **tool_results/step1_1.txt** (step 1): the saved tool output of the step 1 enumeration run.
- **build.py** (step 2): the script that built truck_assignment_plan.xlsx from solution.json.
- **tool_results/step2_1.txt** and **tool_results/step2_2.txt** (step 2): saved tool outputs from the workbook build and the recalculation/formula check (0 errors reported [S5]).
- **solver.py** and **verify_solve.py** (step 3): the verifier's independent subset-based dynamic-programming solver and its run, which found the same minimum, $6,356.25 [S7].
- **audit_workbook.py** and **audit_workbook_v2.py** (step 3): the verifier's workbook audit scripts (the v2 script is the one cited for the audit [S9]).
- **tool_results/step3_4.txt** (step 3): the saved tool output of the verifier's audit run.

## 5) Assumptions
- Input data are exactly as given in the task statement. No web research was used, and today's date (22 October 2026) does not affect any figure.
- A truck with no loads costs nothing. This does not arise here, because all four trucks are required.
- Costs were computed exactly, with no rounding [S2].

## Limitations
- **Step 1 (Optimization Analyst), partial:** the "$6.25" margin was cited to S2 mislabelled, because it is not stated in S2 itself. It is the difference between the next-best cost of $6,362.50 and the optimum of $6,356.25, both from S2. The optimum and the counts are unaffected.
- **Step 3 (Independent Verifier), flagged partial/"DISPUTED" by the automated check:** the flagged pairs were weight 138,000 (step 1) vs 44,500, and miles 2,425 (step 2) vs 680. The verifier's own memo gives verdict PASS, lists no issues, and states "Discrepancies: None." In the tables, 138,000 and 2,425 are the all-truck totals, while 44,500 and 680 are Truck A's figures. I did not recompute anything to resolve this, so the automated flag is reported here as unresolved.
- **Step 2 (Workbook Builder):** 7 of its figures carried no source tags. They match the figures in steps 1 and 3.
