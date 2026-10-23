# One-year raw storage estimate: Snowflake, RAW.CLICK_EVENTS and copies (storage_estimate.md)

Prepared 22 Oct 2026. Decimal units (1 TB = 1,000 GB). The file storage_estimate.md is saved in the workspace. This text is the final version and governs if the file differs.

## 1. Headline (uncompressed)
- 30,000,000 events/day x 2,000 B = 60,000,000,000 B = 60 GB/day (calc).
- 60 GB/day x 365 days = 21,900 GB = **21.9 TB, about 22 TB uncompressed** (calc: 30e6*2000/1e9*365/1000 = 21.9).
- Snowflake bills compressed bytes after load. 22 TB is the upper bound and the base for every scenario below.

## 2. Prices and sources (each dated or labelled)
| Price or rule | Value | Source and date |
|---|---|---|
| Capacity (pre-purchased) storage | $23 per TB-month, compressed | [S3], Snowflake US storage price cut, 2016. This is 10 years old, so for Oct 2026 it is an **assumption**. |
| On-demand storage | $40 per TB-month, compressed | [S3], 2016. Also an **assumption** for Oct 2026. |
| Compression guidance | [S3] (2016) assumes 5x compression when it quotes an effective price of $5/TB-month or less. This is a vendor planning assumption, not a measured ratio for this data. | 5x is from [S3], 2016. 3x and 8x are my **assumptions** to bracket it. |
| How storage is held | Compressed columnar micro-partitions on cloud storage. No ratio is given. | [S1], published 31 Mar 2025 |
| Time Travel (1 day, as set for this design) and Fail-safe (7 days) | Both bill only changed or deleted data, at the storage price. | [unverified] my own knowledge, not in the fetched sources, Oct 2026 |

I did not use any number from [S2]. Every $ figure below uses the $23 or $40 price from [S3] (2016, assumption for 2026).

## 3. Modelling assumptions (all mine, labelled)
- The deduped CLEAN.EVENTS is assumed to be as big as RAW (100%). This is conservative. The real Kafka redelivery duplicate rate is probably small, but I have no measured figure.
- Daily compressed load = 60 GB / ratio. At 5x it is 60/5 = 12 GB/day. At 3x it is 60/3 = 20 GB/day.
- RAW is append-only, so Time Travel and Fail-safe add almost nothing for it.
- CLEAN is MERGEd nightly. One day of rewritten data sits in Time Travel (1 day) and then in Fail-safe (7 days). That is 1 x daily load for Time Travel plus 7 x daily load for Fail-safe.
- Worst case: both RAW and CLEAN are fully rewritten every day, so the churn doubles.
- The monthly cost is the steady state at the end of year 1, with all 365 days held. Over year 1 the bill grows linearly, so the average month is about half. Scenario 2 example: 100.74 x 12 x 0.5 = $604.44 for the first year.

## 4. Scenarios (scenario x TB x monthly USD)
| # | Scenario | Arithmetic | TB stored | Monthly USD |
|---|---|---|---|---|
| 0 | Uncompressed upper bound (not billed this way) | 21.9 x $23 [S3, 2016, assumption] = 503.70 | 21.90 | $503.70 |
| 1 | RAW only, 3x compression | 21.9 / 3 = 7.30 TB; 7.30 x $23 = 167.90 | 7.30 | $167.90 |
| 2 | RAW only, 5x compression (base case) | 21.9 / 5 = 4.38 TB; 4.38 x $23 = 100.74 | 4.38 | $100.74 |
| 3 | RAW only, 8x compression | 21.9 / 8 = 2.7375 TB; 2.7375 x $23 = 62.96 | 2.74 | $62.96 |
| 4 | RAW + deduped copy, 5x | 4.38 x 2 = 8.76 TB; 8.76 x $23 = 201.48 | 8.76 | $201.48 |
| 5 | Scenario 4 + Time Travel 1 day + Fail-safe 7 days on CLEAN only, 5x | 8.76 + 0.012 (1 x 12 GB) + 0.084 (7 x 12 GB) = 8.856 TB; 8.856 x $23 = 203.69 | 8.86 | $203.69 |
| 6 | Scenario 4 + Time Travel + Fail-safe, both tables rewritten daily, 5x | 8.76 + 2 x 12 GB x (1 + 7) = 8.76 + 0.192 = 8.952 TB; 8.952 x $23 = 205.90 | 8.95 | $205.90 |
| 7 | Pessimistic: raw + dedup, 3x, both tables rewritten daily | 14.6 + 2 x 20 GB x 8 = 14.6 + 0.32 = 14.92 TB; 14.92 x $23 = 343.16 | 14.92 | $343.16 |
| 8 | Scenario 4 at the on-demand price | 8.76 x $40 [S3, 2016, assumption] = 350.40 | 8.76 | $350.40 |

All $23 rates are [S3], 2016, an assumption for Oct 2026. Time Travel and Fail-safe sizes in scenarios 5 to 7 rest on the [unverified] billing rule in section 2.

## 5. Reading the table
- **Headline:** 21.9 TB, about 22 TB uncompressed, is about 4.38 TB billed at the 5x assumption (21.9 / 5).
- **Realistic range:** about $63 to $206 per month at the capacity price, once the deduped copy and Time Travel / Fail-safe are included (scenarios 3 to 6). The pessimistic case is about $343 per month.
- **Biggest levers:**
  - Compression ratio: 8x vs 3x is a 2.67x spread (8 / 3).
  - A second deduped copy: it doubles the cost.
  - On-demand vs capacity pricing: 40 / 23 = 1.74x.
  - Time Travel plus Fail-safe: scenario 5 is (203.69 - 201.48) / 201.48 = 1.1% above scenario 4. Scenario 6 is 2.2% above. Both are under 3%.
- **Storage is small next to compute** at this size. The nightly load, dedup and DAU jobs on a small warehouse cost more, but I did not price compute here.
- **Cost reducers:**
  - Keep CLEAN as the long-lived copy and apply a retention window to RAW, for example 30 to 90 days.
  - Cluster CLEAN by event date.
  - Set Time Travel to 1 day on RAW and CLEAN.
  - Use a transient table for RAW if Fail-safe is not needed.
- **Kafka connector landing:** it lands VARIANT (RECORD_METADATA + RECORD_CONTENT), which adds metadata per row. Flattening to typed columns in CLEAN usually compresses better ([unverified], my own knowledge).

## 6. Could not confirm
- The current (Oct 2026) Snowflake storage price. The only price in the fetched sources is the 2016 figure in [S3]. Prices also vary by region and cloud. Verify before quoting $ externally.
- A measured compression ratio for 2 KB clickstream JSON. 3x, 5x and 8x are assumptions. Check with a load test of one week of real data: compare TABLE_STORAGE_METRICS bytes with the row count.
- Official Time Travel and Fail-safe billing rules. They are not in the fetched pages, so they are tagged [unverified].
MISSING DATA: Current (Oct 2026) Snowflake storage $/TB-month — searched fetched pages [S1][S2][S3]; only the 2016 price ($23 capacity, $40 on-demand) in [S3] was usable, so prices are labelled assumptions
MISSING DATA: Measured or documented compression ratio for clickstream data — searched [S1][S2][S3]; only a 5x planning assumption in [S3] (2016)
MISSING DATA: Official Snowflake documentation on Time Travel and Fail-safe billing — not in the fetched sources, so those rules are tagged [unverified]