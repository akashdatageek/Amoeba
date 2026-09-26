file: shipment_data.xlsx

```python
import openpyxl
from openpyxl import Workbook

# Create workbook and select active sheet
wb = Workbook()
ws = wb.active
ws.title = "Shipment Data"

# 1. Table Structure: Define headers
headers = ["Lane", "Loads", "Avg Revenue", "Total Revenue"]
ws.append(headers)

# 2. Row Data: Populate data rows based on specification
# Lane A: 12 [unverified] loads, 1,850 [unverified] avg, 22,200 [unverified] total
# Lane B: 7 [unverified] loads, 2,400 [unverified] avg, 16,800 [unverified] total
# Lane C: 20 [unverified] loads, 1,420 [unverified] avg, 28,400 [unverified] total
# Lane D: 4 [unverified] loads, 3,100 [unverified] avg, 12,400 [unverified] total
data = [
    ["Lane A", 12, 1850, 22200],
    ["Lane B", 7, 2400, 16800],
    ["Lane C", 20, 1420, 28400],
    ["Lane D", 4, 3100, 12400],
]

for row in data:
    ws.append(row)

# 3. Excel Formulas for Totals Row (Row 6)
ws["A6"] = "Totals"
ws["B6"] = "=SUM(B2:B5)" # Total Loads [unverified]
ws["C6"] = "=D6/B6"       # Weighted Average Revenue per Load [unverified]
ws["D6"] = "=SUM(D2:D5)" # Total Revenue [unverified]

# Save the file
wb.save("shipment_data.xlsx")
```

BLOCKED: excel_generator — The .xlsx file could not be generated because the required tool is unavailable.
