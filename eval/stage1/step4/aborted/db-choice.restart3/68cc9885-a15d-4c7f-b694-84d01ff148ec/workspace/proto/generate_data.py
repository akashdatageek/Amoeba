#!/usr/bin/env python3
"""Deterministic synthetic multi-tenant event generator (seed fixed). Usage: python3 generate_data.py [--events 300000] [--out data]"""
import argparse, csv, json, os, random, datetime as dt
from collections import defaultdict
ap = argparse.ArgumentParser(); ap.add_argument("--events", type=int, default=300000)
ap.add_argument("--out", default="data"); ap.add_argument("--seed", type=int, default=42); a = ap.parse_args()
rng = random.Random(a.seed); os.makedirs(a.out, exist_ok=True)
TENANTS = [(1,"acme","eu",.55),(2,"globex","non-eu",.25),(3,"initech","eu",.12),(4,"umbrella","non-eu",.06),(5,"hooli","eu",.02)]  # skewed volumes
TYPES = [("page_view",.60),("click",.20),("signup",.06),("add_to_cart",.07),("purchase",.04),("logout",.03)]
START = dt.datetime(2026,1,1,tzinfo=dt.timezone.utc); DAYS = 90
users = {t[0]: max(50,int(a.events*t[3]/20)) for t in TENANTS}
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")
daily_events = defaultdict(int); daily_users = defaultdict(set); daily_purch = defaultdict(int)
eid = 0
with open(f"{a.out}/events.csv","w",newline="") as fc, open(f"{a.out}/events.jsonl","w") as fj:
    w = csv.writer(fc); w.writerow(["tenant_id","event_id","ts","type","user_id","properties"])
    for tid,_,_,wt in TENANTS:
        n = round(a.events*wt)
        for _ in range(n):
            eid += 1
            ts = START + dt.timedelta(seconds=rng.randrange(DAYS*86400))
            typ = rng.choices([t[0] for t in TYPES],[t[1] for t in TYPES])[0]
            uid = int(rng.paretovariate(1.2)) % users[tid] + 1  # skewed user activity
            props = {"country": rng.choice(["DE","FR","US","GB","NL"]), "plan": rng.choice(["free","pro"])}
            if typ == "purchase": props["amount"] = round(rng.uniform(5,500),2)
            w.writerow([tid,eid,iso(ts),typ,uid,json.dumps(props)])
            fj.write(json.dumps({"tenant_id":tid,"event_id":eid,"ts":{"$date":iso(ts)},"type":typ,"user_id":uid,"properties":props})+"\n")
            d = ts.date(); daily_events[(tid,d)] += 1; daily_users[(tid,d)].add(uid)
            if typ == "purchase": daily_purch[(tid,d)] += 1
with open(f"{a.out}/dashboard_daily.csv","w",newline="") as f, open(f"{a.out}/dashboard_daily.jsonl","w") as fj:
    w = csv.writer(f); w.writerow(["tenant_id","day","metric","value"])
    for (tid,d),c in sorted(daily_events.items()):
        for m,v in (("events",c),("dau",len(daily_users[(tid,d)])),("purchases",daily_purch[(tid,d)])):
            w.writerow([tid,d.isoformat(),m,float(v)])
            fj.write(json.dumps({"tenant_id":tid,"day":{"$date":d.isoformat()+"T00:00:00Z"},"metric":m,"value":float(v)})+"\n")
with open(f"{a.out}/tenants.csv","w",newline="") as f:
    w = csv.writer(f); w.writerow(["tenant_id","name","region"]); [w.writerow(t[:3]) for t in TENANTS]
with open(f"{a.out}/tenants.jsonl","w") as f:
    for t in TENANTS: f.write(json.dumps({"_id":t[0],"name":t[1],"region":t[2]})+"\n")
print("events written:", eid, "tenants:", len(TENANTS), "daily rows:", len(daily_events)*3)
