I read "weekly retail on-highway diesel price for Indiana" as EIA weekly Midwest (PADD 2) retail diesel price, used as a proxy because EIA publishes no Indiana-only weekly series; if you meant EIA weekly Indiana-specific retail diesel price, if such a series exists or EIA weekly Midwest regional price, with Indianapolis or a nearby metro as a cross-check or EIA weekly US national average diesel price, as the fallback, the answer below may not apply.

## Memo file and page count
- File: fuel_surcharge_memo.docx. I converted it to PDF with soffice and counted pages with pypdf. The result is 2 pages, which meets the 2-page limit [S111].
- Word count is about 800: 674 in paragraphs and 126 in tables [S111].
- The memo refers to the Excel workbook and the PNG chart as attachments. I did not confirm that the chart is embedded.

## Structure (read back from the saved file, 2026-10-23)
- The memo opens with the proxy line, then a To/From/Date/Subject header dated 23 October 2026 [S112].
- It has seven sections:
  1. Bottom line
  2. Data and method
  3. Surcharge schedule
  4. 52-week results
  5. ATRI comparison
  6. Not obtained / substituted
  7. Sources
- Band table: 11 rows, a header plus 10 rows of 4 column pairs. It covers 40 bands from $3.00 to $5.00 in 5-cent steps, priced at the band midpoint. The last cell is $0.60 for the $4.95–$5.00 band [S112].
- Stats table: 4 rows. Average, highest and lowest week each show date, price, surcharge and fleet fuel cost [S112].

## Figures in the memo
All EIA figures are from series EMD_EPD2D_PTE_R20_DPG, Midwest (PADD 2) No. 2 diesel retail price in $/gal, pulled from the EIA API v2 and retrieved 2026-10-23 [S3].
- **Window:** 52 weekly releases, Monday price dates 2025-10-27 to 2026-10-19 [S3].
- **Latest week:** as of 2026-10-19 the price is $6.352/gal [S3][S58]. The EIA dnav page copy ends 10/12 and was released 10/14/2026 [S1].
- **Average (52 weeks):**
  - Price is $4.787/gal (4.78738), as of 2026-10-19 [S109].
  - Surcharge is $0.57/mi (0.5708, the mean of the rounded weekly values) [S109].
  - Fleet fuel cost is $62,158.78 per week [S111].
- **Highest week, 2026-09-21:** price $6.68, surcharge $0.88/mi, fleet cost $86,732.26 [S112].
- **Lowest week, 2026-01-12:** price $3.365, surcharge $0.34/mi, fleet cost $43,690.73 [S112].
- **Fleet and totals:**
  - Gallons per week are 35 × 2,300 ÷ 6.2 = 12,983.871.
  - The 52-week total fleet fuel cost is $3,232,256.77 [S109].
  - The carrier's average fuel cost is $0.7722/mi, which is the average price ÷ 6.2 = 4.78738 ÷ 6.2 [S109].
- **ATRI:** "An Analysis of the Operational Costs of Trucking", released 15 Jul 2026, cost data year 2025. I cite ATRI's own press release (truckingresearch.org/2026/07/new-atri-report-details-accelerating-costs-and-low-profitability-despite-cuts), not S34 [S35].
  - Total marginal cost is $2.336/mi [S35].
  - Cost excluding fuel is $1.854/mi [S35].
  - Fuel is $0.482/mi, derived as 2.336 − 1.854. It is labelled "derived", not a published table value, and the memo says the full PDF was not read.
  - Fuel share is 20.6% (0.482 ÷ 2.336).
  - The carrier is +$0.2902/mi above ATRI fuel (0.7722 − 0.482), or 60.2% more (0.2902 ÷ 0.482).
  - Caveat: the comparison is not like-for-like. ATRI is an industry-wide average on 2025 data [S35]. The carrier figure uses Midwest prices for 2025-10-27 to 2026-10-19 at 6.2 mpg [S3].
- **Prices above $5.00:** the 52-week high of $6.68 and the latest week of $6.352 fall outside the band table [S3]. The formula still applies there. For example, (6.68 − 1.25) ÷ 6.2 = $0.88/mi.

## Assumptions stated in the memo
- Gallons per week are constant.
- Surcharge is calculated at band midpoints.
- The surcharge applies to every mile.
- Midwest (PADD 2) stands in for Indiana.

## Not obtained / substituted (memo section 6)
- **Indiana-only weekly EIA series:** none exists. Midwest PADD 2 is the proxy (EIA series above, retrieved 2026-10-23) [S3].
- **ATRI's stated fuel cost per mile:** not found. I used 2.336 − 1.854 = $0.482/mi (ATRI release of 15 Jul 2026) [S35].
- **Newer ATRI edition:** no search for an edition newer than July 2026 was run, so that point is unconfirmed.

## Not confirmed in this step
- I checked the memo's layout by page count only. I did not view the rendered pages.
- I did not re-read the full memo text after the readback was cut short.
- No live re-fetch of EIA or ATRI was possible (no network). The memo rests on files saved 2026-10-23.
BLOCKED: network/live fetch — EIA and ATRI pages could not be re-fetched live; memo rests on files saved 2026-10-23
BLOCKED: image inspection — rendered memo pages and chart PNG were not viewed
MISSING DATA: ATRI fuel cost per mile as a stated table value — looked in ATRI press release and summary [S35]; substituted 2.336 − 1.854 = 0.482 $/mi
MISSING DATA: Check for an ATRI edition newer than July 2026 — not run
