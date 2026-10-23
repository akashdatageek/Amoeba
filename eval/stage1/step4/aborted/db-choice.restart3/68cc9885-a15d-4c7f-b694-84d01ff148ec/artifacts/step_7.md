I read "multi-tenant" as Shared database with a tenant ID column or tenant field; if you meant Separate schema or database per tenant, the answer below may not apply.

# Step 7: prototype tests (all PROXY, no real engine)

**Engine status.** No PostgreSQL or MongoDB server was available, and neither were duckdb or pymongo [S91][S84]. Every result below is labelled "PROXY - not engine performance".
- The PostgreSQL side ran on a sqlite3 stand-in. It has no partitioning, no jsonb and no RLS.
- The MongoDB side ran as in-memory Python dicts, sorted per tenant to mimic the {tenant_id:1, ts:-1} index. It has no aggregation engine, no validator and no WiredTiger.

**Files in the workspace:**
- `results.csv` has a header plus 10 test rows [S94][S95]. The rows are Q1 to Q6, an events row count, a dashboard_daily row count, stored size and schema syntax validation.
- `run_tests.py` is the test runner.
- The data is in `proto/data/`.
- The sqlite file is `proto/t.db`.
- The full runner output is in `tool_results/step7_5.txt`. The full results.csv text is in `tool_results/step7_6.txt`.

Each timing is the median of 3 runs per tenant, summed over the 5 tenants.

| test | PostgreSQL result (sqlite stand-in) | MongoDB result (Python dicts) | engine or proxy | notes |
|---|---|---|---|---|
| Q1 daily active users | 450 rows; 422.93 ms | 450 rows; 148.83 ms | PROXY - not engine performance | Row counts match and result sets are identical [S95]. Timing is not evidence. |
| Q2 top event types, 30 days | 30 rows; 121.93 ms | 30 rows; 125.52 ms | PROXY - not engine performance | Row counts match and result sets are identical [S95]. Timing is not evidence. |
| Q3 funnel (page_view, signup, purchase) | 5 rows; 447.32 ms | 5 rows; 214.76 ms | PROXY - not engine performance | Row counts match [S95]. The rest of the note was cut from the output I saw. |
| Q4 rolling 7-day count | row is in results.csv; not seen | row is in results.csv; not seen | PROXY - not engine performance | The script compares result sets. I did not see the outcome (output cut). |
| Q5 latest 100 events | row is in results.csv; not seen | row is in results.csv; not seen | PROXY - not engine performance | The script checks 100 rows per tenant. It does not compare tie order on ts. I did not see the outcome. |
| Q6 cross-tenant leak check (isolation) | row is in results.csv; not seen | row is in results.csv; not seen | PROXY - not engine performance | The script counts foreign-tenant rows from scoped queries and runs an unscoped negative control. I did not see the pass or fail result. |
| Events row count | row is in results.csv; not seen | row is in results.csv; not seen | PROXY - not engine performance | The script compares total and per-tenant counts. I did not see the outcome. |
| dashboard_daily row count | row is in results.csv; not seen | row is in results.csv; not seen | PROXY - not engine performance | The script compares counts. I did not see the outcome. |
| Stored size | sqlite file size is in results.csv; not seen | events.jsonl 48,283,171 bytes (raw file, not WiredTiger size) [S95] | PROXY - not engine performance | events.csv is 25,807,268 bytes [S95]. These are raw file sizes and say nothing about real PostgreSQL or Atlas storage. |
| Schema syntax validation | not run (no postgres) | not run (no mongod or pymongo) | not tested | schema.sql and mongo_schema.js have never run on a real engine [S95][S91]. |

**What I confirmed.**
- The runner finished without errors.
- results.csv exists and has the 10 labelled rows [S94][S95].
- Q1, Q2 and Q3 have matching row counts on both sides [S95].
- The Q4, Q5 and Q6 outcomes, the row-count parity rows and the sqlite size were cut from every output I saw. I did not verify them, and I do not claim the isolation test passed. Read `tool_results/step7_6.txt` or results.csv before relying on those rows.
- Step 6 gave 300,000 events and 1,350 rollup rows, and about 71 MB of CSV and JSONL [S84]. That is not a figure from this step's runs.

**Reading the Q1–Q3 timings.** The proxies differ in kind. sqlite is compiled and disk-backed, and the Python dicts are in memory. The gaps reflect that difference, not PostgreSQL or MongoDB. Do not use these timings to choose a database.

# Limitations
1. No real engine ran. PostgreSQL partitioning, jsonb, RLS and the (tenant_id, ts) index plan were not exercised. MongoDB validators, aggregation pipelines and indexes were not exercised either. The pipelines in queries_mongo.py never ran. Python functions in run_tests.py stood in for them.
2. Row-count parity covers only this proxy data and logic. It does not prove that the real SQL and real pipelines return the same rows.
3. The isolation test is a proxy. It checks that scoped queries return no foreign rows. It does not test PostgreSQL RLS, and it does not test MongoDB's application-layer `scoped()` wrapper. MongoDB isolation depends on application code, not on the database (step 6). I did not see the isolation outcome.
4. The data is synthetic, with 5 tenants and about 300,000 events [S84]. About 71 MB against 10 TB (50 × 200 GB = 10,000 GB) is about 71 / 10,000,000 = 0.0007%. Skew, cache and noisy-neighbour effects at scale are unknown.
5. Sizes are file sizes of CSV, JSONL and sqlite. They are not WiredTiger or PostgreSQL heap and index sizes, and they say nothing about compression.
6. Q5 does not compare tie order on ts.
7. I did not review all of schema.sql after the events table. Its syntax is unvalidated.
8. Timings come from one machine with no concurrency. The target peak of 5,000 queries per minute is 5,000 / 60 = 83.3 queries per second across all tenants. None of that was simulated.
9. The Q4–Q6, parity and sqlite-size outcomes were not seen (see "What I confirmed").

# What a real 10 TB test needs
- A PostgreSQL target (RDS or Aurora PostgreSQL, Cloud SQL or AlloyDB) and a MongoDB Atlas cluster in an EU region on AWS or GCP. Size both from the cost model.
- Run schema.sql and mongo_schema.js on real engines and fix any syntax errors.
- Load a synthetic or anonymised dataset of 10 TB (50 tenants × 200 GB) with realistic skew. Include time partitions, jsonb or document properties, and the dashboard rollup jobs.
- Replay a mixed workload that peaks at 5,000 queries per minute across all tenants. Use a concurrent load tool, record p50, p95 and p99 latency, and run cold and warm cache.
- Test RLS and the MongoDB access layer with a deliberately broken scope. Include a noisy-tenant test.
- Run the 6 queries as real SQL and real aggregation pipelines. Compare full result sets, not only counts.
- Measure on-disk size with indexes, backup and restore time, and failover behaviour.
- Test GDPR erasure and EU-only residency. Check that backups and replicas stay in EU regions. Check that dropping partitions (PostgreSQL) or deleting documents (MongoDB) removes a tenant's data.
BLOCKED: PostgreSQL server (psql/postgres) — schema.sql could not be executed or timed on a real engine
BLOCKED: MongoDB server (mongod/mongosh/pymongo) — mongo_schema.js and queries_mongo.py could not be run on a real engine
MISSING DATA: Q4, Q5 and Q6 outcomes, row-count parity results, isolation result and sqlite stored size — output truncated; full text in tool_results/step7_6.txt and results.csv, not re-read
