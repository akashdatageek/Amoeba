memo: spreadsheet_specification

**1 [unverified]. Table Structure**
The spreadsheet shall consist of a table with the following columns:
- Column A: Lane
- Column B: Loads
- Column C: Avg Revenue
- Column D: Total Revenue

**2 [unverified]. Row Data**
| Row | Column A (Lane) | Column B (Loads) | Column C (Avg Revenue) | Column D (Total Revenue) |
| :--- | :--- | :--- | :--- | :--- |
| 2 [unverified] | Lane A | 12 [unverified] | 1850 [unverified] | =B2*C2 |
| 3 [unverified] | Lane B | 7 [unverified] | 2400 [unverified] | =B3*C3 |
| 4 [unverified] | Lane C | 20 [unverified] | 1420 [unverified] | =B4*C4 |
| 5 [unverified] | Lane D | 4 [unverified] | 3100 [unverified] | =B5*C5 |

*Calculated values for verification:*
- Lane A Total: 12 * 1850 = 22,200
- Lane B Total: 7 * 2400 = 16,800
- Lane C Total: 20 * 1420 = 28,400
- Lane D Total: 4 * 3100 = 12,400

**3 [unverified]. Totals Row (Row 6 [unverified])**
The bottom row shall be designated as the "Totals" row with the following specifications:
- Cell A6 [unverified]: "Totals"
- Cell B6 [unverified] (Total Loads): `=SUM(B2:B5)`
- Cell D6 [unverified] (Total Revenue): `=SUM(D2:D5)`
- Cell C6 [unverified] (Weighted Average Revenue per Load): `=D6/B6`

**4 [unverified]. Success Criteria Verification**
- Total revenue for each lane is calculated via formula `=B[row]*C[row]`.
- Total Loads is the sum of Column B.
- Total Revenue is the sum of Column D.
- Weighted Average Revenue per Load is calculated as Total Revenue (D6 [unverified]) divided by Total Loads (B6 [unverified]).
