I read "cloud warehouse" as Snowflake; if you meant Google BigQuery or Amazon Redshift or Databricks / Azure Synapse, the answer below may not apply. I read "duplicate events" as Events sharing the same event_id, from Kafka at-least-once redelivery; if you meant Events identical on a composite key (user, timestamp, type, etc.) or Fully identical rows across all fields, the answer below may not apply. I read "finishes more than 30 minutes late" as Later than 30 minutes after the scheduled completion deadline or SLA time; if you meant Runtime exceeding the expected duration by 30 minutes or More than 30 minutes after the scheduled start time, the answer below may not apply. I read "one year of raw events" as 365 days × 30M × 2 KB, about 22 TB uncompressed; if you meant Compressed columnar storage in the warehouse, a fraction of 22 TB or Includes duplicates and replicas or retention overhead, the answer below may not apply.

**FILE STATUS (read this first).** The runbook sections for fixes, verification, escalation and post-incident notes are NOT yet in runbook.md on disk.
- I tried twice to append them with a shell heredoc, and the sandbox refused both times.
- First refusal: network_command, because the text contained a curl example.
- Second refusal: unsafe_command, because the text contained the path "/connectors/", which the sandbox read as a path outside the workspace.
- Nothing was written either time. No turn is left to retry.
- runbook.md still holds only the earlier part (sections 1-3).
- The complete text to append is below. I removed the curl line and the "/connectors/" paths, so it should pass the sandbox. Append it with local:Write or local:Edit rather than a heredoc.
- None of the SQL or shell below was run. There is no Snowflake, Kafka or PagerDuty access. All of it is untested.
- Table names and columns come from snowflake_pipeline.sql [S67]. Numbers inside SQL are code literals (offsets, limits), not data figures.

---
# Runbook part 2: fixes, verification, escalation, post-incident

Names come from snowflake_pipeline.sql [S67] and pipeline_code.md: RAW.CLICK_EVENTS, CLEAN.EVENTS (event_id, user_id, country, event_type, event_ts, ingested_at, event_date), MART.DAU_BY_COUNTRY (day, country, dau, computed_at), OPS.JOB_RUNS (job_name, business_date, status, rows_in, rows_loaded, duplicates_removed, started_at, finished_at) [S67]. The task, warehouse and connector names are not fixed in those files, so they stay as <PLACEHOLDERS>. Test each command in a non-production schema first.

## Section 4. Fixes (pick the branch from the decision tree in section 3)
Start every session with `ALTER SESSION SET TIMEZONE = 'UTC';`. Business day D is yesterday in UTC.

### Fix A: resume suspended tasks
```sql
SELECT SYSTEM$TASK_DEPENDENTS_ENABLE('<ROOT_TASK>');   -- resumes the dependents, not the root
ALTER TASK <ROOT_TASK> RESUME;
SHOW TASKS IN SCHEMA <DB>.<SCHEMA>;                    -- state must say 'started'
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
A rerun is safe because each stage is idempotent: dedup uses WHEN NOT MATCHED on event_id, and DAU is rewritten for the day. If CLEAN.EVENTS looks wrong, do not rerun blindly; escalate.
```sql
EXECUTE TASK <ROOT_TASK>;            -- whole graph, business date = yesterday UTC
-- or one stage, in this order:
EXECUTE TASK <DEDUP_TASK>;
EXECUTE TASK <DAU_TASK>;
EXECUTE TASK <JOB_RUN_MARKER_TASK>;
```
The graph always computes yesterday in UTC. To fix any other day, use Fix E.

### Fix E: idempotent backfill for one UTC day
Use it when the task graph cannot be rerun for day D, or to repair an earlier day. Running it twice gives the same result: the MERGE inserts only event_ids not yet in CLEAN.EVENTS, and the DAU step deletes and re-inserts the day inside one transaction.

Prerequisite: RAW.CLICK_EVENTS rows for the day exist (run the count query from section 2). If they do not, fix ingestion (Fix C) first. A backfill cannot create events that were never loaded. RAW.CLICK_EVENTS column names below are assumed to match CLEAN.EVENTS [unverified].
```sql
ALTER SESSION SET TIMEZONE = 'UTC';
SET backfill_day = '2026-10-21';          -- EDIT: the UTC day to repair (example only: the day before the run date, 22 Oct 2026)

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

-- Step C. Record the run so the watchdog sees SUCCESS (only after the Verify checks pass).
INSERT INTO OPS.JOB_RUNS (job_name, business_date, status, rows_in, rows_loaded, duplicates_removed, started_at, finished_at)
SELECT 'dau_nightly', $backfill_day::DATE, 'SUCCESS',
  (SELECT COUNT(*) FROM RAW.CLICK_EVENTS
    WHERE event_ts >= $backfill_day::DATE AND event_ts < DATEADD('day', 1, $backfill_day::DATE)),
  (SELECT COUNT(*) FROM CLEAN.EVENTS WHERE event_date = $backfill_day::DATE),
  NULL, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP();
```
Notes:
- The MERGE matches on event_id alone. If an earlier copy sits in CLEAN.EVENTS under another event_date, it is skipped. That is correct for the event_id rule.
- A backfill of an old day scans CLEAN.EVENTS on event_id, so it is slower than the nightly run (which uses a look-back window). Resize first (Fix B) if the warehouse is small.
- Do not backfill several days in parallel. Go one day at a time, oldest first.
- Step C is a manual marker: mention it in the incident notes. Leave any FAILED or partial row for the same business_date as history.

## Section 5. Verification after the fix, and how to resolve the page
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
The watchdog sends a resolve payload when it next sees success. If it is down, or you do not want to wait, resolve by hand with the same dedup_key as the trigger, `dau-nightly-<run_date>`. Either use "Resolve" on the incident in the PagerDuty UI, or send this body to the PagerDuty Events API v2 enqueue endpoint:
`{"routing_key": "<PAGERDUTY_ROUTING_KEY>", "event_action": "resolve", "dedup_key": "dau-nightly-<run_date>"}`
Resolve only after the Verify checks pass. Add a note with the cause, the fix and the commands used. If the job is still failing, do not resolve: acknowledge and escalate (section 6).

## Section 6. Escalation
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

## Section 7. Post-incident notes
Within <N> working days, write a short, blameless review:
1. Timeline in UTC: scheduled start, SLA deadline, page time (should be the SLA deadline plus 30 minutes, the task's rule), ack, fix, resolve.
2. Failed stage and root cause (connector, dedup, DAU, warehouse, Snowflake, watchdog).
3. Impact: how long the DAU dashboard was stale, and whether any published day's numbers changed.
4. Data check: before and after counts from backfill Step A and the Verify queries; any lost events.
5. Detection: did the page fire on time and only once (same dedup_key on repeated checks)? Any false or missed page?
6. Cleanup: warehouse size back to normal (Fix B); tasks started (Fix A); manual OPS.JOB_RUNS marker noted (backfill Step C).
7. Follow-ups, each with an owner and a date: replace placeholders with real task, warehouse and connector names; run all SQL and shell in a test account and fix what fails; set the stall threshold and the DAU swing baseline from real data; add a connector-lag alert before the SLA; load-test the peak ingest rate (never done).
8. Update this runbook with anything wrong or missing.

---
**Limits of this part:** no SQL or shell command was run (no Snowflake, Kafka or PagerDuty access). Task, warehouse, connector and contact names and escalation times are placeholders. RAW.CLICK_EVENTS column names are assumed. Nothing was sent to PagerDuty. The sections 1-3 in runbook.md came from step 6, which is marked STALE (built before step 4's rework), and were not re-checked against the reworked pipeline.
BLOCKED: local:Bash — the append of sections 4-7 to runbook.md was refused twice (first a curl example, then the path '/connectors/' in the text), so runbook.md still holds only sections 1-3; no turn was left to retry
BLOCKED: Snowflake account — none of the runbook SQL could be executed or validated
BLOCKED: Kafka / Kafka Connect and PagerDuty access — connector restart and manual resolve steps were not run
MISSING DATA: Names of Snowflake tasks, warehouse, Kafka connector and consumer group — not fixed in snowflake_pipeline.sql or pipeline_code.md [S67]; left as placeholders
MISSING DATA: RAW.CLICK_EVENTS column list — not confirmed; assumed to match CLEAN.EVENTS
MISSING DATA: Day-to-day DAU swing baseline and Kafka topic retention — not measured; no data access
MISSING INPUT: Step 6 output is marked STALE (built before step 4's rework) — sections 1-3 in runbook.md were not re-checked against the reworked pipeline
