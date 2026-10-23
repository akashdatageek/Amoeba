-- NOT executed in Snowflake (no account available). Run as one Snowflake Task graph: dedup -> DAU -> job-run marker.
ALTER SESSION SET TIMEZONE = 'UTC';
SET lookback_days  = 3;                                              -- parameter, tune to Kafka redelivery behaviour
SET business_date  = (SELECT DATEADD('day', -1, CURRENT_DATE()));    -- D = yesterday UTC; pass explicitly for backfills
SET window_start   = (SELECT DATEADD('day', -$lookback_days, $business_date)::TIMESTAMP_NTZ);
SET window_day     = (SELECT $window_start::DATE);

CREATE TABLE IF NOT EXISTS CLEAN.EVENTS (event_id STRING NOT NULL, user_id STRING, country STRING, event_type STRING,
  event_ts TIMESTAMP_NTZ NOT NULL, ingested_at TIMESTAMP_NTZ NOT NULL, event_date DATE) CLUSTER BY (event_date);
CREATE TABLE IF NOT EXISTS MART.DAU_BY_COUNTRY (day DATE, country STRING, dau NUMBER, computed_at TIMESTAMP_NTZ, PRIMARY KEY (day, country));
CREATE TABLE IF NOT EXISTS OPS.JOB_RUNS (job_name STRING, business_date DATE, status STRING, rows_in NUMBER, rows_loaded NUMBER,
  duplicates_removed NUMBER, started_at TIMESTAMP_NTZ, finished_at TIMESTAMP_NTZ);

BEGIN TRANSACTION;
-- (1) Dedup by event_id: earliest ingested_at wins inside the look-back window; WHEN NOT MATCHED = anti-join on loaded ids,
--     so redeliveries (same-day or a later ingestion day) never create a second row. Re-running inserts 0 rows.
MERGE INTO CLEAN.EVENTS t
USING (
  SELECT event_id, user_id, country, event_type, event_ts, ingested_at, DATE_TRUNC('day', event_ts)::DATE AS event_date
  FROM RAW.CLICK_EVENTS
  WHERE ingested_at >= $window_start
  QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY ingested_at) = 1
) s
ON t.event_id = s.event_id            -- no event_date prune here: a late event may carry an old event_ts
WHEN NOT MATCHED THEN INSERT (event_id, user_id, country, event_type, event_ts, ingested_at, event_date)
  VALUES (s.event_id, s.user_id, s.country, s.event_type, s.event_ts, s.ingested_at, s.event_date);

-- (2) DAU per UTC day and country, idempotent delete-and-insert of the recomputed days (same transaction).
DELETE FROM MART.DAU_BY_COUNTRY WHERE day >= $window_day;
INSERT INTO MART.DAU_BY_COUNTRY (day, country, dau, computed_at)
SELECT DATE_TRUNC('day', event_ts)::DATE AS day, COALESCE(UPPER(country), 'UNKNOWN') AS country,
       COUNT(DISTINCT user_id) AS dau, CURRENT_TIMESTAMP()::TIMESTAMP_NTZ
FROM CLEAN.EVENTS
WHERE user_id IS NOT NULL AND event_date >= $window_day
GROUP BY 1, 2;
COMMIT;

-- (2b) Equivalent MERGE form (upsert only; does not remove a (day,country) row that disappeared, hence delete+insert above is primary):
-- MERGE INTO MART.DAU_BY_COUNTRY m USING (<the SELECT above>) a ON m.day=a.day AND m.country=a.country
-- WHEN MATCHED THEN UPDATE SET dau=a.dau, computed_at=a.computed_at
-- WHEN NOT MATCHED THEN INSERT (day,country,dau,computed_at) VALUES (a.day,a.country,a.dau,a.computed_at);

-- (3) Success marker: written only if (1) and (2) succeeded (last task in the graph); the watchdog reads this row.
INSERT INTO OPS.JOB_RUNS (job_name, business_date, status, rows_in, rows_loaded, duplicates_removed, started_at, finished_at)
SELECT 'dau_nightly', $business_date, 'SUCCESS',
       (SELECT COUNT(*) FROM RAW.CLICK_EVENTS WHERE ingested_at >= $window_start),
       (SELECT COUNT(*) FROM CLEAN.EVENTS WHERE ingested_at >= $window_start),
       (SELECT COUNT(*) FROM RAW.CLICK_EVENTS WHERE ingested_at >= $window_start) - (SELECT COUNT(*) FROM CLEAN.EVENTS WHERE ingested_at >= $window_start),
       NULL, CURRENT_TIMESTAMP()::TIMESTAMP_NTZ;
