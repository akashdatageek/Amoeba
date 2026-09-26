import openpyxl
from openpyxl.styles import Font

# Create workbook and sheet
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Shipments"

# Headers
headers = ["Lane", "Loads", "Avg Revenue", "Total Revenue"]
ws.append(headers)

# Data rows
data = [
    ["Lane A", 12, 1850, 22200],
    ["Lane B", 7, 2400, 16800],
    ["Lane C", 20, 1420, 28400],
    ["Lane D", 4, 3100, 12400],
]

for row in data:
    ws.append(row)

# Totals Row
ws["A6"] = "Totals"
ws["B6"] = "=SUM(B2:B5)"
ws["C6"] = "=D6/B6"
ws["D6"] = "=SUM(D2:D5)"

# Formatting
arial_font = Font(name='Arial')
for row in ws.iter_rows():
    for cell in row:
        cell.font = arial_font

# Currency formatting for columns C and D
for row in range(2, 7):
    ws[f"C{row}"].number_format = '$"#,##0'
    ws[f"D{row}"].number_format = '$"#,##0'

wb.save("shipment_data.xlsx")