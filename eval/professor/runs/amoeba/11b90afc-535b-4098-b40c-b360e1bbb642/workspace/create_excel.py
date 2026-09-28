import openpyxl
from openpyxl.styles import Font

# Create workbook and sheet
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Fuel Costs"

# Define headers
headers = ["Leg", "Distance (mi)", "Gallons", "Cost (USD)"]
ws.append(headers)

# Define data (with corrected Leg 2 cost: 26.92 * 6.29 = 169.33)
data = [
    ["Chicago–Indianapolis", 185, 28.46, 179.02],
    ["Indianapolis–Columbus", 175, 26.92, 169.33],
    ["Columbus–Pittsburgh", 185, 28.46, 179.02],
]

for row in data:
    ws.append(row)

# Add Total row
total_row_idx = 5
ws.cell(row=total_row_idx, column=1, value="Total")
ws.cell(row=total_row_idx, column=2, value="") 
ws.cell(row=total_row_idx, column=3, value="=SUM(C2:C4)")
ws.cell(row=total_row_idx, column=4, value="=SUM(D2:D4)")

# Apply Arial font to all cells
arial_font = Font(name='Arial')
for row in ws.iter_rows():
    for cell in row:
        cell.font = arial_font

# Save the file
wb.save("fuel_cost_file.xlsx")
