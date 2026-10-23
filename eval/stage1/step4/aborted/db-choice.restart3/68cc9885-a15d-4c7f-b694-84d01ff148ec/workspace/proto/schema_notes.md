# schema_notes.md - event and dashboard prototype (step 6)
I read "multi-tenant" as Shared database with a tenant ID column or tenant field; if you meant Separate schema or database per tenant, the answer below may not apply.

## Engine availability (checked in the sandbox, no network)
- psql / postgres / mongod / mongosh: not found on PATH (`which` printed nothing) [S75]
- Python 3.11.17 with sqlite3 only; duckdb, pymongo, psycopg2 are NOT installed [S75]
- Consequence: schema.sql and mongo_schema.js were written but NOT executed on a real engine; syntax is unvalidated. Only generate_data.py ran (300,000 events, 5 tenants, 1,350 rollup rows, 71 MB of CSV+JSONL) and both Python files compile [S76]. queries_mongo.py builds all 6 pipelines as plain data (4,3,3,4,4,3 stages) [S76]. Any later timing in sqlite/Python is a PROXY - not engine performance, and is not evidence for choosing a database.

## Files
schema.sql, mongo_schema.js, generate_data.py, queries.sql, queries_mongo.py, data/ (events.csv/.jsonl, dashboard_daily.csv/.jsonl, tenants.csv/.jsonl)

## Design notes
1. Shared database, tenant_id on every row: PostgreSQL `events(tenant_id, event_id, ts, type, user_id, properties jsonb)` partitioned by RANGE(ts) monthly (Jan-Apr 2026 plus DEFAULT); MongoDB `events` with the same fields.
2. Indexes. PG: (tenant_id, ts DESC), (tenant_id, type, ts), GIN jsonb_path_ops on properties (extra write cost; drop if properties filters are rare). Mongo: {tenant_id:1, ts:-1}, {tenant_id:1,type:1,ts:1}, unique {tenant_id:1,event_id:1}. Every index leads with tenant_id so each query is tenant-scoped.
3. Primary key: PG must include the partition key, so PK = (tenant_id, event_id, ts); uniqueness of (tenant_id,event_id) alone is not enforced across partitions. Mongo enforces unique (tenant_id,event_id).
4. Rollups: `dashboard_daily(tenant_id, day, metric, value)` in both; metrics events, dau, purchases; PK/unique on (tenant_id, day, metric). Generator computes them from the events, so dashboard reads need no scan of raw events.
5. Isolation. PG: row-level security policies on events and dashboard_daily keyed on `current_setting('app.tenant_id')`; table owners/superusers bypass RLS unless FORCE ROW LEVEL SECURITY is added (not added yet - to do). MongoDB: no RLS; isolation relies on the tenant-scoped accessor `scoped()` in queries_mongo.py, so a coding error can leak data. This is a real design difference to carry into the risk table.
6. Region: tenants.region ('eu','non-eu') marks EU tenants. A shared cluster with EU and non-EU tenants in one region would break EU residency; the real design needs a separate EU cluster/project per cloud (to be assessed in the GDPR step), not just a column.
7. MongoDB option not used: time-series collection (timeField ts, metaField tenant_id) - skipped for row parity with PG.
8. Data: seed 42, tenant volume shares 55/25/12/6/2 %, Pareto-skewed users, 90 days from 2026-01-01, 6 event types. Query window for Q2 is 2026-03-02..2026-03-31.
9. Six paired queries (SQL / aggregation): Q1 daily active users, Q2 top event types 30 days, Q3 ordered funnel page_view->signup->purchase, Q4 rolling 7-day count (window function / $setWindowFields), Q5 latest 100 events, Q6 cross-tenant leak check (expect 1 tenant visible, 0 foreign rows).

## Not done / for the TEST step
- Load and run on real PostgreSQL and MongoDB: impossible here; use sqlite/Python proxy and label it PROXY.
- Mongo `$dateTrunc` and `$setWindowFields` need MongoDB 5.0+ [unverified]; mongoimport type inference for int/double fields is untested.
- A real 10 TB test (50 x 200 GB) needs real instances of RDS/Aurora/Cloud SQL/AlloyDB and Atlas, a 5,000 queries/min load generator, and EU-region deployments.
