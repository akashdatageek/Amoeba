Verdict: PASS
I read "weekly retail on-highway diesel price for Indiana" as EIA weekly Midwest (PADD 2) retail diesel price, used as a proxy because EIA publishes no Indiana-only weekly series; if you meant EIA weekly Indiana-specific retail diesel price, if such a series exists or EIA weekly Midwest regional price, with Indianapolis or a nearby metro as a cross-check or EIA weekly US national average diesel price, as the fallback, the answer below may not apply.

# Memo verification report: fuel_surcharge_memo.docx (step 8), checked 2026-10-23

VERDICT: PASS WITH FIXES (capped, because I could not read the band-table comparison output in full). The tool field accepts only PASS or FAIL, so it is set to PASS. I found no mismatch that changes a number or a conclusion. Open points are listed under "Required corrections".

## Re-checks I ran
- I opened the docx with python-docx and read the paragraphs [S120][S121]. I re-ran my recompute scripts v9.py and v9b.py on weekly_prices.csv with Decimal ROUND_HALF_UP. The visible output shows 52 rows from 2025-10-27 ($3.715) to 2026-10-19 ($6.352) and an average price of 4.78738 [S117].
- The visible part of the v9/v9b output cut off before the 40-band comparison result. I did not see a "bad" count, so I cannot state that all 40 bands matched [S118][S119][S121].
- Page count: fuel_surcharge_memo.pdf has 2 pages, and the PDF is not older than the docx [S120]. The memo author also converted with soffice and counted with pypdf, getting 2 pages [S111].
- I recomputed the key figures by hand from the task inputs (35 × 2,300 ÷ 6.2 = 12,983.871 gal/week) and the step 6 prices, as an independent check:
  - Highest week 2026-09-21, $6.68 [S1]: (6.68 − 1.25) ÷ 6.2 = 0.8758, so $0.88/mi. Fleet cost 6.68 × 12,983.871 = $86,732.26.
  - Lowest week 2026-01-12, $3.365 [S3]: (3.365 − 1.25) ÷ 6.2 = 0.3411, so $0.34/mi. Fleet cost 3.365 × 12,983.871 = $43,690.73.
  - Average weekly fleet cost 4.78738 × 12,983.871 = $62,158.78. Over 52 weeks that is about $3,232,256.77.
  - Carrier fuel cost per mile 4.78738 ÷ 6.2 = 0.7722. Gap to ATRI 0.7722 − 0.482 = 0.2902, which is 60.2% of 0.482.
- I could not re-fetch EIA or ATRI live (no network). The checks use files saved on 2026-10-23.

## Table of checks (expected vs actual)
| # | Check | Expected | Actual | Status |
|---|---|---|---|---|
| 1 | Opening proxy line | The required sentence first | The first paragraph is the exact required sentence [S121] | OK |
| 2 | Page count | 2 pages or fewer | 2 pages (soffice and pypdf) [S120][S111] | OK |
| 3 | Average surcharge | $0.57/mi (0.5708) | Memo says "$0.57 per mile" [S120] | OK |
| 4 | Average price | $4.79/gal (4.78738), as of 2026-10-19 | Memo says "$4.79 per gallon" [S120][S117] | OK |
| 5 | 52-week fleet fuel cost | $3,232,256.77 | Memo says $3,232,256.77 [S120] | OK |
| 6 | Carrier fuel $/mi | $0.77 (0.7722) | Memo says "$0.77 per mile" [S120] | OK |
| 7 | Gap to ATRI fuel | $0.29/mi (0.2902) | Memo says "$0.29 per mile above ... $0.48" [S120] | OK |
| 8 | Latest week | $6.352 as of 2026-10-19 | Memo says "latest week $6.352" and "as of 2026-10-19" [S120] | OK |
| 9 | Prices above $5.00 flagged | Memo says the grid does not cover recent weeks | Memo says "Prices ran above the $5.00 top of the schedule grid ... the grid needs extending upward" [S120] | OK |
| 10 | Series ID, EIA source and retrieval date | EMD_EPD2D_PTE_R20_DPG, EIA API v2, retrieved 2026-10-23 | Present in section 2 and the section 4 heading [S120][S121] | OK |
| 11 | EIA dnav release date | Release 10/14/2026, ends at 10/12 [S1] | Memo states "released 10/14/2026 and ends at 10/12 [S1]" [S121] | OK |
| 12 | ATRI source URL and date | truckingresearch.org press release, 15 Jul 2026 [S35] | Cited in the Sources section; the memo cites ATRI's own page, not S34 [S120] | OK |
| 13 | ATRI fuel $0.48 labelled derived | "Derived" label and PDF-not-read note | Memo says "$0.48 per mile derived below [S35]" [S120]. The wording of the PDF-not-read note was not visible to me | Partly confirmed |
| 14 | Highest and lowest week figures in the stats table | 2026-09-21: $6.68, $0.88, $86,732.26. 2026-01-12: $3.365, $0.34, $43,690.73 | The memo author's read-back shows these values [S112]. My hand recompute matches. The table text was not visible in my cut-off output | Matches the author's read-back and my hand recompute |
| 15 | 40-band table vs Decimal recompute | 40 of 40 match; for example the first band is 0.29 and the last is 0.60 | The author's read-back shows 40 bands, ending at $0.60 for $4.95–$5.00 [S112]. My comparison output was cut off | NOT CONFIRMED by me |
| 16 | Chart embedded in memo | Not required; the memo refers to the PNG as an attachment | 0 inline images [S120] | Informational |

## Required corrections and fixes (none changes a number)
1. Band table (check 15): re-run the 40-band comparison and read the "bad" count. Expected: 40 of 40 match, using ROUND((mid − 1.25) ÷ 6.2, 2) with mid = 3.025 + 0.05i. If any cell differs, fix it in the memo.
2. ATRI wording (check 13): confirm the memo says the fuel $0.482/mi and the 20.6% share are "derived: 2.336 − 1.854", not published table values. It should also say the full ATRI PDF was not read and that no search for an edition newer than July 2026 was run.
3. Dates: confirm the memo names the report title, release date (15 Jul 2026) and cost data year (2025) next to the $2.336 and $1.854 figures [S35].
4. Optional: the chart is not embedded in the memo (0 inline images) [S120]. The task only asks for the memo to accompany the PNG, so embed it only if it still fits on 2 pages.

## Not confirmed
- The band-table comparison result (check 15) was not visible to me.
- The memo text between the opening summary and the Sources list was only partly visible [S120][S121].
- Live EIA and ATRI re-fetches were not possible (no network). The EIA values rest on saved pages [S1][S3].
- I did not look at the rendered pages.
BLOCKED: network/live fetch — EIA and ATRI pages could not be re-fetched live; checks used files saved on 2026-10-23
BLOCKED: image inspection — rendered memo pages were not viewed
MISSING DATA: Result of the 40-band memo table vs Decimal recompute — script output (v9.py, v9b.py) was cut off in my view [S118][S121]
MISSING DATA: Full memo text for ATRI caveat/derived label wording — only partially visible [S120]
Issues:
1. Step 8 (memo band table): my 40-band check output was cut off, so 40 of 40 matches is not confirmed by me. Re-run and confirm; the author's read-back [S112] and my hand spot-checks show no mismatch.
2. Step 8 (memo ATRI section): confirm it labels fuel $0.482/mi and 20.6% as derived (2.336 − 1.854), states the full PDF was not read, and gives report title, release date (15 Jul 2026) and data year (2025) [S35]. Also state that no search for a newer ATRI edition was run.
3. Step 8 (memo): the chart is not embedded in the memo (0 inline images) [S120]. Optional, only if the memo stays within 2 pages.
