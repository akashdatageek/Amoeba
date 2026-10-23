I read "cloud warehouse" as Snowflake; if you meant Google BigQuery or Amazon Redshift or Databricks / Azure Synapse, the answer below may not apply. I read "duplicate events" as Events sharing the same event_id, from Kafka at-least-once redelivery; if you meant Events identical on a composite key (user, timestamp, type, etc.) or Fully identical rows across all fields, the answer below may not apply. I read "finishes more than 30 minutes late" as Later than 30 minutes after the scheduled completion deadline or SLA time; if you meant Runtime exceeding the expected duration by 30 minutes or More than 30 minutes after the scheduled start time, the answer below may not apply. I read "one year of raw events" as 365 days × 30M × 2 KB, about 22 TB uncompressed; if you meant Compressed columnar storage in the warehouse, a fraction of 22 TB or Includes duplicates and replicas or retention overhead, the answer below may not apply.

# Step 7 memo: runbook.md now holds sections 1-7

## File status
- runbook.md on disk is 22,709 bytes [S85]. The headings in the file, in order, are:
  - 1 What the alert means and the impact
  - 2 First 5 minutes
  - 3 Decision tree by stage
  - 4 Fixes (Fix A to Fix E)
  - 5 Verification after the fix, and how to resolve the page
  - 6 Escalation
  - 7 Post-incident notes
- Sections 4-7 were written to the file, so the earlier gap (issue 1) is closed [S85]. I confirmed the headings and file size only. I did not re-read the full text after the write.
- Payload files `payloads/trigger.NOT_SENT.json` and `payloads/resolve.NOT_SENT.json` exist, and `grep -c "NOT SENT"` returned 1 for each [S85]. Both files are marked NOT SENT, so nothing was sent. This was a count, not a read of the contents.

## Real task, warehouse and connector names (issue 2 not fixable)
- `snowflake_pipeline.sql` has no CREATE TASK or warehouse definition. A grep for "task|warehouse" matched only two comment lines. Line 1 says "Run as one Snowflake Task graph: dedup -> DAU -> job-run marker". Line 43 is the comment on the success marker that the watchdog reads [S85].
- No real names exist to copy, so the runbook keeps these placeholders:
  - `<ROOT_TASK>`, `<DEDUP_TASK>`, `<DAU_TASK>`, `<JOB_RUN_MARKER_TASK>`
  - `<WAREHOUSE>`
  - `<CONNECTOR>`, `<CONNECT_HOST>`
- The pipeline owner (step 4) must add CREATE TASK statements, or the on-call team must fill in the names before go-live.
- Sections 1-3 also contain `<CONNECTOR_NAME>` and `<CONNECTOR_CONSUMER_GROUP>`, which need the same fix.

## MART column name (issue 3)
- The runbook uses `day` for MART.DAU_BY_COUNTRY, matching `snowflake_pipeline.sql`.
- The only runbook line that mentions both DAU_BY_COUNTRY and `event_date` is the part-2 intro (line 135). It lists the CLEAN.EVENTS columns, where `event_date` is correct [S85].
- I did not open the sqlite file or the step 1 memo. Whether `event_date` is still used for the mart there is not confirmed.

## Issues 4 and 5
- Issue 4 is in step 2's files: the storage-price typo and the 2016-source prices. Issue 5 is in step 8's citations. I did not touch either.
- For reference, the arithmetic is 365 × 30,000,000 × 2 KB = 21.9 TB, using decimal units (calculated, not taken from a source). The $23 and $40 per TB prices are assumptions, not current Snowflake prices.

---

# Runbook part 2: sections 4-7 (the text in runbook.md)

Names come from `snowflake_pipeline.sql` and `pipeline_code.md`:
- RAW.CLICK_EVENTS
- CLEAN.EVENTS (event_id, user_id, country, event_type, event_ts, ingested_at, event_date)
- MART.DAU_BY_COUNTRY (day, country, dau, computed_at)
- OPS.JOB_RUNS (job_name, business_date, status, rows_in, rows_loaded, duplicates_removed, started_at, finished_at)

Test each command in a non-production schema first. None of it has been run.

## 4. Fixes (pick the branch from the decision tree in section 3)
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
A resize applies to new queries only. Write the resize in the incident notes so that it is reverted.

### Fix C: restart a stalled Kafka connector (ingestion branch)
- Use the Kafka Connect REST API on `<CONNECT_HOST>:<PORT>`.
- Call the status endpoint for `<CONNECTOR>` first. Then call its restart endpoint with the options includeTasks=true and onlyFailed=true.
- If the connector is healthy but lag keeps growing, escalate (section 6).
- Check the topic retention before the lag gets older than the retention period [unverified: retention was not checked]. Events past retention are lost.

### Fix D: rerun a stage
A rerun is safe because each stage is idempotent. Dedup uses WHEN NOT MATCHED on event_id, and DAU is rewritten for the day. If CLEAN.EVENTS looks wrong, do not rerun blindly; escalate.
```sql
EXECUTE TASK <ROOT_TASK>;            -- whole graph, business date = yesterday UTC
-- or one stage, in this order:
EXECUTE TASK <DEDUP_TASK>;
EXECUTE TASK <DAU_TASK>;
EXECUTE TASK <JOB_RUN_MARKER_TASK>;
```
The graph always computes yesterday in UTC. To fix any other day, use Fix E.

### Fix E: idempotent backfill for one UTC day
Use it when the task graph cannot be rerun for day D, or to repair an earlier day. Running it twice gives the same result:
- The MERGE inserts only event_ids not yet in CLEAN.EVENTS.
- The DAU step deletes and re-inserts the day inside one transaction.

Prerequisite: RAW.CLICK_EVENTS rows for the day exist (run the count query from section 2). If they do not, fix ingestion (Fix C) first. A backfill cannot create events that were never loaded. The RAW.CLICK_EVENTS column names below are assumed to match CLEAN.EVENTS [unverified].
```sql
ALTER SESSION SET TIMEZONE = 'UTC';
SET backfill_day = '2026-10-21';          -- EDIT: the UTC day to repair (example: the day before the run date, 22 Oct 2026)

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
- A backfill of an old day scans CLEAN.EVENTS on event_id, so it is slower than the nightly run. Resize first (Fix B) if the warehouse is small.
- Do not backfill several days in parallel. Go one day at a time, oldest first.
- Step C is a manual marker; mention it in the incident notes. Leave any FAILED or partial row for the same business_date as history.

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
- The watchdog sends a resolve payload when it next sees success.
- If it is down, or you do not want to wait, resolve by hand with the same dedup_key as the trigger, `dau-nightly-<run_date>`. Either use "Resolve" on the incident in the PagerDuty UI, or send this body to the PagerDuty Events API v2 enqueue endpoint: `{"routing_key": "<PAGERDUTY_ROUTING_KEY>", "event_action": "resolve", "dedup_key": "dau-nightly-<run_date>"}`
- Resolve only after the Verify checks pass. Add a note with the cause, the fix and the commands used.
- If the job is still failing, do not resolve: acknowledge and escalate (section 6).

## 6. Escalation
All contacts and times are placeholders. Fill them in before this runbook goes live.

| Level | Who | When to escalate | How |
|---|---|---|---|
| L1 | On-call SRE (you) | Page received | Acknowledge in PagerDuty within <ACK_TARGET> |
| L2 | Data platform engineer on call: <NAME / ROTATION> | No clear cause or fix by <T1> after ack, or a rerun of a failed dedup/DAU stage fails again | PagerDuty escalation policy <POLICY_NAME>; Slack <#CHANNEL> |
| L3 | Data engineering lead: <NAME> | Unresolved at <T2> after ack, a backfill needs a CLEAN.EVENTS repair, or the CLEAN.EVENTS count is below the distinct event_ids | Phone <NUMBER> |
| Platform | Kafka / Kafka Connect owner: <TEAM> | Connector will not restart, lag grows with a healthy connector, or retention is at risk | <CONTACT> |
| Vendor | Snowflake support (account <ACCOUNT_ID>), status page <URL> | Snowflake outage or errors not on our side | Support case, severity <SEV> |
| Business | DAU dashboard owner: <NAME> | Page is open and the dashboard is stale, so they can tell consumers | <CONTACT> |

Escalate at once, without waiting for <T1>, when:
- the data in CLEAN.EVENTS or MART.DAU_BY_COUNTRY looks wrong (not only late);
- Kafka events may be lost to retention;
- you cannot reach Snowflake or PagerDuty.

When you escalate, give: the run_date, the failed stage, the TASK_HISTORY error text, the connector lag, what you tried, and the incident link.

## 7. Post-incident notes
Within <N> working days, write a short, blameless review:
1. Timeline in UTC: scheduled start, SLA deadline, page time (should be the SLA deadline plus 30 minutes), ack, fix, resolve.
2. Failed stage and root cause (connector, dedup, DAU, warehouse, Snowflake, watchdog).
3. Impact: how long the DAU dashboard was stale, and whether any published day's numbers changed.
4. Data check: before and after counts from backfill Step A and the Verify queries; any lost events.
5. Detection: did the page fire on time and only once (same dedup_key on repeated checks)? Any false or missed page?
6. Cleanup: warehouse size back to normal (Fix B); tasks started (Fix A); manual OPS.JOB_RUNS marker noted (backfill Step C).
7. Follow-ups, each with an owner and a date:
   - replace placeholders with real task, warehouse and connector names;
   - run all SQL and shell in a test account and fix what fails;
   - set the stall threshold and the DAU swing baseline from real data;
   - add a connector-lag alert before the SLA;
   - load-test the peak ingest rate (never done).
8. Update this runbook with anything wrong or missing.

---
**Limits:**
- No SQL or shell command was run. There is no Snowflake, Kafka Connect or PagerDuty access, and nothing was sent.
- Task, warehouse, connector and contact names and the escalation times are placeholders.
- RAW.CLICK_EVENTS column names are assumed.
- Sections 1-3 came from step 6, which is marked STALE. I did not re-check their full text against the reworked pipeline.
BLOCKED: Snowflake account — none of the runbook SQL (fixes, backfill, verification) could be executed or validated
BLOCKED: Kafka Connect and PagerDuty access — connector restart and manual resolve steps were not run
BLOCKED: local:Bash — a full re-read of runbook.md sections 1-3 against the reworked pipeline was not done; only headings and grep checks
MISSING DATA: Real Snowflake task, warehouse and Kafka connector names — snowflake_pipeline.sql has no CREATE TASK or warehouse definition (grep for task|warehouse matched only comment lines 1 and 43) [S85]; placeholders kept
MISSING DATA: RAW.CLICK_EVENTS column list — not confirmed; assumed to match CLEAN.EVENTS
MISSING DATA: DAU day-to-day swing baseline and Kafka topic retention — not measured; no data access
MISSING DATA: Whether the sqlite file and step 1 memo still say event_date for the mart column — those files were not opened in this step
MISSING INPUT: Real CREATE TASK and warehouse definitions — step 4 pipeline (snowflake_pipeline.sql has only a task-graph comment) [S85]
MISSING INPUT: Step 6 output is marked STALE — sections 1-3 were not fully re-checked against the reworked pipeline
