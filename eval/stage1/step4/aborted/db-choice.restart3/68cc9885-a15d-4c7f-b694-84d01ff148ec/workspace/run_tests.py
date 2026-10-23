import csv, json, sqlite3, time, statistics, os, collections, datetime as dt
D='proto/data/'
def ts_s(v):
    if isinstance(v,dict): v=list(v.values())[0]
    if isinstance(v,(int,float)): return dt.datetime.fromtimestamp(v/1000 if v>1e11 else v, dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    return str(v).replace('T',' ')[:19]
DBF='proto/t.db'
if os.path.exists(DBF): os.remove(DBF)
db=sqlite3.connect(DBF)
db.execute('create table events(tenant_id int,event_id int,ts text,type text,user_id int,properties text)')
db.execute('create table dashboard_daily(tenant_id int,day text,metric text,value real)')
ev=list(csv.DictReader(open(D+'events.csv')))
db.executemany('insert into events values(?,?,?,?,?,?)',[(int(r['tenant_id']),int(r['event_id']),ts_s(r['ts']),r['type'],int(r['user_id']),r['properties']) for r in ev])
dd=list(csv.DictReader(open(D+'dashboard_daily.csv')))
db.executemany('insert into dashboard_daily values(?,?,?,?)',[(int(r['tenant_id']),r['day'][:10],r['metric'],float(r['value'])) for r in dd])
db.execute('create index ix_t_ts on events(tenant_id,ts)'); db.commit()
tids=sorted({r[0] for r in db.execute('select distinct tenant_id from events')})
docs=[json.loads(l) for l in open(D+'events.jsonl')]
for d in docs: d['ts']=ts_s(d['ts'])
idx=collections.defaultdict(list)
for d in docs: idx[d['tenant_id']].append(d)
for t in idx: idx[t].sort(key=lambda d:d['ts'],reverse=True)
rolls=[json.loads(l) for l in open(D+'dashboard_daily.jsonl')]
def scoped(t): return idx.get(t,[])
LO,HI='2026-03-02','2026-04-01'
def sq(q,t): return db.execute(q,(t,)).fetchall()
SQ={
'Q1_dau':"select substr(ts,1,10) d,count(distinct user_id) from events where tenant_id=? group by 1 order by 1",
'Q2_top_types_30d':f"select type,count(*) n from events where tenant_id=? and ts>='{LO}' and ts<'{HI}' group by type order by n desc,type",
'Q3_funnel':"with f as(select user_id,min(case when type='page_view' then ts end) v,min(case when type='signup' then ts end) s,min(case when type='purchase' then ts end) p from events where tenant_id=? group by user_id) select count(v),count(case when s>v then 1 end),count(case when s>v and p>s then 1 end) from f",
'Q4_rolling7':"with d as(select substr(ts,1,10) day,count(*) n from events where tenant_id=? group by 1) select day,(select sum(n) from d d2 where d2.day<=d.day and d2.day>date(d.day,'-7 day')) from d order by day",
'Q5_latest100':"select event_id,ts from events where tenant_id=? order by ts desc,event_id desc limit 100",
}
def m1(t):
    c=collections.defaultdict(set)
    for d in scoped(t): c[d['ts'][:10]].add(d['user_id'])
    return sorted((k,len(v)) for k,v in c.items())
def m2(t):
    c=collections.Counter(d['type'] for d in scoped(t) if LO<=d['ts']<HI)
    return sorted(c.items(),key=lambda x:(-x[1],x[0]))
def m3(t):
    v={};s={};p={}
    for d in scoped(t):
        m={'page_view':v,'signup':s,'purchase':p}.get(d['type'])
        if m is not None and (d['user_id'] not in m or d['ts']<m[d['user_id']]): m[d['user_id']]=d['ts']
    a=len(v); b=[u for u in s if u in v and s[u]>v[u]]; c=[u for u in b if u in p and p[u]>s[u]]
    return [(a,len(b),len(c))]
def m4(t):
    c=collections.Counter(d['ts'][:10] for d in scoped(t)); out=[]
    for day in sorted(c):
        lo=(dt.date.fromisoformat(day)-dt.timedelta(days=7)).isoformat()
        out.append((day,sum(n for k,n in c.items() if lo<k<=day)))
    return out
def m5(t): return [(d['event_id'],d['ts']) for d in scoped(t)[:100]]
MG={'Q1_dau':m1,'Q2_top_types_30d':m2,'Q3_funnel':m3,'Q4_rolling7':m4,'Q5_latest100':m5}
rows=[]; LAB='PROXY - not engine performance'
def timed(f):
    ts=[]
    for _ in range(3):
        t0=time.perf_counter(); r=f(); ts.append(time.perf_counter()-t0)
    return r,statistics.median(ts)*1000
for q in SQ:
    nS=nM=0; tS=tM=0; match=True
    for t in tids:
        rs,a=timed(lambda:sq(SQ[q],t)); rm,b=timed(lambda:MG[q](t))
        nS+=len(rs); nM+=len(rm); tS+=a; tM+=b
        ok=len(rs)==len(rm) if q=='Q5_latest100' else [tuple(x) for x in rs]==[tuple(x) for x in rm]
        match&=ok
    rows.append([q,nS,nM,round(tS,2),round(tM,2),match])
leaks_s=0; leaks_m=0
for t in tids:
    leaks_s+=db.execute('select count(*) from (select * from events where tenant_id=?) where tenant_id<>?',(t,t)).fetchone()[0]
    leaks_m+=sum(1 for d in scoped(t) if d['tenant_id']!=t)
neg_s=db.execute('select count(*) from events where tenant_id<>?',(tids[0],)).fetchone()[0]
neg_m=sum(1 for d in docs if d['tenant_id']!=tids[0])
rows.append(['Q6_leak_check',leaks_s,leaks_m,0,0,leaks_s==leaks_m==0])
cs=dict(db.execute('select tenant_id,count(*) from events group by 1').fetchall()); cm={t:len(v) for t,v in idx.items()}
tot_s=len(ev); tot_m=len(docs)
dbsize=os.path.getsize(DBF); jl=os.path.getsize(D+'events.jsonl'); cv=os.path.getsize(D+'events.csv')
out=[['test','postgresql_side_result','mongodb_side_result','engine_or_proxy','notes']]
for q,a,b,x,y,m in rows:
    if q=='Q6_leak_check':
        note=f'isolation: {leaks_s}/{leaks_m} foreign-tenant rows from scoped queries; negative control (unscoped) sees {neg_s}/{neg_m} foreign rows. RLS and Mongo access-layer enforcement NOT tested' if m else 'LEAK FOUND'
        out.append([q,f'{a} foreign rows (sqlite stand-in)',f'{b} foreign rows (python dicts)',LAB,note])
    else:
        note=('row counts match; result sets identical' if m else 'MISMATCH') if q!='Q5_latest100' else ('row counts match (100 per tenant); tie order not compared' if m else 'MISMATCH')
        out.append([q,f'{a} rows; median {x} ms (sum over {len(tids)} tenants, 3 runs; sqlite stand-in)',f'{b} rows; median {y} ms (sum over {len(tids)} tenants, 3 runs; python dicts)',LAB,note+'; timing not evidence'])
out.append(['row_count_events',f'{tot_s}: per tenant {cs}',f'{tot_m}: per tenant {cm}',LAB,'counts equal' if tot_s==tot_m and cs==cm else 'MISMATCH'])
out.append(['row_count_dashboard_daily',f'{len(dd)}',f'{len(rolls)}',LAB,'counts equal' if len(dd)==len(rolls) else 'MISMATCH'])
out.append(['stored_size',f'sqlite file {dbsize} bytes',f'events.jsonl {jl} bytes (raw file, not WiredTiger size)',LAB,f'events.csv {cv} bytes; says nothing about real Postgres/Atlas storage'])
out.append(['schema_syntax_validation','not run (no postgres)','not run (no mongod/pymongo)','not tested','schema.sql, mongo_schema.js never executed on a real engine'])
csv.writer(open('results.csv','w',newline='')).writerows(out)
for r in out: print(' | '.join(map(str,r)))
