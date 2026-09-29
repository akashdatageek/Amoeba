**Memo: Fuel Cost Analysis**

**Current US Diesel Price:** $6.4709 [S3] (as of 9/27/26)
**Source:** https://gasprices.aaa.com

**Fuel Cost Calculations (at 6.5 mpg):**
- Chicago–Indianapolis: 185 [S3] miles, 28.46 gallons, $184.17
- Indianapolis–Columbus: 175 [S3] miles, 26.92 gallons, $174.22
- Columbus–Pittsburgh: 185 [S3] miles, 28.46 gallons, $184.17

**Files:**
- `fuel_costs.xlsx`: Excel file containing the legs, gallons, and costs. The total row is implemented using formulas: `=SUM(B2:B4)` for gallons and `=SUM(C2:C4)` for cost.
- `create_excel.py`: Python script used to create the Excel workbook.
- `create_fuel_costs.py`: Python script used to generate the fuel costs data in the Excel file.
