import openpyxl
from openpyxl.styles import Font, NumberFormat

# Data
legs = [
    ("Chicago to Indianapolis", 185),
    ("Indianapolis to Columbus", 175),
    ("Columbus to Pittsburgh", 185)
]
mpg = 6.5
diesel_price = 6.4709
source = "Source: AAA National Average (https://gasprices.aaa.com), Price as of 9/27/26"

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Fuel Costs"

# Professional Font
arial_font = Font(name='Arial')

# Headers
headers = ["Leg", "Distance (mi)", "Gallons", "Cost"]
for col, header in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col, value=header)
    cell.font = arial_font

# Trip Legs
for row_idx, (leg_name, distance) in enumerate(legs, 2):
    ws.cell(row=row_idx, column=1, value=leg_name).font = arial_font
    ws.cell(row=row_idx, column=2, value=distance).font = arial_font
    
    # Gallons = Distance / MPG
    # We will put MPG in cell B6
    ws.cell(row=row_idx, column=3, value=f"=B{row_idx}/$B$6").font = arial_font
    
    # Cost = Gallons * Price
    # We will put Price in cell B5
    ws.cell(row=row_idx, column=4, value=f"=C{row_idx}*$B$5").font = arial_font

# Total Row
total_row = len(legs) + 2
ws.cell(row=total_row, column=1, value="Total").font = arial_font
ws.cell(row=total_row, column=2, value=f"=SUM(B2:B{total_row-1})").font = arial_font
ws.cell(row=total_row, column=3, value=f"=SUM(C2:C{total_row-1})").font = arial_font
ws.cell(row=total_row, column=4, value=f"=SUM(D2:D{total_row-1})").font = arial_font

# Inputs and Source
ws.cell(row=5, column=1, value="Diesel Price:").font = arial_font
ws.cell(row=5, column=2, value=diesel_price).font = arial_font
ws.cell(row=5, column=2).number_format = '"$"#,##0.0000'

ws.cell(row=6, column=1, value="Fuel Efficiency (MPG):").font = arial_font
ws.cell(row=6, column=2, value=mpg).font = arial_font

ws.cell(row=7, column=1, value=source).font = arial_font

# Formatting Costs as Currency
for row in range(2, total_row + 1):
    ws.cell(row=row, column=4).number_format = '"$"#,##0.00'

# Formatting Gallons to 2 decimal places
for row in range(2, total_row + 1):
    ws.cell(row=row, column=3).number_format = '0.00'

wb.save("fuel_costs.xlsx")