memo: final delivery

## Final Delivery Memo
The shipment data has been processed into an Excel file; however, the verification process failed.

## Deliverables
- `shipment_data.xlsx`: Excel file containing shipment data for Lanes A-D, a totals row, and the average revenue formula.
- `create_excel.py`: Python script used to generate the Excel file.

## Summary of Results
- Lane A: 12 [unverified] loads, $1,850 [unverified] avg
- Lane B: 7 [unverified] loads, $2,400 [unverified] avg
- Lane C: 20 [unverified] loads, $1,420 [unverified] avg
- Lane D: 4 [unverified] loads, $3,100 [unverified] avg
- Totals row: Implemented [S2]
- Average Revenue Formula: `=SUM(D2:D5)/SUM(B2:B5)` implemented in cell C6 [S2]

## Limitations
- Step 2: Data population in `shipment_data.xlsx` was not verified [unverified].
- Step 2: Formula evaluation was blocked due to missing `recalc.py` script.
- Step 3: Verification failed (Verdict: FAIL) because the analyst was unable to open `shipment_data.xlsx` to independently verify totals and formulas.

- BLOCKED: Excel file access (the team had no such capability; added by plain code)
- BLOCKED: scripts/recalc.py (the team had no such capability; added by plain code)

