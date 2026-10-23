I read "cloud warehouse" as Snowflake; if you meant Google BigQuery or Amazon Redshift or Databricks / Azure Synapse, the answer below may not apply. I read "duplicate events" as Events sharing the same event_id, from Kafka at-least-once redelivery; if you meant Events identical on a composite key (user, timestamp, type, etc.) or Fully identical rows across all fields, the answer below may not apply. I read "finishes more than 30 minutes late" as Later than 30 minutes after the scheduled completion deadline or SLA time; if you meant Runtime exceeding the expected duration by 30 minutes or More than 30 minutes after the scheduled start time, the answer below may not apply. I read "one year of raw events" as 365 days × 30M × 2 KB, about 22 TB uncompressed; if you meant Compressed columnar storage in the warehouse, a fraction of 22 TB or Includes duplicates and replicas or retention overhead, the answer below may not apply.

# MEMO: Nightly clickstream pipeline (Kafka -> Snowflake -> DAU by country -> PagerDuty)

## Objective, delivery plan and assumptions

**Objective.** Land 30M events/day (about 2 KB each, both from the task) from Kafka in Snowflake. Remove duplicates by event_id. Publish daily active users (DAU) per UTC day per country by the SLA deadline. Page the on-call engineer through PagerDuty if the job is more than 30 minutes past that deadline (task), even if the job itself is dead.

**Deliverables (whole task):**
- This architecture and tool-choice memo (this step).
- storage_estimate.md, the one-year storage estimate (next step).
- Transformation SQL, tested on a sample of real-looking data.
- Watchdog code.
- On-call runbook.

**Assumptions** (labelled assumptions, not facts):
- Warehouse = Snowflake.
- A duplicate = same event_id. Kafka is at-least-once, so redelivery is expected.
- "Late" = more than 30 minutes after the SLA deadline.
- "One year raw" = 365 × 30M × 2 KB, about 22 TB uncompressed.
- Each event carries event_id, user_id, event_ts (UTC), country (ISO code) and event_type. A null user_id is excluded from DAU. A null country becomes 'UNKNOWN'.
- The SLA deadline is a parameter (`SLA_DEADLINE_UTC`), example value 04:00 UTC (example given in the brief).
- The business day is the UTC calendar day of event_ts.
- Peak rate is about three times the average. This is a design assumption [unverified].
- The nightly run takes about 20 to 40 minutes on a Small warehouse. This is an estimate to confirm on real data [unverified].

**Risks (summary, detail in the risk table below):** redelivery after the look-back window; connector lag or stall; the watchdog itself dies; dirty or missing country data; cost drift, because Snowflake prices are not verified in this step.

## Numbers
- Daily volume: 30e6 × 2000 B = 60 GB/day (calc result).
- Yearly volume: 60 GB × 365 = 21,900 GB = 21.9 TB, headline about 22 TB uncompressed. The next step does the cost modelling.
- Average rate: 30,000,000 / 86,400 s = about 347 events/s (calculated). At the assumed peak factor of 3 that is 3 × 347 = about 1,041 events/s. Whether one connector setup handles this is [unverified]; to be load-tested.
- Look-back volume with a 3-day window (parameter [unverified]): 3 × 30M = 90M rows; 90M × 2 KB = 180 GB uncompressed scanned for dedup. Snowflake compresses columnar data, so the real scan is smaller.

## Options table (chosen vs rejected, with reason)

| Concern | Chosen | Rejected alternative(s) | Why chosen / why rejected |
|---|---|---|---|
| Ingestion | **Snowflake Kafka connector using Snowpipe Streaming** into RAW.CLICK_EVENTS (continuous landing) | (a) Kafka -> S3 files + Snowpipe/COPY; (b) Flink/Spark Structured Streaming stream processor | Chosen: no files, no extra service, low latency, managed inside Snowflake. RAW is ready before the nightly run starts. At-least-once delivery is accepted and duplicates are removed downstream. Rejected (a): extra object store, small-file/compaction concerns, one more component to monitor. Rejected (b): a cluster to run for a daily batch need; exactly-once is complex and would still be verified by dedup. |
| Orchestration | **Snowflake Tasks** (task graph: dedup -> DAU -> log row, plus a finalizer) | (a) Apache Airflow (MWAA/Composer); (b) dbt Core/Cloud scheduler | Chosen: three SQL steps that all run in Snowflake need no external orchestrator. Simplest option that meets the SLA. Rejected (a): a whole platform to host for a linear three-step job. Rejected (b): good for modelling, but it still needs a scheduler and does not remove the need for a by-day backfill procedure. It can be adopted later if the model count grows. |
| Dedup method | **Windowed MERGE** into CLEAN.EVENTS keyed on event_id, earliest ingested_at kept (ROW_NUMBER ... QUALIFY rank = 1), over a look-back window | (a) Dynamic table with a dedup query; (b) stateful dedup in a stream processor; (c) plain SELECT DISTINCT | Chosen: explicit, idempotent, rerunnable per day, window bounds cost. Rejected (a): less control over day-based reruns and backfills. Rejected (b): needs a stream processor (rejected above). Rejected (c): removes only fully identical rows; redelivered copies differ in ingested_at, so they would survive. |
| Alerting | **External watchdog** (scheduled cloud function or cron outside Snowflake) reads OPS.JOB_RUNS and calls the **PagerDuty** Events API | (a) Task failure notification / alert raised inside the job; (b) Airflow SLA-miss callback | Chosen: works when the job is hung, suspended or dead, because it fires on the absence of a success row. Rejected (a): a dead or never-started task sends nothing; kept only as a non-paging early warning to Slack/email. Rejected (b): Airflow is not in the stack, and a dead scheduler would also be silent. |
| Run-state store | **OPS.JOB_RUNS** table in Snowflake | Logs only | Queryable success/failure record per business date; the watchdog needs no log parsing. |

## Decision (architecture)

```
Kafka topic(s) --(Kafka connector, Snowpipe Streaming, continuous)--> RAW.CLICK_EVENTS   (duplicates expected)
Nightly Task graph (cron in UTC, per business day D = yesterday UTC):
  DEDUP_TASK : MERGE -> CLEAN.EVENTS      (window: last LOOKBACK_DAYS days ending D)
  DAU_TASK   : recompute MART.DAU_BY_COUNTRY for the same window days
  LOG_TASK   : INSERT SUCCESS row into OPS.JOB_RUNS (after DAU_TASK only)
  FINALIZER  : INSERT FAILED row if any task failed (early signal only)
Outside Snowflake:
  WATCHDOG (cloud function / cron, every 5 min [unverified]) --> reads OPS.JOB_RUNS --> PagerDuty
```

**Named objects:**

| Object | Purpose / key columns |
|---|---|
| **RAW.CLICK_EVENTS** | Landing table from the connector. Columns: RECORD_METADATA (VARIANT: topic, partition, offset), RECORD_CONTENT (VARIANT, the event) or flattened event_id, user_id, event_ts, country, event_type, payload, plus `ingested_at` (default CURRENT_TIMESTAMP). Append-only. Duplicates kept. |
| **CLEAN.EVENTS** | One row per event_id. Event columns plus event_date (UTC date of event_ts) and the earliest ingested_at. Clustered by event_date. |
| **MART.DAU_BY_COUNTRY** | event_date (UTC), country, dau = COUNT(DISTINCT user_id), computed_at. Unique on (event_date, country). |
| **OPS.JOB_RUNS** | run_id, job_name, business_date, status (STARTED / SUCCESS / FAILED), started_at, finished_at, rows_raw, rows_inserted, rows_dau, sla_deadline_utc. |

**Dedup logic.** Select from RAW the rows whose event_date is inside the window. Rank per event_id by ingested_at ascending, tie-break on Kafka partition and offset. Keep rank 1. MERGE into CLEAN.EVENTS ON event_id (target also restricted to the window dates for pruning) WHEN NOT MATCHED THEN INSERT. Matched rows are not updated, so the earliest ingested_at is preserved and a rerun adds nothing.

**Look-back window.** Default `LOOKBACK_DAYS` = 3 (a parameter, [unverified] starting value). Kafka redelivery typically happens within minutes to hours [unverified], so this is generous; validate by measuring the maximum redelivery gap in real RAW data. Each nightly run re-deduplicates the last 3 days (D minus 2, D minus 1, D). Late redelivered copies are discarded because their event_id is already in CLEAN. First-time late events inside the window are inserted.

**DAU.** For the window days, in one transaction: DELETE those dates from MART.DAU_BY_COUNTRY, then INSERT `SELECT event_date, COALESCE(country,'UNKNOWN'), COUNT(DISTINCT user_id) ... WHERE user_id IS NOT NULL GROUP BY event_date, country`. This is the trailing-window recompute: late data corrects earlier days automatically.

**Idempotent rerun by UTC day.** The tasks call a parameterised procedure: `CALL OPS.RUN_DAY(<business_date>, <lookback_days>)`. The scheduled run passes yesterday in UTC. A manual rerun passes any chosen date. The MERGE is insert-only on event_id and the mart is delete-and-insert by date, so running the same day any number of times gives the same result, and a partial failure leaves no mixed state. Backfill is a loop over dates. Each run writes a new JOB_RUNS row; the watchdog looks at the latest status per business_date.

## SLA timeline (UTC; the SLA is a parameter)

| Time (UTC) | Event |
|---|---|
| 00:00 [unverified] | Business day D ends. Continuous ingestion keeps landing late events. |
| 01:00 [unverified] | Nightly Task graph starts for D (cron `0 1 * * *` in UTC [unverified]). Gives one hour of grace for stragglers. |
| 01:00 to 01:40 [unverified] | DEDUP_TASK, then DAU_TASK (runtime estimate of 20 to 40 minutes, see assumptions). |
| about 01:45 [unverified] | LOG_TASK writes the SUCCESS row. **Expected finish.** |
| 04:00 (parameter, example from the brief) | **SLA deadline** (`SLA_DEADLINE_UTC`). About 2h15m of slack for retries (04:00 minus 01:45). |
| 04:00 to 04:30 | Grace period. The watchdog keeps polling but does not page. An optional Slack warning may go out if there is no SUCCESS row. |
| **04:30** | **Page at deadline + 30 min** (`PAGE_AFTER_MIN` = 30, from the task). If there is no SUCCESS row for D, the watchdog triggers PagerDuty (severity critical, dedup_key = `clickstream-dau-<D>`). |

Chicago is UTC minus 5 in summer time and UTC minus 6 in winter [unverified]. Keep all schedules in UTC to avoid daylight-saving shifts.

## External watchdog design

- **Where it runs:** outside Snowflake and outside the Task graph: a scheduled cloud function (for example AWS Lambda on EventBridge, or Cloud Scheduler plus Cloud Function) or cron on a separate host. It runs every 5 minutes [unverified], using a read-only Snowflake user limited to OPS.JOB_RUNS and a RAW freshness view. Credentials sit in a secrets manager.
- **Checks on each run:**
  1. Compute the expected business_date (yesterday UTC) and `deadline = today UTC date + SLA_DEADLINE_UTC`.
  2. If now is later than deadline + 30 min and no row with status = SUCCESS exists for that business_date, trigger PagerDuty. This covers a failed, hung, never-started or suspended job.
  3. If the Snowflake query fails or times out, trigger PagerDuty (**fail closed**: being unable to check is also a page).
  4. Optional freshness check: `MAX(ingested_at)` in RAW.CLICK_EVENTS older than a threshold gives a warning (connector stalled).
- **PagerDuty:** Events API with `dedup_key = clickstream-dau-<business_date>` so repeated runs do not open new incidents. When a SUCCESS row appears, the watchdog sends a `resolve` for the same key.
- **Its own heartbeat:** after every successful check, the watchdog pings an independent dead-man's-switch (for example Healthchecks.io, Cronitor, or a CloudWatch alarm on missing invocations) with a grace of 15 minutes [unverified]. If pings stop, that service pages the on-call through a separate PagerDuty integration. A dead watchdog is therefore noticed.
- **Early warning (non-paging):** a Snowflake notification integration to Slack/email on task error, and a FAILED row from the finalizer. They help diagnosis, but the page does not depend on them.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Redelivery or late events arrive beyond the look-back window (duplicates or missed events). | Measure the maximum redelivery gap. Raise LOOKBACK_DAYS if needed. Weekly reconciliation counting duplicate event_ids in CLEAN (expected zero). |
| Connector lag or stall leaves RAW incomplete at the nightly start. | RAW freshness check in the watchdog. One hour of grace. Rerun by day after recovery. |
| Watchdog or its schedule dies. | Its own heartbeat (see watchdog section). Test the alert path in a game day. |
| Snowflake warehouse suspended, resource monitor limit hit, or credits exhausted. | Resource monitor with a notify threshold below the suspend threshold. Watchdog fails closed. |
| Missing or invalid country or user_id distorts DAU. | Map null country to 'UNKNOWN'. Exclude null user_id. Track both rates as data-quality metrics. |
| Cost and storage figures are not verified. | The next step dates its sources. No price is claimed in this memo. |
| The runtime estimate is wrong. | Test on a sample, then load-test at real volume before go-live. The SLA slack is wide. |
| Interpretation differs (BigQuery/Redshift, composite-key duplicates). | Assumptions are stated at the top; the design is portable in concept, but the answer does not apply as written. |

## Why this is the simplest design that meets the SLA
- One platform (Snowflake) holds ingestion, transformation and state. The only external component is the watchdog, which must be external to be reliable.
- The nightly work is a three-step SQL chain, finishing about 45 minutes after start (assumed) against the SLA deadline.
- Rerun, backfill and late-data correction all use one procedure parameterised by day.

Sources: no web source was used in this step. Figures tagged [unverified] are engineering judgement or my own knowledge. Calculated figures: 60 GB/day (calc tool), 21.9 TB/year, 347 events/s, and the 90M-row / 180 GB look-back, all derived from the task's numbers.
