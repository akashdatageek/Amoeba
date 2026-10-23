#!/usr/bin/env python3
"""Per-probe VWC stats from readings.csv (probe_id,timestamp_utc,vwc_pct). Always writes 12 probe rows.
VWC is used exactly as reported in the payload; values outside 0-100 are excluded and counted.
below_20 = mean < 20.0 (strict, tested on the unrounded mean). coverage < 75% -> LOW COVERAGE.
If readings.csv is missing -> every row is NOT PULLED with blank averages.
Usage: python3 analyse_vwc.py [--readings readings.csv] [--probes probes.txt] [--out probe_averages.csv]"""
import argparse, csv, os, statistics as st
from collections import defaultdict
ap = argparse.ArgumentParser()
ap.add_argument("--readings", default="readings.csv"); ap.add_argument("--probes", default="probes.txt")
ap.add_argument("--out", default="probe_averages.csv"); ap.add_argument("--expected", type=int, default=24)
ap.add_argument("--n-probes", type=int, default=12); ap.add_argument("--min-cov", type=float, default=75.0)
a = ap.parse_args()
pulled = os.path.exists(a.readings)
data, bad, miss = defaultdict(list), defaultdict(int), defaultdict(int)
ids = [l.strip() for l in open(a.probes) if l.strip()] if os.path.exists(a.probes) else []
if pulled:
    for r in csv.DictReader(open(a.readings)):
        p = r["probe_id"]
        if p not in ids: ids.append(p)
        try: v = float(r["vwc_pct"])
        except (ValueError, TypeError): miss[p] += 1; continue   # blank = payload lacks the key
        if 0 <= v <= 100: data[p].append(v)
        else: bad[p] += 1
ids = list(dict.fromkeys(ids))
n_real = len(ids)
while len(ids) < a.n_probes: ids.append(f"PROBE_ID_UNKNOWN_{len(ids)+1:02d}")  # placeholder, not a real ID
rows = []
for i, p in enumerate(ids):
    if not pulled or i >= n_real:
        rows.append([p, "", a.expected, "", "", "", "NOT PULLED"]); continue
    v = data.get(p, []); n = len(v); cov = round(100 * n / a.expected, 1)
    m = st.mean(v) if n else None
    rows.append([p, n, a.expected, cov, "" if m is None else round(m, 2),
                 "" if m is None else str(m < 20.0).upper(),
                 "OK" if cov >= a.min_cov else "LOW COVERAGE"])
with open(a.out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["probe_id","n_readings","expected_readings","coverage_pct","avg_vwc_pct","below_20","status"])
    w.writerows(rows)
for p in ids:
    if bad[p] or miss[p]: print(f"{p}: excluded out-of-range={bad[p]}, missing/blank key={miss[p]}")
if pulled and n_real != a.n_probes: print(f"WARNING: {n_real} probes found in data, expected {a.n_probes}")
print(f"wrote {a.out}: {len(rows)} rows; pulled={pulled}")
