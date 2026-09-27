memo: final_delivery

## Verification Summary
Verification Status: Failed.

- R1 (Turn shipment data into an Excel file): `shipment_data.xlsx` was created in Step 2, but verification failed in Step 3.
- R2 (Include a totals row): UNVERIFIED [S3].
- R3 (Include a formula for average revenue per load): UNVERIFIED [S3].

## Deliverables
- `shipment_data.xlsx`: An Excel file intended to contain shipment data for Lane A [unverified], Lane B [unverified], Lane C [unverified], and Lane D [unverified], including a totals row [unverified] and formulas for total revenue and average revenue per load [unverified].
- `generate_shipments.py`: The Python script used to generate the `shipment_data.xlsx` file.

## Limitations
- Step 2: Incomplete (max_turns).
- Step 3: Partial/FAIL (Lacked File Access, Script Access).
- Figures: Totals row formulas and Average revenue per load formula are UNVERIFIED [S3].
