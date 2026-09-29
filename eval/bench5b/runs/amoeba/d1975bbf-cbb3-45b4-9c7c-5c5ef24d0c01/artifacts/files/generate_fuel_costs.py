from openpyxl import Workbook
from openpyxl.styles import Font

# Create workbook and sheet
wb = Workbook()
ws = wb.active
ws.title = "Fuel Costs"

# Define headers and data
headers = ['Leg', 'Gallons', 'Cost']
data = [
    ['Chicago–Indianapolis', 28.46, 184.17],
    ['Indianapolis–Columbus', 26.92, 174.22],
    ['Columbus–Pittsburgh', 28.46, 184.17],
]

# Add headers
ws.append(headers)

# Add data rows
for row in data:
    ws.append(row)

# Add Total row with formulas
# B2:B4 are the Gallons, C2:C4 are the Costs
ws.append(['Total', '=SUM(B2:B4)', '=SUM(C2:C4)'])

# Apply professional font (Arial) to all cells
font_arial = Font(name='Arial')
for row in ws.iter_rows():
    for cell in row:
        cell.font = font_arial

# Save the file
wb.save('fuel_costs.xlsx')
print("fuel_costs.xlsx created successfully.")