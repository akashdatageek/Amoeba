import openpyxl
from openpyxl.styles import Font, Alignment

# Create workbook and sheet
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Shipment Data"

# Professional font
arial_font = Font(name='Arial')

# Headers
headers = ['Lane', 'Loads', 'Avg Revenue', 'Total Revenue', 'Weighted Avg']
for col_num, header in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col_num, value=header)
    cell.font = Font(name='Arial', bold=True)
    cell.alignment = Alignment(horizontal='center')

# Data
data = [
    ['Lane A', 12, 1850],
    ['Lane B', 7, 2400],
    ['Lane C', 20, 1420],
    ['Lane D', 4, 3100],
]

# Populate data and row formulas
for row_idx, (lane, loads, avg_rev) in enumerate(data, 2):
    ws.cell(row=row_idx, column=1, value=lane).font = arial_font
    ws.cell(row=row_idx, column=2, value=loads).font = arial_font
    ws.cell(row=row_idx, column=3, value=avg_rev).font = arial_font
    # Total Revenue formula: Loads * Avg Revenue
    ws.cell(row=row_idx, column=4, value=f'=B{row_idx}*C{row_idx}').font = arial_font

# Totals Row (Row 6)
ws.cell(row=6, column=1, value='Totals').font = Font(name='Arial', bold=True)
ws.cell(row=6, column=2, value='=SUM(B2:B5)').font = Font(name='Arial', bold=True)
ws.cell(row=6, column=4, value='=SUM(D2:D5)').font = Font(name='Arial', bold=True)

# Weighted Average Formula (Cell E6)
ws.cell(row=6, column=5, value='=D6/B6').font = Font(name='Arial', bold=True)

# Apply Arial to all used cells
for row in ws.iter_rows():
    for cell in row:
        if not cell.font.name: # avoid overwriting bold headers
            cell.font = arial_font

# Save file
wb.save('shipment_data.xlsx')