import csv
from collections import defaultdict
from datetime import datetime

seen = set()
kept = []
rows_before = 0
with open("events.csv", newline="") as f:
    for row in csv.DictReader(f):
        rows_before += 1
        datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))  # ISO 8601 check
        if row["event_id"] in seen:
            continue  # keep first occurrence only
        seen.add(row["event_id"])
        kept.append(row)

users = defaultdict(set)
for r in kept:
    users[r["country"]].add(r["user_id"])

rows_after = len(kept)
print(f"rows_before={rows_before}")
print(f"rows_after={rows_after}")
print(f"duplicates_removed={rows_before - rows_after}")
print("country -> distinct_users (first occurrence kept per event_id)")
for c in sorted(users):
    print(f"{c}: {len(users[c])}")

with open("events_deduped.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["event_id", "user_id", "country", "ts"])
    w.writeheader()
    w.writerows(kept)
