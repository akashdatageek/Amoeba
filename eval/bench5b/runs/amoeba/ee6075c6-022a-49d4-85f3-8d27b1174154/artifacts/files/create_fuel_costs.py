from openpyxl import Workbook
from openpyxl.styles import Font

# Create workbook and select active sheet
wb = Workbook()
ws = wb.active
ws.title = "Fuel Costs"

# Header row
headers = ['Leg', 'Gallons', 'Cost']
ws.append(headers)

# Verified data from Step 2
data = [
    ['Chicago–Indianapolis', 28.46, 184.17],
    ['Indianapolis–Columbus', 26.92, 174.22],
    ['Columbus–Pittsburgh', 28.46, 184.17],
]

for row in data:
    ws.append(row)

# Total row with Excel formulas
ws.append(['Total', '=SUM(B2:B4)', '=SUM(C2:C4)'])

# Apply professional font (Arial) to all cells
arial_font = Font(name='Arial')
for row in ws.iter_rows():
    for cell in row:
        cell.font = arial_font

# Save the file
wb.save('fuel_costs.xlsx')
