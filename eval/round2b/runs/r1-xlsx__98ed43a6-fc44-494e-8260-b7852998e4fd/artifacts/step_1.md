memo: spreadsheet_specification

### Spreadsheet Layout
**Columns:**
- Column A: Lane
- Column B: Loads
- Column C: Avg Revenue
- Column D: Total Revenue

**Row Data:**
| Row | Column A (Lane) | Column B (Loads) | Column C (Avg Revenue) | Column D (Total Revenue) |
| :--- | :--- | :--- | :--- | :--- |
| 1 [unverified] | Lane | Loads | Avg Revenue | Total Revenue |
| 2 [unverified] | Lane A | 12 [unverified] | 1850 [unverified] | =B2*C2 (12 * 1850 = 22,200) |
| 3 [unverified] | Lane B | 7 [unverified] | 2400 [unverified] | =B3*C3 (7 * 2400 = 16,800) |
| 4 [unverified] | Lane C | 20 [unverified] | 1420 [unverified] | =B4*C4 (20 * 1420 = 28,400) |
| 5 [unverified] | Lane D | 4 [unverified] | 3100 [unverified] | =B5*C5 (4 * 3100 = 12,400) |
| 6 [unverified] | **Totals** | **[Formula 1 [unverified]]** | **[Formula 3 [unverified]]** | **[Formula 2 [unverified]]** |

### Calculations (for verification)
- Lane A Total: 12 [unverified] * 1850 [unverified] = 22,200
- Lane B Total: 7 [unverified] * 2400 [unverified] = 16,800
- Lane C Total: 20 [unverified] * 1420 [unverified] = 28,400
- Lane D Total: 4 [unverified] * 3100 [unverified] = 12,400

### Excel Formulas for Totals Row (Row 6 [unverified])
- **[Formula 1 [unverified]] Total Loads (Cell B6 [unverified]):** `=SUM(B2:B5)`
- **[Formula 2 [unverified]] Total Revenue (Cell D6 [unverified]):** `=SUM(D2:D5)`
- **[Formula 3 [unverified]] Weighted Average Revenue per Load (Cell C6 [unverified]):** `=D6/B6`
