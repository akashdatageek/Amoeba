I read "weekly retail on-highway diesel price for Indiana" as An EIA Indiana state-level weekly series, if one exists; if you meant The EIA Midwest (PADD 2) weekly all-types diesel price as the nearest available series or The EIA U.S. national weekly average diesel price, the answer below may not apply. I read "5-cent price band from $3.00 to $5.00" as Bands run in 5-cent steps ($3.00, $3.05 ... $5.00), each giving the surcharge at that price; if you meant Ranges such as $3.00–$3.04, with the surcharge computed at the low end or midpoint, the answer below may not apply.

**Step 5 status: NOT COMPLETE. `fuel_surcharge_workbook.xlsx` was not created.**

**File listing:** none. No file was written or run in this step. There is no readback of formulas or values and no recalculation result. Because no workbook exists, there are no cached values, and none can be claimed.

**Build script (code, NOT RUN, NOT TESTED).** It is a plan for the rerun. It reads the 52 prices from a `prices` list that step 3 must supply, and it invents no price.

```python
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.styles import Font
# prices = [(date, price, series_id, url), ...]  # 52 rows, MUST come from step 3 / EIA
wb = Workbook(); F = Font(name="Arial")
inp = wb.active; inp.title = "Inputs"
rows = [("Base price ($/gal)",1.25,"base"),("Fuel economy (mpg)",6.2,"mpg"),
        ("Tractors",35,"trucks"),("Miles per truck per week",2300,"miles_wk")]
for i,(l,v,n) in enumerate(rows,1):
    inp.cell(i,1,l); inp.cell(i,2,v)
    wb.defined_names[n] = DefinedName(n, attr_text=f"Inputs!$B${i}")
inp["A5"]="Fleet miles per week"; inp["B5"]="=trucks*miles_wk"
inp["A6"]="Fleet gallons per week"; inp["B6"]="=B5/mpg"
for n,c in (("fleet_miles","B5"),("fleet_gal","B6")):
    wb.defined_names[n] = DefinedName(n, attr_text=f"Inputs!${c[0]}${c[1]}")
w = wb.create_sheet("Weekly")
w.append(["Week date","Price ($/gal)","Series ID","Source URL","Surcharge ($/mi)",
          "Gallons","Fuel cost ($)","Fuel cost per mile ($)"])
for r,(d,p,s,u) in enumerate(prices,2):
    w.append([d,p,s,u,f"=ROUND((B{r}-base)/mpg,2)","=fleet_gal",f"=F{r}*B{r}",f"=B{r}/mpg"])
b = wb.create_sheet("Bands"); b.append(["Price ($/gal)","Surcharge ($/mi)"])
for k in range(41):
    r = k+2
    b.append([3.00 if k==0 else f"=A{r-1}+0.05", f"=ROUND((A{r}-base)/mpg,2)"])
# Summary: AVERAGE/MAX/MIN of Weekly!B2:B53, INDEX/MATCH for the high and low weeks,
# SUM(Weekly!G2:G53), total cost / (52*fleet_miles), ATRI fuel per mile and share, difference.
# Notes: source and date of every figure. wb.save("fuel_surcharge_workbook.xlsx")
```

Then run headless LibreOffice recalculation (`scripts/recalc.py`), read the cells back, and compare them with a Decimal ROUND_HALF_UP recomputation.

**done_when is not met:**
- The xlsx was not created, so it was not opened with openpyxl.
- No surcharge, fuel cost or statistics formulas were written for 52 weekly rows or 41 bands.
- No recalculation was run. If the workbook is built later without a recalculation, values appear only when it is opened in Excel.

**MISSING DATA:** the 52 weekly EIA diesel prices (week dates, prices, series ID, source URL) — step 3 returned status "incomplete" with no content, and the fetched files in `sources/` ([S1], [S2], [S3], [S6], [S7]) are not EIA price data. Whether an Indiana state series exists, or the Midwest proxy must be used, is not established. No price was invented.

**BLOCKED / NOT NEEDED:**
- BLOCKED: Bash — the build script, the LibreOffice recalculation and the Decimal half-up cross-check could not be run.
- BLOCKED: local:Write — the workbook, `series_note.md` and `atri.md` could not be written. Step 4 also did not write `atri.md`.
- BLOCKED: Edit — nothing to edit, since no file exists.

**Inputs ready for the Inputs and Summary sheets:**
- From the task: base price $1.25, 6.2 mpg, 35 tractors, 2,300 miles per truck per week.
- Fleet miles per week: 35 × 2,300 = 80,500.
- Fleet gallons per week: 80,500 ÷ 6.2 = 12,983.87.
- ATRI total average marginal cost: $2.336 per mile, data year 2025, "2026 Update" edition, released July 2026 (exact day not seen) [S2], [S4]. These come from step 4, which read search snippets only.
- ATRI fuel cost per mile: $0.482 [S1], [S5]. This comes from a TRID summary snippet, not from the ATRI report itself, and must be labelled that way.
- Fuel share: 0.482 ÷ 2.336 = 0.2063, which is 20.63% (hand calculation).
- Bands: 41 price points, $3.00 to $5.00 in $0.05 steps. Check: (5.00 − 3.00) ÷ 0.05 + 1 = 41.
- Difference from ATRI and the counts of weeks above $5.00 and below $3.00: not computable until the weekly prices exist.

**Rerun needs:** (1) the 52 prices with dates, series ID and URL from step 3; (2) a turn with Bash and Write available to run the script, recalculate, and compare; (3) afterwards the chart `price_surcharge_chart.png` and `summary.json`.
