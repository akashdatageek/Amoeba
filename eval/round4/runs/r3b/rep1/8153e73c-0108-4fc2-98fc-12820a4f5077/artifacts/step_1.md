memo: spreadsheet_specification

### 1 [unverified]. Column Definitions
| Column | Header | Data Type | Description |
| :--- | :--- | :--- | :--- |
| A | Lane | Text | The identifier for the shipping lane |
| B | Loads | Number | Total number of loads for the lane |
| C | Avg Revenue | Currency | Average revenue per load for the lane |
| D | Total Revenue | Currency | Calculated total revenue (Loads * Avg Revenue) |

### 2 [unverified]. Row Data
| Row | Column A (Lane) | Column B (Loads) | Column C (Avg Revenue) | Column D (Total Revenue) |
| :--- | :--- | :--- | :--- | :--- |
| 1 [unverified] | **Lane** | **Loads** | **Avg Revenue** | **Total Revenue** |
| 2 [unverified] | Lane A | 12 [unverified] | $1,850 [unverified] | $22,200 (12 * 1850) |
| 3 [unverified] | Lane B | 7 [unverified] | $2,400 [unverified] | $16,800 (7 * 2400) |
| 4 [unverified] | Lane C | 20 [unverified] | $1,420 [unverified] | $28,400 (20 * 1420) |
| 5 [unverified] | Lane D | 4 [unverified] | $3,100 [unverified] | $12,400 (4 * 3100) |
| 6 [unverified] | **Totals** | **[Formula B6]** | | **[Formula D6]** |

### 3 [unverified]. Totals Row & Weighted Average Formulas
The following formulas should be implemented in the specified cells:

- **Total Loads (Cell B6):** `=SUM(B2:B5)`
- **Total Revenue (Cell D6):** `=SUM(D2:D5)`
- **Weighted Average Revenue per Load:** `=D6/B6` 
*(Note: This formula should be placed in a designated "Weighted Average" cell, e.g., Cell E6 or a separate summary row, to calculate the true average across all loads).*
