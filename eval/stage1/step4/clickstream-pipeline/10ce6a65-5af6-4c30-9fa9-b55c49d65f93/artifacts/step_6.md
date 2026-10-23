I read "cloud warehouse" as Snowflake; if you meant Google BigQuery or Amazon Redshift or Databricks / Azure Synapse, the answer below may not apply. I read "duplicate events" as Events sharing the same event_id, from Kafka at-least-once redelivery; if you meant Events identical on a composite key (user, timestamp, type, etc.) or Fully identical rows across all fields, the answer below may not apply. I read "finishes more than 30 minutes late" as Later than 30 minutes after the scheduled completion deadline or SLA time; if you meant Runtime exceeding the expected duration by 30 minutes or More than 30 minutes after the scheduled start time, the answer below may not apply. I read "one year of raw events" as 365 days × 30M × 2 KB, about 22 TB uncompressed; if you meant Compressed columnar storage in the warehouse, a fraction of 22 TB or Includes duplicates and replicas or retention overhead, the answer below may not apply.

**FILE STATUS.** runbook.md was written to the workspace by local:Write [S54]. That file has the same content as below. The only difference is that this output has fewer bare numbers and more tags, to satisfy the figure-tagging check. I had no turn left to rewrite the file. The next step should append sections 4-7 to runbook.md. If the tags matter, it should replace the file with this text. None of the SQL or shell commands was run, because there is no Snowflake or Kafka access. All of it is untested.

---

# Runbook: nightly clickstream DAU job (part 1: sections 1-3)

Table names are the ones in pipeline_code.md [S53]: RAW.CLICK_EVENTS, CLEAN.EVENTS, MART.DAU_BY_COUNTRY, OPS.JOB_RUNS. The pipeline_code.md output I read did not show fixed names for the Snowflake tasks, warehouse, Kafka connector or consumer group. They appear as <PLACEHOLDERS>. Triage step "Find the tasks" shows how to discover the task names. I did not see the OPS.JOB_RUNS column list, so the query uses SELECT * and ORDER BY on column two [unverified: column two is the business date, as in the sample audit row ('dau_nightly','2026-10-21','SUCCESS',…) from step 4].

## 1. What the alert means and the impact
- **Alert.** A PagerDuty incident with dedup_key `dau-nightly-<run_date>` and severity critical. The external watchdog (watchdog.py) raises it.
- **Rule.** The watchdog pages when the run for `run_date` has no SUCCESS row in OPS.JOB_RUNS by the SLA deadline plus 30 minutes (task). Exactly 30 minutes after the deadline is not a page. One minute later is a page. The simulation passed all 15 checks (watchdog_report.md) [S49]. The SLA deadline is a parameter. 04:00 UTC is an example value only.
- **Impact.** MART.DAU_BY_COUNTRY has no rows, or only some rows, for business day D (yesterday, UTC). The **DAU dashboard is therefore stale**. No raw data is lost. Kafka keeps the events, and RAW.CLICK_EVENTS keeps what was already loaded. The risk is delay, not loss, unless Kafka retention expires [unverified: retention not checked].
- **The page does not clear itself.** If the job finishes late, the watchdog logic still says "page" [S49, scenario 5]. Only a resolve payload with the same dedup_key closes the incident (section 5, part 2).
- **Duplicate pages.** Repeated checks reuse one dedup_key, so there should be one incident per run_date. Two incidents for one run_date is a watchdog bug (branch F). PagerDuty-side dedup was not observed, because nothing was sent [S49].

## 2. First 5 minutes (do in order)
Start every Snowflake session with `ALTER SESSION SET TIMEZONE = 'UTC';`. Business day D is yesterday in UTC. The time windows in the queries below (last day, last hour, last 6 hours) are adjustable defaults [unverified].

1. **Acknowledge** the page in PagerDuty. Note the run_date and the "last stage" from the alert's custom_details.

2. **Find the tasks and their state** (TASK_HISTORY):
```sql
SHOW TASKS IN ACCOUNT;   -- note names, schedule, state (started/suspended)
SELECT name, state, scheduled_time, query_start_time, completed_time, error_code, error_message
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
       SCHEDULED_TIME_RANGE_START => DATEADD('hour', -24, CURRENT_TIMESTAMP()),
       RESULT_LIMIT => 100))
ORDER BY scheduled_time DESC;
```
   - FAILED: error_message tells you the stage.
   - EXECUTING for a long time: that stage is slow.
   - No row for last night: the tasks are suspended, or the root task never ran.

3. **Read the pipeline run log** (OPS.JOB_RUNS):
```sql
SELECT * FROM OPS.JOB_RUNS
WHERE job_name = 'dau_nightly'   -- [unverified column name; drop the WHERE if it errors]
ORDER BY 2 DESC
LIMIT 5;
```
   Look for the run_date from the alert.
   - A SUCCESS row exists: the alert may be a late finish. Do the "layers" check below, then resolve (section 5).
   - A FAILED row exists: note the stage.
   - No row exists: the job never started, or it is still running.

4. **Is raw data arriving?** Latest ingest time in RAW.CLICK_EVENTS:
```sql
SELECT MAX(ingested_at) AS latest_ingest,
       DATEDIFF('minute', MAX(ingested_at), CURRENT_TIMESTAMP()) AS minutes_behind,
       COUNT(*) AS rows_last_hour
FROM RAW.CLICK_EVENTS
WHERE ingested_at >= DATEADD('hour', -1, CURRENT_TIMESTAMP());
```
   If minutes_behind is above about 15 [unverified threshold, tune it], or rows_last_hour is 0, ingestion is stalled: go to branch A. If the query errors on a column name, run `DESC TABLE RAW.CLICK_EVENTS;`.

5. **Kafka connector lag.** Snowflake shows only the effect (previous step). Read the lag on the Kafka side:
```bash
kafka-consumer-groups.sh --bootstrap-server <BROKER:PORT> --describe --group <CONNECTOR_CONSUMER_GROUP>
# LAG column per partition. Growing lag plus a flat latest_ingest means the connector is stalled.
```
   Also check the connector status with the Kafka Connect REST endpoint `GET /connectors/<CONNECTOR_NAME>/status` on <CONNECT_HOST> (or the Connect UI, or your team's approved tooling). Look for state RUNNING versus FAILED or PAUSED on the connector and on each task.

6. **Did last night's data land in each layer?**
```sql
SELECT 'RAW' AS layer, COUNT(*) AS n FROM RAW.CLICK_EVENTS
  WHERE event_ts >= DATEADD('day', -1, CURRENT_DATE()) AND event_ts < CURRENT_DATE()
UNION ALL
SELECT 'CLEAN', COUNT(*) FROM CLEAN.EVENTS WHERE event_date = DATEADD('day', -1, CURRENT_DATE())
UNION ALL
SELECT 'DAU rows', COUNT(*) FROM MART.DAU_BY_COUNTRY WHERE day = DATEADD('day', -1, CURRENT_DATE());
```
   Expect about 30M raw events per day (task). CLEAN should be a little lower, because duplicates are removed (the step 4 sample lost 3.45%) [S43]. DAU rows should be one per country seen. A zero in a layer shows which stage broke. The column names event_date and day are [unverified]; check with DESC TABLE if the query errors.

7. **Warehouse state:**
```sql
SHOW WAREHOUSES;   -- state, size, auto_suspend for <WAREHOUSE>
SELECT * FROM TABLE(INFORMATION_SCHEMA.WAREHOUSE_LOAD_HISTORY(
       DATE_RANGE_START => DATEADD('hour', -6, CURRENT_TIMESTAMP()),
       WAREHOUSE_NAME => '<WAREHOUSE>'))
ORDER BY start_time DESC;   -- queued load above 0 for a long time = undersized
```

8. **Decide.** Use the section 3 tree with what the steps above showed. If you cannot name the stage within 5 minutes (the target of this section), escalate (section 6, part 2). Post a short incident note: stage, evidence, next action.

## 3. Decision tree by stage
Start at the first question that matches. Fixes are in section 4 (part 2).

1. Can you run `SELECT 1;` in Snowflake? If not, or the Snowflake status page shows an incident, go to branch E. Otherwise continue.
2. Is the warehouse suspended or missing, or did a resource monitor trip (SHOW WAREHOUSES; the error text mentions "suspended" or "credit quota")? Go to branch D.
3. Is RAW.CLICK_EVENTS fresh and the connector healthy? If not, go to branch A. Otherwise continue.
4. Did dedup fail or run slowly (TASK_HISTORY; the CLEAN.EVENTS count for D is zero or low)? Go to branch B.
5. Is CLEAN.EVENTS fine but MART.DAU_BY_COUNTRY has no rows for D? Go to branch C.
6. Does OPS.JOB_RUNS show SUCCESS but you were paged, or was there no page when there should have been? Go to branch F.

**(A) Ingestion stalled** (RAW.CLICK_EVENTS stopped growing, Kafka lag growing)
- Connector FAILED or PAUSED: restart it through Kafka Connect and read its logs for auth or schema errors.
- Connector RUNNING but lag grows: it is behind. Check for Snowflake-side errors and add connector tasks or capacity. Whether one connector setup handles the assumed peak of about 1,041 events/s (step 1, calculated from 347 events/s average × 3) was never load-tested [unverified].
- Kafka itself is down: page the Kafka/streaming owner (section 6, part 2).
- After recovery, wait until lag reaches zero, then run the by-day rerun for D (section 4).

**(B) Dedup slow or failed** (the stage that writes CLEAN.EVENTS)
- FAILED with a SQL error: read error_message in TASK_HISTORY. Fix the cause and rerun the dedup stage only. It is an idempotent MERGE on event_id, tested in sqlite only, not in Snowflake [S43].
- EXECUTING much longer than normal: check the warehouse state step for queuing, and resize the warehouse (branch D) rather than killing the query. Kill it only if it has run far past its normal time [unverified: normal time not measured; the plan assumed about 45 minutes for the whole chain, step 1].
- CLEAN.EVENTS count is below the expected distinct event_ids: stop and escalate. Do not rerun blindly.

**(C) DAU failed** (the stage that writes MART.DAU_BY_COUNTRY)
- Dedup is SUCCESS but the DAU task FAILED or was skipped: read error_message and rerun the DAU stage for D. Part 2 gives the exact procedure. In sqlite a rerun left the DAU rows unchanged [S43].
- DAU rows exist but look wrong (very low, or a country missing): do not publish. Check CLEAN.EVENTS for D and escalate to the analytics owner.

**(D) Warehouse suspended or undersized**
- Suspended, by hand or by a resource monitor: resume it. Tell the cost owner if a resource monitor tripped. Raise the quota only with approval.
- Running but queued or slow: resize one step up for the rerun, then size back down (section 4).
- If the tasks themselves are suspended, resume them: children first, root last (section 4).

**(E) Snowflake outage**
- Confirm on the Snowflake status page and with a login attempt. Nothing can be run, so do not try workarounds.
- Keep the incident acknowledged and post status. Kafka keeps the events, but check that its retention is longer than the outage [unverified].
- When Snowflake recovers, check that the connector reconnected (branch A), then rerun D (section 4).

**(F) The watchdog itself is failing**
- Signs: no page although the job is late, a page for a job that succeeded, or two incidents for one run_date.
- Check in this order:
  1. Is the watchdog's scheduler running (last run time in its logs)?
  2. Can it read OPS.JOB_RUNS (credentials, network, warehouse for its query)?
  3. Is the PagerDuty routing key valid?
- The watchdog should fail closed: if it cannot read the state it should page, not stay silent. This is a design intent, not tested.
- While it is broken, run the OPS.JOB_RUNS query yourself. If there is no SUCCESS row for the run_date and now is later than the SLA deadline plus 30 minutes, treat the job as late.
- A page for a job that actually succeeded: confirm with the OPS.JOB_RUNS and layer-count queries, resolve the incident with the same dedup_key, and tell the watchdog owner.
- The watchdog and its scheduler were only simulated (watchdog_report.md) [S49]. They were never deployed or run against PagerDuty or Snowflake.

---
**Limits of this part:** no SQL or shell command was executed. Task, warehouse and connector names are placeholders. Column names beyond those seen in pipeline_code.md are unverified. The 15-minute stall threshold is unverified. Kafka retention was not checked.
BLOCKED: Snowflake account — none of the runbook SQL could be executed or validated
BLOCKED: Kafka / Kafka Connect access — consumer-group lag and connector status commands were not run
BLOCKED: local:Write — runbook.md was saved earlier [S54] with the pre-tagging text; no turn was left to rewrite it with the tag-tidied text in this output
MISSING DATA: Names of Snowflake tasks, warehouse, Kafka connector and consumer group — not seen in pipeline_code.md output read (S50-S53); left as placeholders
MISSING DATA: Full column list of OPS.JOB_RUNS and RAW.CLICK_EVENTS — only partly visible in truncated pipeline_code.md output (S53)
