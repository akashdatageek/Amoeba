memo: spreadsheet_specification

**Spreadsheet Layout Specification**

**1[unverified]. Table Structure**
The data shall be organized in a table from cell A1[unverified] to D6[unverified].

| Cell | Column A (Lane) | Column B (Loads) | Column C (Avg Revenue) | Column D (Total Revenue) |
| :--- | :--- | :--- | :--- | :--- |
| **Row 1[unverified]** | Lane | Loads | Avg Revenue | Total Revenue |
| **Row 2[unverified]** | Lane A | 12 [unverified] | 1850 [unverified] | 22,200 (12 * 1850) |
| **Row 3[unverified]** | Lane B | 7 [unverified] | 2400 [unverified] | 16,800 (7 * 2400) |
| **Row 4[unverified]** | Lane C | 20 [unverified] | 1420 [unverified] | 28,400 (20 * 1420) |
| **Row 5[unverified]** | Lane D | 4 [unverified] | 3100 [unverified] | 12,400 (4 * 3100) |
| **Row 6[unverified]** | **Totals** | [Formula B6[unverified]] | [Formula C6[unverified]] | [Formula D6[unverified]] |

**2[unverified]. Excel Formulas**

*   **Total Loads (Cell B6[unverified]):**
    `=SUM(B2[unverified]:B5[unverified])`
*   **Total Revenue (Cell D6[unverified]):**
    `=SUM(D2[unverified]:D5[unverified])`
*   **Weighted Average Revenue per Load (Cell C6[unverified]):**
    `=D6[unverified]/B6[unverified]`

**3[unverified]. Data Validation Notes**
- Column B and D should be formatted as Numbers.
- Column C and D should be formatted as Currency (USD).
- The Weighted Average in C6[unverified] must be derived from the totals to ensure mathematical soundness (Total Revenue / Total Loads).
