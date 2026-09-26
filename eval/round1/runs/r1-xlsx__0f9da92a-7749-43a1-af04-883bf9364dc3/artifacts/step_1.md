memo: spreadsheet_specification

**Spreadsheet Schema Specification**

**1 [unverified]. Column Definitions**
- Column A: Lane (Text)
- Column B: Loads (Numeric)
- Column C: Avg Revenue (Currency)
- Column D: Total Revenue (Currency)

**2 [unverified]. Row Data**
| Row | Column A (Lane) | Column B (Loads) | Column C (Avg Revenue) | Column D (Total Revenue) |
| :--- | :--- | :--- | :--- | :--- |
| 1 [unverified] | **Lane** | **Loads** | **Avg Revenue** | **Total Revenue** |
| 2 [unverified] | Lane A | 12 [unverified] | $1,850 [unverified] | $22,200 (12 [unverified] * 1,850 [unverified]) |
| 3 [unverified] | Lane B | 7 [unverified] | $2,400 [unverified] | $16,800 (7 [unverified] * 2,400 [unverified]) |
| 4 [unverified] | Lane C | 20 [unverified] | $1,420 [unverified] | $28,400 (20 [unverified] * 1,420 [unverified]) |
| 5 [unverified] | Lane D | 4 [unverified] | $3,100 [unverified] | $12,400 (4 [unverified] * 3,100 [unverified]) |
| 6 [unverified] | **Totals** | [Formula 1 [unverified]] | [Formula 3 [unverified]] | [Formula 2 [unverified]] |

**3 [unverified]. Totals Row Formulas**
- **Formula 1 [unverified] (Total Loads - Cell B6 [unverified]):** `=SUM(B2 [unverified]:B5 [unverified])`
- **Formula 2 [unverified] (Total Revenue - Cell D6 [unverified]):** `=SUM(D2 [unverified]:D5 [unverified])`
- **Formula 3 [unverified] (Weighted Average Revenue per Load - Cell C6 [unverified]):** `=D6 [unverified]/B6 [unverified]`
