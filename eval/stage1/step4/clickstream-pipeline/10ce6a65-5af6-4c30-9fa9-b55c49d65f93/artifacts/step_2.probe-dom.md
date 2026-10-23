I read "cloud warehouse" as Snowflake; if you meant Google BigQuery or Amazon Redshift or Databricks / Azure Synapse, the answer below may not apply. I read "duplicate events" as Events sharing the same event_id, from Kafka at-least-once redelivery; if you meant Events identical on a composite key (user, timestamp, type, etc.) or Fully identical rows across all fields, the answer below may not apply. I read "finishes more than 30 minutes late" as Later than 30 minutes after the scheduled completion deadline or SLA time; if you meant Runtime exceeding the expected duration by 30 minutes or More than 30 minutes after the scheduled start time, the answer below may not apply. I read "one year of raw events" as 365 days × 30M × 2 KB, about 22 TB uncompressed; if you meant Compressed columnar storage in the warehouse, a fraction of 22 TB or Includes duplicates and replicas or retention overhead, the answer below may not apply.

# storage_estimate.md: one-year raw storage estimate (Snowflake), prepared 22 Oct 2026
Saved as storage_estimate.md (workspace file, written with local:Write [S38]).

## Headline
- 30,000,000 events/day x 2,000 B (both from the task) = 60 GB/day (calc: 30e6*2000/1e9 = 60).
- 60 GB/day x 365 = 21,900 GB = **21.9 TB, about 22 TB uncompressed** (calc: 60*365/1000 = 21.9).

## Prices, compression and retention rules (each dated or labelled)
- **Storage price: ASSUMPTION, dated 2016, NOT current.** $23/TB/month compressed capacity and $40/TB/month compressed on-demand, US, effective 1 Dec 2016, from the Snowflake press release of 22 Nov 2016 [S3]. I found no current (Oct 2026) price and claim none. Real Oct 2026 prices depend on region, edition and contract [unverified].
- **Compression 3x / 5x / 8x: planning assumptions, not measured on this data.** An undated secondary pricing explainer says Snowflake bills on compressed size and that its own cost examples assume 5:1 [S2]. That page has no date I could confirm and is not checked against Snowflake docs. The 3x and 8x bounds are my own [unverified].
- **Time Travel 1 day: [unverified] rule.** I assume prior versions of changed or deleted data are kept 1 day and billed as storage. Official billing docs not retrieved.
- **Fail-safe 7 days: [unverified] rule.** I assume a further 7 days after Time Travel for permanent tables, billed as storage. Official docs not retrieved.
- **Deduped copy: assumption.** CLEAN.EVENTS is about the same size as RAW (2x total). Real duplicates are probably a small share, so this is conservative.
- **Churn model: assumption.** The nightly look-back recompute rewrites 3 days of CLEAN.EVENTS per night: 3 x 60 GB / 5 = 36 GB = 0.036 TB of replaced compressed data per day. RAW is append-only, so it adds no churn.

## Scenario table (scenario x TB x monthly USD)
Monthly USD = TB x price. Both prices are the dated 2016 assumptions from [S3] (22 Nov 2016): $23 and $40 per TB-month. Not current prices.

| # | Scenario | Arithmetic | TB stored | USD/month at $23 (2016 capacity, assumption) | USD/month at $40 (2016 on-demand, assumption) |
|---|---|---|---|---|---|
| 1 | Raw, uncompressed (headline) | 60 GB x 365 / 1000 | 21.9 | 21.9 x 23 = 503.70 | 21.9 x 40 = 876.00 |
| 2 | Raw, 3x compression (assumption) | 21.9 / 3 | 7.3 | 7.3 x 23 = 167.90 | 7.3 x 40 = 292.00 |
| 3 | Raw, 5x compression (base case, assumption [S2], undated) | 21.9 / 5 | 4.38 | 4.38 x 23 = 100.74 | 4.38 x 40 = 175.20 |
| 4 | Raw, 8x compression (assumption) | 21.9 / 8 | 2.7375 | 2.7375 x 23 = 62.96 | 2.7375 x 40 = 109.50 |
| 5 | Raw + deduped copy, 5x | 2 x 4.38 | 8.76 | 8.76 x 23 = 201.48 | 8.76 x 40 = 350.40 |
| 6 | #5 + Time Travel 1 day + Fail-safe 7 days, realistic churn ([unverified] rules) | 8.76 + 1 x 0.036 + 7 x 0.036 (= 0.036 + 0.252) | 9.048 | 9.048 x 23 = 208.10 | 9.048 x 40 = 361.92 |
| 7 | Lever: RAW kept 30 days only, plus full deduped copy, 5x | 30 x 60 GB = 1.8 TB; 1.8 / 5 = 0.36; 0.36 + 4.38 | 4.74 | 4.74 x 23 = 109.02 | 4.74 x 40 = 189.60 |
| 8 | Stress: #5 with whole clean table rewritten daily, Time Travel 1 day + Fail-safe 7 days ([unverified] rules) | 8.76 + 1 x 4.38 + 7 x 4.38 (= 8.76 + 4.38 + 30.66) | 43.8 | 43.8 x 23 = 1,007.40 | 43.8 x 40 = 1,752.00 |

## Reading the table
- The headline is 21.9 TB, about 22 TB uncompressed. At the assumed 5x it is about 4.4 TB, roughly $101 to $175 per month at the dated 2016 prices. These are not current prices and are for relative sizing only.
- Raw plus a deduped copy with Time Travel and Fail-safe is about 9 TB at 5x (row 6), about $208 to $362 per month at 2016 prices. It stays close to the raw estimate because only a short trailing window is rewritten.
- The cost lever is a short RAW retention after dedup (row 7). The cost risk is rewriting the whole clean table daily (row 8), so the MERGE should touch only the look-back window.

## NOT NEEDED: Current (Oct 2026) Snowflake $/TB-month, measured compression ratio and official Time Travel/Fail-safe billing docs — worked around: used the dated 2016 prices ($23 capacity, $40 on-demand) from [S3] as labelled assumptions; labelled 3x/5x/8x compression as planning assumptions; modelled Time Travel and Fail-safe as [unverified] rules; arithmetic shown.

## What the work-around does not cover
- No current price. The Oct 2026 $/TB-month depends on region, edition and capacity contract, and needs a check on the Snowflake pricing page.
- No measured compression. Real ratios for JSON/VARIANT clickstream events need a sample load. The 5x figure rests on one undated secondary page [S2].
- Time Travel and Fail-safe retention and billing are unverified. Defaults depend on edition and table type, so confirm them in the official docs.
- Compute, Snowpipe Streaming ingest, Kafka infrastructure, cross-region or replica copies and volume growth are out of scope.
MISSING DATA: Current (Oct 2026) Snowflake storage $/TB-month by region and edition — web search returned only the 22 Nov 2016 press release [S3]
MISSING DATA: Measured compression ratio for this clickstream data — no sample loaded; 5:1 only from an undated secondary page [S2]
MISSING DATA: Official Snowflake Time Travel and Fail-safe billing documentation — not retrieved; rules marked [unverified]
