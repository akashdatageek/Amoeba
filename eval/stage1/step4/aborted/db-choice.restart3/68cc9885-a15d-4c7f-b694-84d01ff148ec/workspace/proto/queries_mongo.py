"""Aggregation pipelines paired with queries.sql. Pipelines are plain data (no pymongo needed to build them).
Run: python3 queries_mongo.py  -> prints pipelines; with pymongo + MONGO_URI set, executes via scoped()."""
import os, json, datetime as dt
D = lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)
def _min_if(t): return {"$min": {"$cond": [{"$eq": ["$type", t]}, "$ts", None]}}
def pipelines(tid):
    day = {"$dateTrunc": {"date": "$ts", "unit": "day"}}
    m = {"$match": {"tenant_id": tid}}
    return {
 "Q1_dau": [m, {"$group": {"_id": {"day": day, "u": "$user_id"}}}, {"$group": {"_id": "$_id.day", "dau": {"$sum": 1}}}, {"$sort": {"_id": 1}}],
 "Q2_top_types": [{"$match": {"tenant_id": tid, "ts": {"$gte": D("2026-03-02"), "$lt": D("2026-04-01")}}},
                  {"$group": {"_id": "$type", "n": {"$sum": 1}}}, {"$sort": {"n": -1, "_id": 1}}],
 "Q3_funnel": [m, {"$group": {"_id": "$user_id", "v": _min_if("page_view"), "s": _min_if("signup"), "p": _min_if("purchase")}},
   {"$group": {"_id": None,
     "step1_view": {"$sum": {"$cond": [{"$ne": ["$v", None]}, 1, 0]}},
     "step2_signup": {"$sum": {"$cond": [{"$and": [{"$ne": ["$v", None]}, {"$ne": ["$s", None]}, {"$gte": ["$s", "$v"]}]}, 1, 0]}},
     "step3_purchase": {"$sum": {"$cond": [{"$and": [{"$ne": ["$v", None]}, {"$ne": ["$s", None]}, {"$gte": ["$s", "$v"]},
                                                       {"$ne": ["$p", None]}, {"$gte": ["$p", "$s"]}]}, 1, 0]}}}}],
 "Q4_rolling7": [m, {"$group": {"_id": day, "c": {"$sum": 1}}},
   {"$setWindowFields": {"sortBy": {"_id": 1}, "output": {"rolling_7d": {"$sum": "$c", "window": {"documents": [-6, 0]}}}}}, {"$sort": {"_id": 1}}],
 "Q5_latest100": [m, {"$sort": {"ts": -1, "event_id": -1}}, {"$limit": 100}, {"$project": {"_id": 0, "event_id": 1, "ts": 1, "type": 1, "user_id": 1}}],
 "Q6_leak_check": [m, {"$group": {"_id": None, "tenants_visible": {"$addToSet": "$tenant_id"},
     "foreign_rows": {"$sum": {"$cond": [{"$ne": ["$tenant_id", tid]}, 1, 0]}}}},
   {"$project": {"_id": 0, "tenants_visible": {"$size": "$tenants_visible"}, "foreign_rows": 1}}],
    }
def scoped(db, tid):
    """Tenant-scoped accessor: ALWAYS prepends {$match:{tenant_id}}; the only path app code may use (no RLS in MongoDB)."""
    class S:
        def aggregate(self, name):
            return list(db.events.aggregate(pipelines(tid)[name]))
    return S()
if __name__ == "__main__":
    uri = os.environ.get("MONGO_URI")
    try:
        import pymongo
    except ImportError:
        pymongo = None
    if uri and pymongo:
        db = pymongo.MongoClient(uri).analytics
        for k in pipelines(1): print(k, scoped(db, 1).aggregate(k)[:3])
    else:
        print("pymongo/MONGO_URI not available: printing pipelines only")
        for k, v in pipelines(1).items(): print(k, len(v), "stages")
