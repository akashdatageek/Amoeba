import sqlite3, csv, inspect, collections, sys
from pipeline_sqlite import DDL, load_raw, run
CSV='sample_events.csv'; WS='2000-01-01T00:00:00Z'; WD='2000-01-01'
def oracle(rows):
    best={}
    for r in rows:
        k=r['event_id']
        if k not in best or r['ingested_at']<best[k]['ingested_at']: best[k]=r
    d=collections.defaultdict(set)
    for r in best.values():
        if r['user_id'] in ('',None): continue
        c=(r['country'] or '').strip().upper() or 'UNKNOWN'
        d[(r['event_ts'][:10],c)].add(r['user_id'])
    return best,{k:len(v) for k,v in d.items()}
def fresh():
    con=sqlite3.connect(':memory:'); con.executescript(DDL); return con
def snap(con): return {(a,b):c for a,b,c in con.execute("SELECT event_date,country,dau FROM dau_by_country")}
rows=list(csv.DictReader(open(CSV)))
best,exp=oracle(rows)
con=fresh(); load_raw(con,CSV)
n_in=con.execute("SELECT COUNT(*) FROM raw_click_events").fetchone()[0]
run(con,WS,WD,'2026-10-21')
n_out=con.execute("SELECT COUNT(*) FROM clean_events").fetchone()[0]
act=snap(con)
keys=set(exp)|set(act)
mism=[(k,exp.get(k),act.get(k)) for k in sorted(keys) if exp.get(k)!=act.get(k)]
res=[]
def chk(name,e,a): res.append((name,e,a,'PASS' if e==a else 'FAIL'))
chk('(day,country) rows: mismatches vs oracle (%d cells)'%len(keys),0,len(mism))
chk('rows in (raw loaded)',len(rows),n_in)
chk('rows after dedup == distinct event_ids',len(best),n_out)
chk('duplicates removed',len(rows)-len(best),n_in-n_out)
dist=con.execute("SELECT COUNT(DISTINCT event_id) FROM clean_events").fetchone()[0]
chk('no duplicate event_id in clean_events',n_out,dist)
# idempotent rerun
before=(snap(con),n_out); run(con,WS,WD,'2026-10-21')
after=(snap(con),con.execute("SELECT COUNT(*) FROM clean_events").fetchone()[0])
chk('idempotent rerun: DAU rows + clean count unchanged',True,before==after)
# cross-day dup, incremental two-night load
ing=lambda r:r['ingested_at'][:10]
days=sorted({ing(r) for r in rows}); d1=days[0]
first=[r for r in rows if ing(r)<=days[1]]; rest=[r for r in rows if ing(r)>days[1]]
c2=fresh(); ins="INSERT INTO raw_click_events VALUES(?,?,?,?,?,?)"
f=lambda r:[(r[k] or None) for k in ('event_id','user_id','country','event_type','event_ts','ingested_at')]
c2.executemany(ins,[f(r) for r in first]); run(c2,days[0]+'T00:00:00Z',days[0],days[1])
c2.executemany(ins,[f(r) for r in rest]); run(c2,days[1]+'T00:00:00Z',days[1],days[-1])
inc=snap(c2); ncl=c2.execute("SELECT COUNT(*) FROM clean_events").fetchone()[0]
chk('incremental 2-night load (look-back 1 day) == oracle, mismatches',0,sum(1 for k in keys if inc.get(k)!=exp.get(k)))
chk('incremental clean rows == distinct ids',len(best),ncl)
# cross-day duplicates: same id, ingested on different UTC days
byid=collections.defaultdict(list)
for r in rows: byid[r['event_id']].append(r)
xd=[k for k,v in byid.items() if len({ing(r) for r in v})>1]
bad=[k for k in xd if c2.execute("SELECT COUNT(*) FROM clean_events WHERE event_id=?",(k,)).fetchone()[0]!=1 or con.execute("SELECT COUNT(*) FROM clean_events WHERE event_id=?",(k,)).fetchone()[0]!=1]
chk('cross-day duplicate ids (%d) each kept exactly once'%len(xd),0,len(bad))
# midnight
m=fresh()
m.executemany(ins,[('a1','A','us','click','2026-10-19T23:59:59Z','2026-10-20T00:30:00Z'),
 ('a2','A','US','click','2026-10-20T00:00:00Z','2026-10-20T00:30:00Z'),
 ('b1','B',None,'click','2026-10-20T00:00:01Z','2026-10-20T00:30:00Z'),
 ('b2','B','us','click','2026-10-20T00:00:00Z','2026-10-20T00:30:00Z'),
 ('a1','A','us','click','2026-10-19T23:59:59Z','2026-10-21T01:00:00Z')])
run(m,WS,WD,'2026-10-20'); s=snap(m)
chk('midnight: synthetic 23:59:59 -> 10-19, 00:00:00 -> 10-20, US/lowercase merged, null->UNKNOWN',
    {('2026-10-19','US'):1,('2026-10-20','US'):2,('2026-10-20','UNKNOWN'):1},s)
mid=[r for r in best.values() if r['event_ts'][11:16] in('23:59','00:00')]
chk('midnight events in sample (count>0)',True,len(mid)>0)
mu=collections.defaultdict(set)
for r in mid:
    mu[(r['event_ts'][:10],(r['country'] or '').upper() or 'UNKNOWN')].add(r['user_id'])
chk('every midnight-event user is within its UTC day oracle & table (cells ok)',True,all(act.get(k,0)>=1 for k in mu))
nul=sum(1 for r in rows if not r['country']); low=sum(1 for r in rows if r['country'] and r['country']!=r['country'].upper())
jr=con.execute("SELECT * FROM job_runs ORDER BY rowid").fetchall()
top=sorted(act.items(),key=lambda x:(x[0][0],-x[1],x[0][1]))
samp=[]; 
for dd in sorted({k[0] for k in act}): samp+= [t for t in top if t[0][0]==dd][:4]
fails=[r for r in res if r[3]=='FAIL']
L=["# Test report: dedup + DAU (sqlite equivalent) on sample_events.csv","",
"**Not executed in Snowflake.** The Snowflake dialect (QUALIFY, MERGE, DATE_TRUNC, Tasks) was not executed in Snowflake: no account or network. Only the sqlite3 equivalent in pipeline_sqlite.py was run. sqlite tests logic, not performance or Snowflake semantics.","",
"## Counts","| Metric | Value |","|---|---|",
f"| Rows in | {n_in:,} |",f"| Rows out (clean_events) | {n_out:,} |",f"| Duplicates removed | {n_in-n_out:,} ({(n_in-n_out)/n_in:.2%} of rows) |",
f"| Distinct event_ids (oracle) | {len(best):,} |",f"| Cross-day duplicate ids | {len(xd)} |",f"| Null/empty country rows; lowercase country rows | {nul}; {low} |",f"| Midnight events (23:59 / 00:00 UTC) in deduped set | {len(mid)} |",
f"| (day,country) cells compared | {len(keys)} |",f"| **Mismatches vs oracle** | **{len(mism)}** |","",
"## Results (check x expected x actual x pass)","| Check | Expected | Actual | Pass |","|---|---|---|---|"]
L+=[f"| {a} | {b} | {c} | {d} |" for a,b,c,d in res]
L+=["",f"Overall: {len(res)-len(fails)}/{len(res)} checks passed. The oracle is independent pure Python (dict/set; earliest ingested_at per event_id; day = event_ts[:10]; country upper-cased, blank -> UNKNOWN; null user_id excluded). The idempotent rerun leaves DAU and clean_events unchanged (job_runs gets one more audit row per run: {len(jr)} rows after the first run was repeated... see below).",
f"job_runs after run 1 + rerun: {len(jr)} rows; first = {jr[0]}","","## Sample of output (top 4 countries per day by DAU)","| event_date | country | dau |","|---|---|---|"]
L+=[f"| {k[0]} | {k[1]} | {v} |" for k,v in samp]
L+=["","## Limits","- Snowflake dialect not executed in Snowflake; QUALIFY/MERGE/DATE_TRUNC translations are untested there.","- sqlite tests logic, not performance, clustering, concurrency or 30M-row/day scale.","- Dedup follows the settled interpretation (same event_id, earliest ingested_at wins). Duplicates arriving after the look-back window would be re-inserted unless the anti-join covers all of CLEAN; the incremental test used a 1-day look-back with the anti-join against CLEAN."]
if mism: L+=["","Mismatch sample: "+str(mism[:5])]
open('test_report.md','w').write("\n".join(L)+"\n")
print("\n".join(L[:40])); print('mismatches',len(mism),'fails',fails)
sys.exit(1 if fails else 0)
