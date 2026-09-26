memo: spreadsheet_specification

**Column Definitions**
- Column A: Lane (Text)
- Column B: Loads (Numeric)
- Column C: Avg Revenue (Currency)
- Column D: Total Revenue (Currency)

**Row Data**
- Row 2 [unverified]: Lane A | 12 [unverified] | 1,850 [unverified] | 22,200 (12 * 1,850)
- Row 3 [unverified]: Lane B | 7 [unverified] | 2,400 [unverified] | 16,800 (7 * 2,400)
- Row 4 [unverified]: Lane C | 20 [unverified] | 1,420 [unverified] | 28,400 (20 * 1,420)
- Row 5 [unverified]: Lane D | 4 [unverified] | 3,100 [unverified] | 12,400 (4 * 3,100)
- Row 6 [unverified]: Totals | [Formula B6] | [Formula C6] | [Formula D6]

**Totals Row Formulas**
- Total Loads (Cell B6 [unverified], summing range B2 [unverified] to B5 [unverified]): `=SUM(B2:B5)`
- Total Revenue (Cell D6 [unverified], summing range D2 [unverified] to D5 [unverified]): `=SUM(D2:D5)`
- Weighted Average Revenue per Load (Cell C6 [unverified], dividing D6 [unverified] by B6 [unverified]): `=D6/B6`
