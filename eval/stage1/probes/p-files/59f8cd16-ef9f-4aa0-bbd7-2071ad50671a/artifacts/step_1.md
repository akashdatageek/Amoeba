BUILD PLAN
- Objective: build prices.xlsx with one sheet 'Prices'. Headers are Item, Qty, Unit price, Total. It has three item rows, live Total formulas and a live grand-total formula. totals.png comes in a later step.
- Numbers: pens 10 x 1.50 = 15, pads 4 x 3.25 = 13, clips 100 x 0.02 = 2, grand total 15 + 13 + 2 = 30. These are my own calculation from the task inputs.
- Assumptions: no currency symbol. The sheet is named 'Prices'. Qty and Unit price are numeric. Number format is 0.00 on columns C and D.
- Risks: openpyxl caches no formula values, so viewers that read cached values show blanks until Excel recalculates on open. I did not run a LibreOffice recalc, so this is untested. The formulas must stay strings starting with '='.
- Checks: reload prices.xlsx with openpyxl and print the cells. Confirm the four exact headers, D2:D4 = B*C and D5 = SUM(D2:D4).

CODE (build_prices.py, run with python3)
```python
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
wb = Workbook()
ws = wb.active
ws.title = "Prices"
ws.append(["Item", "Qty", "Unit price", "Total"])
rows = [("pens", 10, 1.50), ("pads", 4, 3.25), ("clips", 100, 0.02)]
for i, (n, q, p) in enumerate(rows, start=2):
    ws.append([n, q, p, f"=B{i}*C{i}"])
ws["A5"] = "Grand total"
ws["D5"] = "=SUM(D2:D4)"
for r in range(2, 6):
    ws[f"C{r}"].number_format = "0.00"
    ws[f"D{r}"].number_format = "0.00"
for c in ws[1]: c.font = Font(bold=True)
for c in ws[5]: c.font = Font(bold=True)
for col, w in zip("ABCD", (16, 8, 12, 12)):
    ws.column_dimensions[col].width = w
wb.save("prices.xlsx")
# a second pass added the note in A6 (italic): "Note: Qty and Unit price are as given in the task; no currency symbol."
wb2 = load_workbook("prices.xlsx"); s = wb2["Prices"]
for row in s.iter_rows():
    print([c.coordinate + "=" + repr(c.value) for c in row])
```

SAVED CELL CONTENTS of prices.xlsx (reloaded, sheet 'Prices') [S2]
- Row 1: A1='Item', B1='Qty', C1='Unit price', D1='Total'
- Row 2: A2='pens', B2=10, C2=1.5, D2='=B2*C2'
- Row 3: A3='pads', B3=4, C3=3.25, D3='=B3*C3'
- Row 4: A4='clips', B4=100, C4=0.02, D4='=B4*C4'
- Row 5: A5='Grand total', B5 and C5 empty, D5='=SUM(D2:D4)'
- Row 6: A6='Note: Qty and Unit price are as given in the task; no currency symbol.' This is a note row, not a data row.
- Check printed "formulas ok: True": D2 to D5 are all strings starting with '=' [S2]. The file prices.xlsx is 5180 bytes [S2].
- Formatting: header row and row 5 are bold, C and D use 0.00, columns A to D are widened. This is set in the script above. The size and formula checks were confirmed by reload [S2]; the formatting was not re-read.

NOT CONFIRMED: computed values of the formulas (15, 13, 2, 30). No recalculation was run, so no cached values exist in the file. The values are my own arithmetic from the task inputs.
