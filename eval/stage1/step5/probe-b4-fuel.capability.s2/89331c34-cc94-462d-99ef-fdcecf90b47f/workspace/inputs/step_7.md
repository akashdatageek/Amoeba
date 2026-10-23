Verdict: PASS
I read "weekly retail on-highway diesel price for Indiana" as EIA weekly Midwest (PADD 2) retail diesel price, used as a proxy because EIA publishes no Indiana-only weekly series; if you meant EIA weekly Indiana-specific retail diesel price, if such a series exists or EIA weekly Midwest regional price, with Indianapolis or a nearby metro as a cross-check or EIA weekly US national average diesel price, as the fallback, the answer below may not apply.

# Workbook and chart verification report (steps 3, 4, 5), checked 2026-10-23

VERDICT: PASS WITH FIXES. The tool field only accepts PASS or FAIL, so it is set to PASS. No computed number or conclusion changes. The fixes concern where parameters are stored, plus checks I could not finish.

## What I ran
- I opened fuel_surcharge_workbook.xlsx twice with openpyxl, once for formula text and once for cached values, and recomputed everything from weekly_prices.csv in Python with Decimal ROUND_HALF_UP [S104].
- Sheets found: Weekly, Inputs, Bands, Summary, Sources. Formula counts: Weekly 208, Inputs 2, Bands 160, Summary 17, Sources 0 [S100].
- Re-check against a source: the saved EIA dnav page (S1) shows 09/21 = 6.680 and 07/13 = 4.659. The 6.68 matches the workbook's highest price [S16].
- I could not re-fetch EIA or ATRI live because there is no network.

## Table of checks (expected vs actual)
| # | Check | Expected | Actual | Status |
|---|---|---|---|---|
| 1 | Weekly rows | 52 data rows | 52 [S104] | OK |
| 2 | Weekly C:F are formulas | all 52 rows | 0 non-formula rows [S104] | OK |
| 3 | Weekly formula text | surcharge ROUND((B-base)/mpg,2); fleet cost price x gallons; fuel $/mi price/mpg; gallons from Inputs | C2 =ROUND((B2-Inputs!$B$4)/Inputs!$B$5,2); E2 =B2*D2; F2 =B2/Inputs!$B$5; D2 =Inputs!$B$9 [S104] | OK |
| 4 | Date, price, surcharge, fleet cost and fuel $/mi vs my Decimal recompute (gallons = 80,500/6.2 = 12,983.871) | 0 mismatches (tolerance 0.0005 price, 0.0001 surcharge and $/mi, $0.01 cost) | 0 mismatches in 52 rows [S63] | OK |
| 5 | 40 band midpoints and surcharges | midpoint 3.025 + 0.05i; surcharge ROUND((mid-1.25)/6.2,2) | 0 of 40 mismatched; formulas =ROUND((D2-Inputs!$B$4)/Inputs!$B$5,2) [S104] | OK |
| 6 | Summary average price | 4.78738 | 4.78738461538462 [S104] | OK |
| 7 | Summary average surcharge | 0.57077 | 0.570769230769231 [S104] | OK |
| 8 | Highest and lowest price | 6.68 (2026-09-21) and 3.365 (2026-01-12) | 6.68 and 3.365; the weeks match the Decimal recompute [S104] | OK |
| 9 | 52-week total fleet cost | 3,232,256.77 | recompute 3232256.77419; modeler's table 3,232,256.77 [S104][S94] | OK |
| 10 | Average weekly fleet cost | 62,158.78 | 62158.78412 [S104] | OK |
| 11 | Average fuel $/mi | 0.77216 | 0.77216; modeler 0.7722 [S104][S94] | OK |
| 12 | ATRI fuel derivation, share and gap | 2.336-1.854 = 0.482; share 20.6%; gap 0.77216-0.482 = 0.2902 (60.2%) | Summary B17/B18/B19/B20 formulas match modeler's 0.482, 20.6%, 0.2902, 60.2% [S92][S104] | OK. Derived, and flagged as a substitute |
| 13 | Modeler's stats table vs recompute | all equal | all equal at the stated rounding [S94][S104] | OK |
| 14 | Hard-coded parameters only on Inputs | Inputs B4:B7 only | Inputs B4=1.25, B5=6.2, B6=35, B7=2300, each with a "Basis" note [S103]. Band grid start (Bands H1) and width 0.05 (Bands H2) are typed on the Bands sheet. ATRI 2.336 and 1.854 are typed on Sources B21/B22, with source and date [S104][S92] | FIX (labelling and location only) |
| 15 | PNG width | at least 1200 px | 2400 x 1360 [S104] | OK |
| 16 | PNG points per line | 52 | The plotting script prints len of both lines' x data; the modeler reported 52 per line [S94]. I did not see my own output of that print | Not independently confirmed |
| 17 | Axis titles and legend | present | grep of step5.py shows ax2.set_ylabel('Fuel surcharge ($ per mile)') and ax.legend(handles=[l1,l2]) [S104]. The modeler reports titled axes and a legend [S94] | Partly confirmed. I did not open the image |

## Required corrections
1. Hard-coded parameters outside Inputs. Move the band grid start (3.00) and width (0.05) from Bands H1/H2 to Inputs and point Bands B2 and C2 at them. Alternatively, rewrite the Inputs note "Yellow cells are the only hard-coded parameters" so that it names the Bands and Sources inputs too. No values change.
2. Bands column A holds typed integers 1 to 40 as labels. This is acceptable as labels, but the assumptions note should say so.
3. ATRI figures. Keep the "substitute / derived" label on Summary B17 and B18. Say in the memo that the full ATRI PDF was not read. Cite the ATRI press release (S35), not the third-party page S34 [S103].
4. Chart. Before the memo embeds it, confirm by looking at the PNG that both lines show 52 points, that the left, right and x axes are titled, and that the legend lists both lines. Units must be $/gal and $/mi.
5. The memo must say that prices above $5.00 (up to 6.68, latest 6.352) lie outside the $3.00 to $5.00 band table [S92].

## Not confirmed
- Raw output of the hard-coded numeric scan on Weekly, Bands and Summary was cut off in my view [S104]. Only Bands H1/H2 and Sources B21/B22 are known to hold typed values.
- Sources sheet text, beyond the two ATRI rows, was not read in full.
- No live re-fetch of EIA or ATRI was possible. I checked against saved pages from 2026-10-23.
BLOCKED: network/live fetch — EIA and ATRI could not be re-fetched live; checks used saved sources
BLOCKED: image inspection — PNG point count, axis titles and legend not verified by viewing the image
MISSING DATA: Full output of hard-coded numeric constant scan — result was cut in the tool output [S104]
MISSING DATA: Full Sources sheet text — only ATRI rows B21/B22 seen
Issues:
1. Step 3 (Bands sheet): band grid start 3.00 (H1) and width 0.05 (H2) are typed on Bands, not on Inputs, while Inputs says its cells are the only hard-coded parameters. Fix: move them to Inputs and reference them, or reword the note. No numbers change.
2. Step 4 (Summary/Sources): ATRI fuel $0.482/mi and the 20.6% share are derived (2.336 - 1.854), not published. Keep the substitute label, state the full PDF was not read, cite S35 not S34.
3. Step 5 (chart): 52 points per line, axis titles and legend rest on the modeler's report and a script grep, not on viewing the PNG. Confirm visually before embedding in the memo.
4. Step 5/memo: prices above $5.00 (high 6.68, latest 6.352) fall outside the 40-band table; the memo must say so.