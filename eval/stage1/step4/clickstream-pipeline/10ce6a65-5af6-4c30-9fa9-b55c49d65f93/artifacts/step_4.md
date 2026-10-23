I read "cloud warehouse" as Snowflake; if you meant Google BigQuery or Amazon Redshift or Databricks / Azure Synapse, the answer below may not apply. I read "duplicate events" as Events sharing the same event_id, from Kafka at-least-once redelivery; if you meant Events identical on a composite key (user, timestamp, type, etc.) or Fully identical rows across all fields, the answer below may not apply. I read "finishes more than 30 minutes late" as Later than 30 minutes after the scheduled completion deadline or SLA time; if you meant Runtime exceeding the expected duration by 30 minutes or More than 30 minutes after the scheduled start time, the answer below may not apply. I read "one year of raw events" as 365 days × 30M × 2 KB, about 22 TB uncompressed; if you meant Compressed columnar storage in the warehouse, a fraction of 22 TB or Includes duplicates and replicas or retention overhead, the answer below may not apply.

# Test report: dedup + DAU (sqlite equivalent) on sample_events.csv
Saved as test_report.md. It is written by test_dedup_dau.py. The test script exited 0 with "mismatches 0 fails []" [S43].

**The Snowflake dialect was not executed in Snowflake.** QUALIFY, MERGE, DATE_TRUNC and Tasks were not run, because there is no account or network access. Only the sqlite3 equivalent (pipeline_sqlite.py) was run. sqlite tests logic, not performance or Snowflake semantics.

## Counts [S43][S44]
| Metric | Value |
|---|---|
| Rows in (raw loaded) | 21,750 |
| Rows out (clean_events) | 21,000 |
| Duplicates removed | 750 (3.45% of rows) |
| Distinct event_ids (oracle) | 21,000 |
| Cross-day duplicate ids | 200 |
| Null/empty country rows; lowercase country rows | 347; 347 |
| Midnight events (23:59 / 00:00 UTC) in deduped set | 1,317 |
| (day, country) cells compared | 48 |
| **Mismatches vs oracle** | **0** |

## Results (check x expected x actual x pass)
The test script ended with an empty fails list [S43]. That means every check below passed. I saw the actual values for the first four rows and for the idempotency row in the printed output. For the other rows I know only the expected values and that they passed.

| Check | Expected | Actual | Pass |
|---|---|---|---|
| (day,country) mismatches vs oracle (48 cells) | 0 | 0 | PASS |
| Rows in | 21,750 | 21,750 | PASS |
| Rows after dedup == distinct event_ids | 21,000 | 21,000 | PASS |
| Duplicates removed | 750 | 750 | PASS |
| No repeated event_id in clean_events | 21,000 distinct | 21,000 distinct | PASS |
| Idempotent rerun: DAU rows and clean count unchanged | True | True | PASS |
| Incremental 2-night load (1-day look-back, anti-join against CLEAN) vs oracle, mismatches | 0 | 0 | PASS |
| Incremental load: clean rows == distinct ids | 21,000 | 21,000 | PASS |
| Cross-day duplicate ids (200) each kept exactly once, so not double counted | 0 violations | 0 | PASS |
| Midnight synthetic case: 23:59:59 goes to 10-19, 00:00:00 goes to 10-20, US and us merged, null country becomes UNKNOWN | {10-19 US:1, 10-20 US:2, 10-20 UNKNOWN:1} | same | PASS |
| Midnight events exist in the sample | True | True | PASS |
| Every midnight-event (day, country) cell is present in the DAU table | True | True | PASS |

Overall, no check failed [S43].

**Idempotency.** A second run() over the same data left the DAU rows and the clean_events count unchanged. The only difference is one extra OPS job_runs audit row per run: 2 rows after run 1 plus the rerun. The first row is ('dau_nightly','2026-10-21','SUCCESS',21750,21000,750,…) [S43]. The job_runs timestamp (2026-10-23) comes from the sandbox clock, not from today's date, which is 22 Oct 2026.

## Oracle
The oracle is independent pure Python (dict/set). It keeps the earliest ingested_at per event_id. The day is event_ts[:10] (UTC). Country is upper-cased, and blank or null becomes UNKNOWN. Rows with a null user_id are excluded. It does not use SQL or any pipeline code.

## Sample of output (DAU by day and country)
| event_date | country | dau |
|---|---|---|
| 2026-10-19 | US | 1457 [S43] |

The report file holds the top 4 countries per day for all 3 days. I saw only the first row printed [S43].

## Limits
- The Snowflake dialect was not executed in Snowflake. The QUALIFY, MERGE and DATE_TRUNC translations are untested there.
- sqlite tests logic only. It does not test performance, clustering, concurrency or the 30M-row/day scale.
- The sample is synthetic (seed 42, 3 UTC days, 15 countries).
- Dedup follows the settled interpretation: same event_id, earliest ingested_at wins.
- A duplicate that arrives after the look-back window is re-inserted unless the anti-join covers all of CLEAN. The incremental test used a 1-day look-back with the anti-join against CLEAN.
- Rows with a null user_id are excluded from DAU.
- The report's rerun note has a clumsy phrase ("see below") that should be tidied. It does not affect the results.
BLOCKED: Snowflake account/execution environment — the Snowflake SQL (QUALIFY, MERGE, DATE_TRUNC, Tasks) could not be executed or validated in Snowflake; only the sqlite3 equivalent was tested
MISSING DATA: Actual values for some result rows (incremental load, cross-day, midnight checks) — printed output was truncated; only the empty fails list [S43] confirms they passed
MISSING DATA: Top-4 DAU sample rows beyond the first (US 2026-10-19 = 1457) — truncated in the printed output; full rows are in test_report.md
