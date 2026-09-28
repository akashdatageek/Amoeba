import openpyxl
from openpyxl.styles import Font

# Data
price_per_gallon = 6.4709
source = "AAA Fuel Prices (https://gasprices.aaa.com)"
mpg = 6.5
legs = [
    ("Chicago–Indianapolis", 185),
    ("Indianapolis–Columbus", 175),
    ("Columbus–Pittsburgh", 185),
]

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Fuel Costs"

# Professional font
font_arial = Font(name='Arial')

# Headers
headers = ["Leg", "Distance (mi)", "Gallons", "Cost ($")]
for col_num, header in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col_num, value=header)
    cell.font = font_arial

# Diesel Price and Source (Reference cells)
ws['F1'] = "Diesel Price/Gal"
ws['F1'].font = font_arial
ws['F2'] = price_per_gallon
ws['F2'].font = font_arial
ws['F3'] = f"Source: {source}"
ws['F3'].font = font_arial

# MPG Reference
ws['F4'] = "Fuel Efficiency (mpg)"
ws['F4'].font = font_arial
ws['F5'] = mpg
ws['F5'].font = font_arial

# Data rows
for row_num, (leg, dist) in enumerate(legs, 2):
    ws.cell(row=row_num, column=1, value=leg).font = font_arial
    ws.cell(row=row_num, column=2, value=dist).font = font_arial
    
    # Gallons = Distance / MPG
    # Reference F5 for MPG
    ws.cell(row=row_num, column=3, value=f"=B{row_num}/$F$5").font = font_arial
    
    # Cost = Gallons * Price
    # Reference C{row_num} for Gallons and F2 for Price
    ws.cell(row=row_num, column=4, value=f"=C{row_num}*$F$2").font = font_arial

# Total row
total_row = len(legs) + 2
ws.cell(row=total_row, column=1, value="Total").font = font_arial
ws.cell(row=total_row, column=2, value=f"=SUM(B2:B{total_row-1})").font = font_arial
ws.cell(row=total_row, column=3, value=f"=SUM(C2:C{total_row-1})").font = font_arial
ws.cell(row=total_row, column=4, value=f"=SUM(D2:D{total_row-1})").font = font_arial

wb.save("fuel_costs.xlsx")
