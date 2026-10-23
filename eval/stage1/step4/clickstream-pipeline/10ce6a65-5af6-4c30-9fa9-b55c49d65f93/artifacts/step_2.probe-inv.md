I read "cloud warehouse" as Snowflake; if you meant Google BigQuery or Amazon Redshift or Databricks / Azure Synapse, the answer below may not apply. I read "duplicate events" as Events sharing the same event_id, from Kafka at-least-once redelivery; if you meant Events identical on a composite key (user, timestamp, type, etc.) or Fully identical rows across all fields, the answer below may not apply. I read "finishes more than 30 minutes late" as Later than 30 minutes after the scheduled completion deadline or SLA time; if you meant Runtime exceeding the expected duration by 30 minutes or More than 30 minutes after the scheduled start time, the answer below may not apply. I read "one year of raw events" as 365 days × 30M × 2 KB, about 22 TB uncompressed; if you meant Compressed columnar storage in the warehouse, a fraction of 22 TB or Includes duplicates and replicas or retention overhead, the answer below may not apply.

storage_estimate.md is saved in the workspace. It was written by a Bash heredoc, because the first Write call failed on a stale-file error. I checked only the first 5 lines of the saved file [S31]. The table below was recomputed by hand and matches the file.

# One-year raw storage estimate: clickstream into Snowflake (prepared 22 Oct 2026)

## Headline
- 30,000,000 events/day x 2,000 B = 60 GB/day (calc: 30e6*2000/1e9 = 60).
- 60 GB/day x 365 = 21,900 GB = **21.9 TB, about 22 TB uncompressed** (calc: 60*365/1000 = 21.9). Decimal TB, 1 TB = 1,000 GB.

## Prices and sources (retrieved 22 Oct 2026)
- Storage price: about $23/TB-month on a capacity contract and $40/TB-month on demand [S2].
  - S2 is a secondary pricing-explainer article, not Snowflake's own price list. Only its search excerpt supports the figure.
  - Rates vary by cloud and region.
  - Both prices are dated 22 Oct 2026 and treated as assumptions to confirm against the contract.
- Compression: the fetched sources (S1, S2, S3) gave no usable guidance. The 3x, 5x and 8x ratios are scenarios [unverified]. Snowflake bills compressed bytes. Measure the real ratio on about a week of real JSON/VARIANT data.
- Duplicate rate: 1% of events [unverified] assumption.
- Time Travel 1 day + Fail-safe 7 days: modelled as 8 days of churn. Churn = 8 x 60 GB/day / compression ratio, assuming append-only tables (assumption).

## Sensitivity table (size after 365 days of retained data; monthly USD = TB x price)
| Scenario | TB | Monthly USD @ $23/TB (capacity) [S2] | Monthly USD @ $40/TB (on-demand) [S2] | Arithmetic |
|---|---|---|---|---|
| S1 Raw, uncompressed (headline) | 21.90 | 504 | 876 | 60 x 365 / 1000 = 21.9; 21.9 x 23 = 503.7; 21.9 x 40 = 876 |
| S2 Raw, compressed 3x [unverified ratio] | 7.30 | 168 | 292 | 21.9 / 3 = 7.3 |
| S3 Raw, compressed 5x [unverified ratio] | 4.38 | 101 | 175 | 21.9 / 5 = 4.38 |
| S4 Raw, compressed 8x [unverified ratio] | 2.74 | 63 | 110 | 21.9 / 8 = 2.7375 |
| S5 Raw 5x + deduped copy (1% dups) | 8.72 | 200 | 349 | 4.38 + 4.38 x 0.99 = 4.38 + 4.3362 = 8.7162 |
| S6 S5 + Time Travel 1 day + Fail-safe 7 days (5x) | 8.81 | 203 | 352 | 8.7162 + (8 days x 60 GB / 5 / 1000 = 0.096 TB) = 8.8122 |
| S7 Conservative, 3x: raw + dedup + Time Travel 1 day + Fail-safe 7 days | 14.69 | 338 | 587 | 7.3 + 7.3 x 0.99 (= 7.227) + (8 x 60 / 3 / 1000 = 0.16 TB) = 14.687 |
| S8 Worst case, uncompressed: raw + dedup + Time Travel 1 day + Fail-safe 7 days | 44.06 | 1,013 | 1,762 | 21.9 + 21.9 x 0.99 (= 21.681) + (8 x 60 / 1000 = 0.48 TB) = 44.061 |

## Reading the table
- The headline is 21.9 TB (about 22 TB) uncompressed. It is a data-volume figure, not the warehouse bill.
- Realistic year-end bill: 4.38 TB at 5x, so 4.38 x 23 = $101/month on a capacity contract, or $175 on demand. With a deduped copy plus Time Travel and Fail-safe (S6) it is about $203/month, or $352 on demand.
- Time Travel and Fail-safe add little for append-only tables: 8 x 12 GB = 96 GB at 5x. If tables are fully rewritten daily, each retained day can approach a full table copy, up to about 8x the table size. Use incremental MERGE or insert, and transient staging tables with 0-day Time Travel.
- These are year-end figures. Storage grows linearly, so the average over year one is about half if raw data is never expired. Keeping RAW for 90 days only cuts the RAW component to 90/365 of the figures above.
- Excluded: compute, Snowpipe Streaming ingest fees and cloud egress.

## Risks and unconfirmed items
- The price comes from secondary source S2 and may drift. Confirm it against the contract or Snowflake's official pricing page.
- Compression ratios are untested [unverified]. Measure them on real data.
- The 1% duplicate rate is unknown [unverified].
- The Time Travel and Fail-safe churn model assumes append-only tables.
MISSING DATA: Official Snowflake storage price per TB-month — only secondary source S2 (vendor-comparison article) found in fetched pages
MISSING DATA: Snowflake compression guidance for JSON/VARIANT clickstream — searched saved sources S1-S3, none found; 3x/5x/8x are [unverified] scenarios
