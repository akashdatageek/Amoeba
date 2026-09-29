import openpyxl
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.workbook.defined_name import DefinedName

# Create workbook and sheet
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Fuel Costs"

# 1. Inputs
ws['A1'] = "Diesel Price (per gallon):"
ws['B1'] = 6.529
ws['A2'] = "Fuel Efficiency (mpg):"
ws['B2'] = 6.5

# Create Named Ranges
# Note: DefinedName requires the sheet name in the destination
price_range = DefinedName('Diesel_Price', attr_text='"Fuel Costs"!$B$1')
eff_range = DefinedName('Fuel_Efficiency', attr_text='"Fuel Costs"!$B$2')
wb.defined_names.append(price_range)
wb.defined_names.append(eff_range)

# 2. Table Headers
headers = ["Leg", "Distance (miles)", "Gallons", "Cost"]
for col_num, header in enumerate(headers, 1):
    cell = ws.cell(row=4, column=col_num)
    cell.value = header
    cell.font = Font(name='Arial', bold=True)
    cell.alignment = Alignment(horizontal='center')

# 3. Data Rows
legs = [
    ("Chicago–Indianapolis", 185),
    ("Indianapolis–Columbus", 175),
    ("Columbus–Pittsburgh", 185),
]

for row_idx, (leg_name, dist) in enumerate(legs, 5):
    ws.cell(row=row_idx, column=1).value = leg_name
    ws.cell(row=row_idx, column=2).value = dist
    # Gallons = Distance / Fuel_Efficiency
    ws.cell(row=row_idx, column=3).value = f"=B{row_idx}/Fuel_Efficiency"
    # Cost = Gallons * Diesel_Price
    ws.cell(row=row_idx, column=4).value = f"=C{row_idx}*Diesel_Price"

# 4. Total Row
total_row = 8
ws.cell(row=total_row, column=1).value = "Total"
ws.cell(row=total_row, column=1).font = Font(name='Arial', bold=True)
ws.cell(row=total_row, column=2).value = f"=SUM(B5:B7)"
ws.cell(row=total_row, column=3).value = f"=SUM(C5:C7)"
ws.cell(row=total_row, column=4).value = f"=SUM(D5:D7)"

# 5. Formatting
# Font Arial throughout
for row in ws.iter_rows():
    for cell in row:
        cell.font = Font(name='Arial')

# Input highlighting (Light Yellow)
yellow_fill = PatternFill(start_color='FFFFE0', end_color='FFFFE0', fill_type='solid')
ws['B1'].fill = yellow_fill
ws['B2'].fill = yellow_fill

# Currency formatting for Cost column
for row in range(5, total_row + 1):
    ws.cell(row=row, column=4).number_format = '$#,##0.00'

# Borders for the table
thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                    top=Side(style='thin'), bottom=Side(style='thin'))
for row in range(4, total_row + 1):
    for col in range(1, 5):
        ws.cell(row=row, column=col).border = thin_border

# 6. Citation
ws['A11'] = "Source: U.S. Energy Information Administration (EIA), Gasoline and Diesel Fuel Update, 09/21/26, https://www.eia.gov/petroleum/gasdiesel/"

# Column Widths
ws.column_dimensions['A'].width = 25
ws.column_dimensions['B'].width = 18
ws.column_dimensions['C'].width = 12
ws.column_dimensions['D'].width = 12

wb.save('fuel_costs.xlsx')
