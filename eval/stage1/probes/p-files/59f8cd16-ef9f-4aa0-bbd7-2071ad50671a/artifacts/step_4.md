Verdict: PASS
# Memo: Hand-off Note

### Deliverables
- `prices.xlsx` (sheet Prices, columns Item, Qty, Unit price, Total, with live formulas for each Total and for the grand total); file size 5180 bytes [S2].
- `totals.png` (bar chart of the three item totals); file size 21344 bytes [S5], width 1050 px [S12].
- Supporting files: `build_prices.py` (Step 1) and `make_chart.py` (Step 2).

### Figures
| Item | Qty | Unit price | Total |
| :--- | :--- | :--- | :--- |
| pens | 10 | 1.50 | 15.00 [S5] |
| pads (writing pads) | 4 | 3.25 | 13.00 [S5] |
| clips (paper clips) | 100 | 0.02 | 2.00 [S5] |
| **Grand total** | | | **30.00** [unverified] |

### Verification
Verdict: PASS
Issues: none

The QA Reviewer verified that:
- The spreadsheet `prices.xlsx` has the correct headers, items, and live formulas for totals and the grand total [S12].
- The chart `totals.png` shows only the three per-item Total values (15.00 [S5], 13.00 [S5], 2.00 [S5]) with labelled categories and axes, and meets the size requirement of $\ge$ 600 px (1050 px wide [S10]).
- All formulas, computed numbers, and the chart agree with the given inputs [S12].
- The work was preceded by a build plan in Step 1 (R8) covering objectives, numbers, assumptions, risks, and checks.

No currency was specified, so no symbol is used.
Issues: none

## Limitations
- Mislabelled citation: step 1 cites S2 for '5', which S2 does not contain (added by plain code)
- Mislabelled citation: step 1 cites S2 for '0.00', which S2 does not contain (added by plain code)
- Mislabelled citation: step 2 cites S6 for '120', which S6 does not contain (added by plain code)
- Mislabelled citation: step 2 cites S6 for '840', which S6 does not contain; it is in S3, S4, S5 (added by plain code)
- Mislabelled citation: step 2 cites S6 for '600', which S6 does not contain (added by plain code)
- Mislabelled citation: step 2 cites S6 for '7', which S6 does not contain (added by plain code)
- Mislabelled citation: step 2 cites S6 for '4.5', which S6 does not contain (added by plain code)

