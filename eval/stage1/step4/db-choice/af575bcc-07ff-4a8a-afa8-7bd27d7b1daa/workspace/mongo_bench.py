#!/usr/bin/env python3
"""MongoDB prototype + benchmark. Usage: python3 mongo_bench.py N_EVENTS DATADIR [OUT.json]
Needs: running mongod (MONGO_URI, default localhost:27017), pymongo, data from `python3 gen_data.py N DATADIR` (seed 42).
TS=1 also loads a time-series collection events_ts and times Q1,Q2,Q3,Q5 on it."""
import sys, os, json, time, random, platform, threading, itertools, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pymongo import MongoClient, ASCENDING

URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
N = int(sys.argv[1]); D = sys.argv[2]; OUT = sys.argv[3] if len(sys.argv) > 3 else "results_mongodb.json"
RUNS, DUR = 60, int(os.environ.get("DUR", "20"))
cl = MongoClient(URI, maxPoolSize=120); db = cl["analytics"]

def P(v):
    if isinstance(v, dict) and "$date" in v: v = v["$date"]
    if isinstance(v, (int, float)): return dt.datetime.utcfromtimestamp(v)
    return dt.datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)

# ---------- schema: collections, validators, indexes ----------
EV_VAL = {"$jsonSchema": {"bsonType": "object",
  "required": ["event_id", "tenant_id", "occurred_at", "event_type", "user_id", "session_id", "properties"],
  "properties": {"event_id": {"bsonType": ["int", "long"]}, "tenant_id": {"bsonType": ["int", "long"]},
    "occurred_at": {"bsonType": "date"}, "event_type": {"bsonType": "string"},
    "user_id": {"bsonType": "string"}, "session_id": {"bsonType": "string"},
    "properties": {"bsonType": "object"},
    "amount": {"bsonType": ["double", "decimal", "int", "long", "null"]}}}}
DB_VAL = {"$jsonSchema": {"bsonType": "object",
  "required": ["dashboard_id", "tenant_id", "name", "owner", "widgets", "updated_at"],
  "properties": {"tenant_id": {"bsonType": ["int", "long"]}, "updated_at": {"bsonType": "date"},
    "widgets": {"bsonType": "array", "items": {"bsonType": "object",
      "required": ["widget_id", "type", "query_def"],
      "properties": {"widget_id": {"bsonType": ["int", "long", "string"]}, "type": {"bsonType": "string"},
                     "query_def": {"bsonType": "object"}}}}}}}

def setup():
    for c in ("events", "events_ts", "dashboards"): db.drop_collection(c)
    db.create_collection("events", validator=EV_VAL, validationAction="error")
    db.events.create_index([("tenant_id", 1), ("occurred_at", 1)])                 # main access path
    db.events.create_index([("tenant_id", 1), ("user_id", 1), ("occurred_at", 1)])  # Q2 (covered distinct)
    db.events.create_index([("tenant_id", 1), ("session_id", 1)])                   # Q4
    try: db.events.create_index([("tenant_id", 1), ("properties.$**", 1)])          # compound wildcard (7.0+)
    except Exception: db.events.create_index([("properties.$**", 1)])
    db.create_collection("dashboards", validator=DB_VAL)
    db.dashboards.create_index([("tenant_id", 1), ("dashboard_id", 1)], unique=True)
    if os.environ.get("TS") == "1":
        db.create_collection("events_ts", timeseries={"timeField": "occurred_at", "metaField": "tenant_id", "granularity": "hours"})
        db.events_ts.create_index([("tenant_id", 1), ("occurred_at", 1)])

def load(name, coll):
    t0 = time.time(); buf = []; n = 0
    with open(os.path.join(D, "events.jsonl")) as f:
        for line in f:
            d = json.loads(line); d["occurred_at"] = P(d["occurred_at"]); buf.append(d); n += 1
            if len(buf) == 5000: coll.insert_many(buf, ordered=False); buf = []
            if n >= N: break
    if buf: coll.insert_many(buf, ordered=False)
    return n, time.time() - t0

# ---------- pipelines ----------
def Q1(c, t, now): return c.aggregate([{"$match": {"tenant_id": t, "occurred_at": {"$gte": now - dt.timedelta(hours=24), "$lte": now}}},
  {"$group": {"_id": {"h": {"$dateTrunc": {"date": "$occurred_at", "unit": "hour"}}, "t": "$event_type"}, "n": {"$sum": 1}}}, {"$sort": {"_id.h": 1}}])
def Q2(c, t, now): return c.aggregate([{"$match": {"tenant_id": t, "occurred_at": {"$gte": now - dt.timedelta(days=30), "$lte": now}}},
  {"$group": {"_id": {"d": {"$dateTrunc": {"date": "$occurred_at", "unit": "day"}}, "u": "$user_id"}}},
  {"$group": {"_id": "$_id.d", "users": {"$sum": 1}}}, {"$sort": {"_id": 1}}])
def Q3(c, t, now): return c.aggregate([{"$match": {"tenant_id": t, "occurred_at": {"$gte": now - dt.timedelta(days=7), "$lte": now}}},
  {"$group": {"_id": "$event_type", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 10}])
def Q4(c, t, now, steps):  # ordered 3-step funnel per session
    st = lambda e: {"$min": {"$cond": [{"$eq": ["$event_type", e]}, "$occurred_at", None]}}
    return c.aggregate([{"$match": {"tenant_id": t, "occurred_at": {"$gte": now - dt.timedelta(days=7), "$lte": now}, "event_type": {"$in": steps}}},
      {"$group": {"_id": "$session_id", "a": st(steps[0]), "b": st(steps[1]), "c": st(steps[2])}},
      {"$group": {"_id": None, "s1": {"$sum": {"$cond": [{"$ne": ["$a", None]}, 1, 0]}},
        "s2": {"$sum": {"$cond": [{"$and": [{"$ne": ["$a", None]}, {"$gt": ["$b", "$a"]}]}, 1, 0]}},
        "s3": {"$sum": {"$cond": [{"$and": [{"$ne": ["$a", None]}, {"$gt": ["$b", "$a"]}, {"$gt": ["$c", "$b"]}]}, 1, 0]}}}}])
def Q5(c, t, now, k, v): return c.aggregate([{"$match": {"tenant_id": t, "occurred_at": {"$gte": now - dt.timedelta(days=30), "$lte": now}, "properties." + k: v}},
  {"$group": {"_id": {"$dateTrunc": {"date": "$occurred_at", "unit": "day"}}, "sum": {"$sum": "$amount"}}}, {"$sort": {"_id": 1}}])
def Q6(t, did): return db.dashboards.find_one({"tenant_id": t, "dashboard_id": did})  # widgets embedded: 1 read, no join
CNT = itertools.count(10**10); LK = threading.Lock()
def Q7(t, sample, now):
    with LK: base = next(CNT); [next(CNT) for _ in range(len(sample))]
    docs = []
    for i, s in enumerate(sample):
        d = {k: v for k, v in s.items() if k != "_id"}; d["event_id"] = base + i; d["occurred_at"] = now; docs.append(d)
    db.events.insert_many(docs, ordered=False)

def pct(xs, p): xs = sorted(xs); return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]
def timeit(fn, n=RUNS):
    for _ in range(3): fn()
    xs = []
    for _ in range(n):
        t0 = time.perf_counter(); fn(); xs.append((time.perf_counter() - t0) * 1000)
    return {"runs": n, "p50_ms": round(pct(xs, 50), 3), "p95_ms": round(pct(xs, 95), 3), "p99_ms": round(pct(xs, 99), 3),
            "qps_single_thread": round(n / (sum(xs) / 1000), 1)}

def main():
    res = {"status": "EXECUTED", "database": "MongoDB", "environment": {"platform": platform.platform(), "python": platform.python_version(),
           "cpus": os.cpu_count(), "uri": URI.split("@")[-1]}}
    import pymongo; res["environment"]["pymongo"] = pymongo.version
    res["environment"]["mongod"] = cl.server_info()["version"]
    setup()
    n, secs = load("events", db.events)
    with open(os.path.join(D, "dashboards.jsonl")) as f:
        ds = [json.loads(l) for l in f]
    for d in ds: d["updated_at"] = P(d["updated_at"])
    if ds: db.dashboards.insert_many(ds, ordered=False)
    res["row_counts"] = {"events": db.events.count_documents({}), "dashboards": db.dashboards.count_documents({})}
    res["load_time_s"] = round(secs, 2); res["load_events_per_s"] = round(n / secs)
    if os.environ.get("TS") == "1": res["load_time_s_timeseries"] = round(load("ts", db.events_ts)[1], 2)
    raw = {fn: os.path.getsize(os.path.join(D, fn)) for fn in ("events.jsonl", "events.csv") if os.path.exists(os.path.join(D, fn))}
    cs = db.command("collStats", "events"); csd = db.command("collStats", "dashboards")
    res["bytes"] = {"raw_files": raw, "events_uncompressed_size": cs["size"], "events_storageSize": cs["storageSize"],
                    "events_totalIndexSize": cs["totalIndexSize"], "indexSizes": cs["indexSizes"], "dashboards_storageSize": csd["storageSize"]}
    base = raw.get("events.csv") or raw.get("events.jsonl")
    res["ratio_to_raw"] = {"basis_file": "events.csv" if "events.csv" in raw else "events.jsonl",
        "data_only": round(cs["storageSize"] / base, 3), "data_plus_indexes": round((cs["storageSize"] + cs["totalIndexSize"]) / base, 3)}
    # pick median-size tenant
    sizes = list(db.events.aggregate([{"$group": {"_id": "$tenant_id", "n": {"$sum": 1}}}, {"$sort": {"n": 1}}]))
    t = sizes[len(sizes) // 2]["_id"]; res["tenant_sizes"] = {"n_tenants": len(sizes), "median_tenant": t, "min": sizes[0]["n"], "median": sizes[len(sizes)//2]["n"], "max": sizes[-1]["n"]}
    now = list(db.events.aggregate([{"$match": {"tenant_id": t}}, {"$group": {"_id": None, "m": {"$max": "$occurred_at"}}}]))[0]["m"]
    top = [r["_id"] for r in db.events.aggregate([{"$match": {"tenant_id": t}}, {"$group": {"_id": "$event_type", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 3}])]
    sd = db.events.find_one({"tenant_id": t, "properties": {"$ne": {}}}); k = next(iter(sd["properties"])); v = sd["properties"][k]
    did = db.dashboards.find_one({"tenant_id": t})["dashboard_id"]
    sample = list(db.events.find({"tenant_id": t}).limit(1000))
    L = lambda c: list(c)
    qs = {"Q1": lambda: L(Q1(db.events, t, now)), "Q2": lambda: L(Q2(db.events, t, now)), "Q3": lambda: L(Q3(db.events, t, now)),
          "Q4": lambda: L(Q4(db.events, t, now, top)), "Q5": lambda: L(Q5(db.events, t, now, k, v)), "Q6": lambda: Q6(t, did),
          "Q7": lambda: Q7(t, sample, now)}
    if os.environ.get("TS") == "1":
        for q, f in (("Q1", Q1), ("Q2", Q2), ("Q3", Q3)): qs[q + "_timeseries"] = (lambda f=f: L(f(db.events_ts, t, now)))
    res["params"] = {"tenant_id": t, "now": now.isoformat(), "funnel_steps": top, "q5_filter": {k: v}}
    res["queries"] = {q: timeit(f, 50 if q == "Q7" else RUNS) for q, f in qs.items()}
    reads = [qs[q] for q in ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6")]
    res["mixed_80_20"] = {}
    for conc in (8, 32, 84):
        lat = {"r": [], "w": []}; stop = time.time() + DUR; lk = threading.Lock()
        def w():
            r = random.Random(); loc = {"r": [], "w": []}
            while time.time() < stop:
                t0 = time.perf_counter()
                if r.random() < 0.8: r.choice(reads)(); kind = "r"
                else: qs["Q7"](); kind = "w"
                loc[kind].append((time.perf_counter() - t0) * 1000)
            with lk: lat["r"] += loc["r"]; lat["w"] += loc["w"]
        with ThreadPoolExecutor(conc) as ex: [f.result() for f in [ex.submit(w) for _ in range(conc)]]
        tot = len(lat["r"]) + len(lat["w"])
        res["mixed_80_20"][str(conc)] = {"duration_s": DUR, "ops": tot, "ops_per_s": round(tot / DUR, 1), "queries_per_min": round(tot / DUR * 60),
            "read_p95_ms": round(pct(lat["r"], 95), 2) if lat["r"] else None, "write_batch1000_p95_ms": round(pct(lat["w"], 95), 2) if lat["w"] else None}
    db.events.delete_many({"event_id": {"$gte": 10**10}})
    res["limits"] = "Client is Python threads (GIL) on same host as mongod; throughput is a floor, not a server limit. Small scale does not prove 10 TB behaviour."
    json.dump(res, open(OUT, "w"), indent=1, default=str); print(json.dumps(res["queries"], indent=1))
main()
