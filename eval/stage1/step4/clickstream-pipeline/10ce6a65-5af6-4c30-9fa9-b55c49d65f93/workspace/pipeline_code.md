# pipeline_code.md - Step 3 code (event_id dedup, UTC DAU per country, idempotent load)
**Status:** the Snowflake SQL below was NOT executed in Snowflake (no account or network). Only the sqlite3 equivalent was run (smoke run here; formal tests in step 4). Dialect differences: sqlite compares ISO-8601 text timestamps and uses substr(event_ts,1,10) for the UTC day; Snowflake uses TIMESTAMP_NTZ in UTC and DATE_TRUNC('day', event_ts).
Design: dedup key event_id, earliest ingested_at kept (ROW_NUMBER with QUALIFY), restricted to a look-back window and anti-joined to loaded ids; DAU = COUNT(DISTINCT user_id) per UTC day and COALESCE(UPPER(country),'UNKNOWN'); null user_id excluded; null and lowercase countries normalised.

## 1. Snowflake SQL (snowflake_pipeline.sql)
```sql
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
```
## 2. sqlite3 equivalent (pipeline_sqlite.py)
```python
import sqlite3, csv
DDL="""
CREATE TABLE IF NOT EXISTS raw_click_events(event_id TEXT,user_id TEXT,country TEXT,event_type TEXT,event_ts TEXT,ingested_at TEXT);
CREATE TABLE IF NOT EXISTS clean_events(event_id TEXT PRIMARY KEY,user_id TEXT,country TEXT,event_type TEXT,event_ts TEXT,ingested_at TEXT);
CREATE TABLE IF NOT EXISTS dau_by_country(event_date TEXT,country TEXT,dau INTEGER,computed_at TEXT,PRIMARY KEY(event_date,country));
CREATE TABLE IF NOT EXISTS job_runs(job_name TEXT,business_date TEXT,status TEXT,rows_in INTEGER,rows_loaded INTEGER,duplicates_removed INTEGER,finished_at TEXT);
"""
DEDUP="""INSERT INTO clean_events
SELECT event_id,user_id,country,event_type,event_ts,ingested_at FROM (
  SELECT r.*, ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY ingested_at) AS rn
  FROM raw_click_events r WHERE ingested_at >= :window_start) s
WHERE rn = 1
  AND NOT EXISTS (SELECT 1 FROM clean_events c WHERE c.event_id = s.event_id)"""
DAU_DEL="DELETE FROM dau_by_country WHERE event_date >= :from_day"
DAU_INS="""INSERT INTO dau_by_country
SELECT substr(event_ts,1,10), COALESCE(UPPER(country),'UNKNOWN'), COUNT(DISTINCT user_id), CURRENT_TIMESTAMP
FROM clean_events WHERE user_id IS NOT NULL AND substr(event_ts,1,10) >= :from_day
GROUP BY 1,2"""
def load_raw(con,path):
    with open(path,newline='') as f:
        rd=csv.reader(f); next(rd)
        con.executemany("INSERT INTO raw_click_events VALUES(?,?,?,?,?,?)",[[v or None for v in r] for r in rd])
def run(con,window_start,from_day,business_date):
    """Idempotent: dedup is anti-joined on loaded ids; DAU is delete-and-insert per day, in one transaction."""
    p={'window_start':window_start,'from_day':from_day}
    with con:
        rows_in=con.execute("SELECT COUNT(*) FROM raw_click_events WHERE ingested_at >= :window_start",p).fetchone()[0]
        before=con.execute("SELECT COUNT(*) FROM clean_events").fetchone()[0]
        con.execute(DEDUP,p); loaded=con.execute("SELECT COUNT(*) FROM clean_events").fetchone()[0]-before
        con.execute(DAU_DEL,p); con.execute(DAU_INS,p)
        con.execute("INSERT INTO job_runs VALUES('dau_nightly',?,'SUCCESS',?,?,?,CURRENT_TIMESTAMP)",(business_date,rows_in,loaded,rows_in-loaded))
if __name__=='__main__':
    con=sqlite3.connect(':memory:'); con.executescript(DDL); load_raw(con,'sample_events.csv')
    run(con,'2000-01-01T00:00:00Z','2000-01-01','2026-10-21')
    print(con.execute("SELECT COUNT(*),COUNT(DISTINCT event_id) FROM clean_events").fetchone(), con.execute("SELECT * FROM job_runs").fetchall())
    for r in con.execute("SELECT event_date,country,dau FROM dau_by_country ORDER BY 1,3 DESC LIMIT 5"): print(r)
```
## 3. Seeded sample generator (gen_sample.py, random.seed(42)) -> sample_events.csv
```python
import random, csv, datetime as dt
random.seed(42)
C=['US','IN','BR','GB','DE','FR','JP','CA','AU','MX','ES','IT','NL','SE','ZA']
W=[1/(i+1) for i in range(15)]            # skewed: US biggest, ZA smallest
D0=dt.datetime(2026,10,19)                # 3 UTC days: 19, 20, 21 Oct 2026
T=['page_view','click','scroll','add_to_cart','purchase']
iso=lambda d:d.strftime('%Y-%m-%dT%H:%M:%SZ')
rows=[];ids=set();N=21000
for i in range(N):
    day=D0+dt.timedelta(days=random.randrange(3)); r=random.random()
    sec=86400-random.randint(1,60) if r<.03 else random.randint(0,59) if r<.06 else random.randint(0,86399)  # 23:59:xx / 00:00:xx
    ts=day+dt.timedelta(seconds=sec)
    while True:
        eid='%012x'%random.getrandbits(48)
        if eid not in ids: ids.add(eid);break
    uid='u%05d'%(int(4000*random.random()**2)+1)
    if random.random()<.001: uid=''
    c=random.choices(C,W)[0]; q=random.random()
    if q<.01: c=''
    elif q<.025: c=c.lower()
    rows.append([eid,uid,c,random.choice(T),iso(ts),iso(ts+dt.timedelta(seconds=random.randint(1,120)))])
base=list(rows); dups=0;cross=0
for r in random.sample(base,750):
    o=dt.datetime.strptime(r[5],'%Y-%m-%dT%H:%M:%SZ')
    if random.random()<.25:   # redelivery on a later ingestion day
        n=dt.datetime(o.year,o.month,o.day)+dt.timedelta(days=1,seconds=random.randint(0,20*3600))
    else: n=o+dt.timedelta(seconds=random.randint(5,1800))
    if n.date()!=o.date(): cross+=1
    rows.append(r[:5]+[iso(n)]);dups+=1
rows.sort(key=lambda r:(r[5],r[0]))
with open('sample_events.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['event_id','user_id','country','event_type','event_ts','ingested_at']);w.writerows(rows)
mid=sum(1 for r in rows if r[4][11:16] in('23:59','00:00'))
print('rows',len(rows),'distinct',len(ids),'dups',dups,'dup_pct=%.2f'%(100*dups/len(rows)),'cross_day_dups',cross,'midnight_rows',mid,
 'null_country',sum(r[2]=='' for r in rows),'lower',sum(r[2].islower() for r in rows),'null_uid',sum(r[1]=='' for r in rows))
```
