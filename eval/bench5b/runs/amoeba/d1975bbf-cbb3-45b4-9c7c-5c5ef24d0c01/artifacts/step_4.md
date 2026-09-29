**Memo: Final Delivery Summary**

**Current US Average Diesel Price:** $6.4709 [S3] (as of 9/27/26 [S3])
**Source:** https://gasprices.aaa.com

**Fuel Cost Calculations (at 6.5 mpg):**
- Chicago–Indianapolis: 28.4615 [S10] gallons, $184.1715 [S10]
- Indianapolis–Columbus: 26.9230 [S10] gallons, $174.2160 [S10]
- Columbus–Pittsburgh: 28.4615 [S10] gallons, $184.1715 [S10]

**Deliverables:**
- `fuel_costs.xlsx`: An Excel file containing the legs, gallons, and costs, including a total row that uses the formulas `=SUM(B2:B4)` for gallons and `=SUM(C2:C4)` for costs.
- `generate_fuel_costs.py`: The Python script used to generate the `fuel_costs.xlsx` file.

## Limitations
Step 3 was partial because `recalc.py` was missing, which prevented the automated recalculation of formulas via the tool.
