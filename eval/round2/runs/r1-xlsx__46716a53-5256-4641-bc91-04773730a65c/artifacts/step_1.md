memo: spreadsheet_specification

**Spreadsheet Layout Specification**

**1 [unverified]. Table Structure**
- Column A: Lane
- Column B: Loads
- Column C: Avg Revenue
- Column D: Total Revenue

**2 [unverified]. Row Data**
| Row | Column A (Lane) | Column B (Loads) | Column C (Avg Revenue) | Column D (Total Revenue) |
| :--- | :--- | :--- | :--- | :--- |
| 2 [unverified] | Lane A | 12 [unverified] | 1,850 [unverified] | 12 [unverified] * 1,850 [unverified] = 22,200 |
| 3 [unverified] | Lane B | 7 [unverified] | 2,400 [unverified] | 7 [unverified] * 2,400 [unverified] = 16,800 |
| 4 [unverified] | Lane C | 20 [unverified] | 1,420 [unverified] | 20 [unverified] * 1,420 [unverified] = 28,400 |
| 5 [unverified] | Lane D | 4 [unverified] | 3,100 [unverified] | 4 [unverified] * 3,100 [unverified] = 12,400 |
| 6 [unverified] | **Totals** | **[Formula 1 [unverified]]** | **[Formula 3 [unverified]]** | **[Formula 2 [unverified]]** |

**3 [unverified]. Excel Formulas for Totals Row (Row 6 [unverified])**
- **[Formula 1 [unverified]] Total Loads (Cell B6 [unverified]):** `=SUM(B2:B5)`
- **[Formula 2 [unverified]] Total Revenue (Cell D6 [unverified]):** `=SUM(D2:D5)`
- **[Formula 3 [unverified]] Weighted Average Revenue per Load (Cell C6 [unverified]):** `=D6/B6`
