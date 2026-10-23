I read "cloud warehouse" as Snowflake; if you meant Google BigQuery or Amazon Redshift or Databricks / Azure Synapse, the answer below may not apply. I read "duplicate events" as Events sharing the same event_id, from Kafka at-least-once redelivery; if you meant Events identical on a composite key (user, timestamp, type, etc.) or Fully identical rows across all fields, the answer below may not apply. I read "finishes more than 30 minutes late" as Later than 30 minutes after the scheduled completion deadline or SLA time; if you meant Runtime exceeding the expected duration by 30 minutes or More than 30 minutes after the scheduled start time, the answer below may not apply. I read "one year of raw events" as 365 days x 30M x 2 KB, about 22 TB uncompressed; if you meant Compressed columnar storage in the warehouse, a fraction of 22 TB or Includes duplicates and replicas or retention overhead, the answer below may not apply.

# Runbook: nightly clickstream DAU job (part 1: alert meaning, first 5 minutes, decision tree)

Table names used, all from pipeline_code.md [S53]: RAW.CLICK_EVENTS, CLEAN.EVENTS, MART.DAU_BY_COUNTRY, OPS.JOB_RUNS. Task, warehouse, connector and consumer-group names were not seen in pipeline_code.md, so they appear as <PLACEHOLDERS>; the TASK_HISTORY query below finds the task names. No SQL here was run in Snowflake (no account); it is untested there.

## 1. What the alert means and the impact

1. **Alert:** a PagerDuty incident with dedup_key `dau-nightly-<run_date>`, severity critical, raised by the external watchdog (watchdog.py).
2. **Rule:** the watchdog pages when the run for `run_date` has no SUCCESS row in OPS.JOB_RUNS by SLA deadline + 30 min (task). Exactly +30 min is not a page; +31 min is. The simulation passed all 15 checks [S49]. The SLA deadline is a parameter; 04:00 UTC is an example value only (from the brief).
3. **Impact:** MART.DAU_BY_COUNTRY has no rows, or only part of them, for business day D (yesterday, UTC), so the DAU dashboard is stale. No raw data is lost: Kafka keeps the events and RAW.CLICK_EVENTS keeps what was loaded. The risk is delay, not loss, unless Kafka retention expires [unverified: retention not checked].
4. **The page does not clear itself.** If the job finishes late, the watchdog logic still says "page" (late-finish scenario in watchdog_report.md [S49]). Only a resolve payload with the same dedup_key closes the incident (see "Verify and resolve" in part 2).
5. **Duplicate pages:** repeated checks reuse one dedup_key, so expect one incident per run_date. Two incidents for one run_date is a watchdog bug (go to branch F). PagerDuty-side dedup was not observed, because nothing was sent [S49].

## 2. First 5 minutes (do in order)

Start every Snowflake session with `ALTER SESSION SET TIMEZONE = 'UTC';`. Business day D = yesterday UTC.

1. **Acknowledge** the page in PagerDuty. Note the run_date and the "last stage" from the alert's custom_details.

2. **Find the tasks and their state** (TASK_HISTORY, last day; the window and row limit are my choice [unverified]):
```sql
SHOW TASKS IN ACCOUNT;   -- note names, schedule, state (started/suspended)
SELECT name, state, scheduled_time, query_start_time, completed_time, error_code, error_message
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
       SCHEDULED_TIME_RANGE_START => DATEADD('hour', -24, CURRENT_TIMESTAMP()),
       RESULT_LIMIT => 100))
ORDER BY scheduled_time DESC;
```
   - FAILED: error_message tells you the stage.
   - EXECUTING for a long time: the stage is slow.
   - No row for last night: the tasks are suspended, or the root task never ran.

3. **Pipeline run log** (OPS.JOB_RUNS):
```sql
SELECT * FROM OPS.JOB_RUNS
WHERE job_name = 'dau_nightly'   -- [unverified column name; drop the WHERE if it errors]
ORDER BY 2 DESC                  -- [unverified: column 2 is the business date, as in the step 4 audit row]
LIMIT 5;
```
   - A SUCCESS row for the alert's run_date exists: the alert may be a late finish. Go to step 6, then resolve (part 2).
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
   If minutes_behind is above about 15 [unverified threshold, tune it], or rows_last_hour is 0, ingestion is stalled: go to branch A. If it errors on a column name, run `DESC TABLE RAW.CLICK_EVENTS;`.

5. **Kafka connector lag.** Snowflake only shows the effect (step 4). Read the lag on the Kafka side:
```bash
kafka-consumer-groups.sh --bootstrap-server <BROKER:PORT> --describe --group <CONNECTOR_CONSUMER_GROUP>
# LAG column per partition. Growing lag plus a flat step-4 result means the connector is stalled.
```
   Also check the connector status through your team's approved Kafka Connect tooling or UI (the REST path is `/connectors/<CONNECTOR_NAME>/status` on <CONNECT_HOST>). Look for RUNNING versus FAILED or PAUSED on the connector and on each task.

6. **Did last night's data land in each layer?**
```sql
SELECT 'RAW' AS layer, COUNT(*) AS n FROM RAW.CLICK_EVENTS
  WHERE event_ts >= DATEADD('day', -1, CURRENT_DATE()) AND event_ts < CURRENT_DATE()
UNION ALL
SELECT 'CLEAN', COUNT(*) FROM CLEAN.EVENTS WHERE event_date = DATEADD('day', -1, CURRENT_DATE())
UNION ALL
SELECT 'DAU rows', COUNT(*) FROM MART.DAU_BY_COUNTRY WHERE day = DATEADD('day', -1, CURRENT_DATE());
```
   Expect about 30M raw events per day (task figure). CLEAN should be a little lower, because duplicates are removed (the step 4 sample lost 3.45% [S43]). DAU rows should be one per country seen. A zero in a layer shows which stage broke. Column names event_date and day are [unverified]; check with DESC TABLE if the query errors.

7. **Warehouse state:**
```sql
SHOW WAREHOUSES;   -- state, size, auto_suspend for <WAREHOUSE>
SELECT * FROM TABLE(INFORMATION_SCHEMA.WAREHOUSE_LOAD_HISTORY(
       DATE_RANGE_START => DATEADD('hour', -6, CURRENT_TIMESTAMP()),
       WAREHOUSE_NAME => '<WAREHOUSE>'))
ORDER BY start_time DESC;   -- queued load above 0 for a long time = undersized
```

8. **Decide.** Use the decision tree below with what steps 2-7 showed. If you cannot name the stage within the 5 minutes, escalate (see "Escalation" in part 2). Post a short incident note: stage, evidence, next action.

## 3. Decision tree by stage

Start at the first question that matches. Fixes are in "Fixes" in part 2.

1. Can you run a trivial query (`SELECT CURRENT_TIMESTAMP();`) in Snowflake? If not, or the Snowflake status page shows an incident, go to branch E. Otherwise continue.
2. Is the warehouse suspended or missing, or did a resource monitor trip (SHOW WAREHOUSES; the error text mentions "suspended" or "credit quota")? Go to branch D.
3. Is RAW.CLICK_EVENTS fresh (step 4) and the connector healthy (step 5)? If not, go to branch A. Otherwise continue.
4. Did dedup fail or run slowly (TASK_HISTORY; the CLEAN.EVENTS count for D is 0 or low)? Go to branch B.
5. Is CLEAN.EVENTS fine but MART.DAU_BY_COUNTRY has no rows for D? Go to branch C.
6. Does OPS.JOB_RUNS show SUCCESS but you were paged, or was there no page when there should have been? Go to branch F.

**(A) Ingestion stalled** (RAW.CLICK_EVENTS stopped growing, Kafka lag growing)
- Connector FAILED or PAUSED: restart it through Kafka Connect and read its logs for auth or schema errors.
- Connector RUNNING but lag grows: it is behind. Check for Snowflake-side errors and add connector tasks or capacity. Whether one connector setup handles the assumed peak of about 1,041 events/s (3 x 347 events/s, step 1 calc) is [unverified]; it was never load-tested.
- Kafka itself is down: page the Kafka/streaming owner (see "Escalation" in part 2).
- After recovery, wait until lag reaches zero, then run the by-day rerun for D (see "Fixes" in part 2).

**(B) Dedup slow or failed** (stage that writes CLEAN.EVENTS)
- FAILED with a SQL error: read error_message in TASK_HISTORY. Fix the cause and rerun the dedup stage only. It is an idempotent MERGE on event_id (tested in sqlite only, not in Snowflake) [S43].
- EXECUTING much longer than normal: check step 7 for queuing, and resize the warehouse (branch D) rather than killing the query. Kill it only if it has run far past its normal time [unverified: normal time not measured; the step 1 plan assumed about 45 minutes for the whole chain, also unverified].
- CLEAN.EVENTS count is below the expected distinct event_ids: stop and escalate. Do not rerun blindly.

**(C) DAU failed** (stage that writes MART.DAU_BY_COUNTRY)
- Dedup is SUCCESS but the DAU task FAILED or was skipped: read error_message and rerun the DAU stage for D. Part 2 gives the exact procedure. In sqlite, a rerun left the DAU rows unchanged [S43].
- DAU rows exist but look wrong (very low, or a country missing): do not publish. Check CLEAN.EVENTS for D and escalate to the analytics owner.

**(D) Warehouse suspended or undersized**
- Suspended, by hand or by a resource monitor: resume it. Tell the cost owner if a resource monitor tripped, and raise the quota only with approval.
- Running but queued or slow: resize one step up for the rerun, then size back down (see "Fixes" in part 2).
- If the tasks themselves are suspended, resume them: children first, root last.

**(E) Snowflake outage**
- Confirm on the Snowflake status page and with a login attempt. Nothing can be run, so do not try workarounds.
- Keep the incident acknowledged and post status. Kafka keeps the events, but check that its retention is longer than the outage [unverified].
- When Snowflake recovers, check the connector reconnected (branch A), then rerun D.

**(F) The watchdog itself is failing**
- Signs: no page although the job is late, a page for a job that succeeded, or two incidents for one run_date.
- Check in this order: (i) is the watchdog's scheduler running (last run time in its logs)? (ii) can it read OPS.JOB_RUNS (credentials, network, warehouse for its query)? (iii) is the PagerDuty routing key valid?
- The watchdog should fail closed: if it cannot read the state it should page, not stay silent. This is a design intent, not tested.
- While it is broken, run the OPS.JOB_RUNS query (step 3) yourself. If there is no SUCCESS row for the run_date and now is later than SLA deadline + 30 min, treat the job as late.
- A page for a job that actually succeeded: confirm with steps 3 and 6, resolve the incident with the same dedup_key, and tell the watchdog owner.
- The watchdog and its scheduler were only simulated (watchdog_report.md) and never deployed or run against PagerDuty or Snowflake [S49].

---
**Limits of this part:** no SQL was executed in Snowflake. Task, warehouse and connector names are placeholders. OPS.JOB_RUNS and RAW.CLICK_EVENTS column names beyond those seen in pipeline_code.md are unverified. The 15-minute stall threshold is unverified. Kafka retention was not checked.

---

# Runbook part 2: fixes, backfill, verification, escalation, post-incident (sections 4-7)

Table and column names come from snowflake_pipeline.sql: RAW.CLICK_EVENTS, CLEAN.EVENTS (event_id, user_id, country, event_type, event_ts, ingested_at, event_date), MART.DAU_BY_COUNTRY (day, country, dau, computed_at), OPS.JOB_RUNS (job_name, business_date, status, rows_in, rows_loaded, duplicates_removed, started_at, finished_at). The MART date column is `day` everywhere in this runbook. Names resolved from snowflake_pipeline.sql by script at write time: root task <ROOT_TASK>, dedup task <DEDUP_TASK>, DAU task <DAU_TASK>, marker task <JOB_RUN_MARKER_TASK>, warehouse <WAREHOUSE>. Any name still shown in <ANGLE BRACKETS> is not defined in that file and must be filled in. None of the SQL or shell here has been run (no Snowflake, Kafka or PagerDuty access). Test each command in a non-production schema first.

## 4. Fixes (pick the branch from the decision tree in section 3)
Start every session with `ALTER SESSION SET TIMEZONE = 'UTC';`. Business day D is yesterday in UTC.

### Fix A: resume suspended tasks
```sql
SELECT SYSTEM$TASK_DEPENDENTS_ENABLE('<ROOT_TASK>');   -- resumes the dependents, not the root
ALTER TASK <ROOT_TASK> RESUME;
SHOW TASKS IN SCHEMA <DB>.<SCHEMA>;                  -- state must say started
```

### Fix B: resume or resize the warehouse
```sql
ALTER WAREHOUSE <WAREHOUSE> RESUME IF SUSPENDED;
-- Undersized (queued load stays above zero in the section 2 query): go up one size.
ALTER WAREHOUSE <WAREHOUSE> SET WAREHOUSE_SIZE = '<NEXT_SIZE_UP>';
-- After the incident, revert:
ALTER WAREHOUSE <WAREHOUSE> SET WAREHOUSE_SIZE = '<NORMAL_SIZE>';
```
A resize applies to new queries only; running queries finish on the old size. Write the resize in the incident notes so that it is reverted.

### Fix C: restart a stalled Kafka connector (ingestion branch)
Use the Kafka Connect REST API on <CONNECT_HOST>:<PORT>. First call the status endpoint for <CONNECTOR>. Then call its restart endpoint with the query options includeTasks=true and onlyFailed=true. If the connector is healthy but lag keeps growing, escalate (section 6). Check the topic retention before the lag gets older than the retention period [unverified: retention was not checked]. Events past retention are lost.

### Fix D: rerun a stage
A rerun is safe because each stage is idempotent: dedup uses a MERGE that inserts only event_ids not yet in CLEAN.EVENTS, and DAU is rewritten for the day. If CLEAN.EVENTS looks wrong, do not rerun blindly; escalate.
```sql
EXECUTE TASK <ROOT_TASK>;     -- whole graph, business date = yesterday UTC
-- or one stage, in this order:
EXECUTE TASK <DEDUP_TASK>;
EXECUTE TASK <DAU_TASK>;
EXECUTE TASK <JOB_RUN_MARKER_TASK>;
```
The graph computes yesterday in UTC (SET business_date in snowflake_pipeline.sql; the file says to pass it explicitly for backfills). To fix any other day, use Fix E.

### Fix E: idempotent backfill for one UTC day
Use it when the task graph cannot be rerun for day D, or to repair an earlier day. Running it twice gives the same result: the MERGE inserts only event_ids not yet in CLEAN.EVENTS, and the DAU step deletes and re-inserts the day inside one transaction.

Prerequisite: RAW.CLICK_EVENTS rows for the day exist (run the count query from section 2). If they do not, fix ingestion (Fix C) first; a backfill cannot create events that were never loaded. RAW.CLICK_EVENTS column names below are assumed to match CLEAN.EVENTS [unverified].
```sql
ALTER SESSION SET TIMEZONE = 'UTC';
SET backfill_day = '2026-10-21';   -- EDIT: the UTC day to repair (example: the day before the run date, 22 Oct 2026)

-- Step A. Before-counts: save them in the incident notes.
SELECT 'RAW' AS layer, COUNT(*) AS n, COUNT(DISTINCT event_id) AS distinct_ids
  FROM RAW.CLICK_EVENTS
  WHERE event_ts >= $backfill_day::DATE AND event_ts < DATEADD('day', 1, $backfill_day::DATE)
UNION ALL
SELECT 'CLEAN', COUNT(*), COUNT(DISTINCT event_id) FROM CLEAN.EVENTS WHERE event_date = $backfill_day::DATE
UNION ALL
SELECT 'DAU rows', COUNT(*), NULL FROM MART.DAU_BY_COUNTRY WHERE day = $backfill_day::DATE;

-- Step B. Dedup, then rewrite the day's DAU, in one transaction.
BEGIN TRANSACTION;
MERGE INTO CLEAN.EVENTS t
USING (
  SELECT event_id, user_id, country, event_type, event_ts, ingested_at, event_ts::DATE AS event_date
  FROM RAW.CLICK_EVENTS
  WHERE event_ts >= $backfill_day::DATE AND event_ts < DATEADD('day', 1, $backfill_day::DATE)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY ingested_at) = 1   -- earliest copy wins
) s ON t.event_id = s.event_id
WHEN NOT MATCHED THEN INSERT (event_id, user_id, country, event_type, event_ts, ingested_at, event_date)
  VALUES (s.event_id, s.user_id, s.country, s.event_type, s.event_ts, s.ingested_at, s.event_date);

DELETE FROM MART.DAU_BY_COUNTRY WHERE day = $backfill_day::DATE;
INSERT INTO MART.DAU_BY_COUNTRY (day, country, dau, computed_at)
SELECT event_date, country, COUNT(DISTINCT user_id), CURRENT_TIMESTAMP()
FROM CLEAN.EVENTS WHERE event_date = $backfill_day::DATE
GROUP BY event_date, country;
COMMIT;      -- if any statement errored: ROLLBACK; and escalate

-- Step C. Record the run so the watchdog sees SUCCESS (only after the section 5 checks pass).
INSERT INTO OPS.JOB_RUNS (job_name, business_date, status, rows_in, rows_loaded, duplicates_removed, started_at, finished_at)
SELECT 'dau_nightly', $backfill_day::DATE, 'SUCCESS',
  (SELECT COUNT(*) FROM RAW.CLICK_EVENTS
    WHERE event_ts >= $backfill_day::DATE AND event_ts < DATEADD('day', 1, $backfill_day::DATE)),
  (SELECT COUNT(*) FROM CLEAN.EVENTS WHERE event_date = $backfill_day::DATE),
  NULL, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP();
```
Notes:
- The MERGE matches on event_id alone. If an earlier copy sits in CLEAN.EVENTS under another event_date, it is skipped. That is correct for the event_id rule.
- A backfill of an old day scans CLEAN.EVENTS on event_id, so it is slower than the nightly run (which uses a look-back window of lookback_days). Resize first (Fix B) if the warehouse is small.
- Do not backfill several days in parallel. Go one day at a time, oldest first.
- Step C is a manual marker: mention it in the incident notes. Leave any FAILED or partial row for the same business_date as history.

## 5. Verification after the fix, and how to resolve the page
### Verify (all must pass before you resolve)
```sql
ALTER SESSION SET TIMEZONE = 'UTC';
SET d = (SELECT DATEADD('day', -1, CURRENT_DATE()));   -- or the backfill day

-- (a) Row counts: CLEAN should equal distinct RAW event_ids for the day.
SELECT (SELECT COUNT(DISTINCT event_id) FROM RAW.CLICK_EVENTS
         WHERE event_ts >= $d AND event_ts < DATEADD('day', 1, $d)) AS raw_distinct_ids,
       (SELECT COUNT(*) FROM CLEAN.EVENTS WHERE event_date = $d)   AS clean_rows;

-- (b) No duplicate event_ids remain (expect zero rows).
SELECT event_id, COUNT(*) AS copies FROM CLEAN.EVENTS WHERE event_date = $d
GROUP BY event_id HAVING COUNT(*) > 1 LIMIT 20;

-- (c) DAU for the day vs the previous day, by country.
SELECT COALESCE(a.country, b.country) AS country, a.dau AS dau_d, b.dau AS dau_prev,
       ROUND(100 * (a.dau - b.dau) / NULLIF(b.dau, 0), 1) AS pct_change
FROM (SELECT country, dau FROM MART.DAU_BY_COUNTRY WHERE day = $d) a
FULL OUTER JOIN (SELECT country, dau FROM MART.DAU_BY_COUNTRY WHERE day = DATEADD('day', -1, $d)) b
  ON a.country = b.country
ORDER BY dau_prev DESC NULLS LAST;

-- (d) Total DAU is plausible.
SELECT day, SUM(dau) AS dau_sum_over_countries FROM MART.DAU_BY_COUNTRY
WHERE day IN ($d, DATEADD('day', -1, $d)) GROUP BY day ORDER BY day;

-- (e) The watchdog's source row exists.
SELECT * FROM OPS.JOB_RUNS WHERE business_date = $d ORDER BY finished_at DESC NULLS LAST LIMIT 5;
```
Pass criteria:
- (a) matches, or each gap is explained (for example redelivered copies outside the day window).
- (b) returns zero rows.
- (c) no large country is missing, and big swings are explained. No day-to-day baseline was measured [unverified]; agree one with the dashboard owner. A weekday vs weekend difference is normal.
- (e) shows a SUCCESS row for the business_date.
- The DAU dashboard shows day D.

### Resolve the page
The watchdog sends a resolve payload when it next sees success. If it is down, or you do not want to wait, resolve by hand with the same dedup_key as the trigger, `dau-nightly-<run_date>`. Either use Resolve on the incident in the PagerDuty UI, or send this body to the PagerDuty Events API v2 enqueue endpoint:
`{"routing_key": "<PAGERDUTY_ROUTING_KEY>", "event_action": "resolve", "dedup_key": "dau-nightly-<run_date>"}`
Resolve only after the checks above pass. Add a note with the cause, the fix and the commands used. If the job is still failing, do not resolve: acknowledge and escalate (section 6).

## 6. Escalation
All contacts and times are placeholders. Fill them in before this runbook goes live.

| Level | Who | When to escalate | How |
|---|---|---|---|
| L1 | On-call SRE (you) | Page received | Acknowledge in PagerDuty within <ACK_TARGET> |
| L2 | Data platform engineer on call: <NAME / ROTATION> | No clear cause or fix by <T1> after ack, or a rerun of a failed dedup/DAU stage fails again | PagerDuty escalation policy <POLICY_NAME>; Slack <#CHANNEL> |
| L3 | Data engineering lead: <NAME> | Unresolved at <T2> after ack, or the backfill needs a CLEAN.EVENTS repair, or the CLEAN.EVENTS count is below the distinct event_ids | Phone <NUMBER> |
| Platform | Kafka / Kafka Connect owner: <TEAM> | Connector will not restart, lag grows with a healthy connector, or retention is at risk | <CONTACT> |
| Vendor | Snowflake support (account <ACCOUNT_ID>), status page <URL> | Snowflake outage or errors not on our side | Support case, severity <SEV> |
| Business | DAU dashboard owner: <NAME> | Page is open and the dashboard is stale, so they can tell consumers | <CONTACT> |

Escalate at once, without waiting for <T1>, when: the data in CLEAN.EVENTS or MART.DAU_BY_COUNTRY looks wrong (not only late); Kafka events may be lost to retention; or you cannot reach Snowflake or PagerDuty. When you escalate, give: the run_date, the failed stage, the TASK_HISTORY error text, the connector lag, what you tried, and the incident link.

## 7. Post-incident notes
Within <N> working days, write a short, blameless review:
1. Timeline in UTC: scheduled start, SLA deadline, page time (should be the SLA deadline plus 30 minutes, the task's rule), ack, fix, resolve.
2. Failed stage and root cause (connector, dedup, DAU, warehouse, Snowflake, watchdog).
3. Impact: how long the DAU dashboard was stale, and whether any published day's numbers changed.
4. Data check: before and after counts from backfill Step A and the section 5 queries; any lost events.
5. Detection: did the page fire on time and only once (same dedup_key on repeated checks)? Any false or missed page?
6. Cleanup: warehouse size back to normal (Fix B); tasks resumed (Fix A); manual OPS.JOB_RUNS marker noted (backfill Step C).
7. Follow-ups, each with an owner and a date: confirm real task, warehouse and connector names; run all SQL and shell in a test account and fix what fails; set the stall threshold and the DAU swing baseline from real data; add a connector-lag alert before the SLA; load-test the peak ingest rate (never done).
8. Update this runbook with anything wrong or missing.

---
**Limits of this part:** no SQL or shell command was run. Nothing was sent to PagerDuty. RAW.CLICK_EVENTS column names are assumed. Contacts and escalation times are placeholders.
