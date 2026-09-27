memo: spreadsheet_specification

**Spreadsheet Layout Specification**

**1 [unverified]. Table Structure**
- Column A: Lane
- Column B: Loads
- Column C: Avg Revenue
- Column D: Total Revenue

**2 [unverified]. Row Data**
| Row [unverified] | Column A (Lane) | Column B (Loads) | Column C (Avg Revenue) | Column D (Total Revenue) |
| :--- | :--- | :--- | :--- | :--- |
| 1 [unverified] | **Lane** | **Loads** | **Avg Revenue** | **Total Revenue** |
| 2 [unverified] | Lane A | 12 [unverified] | 1,850 [unverified] | =B2*C2 (12 [unverified] * 1,850 [unverified] = 22,200) |
| 3 [unverified] | Lane B | 7 [unverified] | 2,400 [unverified] | =B3*C3 (7 [unverified] * 2,400 [unverified] = 16,800) |
| 4 [unverified] | Lane C | 20 [unverified] | 1,420 [unverified] | =B4*C4 (20 [unverified] * 1,420 [unverified] = 28,400) |
| 5 [unverified] | Lane D | 4 [unverified] | 3,100 [unverified] | =B5*C5 (4 [unverified] * 3,100 [unverified] = 12,400) |
| 6 [unverified] | **Totals** | **=SUM(B2:B5)** | **=D6/B6** | **=SUM(D2:D5)** |

**3 [unverified]. Totals Row Calculations & Formulas**
- **Total Loads (Cell B6):** `=SUM(B2:B5)` 
  - Calculation: 12 [unverified] + 7 [unverified] + 20 [unverified] + 4 [unverified] = 43
- **Total Revenue (Cell D6):** `=SUM(D2:D5)` 
  - Calculation: 22,200 + 16,800 + 28,400 + 12,400 = 79,800
- **Weighted Average Revenue per Load (Cell C6):** `=D6/B6` 
  - Calculation: 79,800 / 43 = 1,855.81
