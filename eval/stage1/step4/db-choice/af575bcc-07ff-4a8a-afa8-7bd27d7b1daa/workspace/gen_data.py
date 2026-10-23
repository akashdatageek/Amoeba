#!/usr/bin/env python3
"""Shared seeded generator (seed 42) -> events.csv / events.jsonl / dashboards.jsonl.
Usage: python3 gen_data.py N_EVENTS OUTDIR   (default 1000000 data)
50 tenants, Zipf-like sizes (exponent chosen so largest = 10x median), 90 days ending 2026-10-22 UTC,
20 event types, ~10k users/tenant, nullable amount, 5-15 property keys nested 1 level."""
import sys, os, csv, json, math, random, datetime as dt, bisect, itertools
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000
OUT = sys.argv[2] if len(sys.argv) > 2 else "data"
os.makedirs(OUT, exist_ok=True)
rnd = random.Random(42)
T = 50
s = math.log(10) / math.log((T + 1) / 2)          # largest/median = 10 (median rank 25.5)
w = [(i + 1) ** -s for i in range(T)]; tot = sum(w)
counts = [max(1, round(N * x / tot)) for x in w]
END = dt.datetime(2026, 10, 22, tzinfo=dt.timezone.utc); SPAN = 90 * 86400
TYPES = ["view", "add_to_cart", "purchase"] + [f"evt_{i:02d}" for i in range(17)]
tw = list(itertools.accumulate(1 / (i + 1) ** 0.8 for i in range(20)))
PLANS = ["free", "pro", "enterprise"]; CH = ["web", "ios", "android", "api"]
def prop():
    p = {"plan": rnd.choice(PLANS), "channel": rnd.choice(CH), "country": rnd.choice(["DE", "FR", "US", "NL", "ES"])}
    for k in range(rnd.randint(2, 10)):      # 5-13 top-level keys so far; add nested object below -> 5-15
        p[f"k{k}"] = rnd.choice([rnd.randint(0, 1000), "v%d" % rnd.randint(0, 50), rnd.random() < .5])
    p["device"] = {"os": rnd.choice(["a", "b", "c"]), "ver": rnd.randint(1, 20)}
    return p
fc = open(f"{OUT}/events.csv", "w", newline=""); cw = csv.writer(fc)
fj = open(f"{OUT}/events.jsonl", "w"); eid = 0
for t in range(T):
    tid = f"t{t:02d}"; users = 10000; nsess = max(1, counts[t] // 4)
    for _ in range(counts[t]):
        eid += 1
        ts = END - dt.timedelta(seconds=rnd.random() * SPAN)
        et = TYPES[bisect.bisect(tw, rnd.random() * tw[-1])] if rnd.random() > .15 else TYPES[rnd.randint(0, 2)]
        u = int(rnd.paretovariate(1.2)) % users; sid = f"{tid}-s{rnd.randrange(nsess)}"
        amt = round(rnd.lognormvariate(3, 1), 2) if (et == "purchase" or rnd.random() < .1) else None
        p = prop(); iso = ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        cw.writerow([eid, tid, iso, et, f"u{u}", sid, json.dumps(p, separators=(",", ":")), "" if amt is None else amt])
        fj.write(json.dumps({"event_id": eid, "tenant_id": tid, "occurred_at": iso, "event_type": et, "user_id": f"u{u}",
                             "session_id": sid, "properties": p, "amount": amt}, separators=(",", ":")) + "\n")
fc.close(); fj.close()
with open(f"{OUT}/dashboards.jsonl", "w") as fd:
    did = 0
    for t in range(T):
        for d in range(rnd.randint(5, 15)):
            did += 1
            ws = [{"widget_id": f"w{did}_{i}", "type": rnd.choice(["line", "bar", "table", "funnel", "number"]),
                   "query_def": {"metric": rnd.choice(["count", "sum_amount", "uniq_users"]), "event_type": rnd.choice(TYPES), "window_days": rnd.choice([1, 7, 30])},
                   "layout": {"x": i % 3, "y": i // 3, "w": 4, "h": 3}} for i in range(rnd.randint(4, 12))]
            fd.write(json.dumps({"dashboard_id": did, "tenant_id": f"t{t:02d}", "name": f"Dash {did}", "owner": f"u{rnd.randrange(50)}",
                                 "widgets": ws, "updated_at": (END - dt.timedelta(hours=rnd.randrange(2000))).isoformat()}) + "\n")
json.dump({"events": eid, "tenants": T, "zipf_s": s, "max": max(counts), "median": sorted(counts)[T // 2 - 1:T // 2 + 1], "seed": 42}, open(f"{OUT}/manifest.json", "w"))
print("generated", eid, "events; per-tenant max", max(counts), "min", min(counts))
