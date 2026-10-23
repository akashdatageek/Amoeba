# storage_estimate.md: One-year raw storage estimate (Snowflake)

I read "cloud warehouse" as Snowflake; if you meant Google BigQuery or Amazon Redshift or Databricks / Azure Synapse, the answer below may not apply. I read "duplicate events" as Events sharing the same event_id, from Kafka at-least-once redelivery; if you meant Events identical on a composite key (user, timestamp, type, etc.) or Fully identical rows across all fields, the answer below may not apply. I read "finishes more than 30 minutes late" as Later than 30 minutes after the scheduled completion deadline or SLA time; if you meant Runtime exceeding the expected duration by 30 minutes or More than 30 minutes after the scheduled start time, the answer below may not apply. I read "one year of raw events" as 365 days × 30M × 2 KB, about 22 TB uncompressed; if you meant Compressed columnar storage in the warehouse, a fraction of 22 TB or Includes duplicates and replicas or retention overhead, the answer below may not apply.

Prepared 22 Oct 2026 (America/Chicago). The web sources were fetched 2026-10-23 02:05 UTC, which is the evening of 22 Oct in Chicago. The file storage_estimate.md was saved in this step (rewritten as [S25] to add the tags). This output is the full table recomputed, so it stands on its own. The wording of the saved file may differ slightly.

## 1. Headline (uncompressed)
- Per day: 30e6 events x 2000 B = 60,000,000,000 B = 60 GB/day (calc).
- Per year: 60 GB x 365 = 21,900 GB = **21.9 TB, about 22 TB uncompressed** (calc: 30e6*2000/1e9*365/1000 = 21.9).
- This is the size at the end of year 1, with all 365 days retained. The average over the year is 21.9 / 2 = 10.95 TB, because the table grows linearly.

## 2. Price and compression inputs (each dated or labelled)
- **Storage price: $23 per TB per month [S2].** It comes from a third-party pricing explainer, not from Snowflake's own price list. The page was fetched 2026-10-23 02:05 UTC, and I found no publication date on it. Treat it as an assumption to check against the Snowflake price list and your contract. Snowflake bills storage per cloud and region, and pre-purchased capacity is usually cheaper [unverified, my own knowledge, as of 22 Oct 2026].
- **Compression of 3x, 5x and 8x are my assumed scenarios** (assumption, 22 Oct 2026, [unverified]). I found no source with a ratio for clickstream JSON. [S3] is an old Snowflake press release on storage reduction, and I used no number from it. Snowflake bills on compressed size [unverified, my own knowledge, as of 22 Oct 2026].
- **Time Travel 1 day** is a modelling choice. The default for permanent tables is 1 day [unverified, my own knowledge, as of 22 Oct 2026].
- **Fail-safe 7 days** applies to permanent tables [unverified, my own knowledge, as of 22 Oct 2026].
- Time Travel and Fail-safe keep only changed or deleted data. Append-only RAW therefore adds almost nothing. The overhead comes from CLEAN rewrites by the MERGE. The model assumes one day of churn: 60 GB / 5 = 12 GB = 0.012 TB at 5x.

## 3. Scenario table (price $23/TB-month [S2], fetched 2026-10-23; year-end size)
| # | Scenario | TB (arithmetic) | Monthly USD (TB x 23) |
|---|---|---|---|
| 1 | Raw, uncompressed (headline, upper bound) | 21.9 | 21.9 x 23 = **$503.70** |
| 2 | Raw, 3x compression (assumed) | 21.9 / 3 = 7.30 | 7.30 x 23 = **$167.90** |
| 3 | Raw, 5x compression (planning case, assumed) | 21.9 / 5 = 4.38 | 4.38 x 23 = **$100.74** |
| 4 | Raw, 8x compression (assumed) | 21.9 / 8 = 2.7375 | 2.7375 x 23 = **$62.96** |
| 5 | Raw + deduped CLEAN copy, 5x | 4.38 x 2 = 8.76 | 8.76 x 23 = **$201.48** |
| 6 | Scenario 5 + Time Travel 1 day (1 day of CLEAN churn) | 8.76 + 0.012 = 8.772 | 8.772 x 23 = **$201.76** |
| 7 | Scenario 6 + Fail-safe 7 days (7 x 0.012 = 0.084) | 8.772 + 0.084 = 8.856 | 8.856 x 23 = **$203.69** |
| 8 | Stress case: CLEAN fully rewritten daily, 5x. Time Travel keeps 1 day (4.38 TB). Fail-safe keeps 7 days (7 x 4.38 = 30.66 TB). | 8.76 + 4.38 + 30.66 = 43.80 | 43.80 x 23 = **$1,007.40** |

Every monthly figure is the TB figure times the $23 price [S2]. Only the price carries a source. The compression ratios and retention periods are assumptions.

## 4. Reading the table
- The headline of 21.9 TB, about 22 TB uncompressed, is about $504 a month at the assumed price. It is a ceiling, not what Snowflake would bill.
- At 5x, one year of raw events is about 4.4 TB, or about $101 a month. Raw plus the deduped copy with Time Travel and Fail-safe is about 8.9 TB, or about $204 a month.
- The 3x to 8x range gives a raw-only band of $62.96 to $167.90 a month.
- Storage is small next to compute. Scenario 8 is the realistic worst case if the look-back recompute rewrites all of CLEAN daily. Avoid that by merging only the trailing window.

## 5. Risks and caveats
1. The price is a third-party figure [S2], undated on the page and on-demand. It varies by cloud, region and contract.
2. The compression ratios are assumptions. Measure them by loading one day (60 GB) and reading `TABLE_STORAGE_METRICS`. Raw JSON in a VARIANT column compresses less well than typed columns.
3. The 2 KB per event and 30M per day come from the task. Peaks, growth and size drift are not modelled.
4. Time Travel and Fail-safe overhead depends on how much CLEAN is rewritten. Scenario 8 bounds it.
5. Transient or short-retention staging tables avoid Fail-safe cost. This is not modelled.
6. Not included: MART tables (small), clones, cross-region replication.
MISSING DATA: Snowflake official storage $/TB-month, dated — only a third-party pricing explainer [S2] (about $23/TB/month, no publication date on the page) was found; official price list not confirmed
MISSING DATA: Compression ratio guidance for clickstream/JSON — searched the fetched sources [S1][S2][S3], none gave one; 3x/5x/8x are labelled assumptions
