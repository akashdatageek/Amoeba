Verdict: FAIL
# QA memo: prices.xlsx and totals.png

## Re-checks I ran
1. I reloaded prices.xlsx with openpyxl (data_only=False). It has one sheet, 'Prices', with dimensions A1:D7 [S8].
2. I used calc to compute 10*1.5 = 15, 4*3.25 = 13 and 100*0.02 = 2. The sum is 15 + 13 + 2 = 30.
3. I read the totals.png header with struct. The PNG signature check was True and the size is 800 x 500 px. I also decoded the pixels with matplotlib and numpy and measured the bars, giving shape (500, 800, 4) [S8].
4. I listed the workspace. prices.xlsx, totals.png, build_xlsx.py and make_chart.py are present [S7].

The R1-R8 list was not passed to me. I mapped it from the task and the settled interpretation: pads = notepads or writing pads, clips = paper clips, and the grand total is one row with SUM.

## Requirement table

| Req | Requirement | Verdict | Evidence |
|---|---|---|---|
| R1 | prices.xlsx has headers Item, Qty, Unit price, Total in A1:D1 | PASS | A1 'Item', B1 'Qty', C1 'Unit price', D1 'Total' [S8]. |
| R2 | Item data is Pens 10 x 1.50, Pads (notepads) 4 x 3.25, Clips (paper clips) 100 x 0.02 | PASS | A2:C2 = Pens, 10, 1.5. A3:C3 = Pads, 4, 3.25. A4:C4 = Clips, 100, 0.02 [S8]. Nothing contradicts the notepads or paper clips reading. |
| R3 | Each item Total is a live formula, Qty x Unit price | PASS | D2 '=B2*C2', D3 '=B3*C3', D4 '=B4*C4'. They are formula strings, not typed values [S8]. |
| R4 | One Grand total row below the items, with SUM in the Total column | PASS | A5 'Grand total'. D5 '=SUM(D2:D4)', which covers exactly the three items [S8]. |
| R5 | Numbers are right: 15, 13, 2, grand total 30 | PASS (arithmetic and formula text only) | calc gave 15, 13, 2 and a sum of 30. The formulas point at the right cells. No spreadsheet-engine recalc was run (see Limitations), so the file holds no cached values. |
| R6 | totals.png exists, is a valid PNG, at least 600x400 px | PASS | Signature True. Size 800 x 500 px. File is 14442 bytes [S4][S8]. |
| R7 | Chart has three bars (Pens 15, Pads 13, Clips 2) and no grand-total (30) bar | PASS for bar count and proportions, NOT VERIFIED for text labels | Pixel analysis found exactly three bar colours in separate x-ranges. Blue spans x 95-282, y 89-439. Orange spans x 330-517, y 136-439. Green spans x 565-751, y 395-439 [S8]. Heights are about 350, 303 and 44 px, close to 15:13:2. There is no fourth or taller bar, so no grand-total bar. I did not view the image, so the Pens/Pads/Clips tick labels and value labels are not confirmed. They rest on make_chart.py and its printed values {'Pens': 15.0, 'Pads': 13.0, 'Clips': 2.0} [S4]. |
| R8 | Build followed the planned layout: header, three items, Grand total row, no other rows | FAIL | A1:D5 matches the plan. A7 also holds the text "Note: Qty and Unit price values are as given in the task." [S3][S8]. The plan has no such row, and the role check requires no other rows. This is why the dimensions read A1:D7. |

## Defects
- **D1 (R8), prices.xlsx cell A7:** the extra note row is not in the planned layout. It changes no number. The builder added it only to satisfy a plain-code row check. Fix: clear A7, or if the note is wanted, have the plan accept it explicitly.
- **D2 (minor, not a requirement failure), prices.xlsx D2:D5:** there are no cached values, because the file was never recalculated. Excel and LibreOffice compute them on open. pandas or a previewer would show D2:D5 as empty. Fix: run recalc.py.

## Limitations
- I did not view totals.png. Its title, axis labels, tick labels (Pens, Pads, Clips) and value labels are NOT VERIFIED. Bar count and proportions come from pixel analysis.
- I ran no LibreOffice recalc, so I did not confirm in a spreadsheet engine that the formulas evaluate to 15, 13, 2 and 30. I checked the formula text and the arithmetic with calc.
- The task has no current-value figure, so no web check was needed.

VERDICT: FAIL. Defect D1: prices.xlsx cell A7 holds an extra note row, so R8 (no other rows) fails. All numbers (15, 13, 2, 30) and the three-bar chart are otherwise correct. The chart text labels are NOT VERIFIED.
BLOCKED: local:Read — could not view totals.png to confirm the title, axis labels, tick labels and value labels
BLOCKED: LibreOffice recalc (recalc.py) — could not confirm the formulas evaluate to 15, 13, 2 and 30 in a spreadsheet engine
MISSING INPUT: R1-R8 requirement list — not in my inputs; mapped from the task and the settled interpretation
Issues:
1. Step 1: prices.xlsx cell A7 holds an extra note row ('Note: Qty and Unit price values are as given in the task.') outside the planned layout of header, three items and Grand total row. Fix: clear A7 and re-save. No number changes.
2. Step 1: prices.xlsx has no cached values for D2:D5, because it was never recalculated. Fix: run recalc.py so previewers and pandas show 15, 13, 2 and 30.
3. Step 2: the text labels on totals.png (title, axis labels, tick labels, value labels) were not visually confirmed. Bar count and proportions were confirmed by pixel analysis, and the labels rest on make_chart.py.
