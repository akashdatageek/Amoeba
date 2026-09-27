memo: spreadsheet_specification

### 1 [unverified]. Column Definitions
- **Column A**: Lane (Text)
- **Column B**: Loads (Numeric)
- **Column C**: Avg Revenue (Currency)
- **Column D**: Total Revenue (Currency)

### 2 [unverified]. Row Data
| Row | Column A (Lane) | Column B (Loads) | Column C (Avg Revenue) | Column D (Total Revenue) |
| :--- | :--- | :--- | :--- | :--- |
| 2 [unverified] | Lane A | 12 [unverified] | $1,850 [unverified] | 12 [unverified] * 1,850 [unverified] = 22,200 |
| 3 [unverified] | Lane B | 7 [unverified] | $2,400 [unverified] | 7 [unverified] * 2,400 [unverified] = 16,800 |
| 4 [unverified] | Lane C | 20 [unverified] | $1,420 [unverified] | 20 [unverified] * 1,420 [unverified] = 28,400 |
| 5 [unverified] | Lane D | 4 [unverified] | $3,100 [unverified] | 4 [unverified] * 3,100 [unverified] = 12,400 |

### 3 [unverified]. Totals Row (Row 6 [unverified])
- **Cell A6 [unverified]**: "Totals"
- **Cell B6 [unverified] (Total Loads)**: `=SUM(B2:B5)`
- **Cell D6 [unverified] (Total Revenue)**: `=SUM(D2:D5)`
- **Cell C6 [unverified] (Weighted Average Revenue per Load)**: `=D6/B6`
