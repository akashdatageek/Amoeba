The following Python code implements the spreadsheet specification from Step 1:

```python
import openpyxl

# Create workbook and select active sheet
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Shipment Data"

# Define headers
headers = ["Lane", "Loads", "Avg Revenue", "Total Revenue"]
ws.append(headers)

# Define data rows based on Step 1 specification
# Lane A: 12 [unverified] loads, 1850 [unverified] avg
# Lane B: 7 [unverified] loads, 2400 [unverified] avg
# Lane C: 20 [unverified] loads, 1420 [unverified] avg
# Lane D: 4 [unverified] loads, 3100 [unverified] avg
data = [
    ["Lane A", 12, 1850, "=B2*C2"],
    ["Lane B", 7, 2400, "=B3*C3"],
    ["Lane C", 20, 1420, "=B4*C4"],
    ["Lane D", 4, 3100, "=B5*C5"],
]

for row in data:
    ws.append(row)

# Insert Totals row (Row 6)
ws["A6"] = "Totals"
ws["B6"] = "=SUM(B2:B5)"  # Total Loads
ws["C6"] = "=D6/B6"       # Weighted Average Revenue per Load
ws["D6"] = "=SUM(D2:D5)"  # Total Revenue

# Save the file
wb.save("shipment_data.xlsx")
```

BLOCKED: excel_generator — Unable to generate the shipment_data.xlsx file as the required tool is unavailable.
