memo: spreadsheet_specification

### Spreadsheet Layout Specification

**1 [unverified]. Table Structure**
- Column A [unverified]: Lane
- Column B [unverified]: Loads
- Column C [unverified]: Avg Revenue
- Column D [unverified]: Total Revenue

**2 [unverified]. Row Data**
| Row | Column A (Lane) | Column B (Loads) | Column C (Avg Revenue) | Column D (Total Revenue) |
| :--- | :--- | :--- | :--- | :--- |
| 1 [unverified] | Lane | Loads | Avg Revenue | Total Revenue |
| 2 [unverified] | Lane A | 12 [unverified] | 1850 [unverified] | 12 [unverified] * 1850 [unverified] = 22,200 |
| 3 [unverified] | Lane B | 7 [unverified] | 2400 [unverified] | 7 [unverified] * 2400 [unverified] = 16,800 |
| 4 [unverified] | Lane C | 20 [unverified] | 1420 [unverified] | 20 [unverified] * 1420 [unverified] = 28,400 |
| 5 [unverified] | Lane D | 4 [unverified] | 3100 [unverified] | 4 [unverified] * 3100 [unverified] = 12,400 |
| 6 [unverified] | **Totals** | **[Formula 1]** | **[Formula 3]** | **[Formula 2]** |

**3 [unverified]. Excel Formulas**
- **Formula 1 (Total Loads):** `=SUM(B2:B5)`
- **Formula 2 (Total Revenue):** `=SUM(D2:D5)`
- **Formula 3 (Weighted Average Revenue per Load):** `=D6/B6`

**4 [unverified]. Summary of Calculated Values (for validation)**
- Total Loads: 12 [unverified] + 7 [unverified] + 20 [unverified] + 4 [unverified] = 43
- Total Revenue: 22,200 + 16,800 + 28,400 + 12,400 = 79,800
- Weighted Average: 79,800 / 43 = 1,855.81
