**NOT EXECUTED: no MongoDB benchmark was run, so this step has no measurements. Every metric in results_mongodb.json is null. The reason is that the sandbox has no MongoDB server and no Python driver. I checked this on 22 Oct 2026 and it is confirmed [S104].**

## 1. Environment check (measured, 22 Oct 2026)
- Probe [S104]: `command -v` found no mongod, no mongosh, no mongo and no mongos. All four are reported MISSING.
- Python [S104]: `ModuleNotFoundError: No module named 'pymongo'`. The same error appears for `mongomock`, so there is no in-process fake either.
- There is no network, so nothing could be installed. Step 5 found the same for PostgreSQL: no binaries and no psycopg2 [S78].
- Static check [S104]: `python3 -m py_compile mongo_bench.py gen_data.py` printed COMPILE_OK. This supersedes my earlier caveat. The syntax of both scripts is valid, but neither has run, so their behaviour is untested.
- File sizes [S104]: mongo_bench.py is 11,079 bytes and results_mongodb.json is 1,554 bytes.
- Not done: no load, no 50+ warm runs per query, no mixed read/write run at concurrency 8/32/84, and no bytes-on-disk measurement.

## 2. Files in the workspace
- `gen_data.py`: the shared seed-42 generator from step 5 [S79]. It compiles [S104] but has not been run, so its row counts and tenant skew are unverified. Use `python3 gen_data.py 2000000 data`. It writes events.jsonl and dashboards.jsonl, which MongoDB should load. Step 5 loads the same files, so the data would be identical.
- `mongo_bench.py`: written as [S101] and compiles [S104]. It is meant to create the collections, load the data, time Q1-Q7, run the mixed workload and write the results JSON. I could not re-read it after writing it. The design below is the intent and may differ in detail from the file, so review the file before use.
- `results_mongodb.json` [S103]: status NOT EXECUTED, with null for every metric. Its text says there is no mongod and no pymongo, and [S104] now supports both statements.

## 3. Schema and collection setup (code, not executed)
```javascript
// Tenant isolation choice: ONE shared collection, tenant_id as the leading key of every index.
// 50 tenants is too few to justify database-per-tenant. The largest tenants could get dedicated collections.
// Isolation is enforced in the app/query layer. Atlas has no row-level security, unlike Postgres RLS (step 5 DDL [S80]).
// Use a mandatory tenant-filter wrapper.
db.createCollection("events", {
  validator: {$jsonSchema: {
    bsonType: "object",
    required: ["tenant_id","ts","event_type","user_id","session_id","properties"],
    properties: {
      tenant_id:{bsonType:"int"}, ts:{bsonType:"date"},
      event_type:{bsonType:"string"}, user_id:{bsonType:"string"},
      session_id:{bsonType:"string"}, properties:{bsonType:"object"},
      amount:{bsonType:["decimal","null"]}
    }}}
});
db.events.createIndex({tenant_id:1, ts:-1});                    // main access path
db.events.createIndex({tenant_id:1, event_type:1, ts:-1});      // Q3
db.events.createIndex({tenant_id:1, session_id:1, ts:1});       // Q4
db.events.createIndex({tenant_id:1, "properties.k":1, ts:-1});  // Q5 (one hot property)

// Variant to test: time-series collection
db.createCollection("events_ts", {timeseries:{timeField:"ts", metaField:"tenant_id", granularity:"hours"}});
// Caveat: time-series collections limit updates, deletes and some index types [unverified].

db.createCollection("dashboards", {validator:{$jsonSchema:{
  bsonType:"object", required:["tenant_id","name","owner","widgets","updated_at"],
  properties:{ widgets:{bsonType:"array", items:{bsonType:"object",
    required:["widget_id","type","query_def"]}}}}}});
db.dashboards.createIndex({tenant_id:1, _id:1});
// Widgets are embedded, so Q6 is a single-document read.
```

## 4. Aggregation pipelines (design, not executed)
```javascript
// Q1 events per hour by type, last 24h
[{$match:{tenant_id:T, ts:{$gte:now24h}}},
 {$group:{_id:{h:{$dateTrunc:{date:"$ts",unit:"hour"}}, t:"$event_type"}, n:{$sum:1}}}]
// Q2 daily unique users, 30d
[{$match:{tenant_id:T, ts:{$gte:now30d}}},
 {$group:{_id:{d:{$dateTrunc:{date:"$ts",unit:"day"}}, u:"$user_id"}}},
 {$group:{_id:"$_id.d", users:{$sum:1}}}]
// Q3 top 10 event types, 7d
[{$match:{tenant_id:T, ts:{$gte:now7d}}},{$group:{_id:"$event_type",n:{$sum:1}}},{$sort:{n:-1}},{$limit:10}]
// Q4 3-step funnel per session, 7d
[{$match:{tenant_id:T, ts:{$gte:now7d}, event_type:{$in:[A,B,C]}}},
 {$group:{_id:"$session_id", s:{$addToSet:"$event_type"}}},
 {$match:{s:{$all:[A,B,C]}}},{$count:"completed"}]
// This checks that all three steps occurred, not their order. An ordered funnel needs min(ts) per step.
// Q5 JSON property filter + sum(amount)/day
[{$match:{tenant_id:T, "properties.k":V, ts:{$gte:now30d}}},
 {$group:{_id:{$dateTrunc:{date:"$ts",unit:"day"}}, total:{$sum:"$amount"}}}]
// Q6  db.dashboards.findOne({tenant_id:T, _id:D})
// Q7  db.events.insertMany(batch_of_1000, {ordered:false})
```

## 5. Results table (all NOT EXECUTED, no server)
| Query | p50 ms | p95 ms | p99 ms | Throughput |
|---|---|---|---|---|
| Q1 events/hour by type, 24h | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q2 daily unique users, 30d | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q3 top 10 event types, 7d | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q4 3-step funnel, 7d | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q5 JSON filter + sum(amount)/day | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q6 dashboard with widgets | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q7 insert 1,000 events | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Mixed read/write workload at concurrency 8 / 32 / 84 | n/a | n/a | n/a | NOT EXECUTED |

Load time, bytes on disk and ratio to raw: NOT EXECUTED. All are null in results_mongodb.json [S103].

## 6. Findings and caveats
- **No MongoDB performance claim can be made from this step.** The PostgreSQL side is also NOT EXECUTED (step 5). There is no like-for-like comparison, so the recommendation memo must not cite benchmark numbers from these prototypes.
- **Ergonomics (design judgement, not measured):**
  - Embedded widgets make Q6 a single-document read.
  - Q2 and Q4 need `$group` aggregation stages that can be memory-heavy, so `allowDiskUse` may be needed [unverified].
  - Exact distinct-user counting (Q2) is expensive in both databases.
- **Tenant isolation:** MongoDB has no row-level security. Isolation depends on application code always adding `tenant_id`, which is a real risk for a 12-person team. Postgres RLS (step 5 DDL [S80]) is stronger on this point. Atlas offers database-level roles, so database-per-tenant is the stronger-isolation option.
- **Time-series option:** untested here. Its update and delete limits matter for GDPR erasure requests.
- **Scripts:** mongo_bench.py and gen_data.py pass a syntax compile [S104] but have never been executed. Treat them as unproven.
- **Extrapolation:** nothing was run, so nothing extrapolates. Even a 1M-5M event test would not prove behaviour at 10 TB (50 x 200 GB = 10,000 GB). If run, bytes-per-document ratios would feed the cost model reasonably well. Small-scale latencies would be indicative only. Concurrency throughput depends on the Atlas tier and would not transfer.
- **To finish:** on a machine with a current mongod and pymongo [unverified], run `python3 gen_data.py 2000000 data`, review mongo_bench.py, run `python3 mongo_bench.py`, and keep the JSON it writes.
BLOCKED: MongoDB server (mongod/mongosh) and pymongo driver, local sandbox — could not start a server, load data, run Q1-Q7, run the concurrency tests or measure on-disk size
MISSING DATA: Measured MongoDB Q1-Q7 p50/p95/p99, throughput at concurrency 8/32/84, load time, bytes on disk and ratio to raw — no runnable server in the sandbox [S104]
