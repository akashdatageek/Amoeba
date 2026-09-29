from openpyxl import Workbook
from openpyxl.styles import Font

wb = Workbook()
ws = wb.active
ws.title = "Fuel Costs"

# Header
headers = ['Leg', 'Gallons', 'Cost']
ws.append(headers)

# Data
data = [
    ['Chicago–Indianapolis', 28.46, 184.17],
    ['Indianapolis–Columbus', 26.92, 174.22],
    ['Columbus–Pittsburgh', 28.46, 184.17],
]

for row in data:
    ws.append(row)

# Total Row
ws.append(['Total', '=SUM(B2:B4)', '=SUM(C2:C4)'])

# Professional Font (Arial)
arial_font = Font(name='Arial')
for row in ws.iter_rows():
    for cell in row:
        cell.font = arial_font

wb.save('fuel_costs.xlsx')
