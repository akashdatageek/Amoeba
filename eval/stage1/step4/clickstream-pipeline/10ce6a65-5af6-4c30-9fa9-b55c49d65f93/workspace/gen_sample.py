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
