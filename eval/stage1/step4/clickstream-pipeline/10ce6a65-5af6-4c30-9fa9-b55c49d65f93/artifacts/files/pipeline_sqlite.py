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
