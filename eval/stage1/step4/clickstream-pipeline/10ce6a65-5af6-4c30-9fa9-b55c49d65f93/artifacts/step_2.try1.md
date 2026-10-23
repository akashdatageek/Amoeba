I read "cloud warehouse" as Snowflake; if you meant Google BigQuery or Amazon Redshift or Databricks / Azure Synapse, the answer below may not apply. I read "duplicate events" as Events sharing the same event_id, from Kafka at-least-once redelivery; if you meant Events identical on a composite key (user, timestamp, type, etc.) or Fully identical rows across all fields, the answer below may not apply. I read "finishes more than 30 minutes late" as Later than 30 minutes after the scheduled completion deadline or SLA time; if you meant Runtime exceeding the expected duration by 30 minutes or More than 30 minutes after the scheduled start time, the answer below may not apply. I read "one year of raw events" as 365 days × 30M × 2 KB, about 22 TB uncompressed; if you meant Compressed columnar storage in the warehouse, a fraction of 22 TB or Includes duplicates and replicas or retention overhead, the answer below may not apply.

# One-year raw clickstream storage estimate (Snowflake), saved as storage_estimate.md
Prepared 22 Oct 2026 (America/Chicago). The file was written to the workspace [S9] and read back earlier in this step to confirm it saved [S8].

## Headline
30M events/day (task) x 2,000 B = 60 GB/day (calc: 30e6*2000/1e9 = 60). 60 GB x 365 = 21.9 TB (calc: 60*365/1000 = 21.9). **Headline: 21.9 TB, about 22 TB uncompressed** (decimal TB, 1 TB = 1000 GB). It is raw bytes before warehouse compression, with no replicas and no retention overhead.

## Prices and sources (each dated or labelled)
- **On-demand storage, about $40/TB-month, US region on AWS** [S1]. Source: espresso.ai, https://espresso.ai/post/explaining-snowflake-pricing. Retrieved 22 Oct 2026; the page's own publication date was not shown. Search snippet only. Treated as the upper-bound price.
- **Capacity (pre-purchased) storage, about $23/TB-month, US AWS** [S1]. keebo.ai also says "about $23/TB" [S2], https://keebo.ai/blog/snowflake-pricing ("Guide for 2026"), retrieved 22 Oct 2026, snippet only. The two secondary sources agree on $23. Base case is $23. I did not read Snowflake's own pricing page, so both prices are as of 22 Oct 2026 and unconfirmed by the vendor.
- **Compression 3x / 5x / 8x: assumptions** as of 22 Oct 2026. I retrieved no Snowflake-documented ratio. The real ratio depends on the schema, on JSON in VARIANT versus typed columns, and on event entropy. Measure it on one week of real data with TABLE_STORAGE_METRICS.
- **Time Travel 1 day and Fail-safe 7 days**: Snowflake's standard retention model [unverified]. Fail-safe is not configurable and applies to permanent tables [unverified]. Both hold only changed or deleted micro-partitions, so append-only raw data adds little. The churn model below is an assumption, as of 22 Oct 2026.
- **Deduped copy**: assumed the same size as raw. Duplicates are expected to be only a few percent (assumption, 22 Oct 2026).

## Scenario table
Monthly USD = TB x price per TB-month, at $23 [S1][S2] or $40 [S1], as of 22 Oct 2026. It is the cost at year end, when all 365 days are held. Daily compressed volume: 0.06 TB / 5 = 0.012 TB at 5x; 0.06 / 3 = 0.02 TB at 3x.

| Scenario | TB stored | Arithmetic | Monthly USD @ $23 (capacity) | Monthly USD @ $40 (on-demand) |
|---|---|---|---|---|
| A. Raw, uncompressed (headline) | 21.90 | 0.06 TB/day x 365 = 21.9 | $504 (21.9 x 23) | $876 (21.9 x 40) |
| B3. Raw, 3x compression (assumed) | 7.30 | 21.9 / 3 | $168 | $292 |
| B5. Raw, 5x compression (assumed) | 4.38 | 21.9 / 5 | $101 | $175 |
| B8. Raw, 8x compression (assumed) | 2.74 | 21.9 / 8 = 2.7375 | $63 | $110 |
| C. Raw + deduped copy, 5x | 8.76 | 2 x 4.38 | $201 | $350 |
| D. C + Time Travel 1 d + Fail-safe 7 d (append-mostly, 5x) | 8.95 | retention extra = 2 copies x (1 d + 7 d) x 0.012 TB/day = 2 x 8 x 0.012 = 0.192; 8.76 + 0.192 = 8.952 | $206 | $358 |
| E. Stress: raw + dedup, 3x, a full day of churn held for Time Travel 1 d + Fail-safe 7 d | 14.92 | 2 x 7.30 = 14.6; retention extra = 2 x 8 x 0.02 = 0.32; 14.6 + 0.32 = 14.92 | $343 | $597 |
| F. Raw + dedup copy, both uncompressed (no compression credit) | 43.80 | 2 x 21.9 | $1,007 | $1,752 |

## Reading the table
- **Planning case is D:** about 8.95 TB, about $206/month at $23 and $358 at $40. Storage is small next to warehouse compute.
- The no-compression ceiling (A) is about $504/month at $23 and $876 at $40.
- Average cost over the first year is about half the year-end figure, because the data grows linearly.
- Levers: limit RAW.CLICK_EVENTS retention to 30–90 days and keep CLEAN long-term. Make staging tables transient with DATA_RETENTION_TIME_IN_DAYS=0, so they have no Fail-safe. Keep Time Travel at 1 day.
- Not included: compute, Snowpipe Streaming ingest fees, cloud-services charges, data transfer, and the MART tables (tiny: countries x days).

## Could not confirm
- Prices rest on two secondary-source search snippets [S1][S2]. I did not verify them on Snowflake's official pricing page. The espresso.ai page date was not shown.
- No Snowflake-documented compression ratio was retrieved, so 3x, 5x and 8x are assumptions.
- The Time Travel and Fail-safe rules come from my own knowledge [unverified].
MISSING DATA: Snowflake official storage $/TB-month — only secondary snippets (espresso.ai, keebo.ai) found via web_search; official pricing page not read
MISSING DATA: Snowflake-documented compression ratio — not retrieved; 3x/5x/8x are labelled assumptions
MISSING DATA: Publication date of the espresso.ai page — not shown in snippet; retrieval date 22 Oct 2026 given instead
