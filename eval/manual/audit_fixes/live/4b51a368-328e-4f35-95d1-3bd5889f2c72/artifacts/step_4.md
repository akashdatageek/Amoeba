I read "weekly retail on-highway diesel price for Indiana" as EIA weekly retail on-highway diesel prices, all types, for the Midwest PADD 2 region, used as a proxy for Indiana; if you meant A true Indiana state-level EIA weekly series, if one exists or Indianapolis city or Midwest regional price used in place of the state, the answer below may not apply. I read "each 5-cent price band from $3.00 to $5.00" as Bands such as $3.00–3.049, $3.05–3.099, and so on up to $5.00, with the surcharge computed at the band's price; if you meant Bands stepping from $3.00 by $0.05 to $5.00 as 41 price points, with the surcharge at each point, the answer below may not apply.

**Step 4 result: fuel_cost_workbook.xlsx built, patched, recalculated and re-opened**

**Code.** Two scripts in the workspace produced the file.
1. `build_workbook.py` reads inputs.json and eia_prices.csv and writes the five sheets [S46]. It ran, and LibreOffice recalculation reported success with 0 errors [S47]. I cannot reprint its full text here because I did not keep a copy of it in this step.
2. `patch_workbook.py` fixes the defects that plain code flagged. Its full text:
```python
from openpyxl import load_workbook
from openpyxl.styles import Font
wb=load_workbook('fuel_cost_workbook.xlsx')
S=wb['Summary']; I=wb['Inputs']
r=I.max_row+2
I.cell(r,1,'ATRI inputs (typed once; Summary links here)').font=Font(name='Arial',bold=True)
r+=1
for row in range(1,S.max_row+1):
    c=S.cell(row,2)
    if isinstance(c.value,(int,float)) and not isinstance(c.value,bool):
        lab=S.cell(row,1).value
        I.cell(r,1,lab); x=I.cell(r,2,c.value); x.font=Font(name='Arial',color='0000FF')
        I.cell(r,3,'ATRI Operational Costs of Trucking 2026 Update (cost year 2025), released 15 July 2026; https://truckingresearch.org/about-atri/atri-research/operational-costs-of-trucking')
        c.value='=Inputs!$B$%d'%r; r+=1
wb.move_sheet('Weekly',offset=-wb.sheetnames.index('Weekly'))
wb.active=0
for ws in wb: ws.sheet_view.tabSelected=(ws.title=='Weekly')
wb.save('fuel_cost_workbook.xlsx')
```
Re-running recalc.py after the patch gave status success, 0 errors and 357 formulas [S50].

**Fixes to the defects plain code listed**
- Typed ATRI total in Summary: the typed 2.336 and 0.482 now sit once in the Inputs sheet (rows 16 and 17, blue font, source note beside each). Summary!B16 is `=Inputs!$B$16` and returns 2.336. Summary!B17 is `=Inputs!$B$17` and returns 0.482 [S50]. The ATRI values are source figures, not calculated, so they have to be typed once. Their source is the ATRI "Operational Costs of Trucking" 2026 Update (cost year 2025), released 15 July 2026 [S36][S30].
- Header check: the Weekly sheet is now the first sheet. Its header row reads week_date, price, surcharge_per_mile, fleet_gallons, fleet_fuel_cost, fuel_cost_per_mile [S50]. Sheet order is Weekly, Inputs, Bands, Summary, Sources [S50].
- Untagged figures: the earlier "54, 55, 42, 42" were sheet row numbers (the totals row, the note rows and the last band row), not data. Weekly data sit in rows 2–53, the totals row is row 54, and Bands rows 2–42 hold 41 bands [S48]. The "$6.25" and "$3.6" figures are EIA prices: $6.250 for week 2026-09-14 and $3.731, $3.670, $3.606 for the first weeks of the window [S27].

**Sheets**
- Inputs: named cells Tractors, MilesPerWeek, MPG, BasePrice, BandStart, BandStep, plus the ATRI inputs block. Also FleetMilesWeek and Weeks are used by the Summary formulas [S50]. I did not see the cell addresses of every name.
- Weekly: 52 data rows, 2025-09-29 to 2026-09-21, EIA series EMD_EPD2D_PTE_R20_DPG (prices typed from eia_prices.csv [S27]).
  - Surcharge: `=ROUND((B2-BasePrice)/MPG,2)`.
  - Gallons: `=Tractors*MilesPerWeek/MPG`.
  - Fleet cost: `=D2*B2`.
  - Cost per mile: `=B/MPG`.
  - No constants inside these formulas [S50][S48].
  - Row 54 (TOTAL / AVERAGE): average price 4.5787, average surcharge 0.5371, gallons 675,161.29, fleet cost $3,091,355.81, average cost per mile 0.7385 [S48].
- Bands: 41 rows by formula, first label "$3.00-3.049", last "$5.00 and above". Surcharges: $3.00 → 0.28, $3.05 → 0.29, $5.00 → 0.60 [S48][S49].
- Summary (formula → recalculated value) [S50]:
  - count of weeks 52; first week 2025-09-29; last week 2026-09-21
  - average price 4.57869 (AVERAGE)
  - highest price 6.68 in the week of 2026-09-21 (MAX with INDEX/MATCH)
  - lowest price 3.365 in the week of 2026-01-12 (MIN with INDEX/MATCH)
  - surcharge: average 0.537115, highest 0.88, lowest 0.34
  - annual gallons 675,161.29; annual fleet fuel cost $3,091,355.81
  - average fuel cost per mile 0.738499 (annual cost ÷ (FleetMilesWeek × Weeks))
  - ATRI total 2.336; ATRI fuel 0.482; fuel share 0.482 ÷ 2.336 = 20.63%
  - carrier minus ATRI fuel per mile = 0.256499; carrier ÷ ATRI fuel = 1.532; carrier fuel ÷ ATRI total = 0.3161
- Sources: series ID, URL, retrieved date (2026-10-16), ATRI edition and URL. Its presence is confirmed [S49]; I did not reprint its cells.

**Caveats for later steps**
- The ATRI comparison is not like-for-like. ATRI uses its own survey diesel price and mpg for cost year 2025; the carrier figure uses Midwest PADD 2 prices and 6.2 mpg. The workbook carries the note "Comparison only; ATRI total includes non-fuel costs".
- The window ends 2026-09-21. That is the last week on the saved EIA page, released 9/22/2026 (Step 2). Newer releases were not fetched, so the window may be 2–3 weeks stale against today, 2026-10-16.
- The 2026 prices ($6.250 and $6.680 [S27]) are far above the 2025 level ($3.731 at the start of the window [S27]). They are not cross-checked against a second source.
- No Indiana state series was found on the pages read, and no dedicated search was run, so "no Indiana series" is unconfirmed.
- The checks are LibreOffice recalculation only (0 errors [S50]). I did not open the file in Excel.

**File:** fuel_cost_workbook.xlsx in the workspace, with `build_workbook.py` and `patch_workbook.py` [S49][S50].
BLOCKED: web fetch — newer EIA weekly releases (after 2026-09-21) were not fetched in the earlier research step, so the 52-week window may be stale
MISSING DATA: Latest published EIA weekly price after 2026-09-21 — saved EIA page released 9/22/2026; newer releases not fetched
MISSING DATA: Indiana state-level weekly EIA diesel series — not seen on pages read; no dedicated search run; Midwest PADD 2 used instead
MISSING DATA: Full text of build_workbook.py — not reprinted in this step; the file is in the workspace
