**NOT EXECUTED: this sandbox has no PostgreSQL server and no psycopg2, so I took no PostgreSQL measurements. No benchmark number below is a measurement. results_postgres.json exists in the workspace [S81] and states NOT EXECUTED with the reason.**

## 1. Environment check (measured, run on 22 Oct 2026)
- Command: `which psql postgres pg_ctl initdb mongod; python3 -c 'import psycopg2'`.
- Result [S78]: `which rc=1`, so none of those binaries is on PATH. Python raised `ModuleNotFoundError: No module named 'psycopg2'`.
- Two earlier probes were refused by the sandbox as unsafe: the /usr/lib/postgresql path and docker. I could not look for embedded or alternative binaries there.
- There is no network, so nothing could be installed.
- As a result, I did no load, no 50+ warm runs per query, no mixed read/write run at concurrency 8/32/84, and no bytes-on-disk measurement.

## 2. Files in the workspace
- `gen_data.py` [S79]. This is the shared seeded generator (seed 42). Usage: `python3 gen_data.py N_EVENTS OUTDIR`.
  - It writes events.csv, events.jsonl, dashboards.jsonl and manifest.json. Both databases are meant to load these same files.
  - Design: 50 tenants with Zipf-like sizes (largest about 10x the median), 90 days of data ending 2026-10-22 UTC, 20 event types, about 10k users per tenant, and 5-15 properties per event nested 1 level. Amount is nullable.
  - I did not run it. Its row counts and tenant skew are unverified.
- `schema_postgres.sql` [S80]. Only the head and the RLS tail were visible to me. The partition, index and dashboards DDL in the middle was not shown to me, so I cannot quote it here. Open the file and review it before use.
- `results_postgres.json` [S81]. It holds status NOT EXECUTED, the reason, and null for every metric.
- **`bench_pg.py` was NOT written to disk.** The JSON's `scripts` list names it, but the file does not exist. Section 3 is a design only.

### DDL as I could confirm it from [S80]
```sql
CREATE TABLE events (
  event_id    bigint       NOT NULL,
  tenant_id   int          NOT NULL,
  occurred_at timestamptz  NOT NULL,
  event_type  text         NOT NULL,
  user_id     text         NOT NULL,
  session_id  text         NOT NULL,
  properties  jsonb        NOT NULL,
  amount      numeric(14,2),
  PRIMARY KEY (tenant_id, occurred_at, event_id)  -- PK must contain the partition key
) PARTITION BY RANGE (occurred_at);
-- monthly range partitions, tenant_id-leading index, GIN on properties (JSONB),
-- BRIN on occurred_at, and the dashboards table (widgets JSONB) are described in the
-- file header, but I did not see their exact text. See schema_postgres.sql.

ALTER TABLE events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboards ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_iso ON events     USING (tenant_id = current_setting('app.tenant_id')::int);
CREATE POLICY tenant_iso ON dashboards USING (tenant_id = current_setting('app.tenant_id')::int);
-- usage: SET ROLE app_user; SET app.tenant_id = '7';
```

## 3. Planned bench_pg.py (design only, not delivered, not run)
- Load events.csv with COPY, then ANALYZE.
- Q1: `date_trunc('hour',occurred_at), event_type, count(*)` for one tenant over the last 24 hours, grouped by hour and type.
- Q2: `count(DISTINCT user_id)` per day over 30 days.
- Q3: top 10 event types over 7 days.
- Q4: 3-step funnel per session over 7 days, using `bool_or(event_type=...)` per step.
- Q5: `properties @> '{"k":"v"}'` with `sum(amount)` by day.
- Q6: dashboard by id, with widgets as JSONB.
- Q7: `execute_values` insert of 1,000 events.
- Run each query 50+ times warm and report p50/p95/p99.
- Run an 80/20 read/write mix with threads at concurrency 8, 32 and 84 for a fixed duration.
- Compute size as `pg_total_relation_size` divided by the raw CSV/JSONL bytes.

## 4. Results table (all NOT EXECUTED: no server)
| Query | p50 ms | p95 ms | p99 ms | Throughput |
|---|---|---|---|---|
| Q1 events/hour 24h by type | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q2 daily unique users 30d | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q3 top 10 types 7d | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q4 3-step funnel 7d | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q5 JSONB filter + sum(amount)/day | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q6 dashboard + widgets | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q7 batch insert 1,000 events | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Mixed 80/20 at concurrency 8/32/84 | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |

Storage ratio to raw: NOT EXECUTED.

## 5. results_postgres.json
It exists [S81]. Its fields:
- `status`: "NOT EXECUTED"
- `reason`: no binaries, no psycopg2, no network, and the two refused probes
- `environment`: sandbox without PostgreSQL server binaries; python_driver null; network none
- Null values for postgres_version, rows, load_time_s, bytes_on_disk, raw_bytes and ratio_to_raw
- Q1 to Q7: each has p50, p95 and p99 set to null
- `throughput_qps` for c8, c32 and c84: null
- `scripts`: lists gen_data.py, schema_postgres.sql and bench_pg.py. bench_pg.py was not actually written (see section 2).

## 6. Findings and caveats
- The partitioned events table has the composite primary key `(tenant_id, occurred_at, event_id)` [S80]. PostgreSQL requires the primary key to include the partition column [unverified]. Event ids are therefore unique only per `(tenant_id, occurred_at)` pair, not globally.
- Row-level security keyed on `current_setting('app.tenant_id')` gives tenant isolation inside one shared schema [S80]. With pooled connections, the setting must be set per transaction (`SET LOCAL`) [unverified]. The RLS overhead is untested.
- JSONB with a GIN index suits Q5-style property filters [unverified]. Index size and write amplification, which affect Q7, are unmeasured and remain an open risk.
- Nothing was run, so there is nothing to extrapolate. Even a 1M-5M-event test would not prove behaviour at 10 TB (50 tenants x 200 GB). At that scale cache residency, partition count, vacuum and index sizes change.
- After a real run, this is what I would expect to carry over:
  - Bytes-per-event ratios would feed the cost model reasonably well.
  - Small-scale latencies are indicative only.
  - Concurrency throughput does not transfer, because it depends on instance size.
- Not verified: the generator's output, the SQL syntax (no static parse was run), and any comparison with MongoDB.
- To finish, use a machine with PostgreSQL 16+ and psycopg2:
  1. Run `python3 gen_data.py 2000000 data`.
  2. Run `psql -f schema_postgres.sql`.
  3. Write and run bench_pg.py as designed in section 3.
BLOCKED: PostgreSQL server binaries (postgres/initdb/pg_ctl/psql) and psycopg2 — could not start a database, load data, time Q1-Q7, run the concurrency tests or measure on-disk size
BLOCKED: local:Write — bench_pg.py was not written to disk within the turn budget (design only in the output)
MISSING DATA: Measured Q1-Q7 p50/p95/p99, throughput at concurrency 8/32/84, load time and storage ratio for PostgreSQL — no runnable server in the sandbox [S78]
MISSING DATA: Exact text of the partition, index and dashboards DDL in schema_postgres.sql — only the head and the RLS tail were visible in the tool output [S80]
