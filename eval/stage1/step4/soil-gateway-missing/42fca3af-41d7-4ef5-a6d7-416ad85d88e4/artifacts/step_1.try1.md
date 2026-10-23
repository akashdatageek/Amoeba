# Step 1 result: Field 7 VWC pull and analysis

**STATUS: NOT PULLED.** No live ChirpStack data was pulled. probe_averages.csv has 12 rows, all NOT PULLED with blank averages. No probe can be called below 20%, so no irrigation order can be written from this step.

## Why nothing was pulled
- The sandbox has no network. A shell attempt to run the fetch code was refused as a network command.
- CHIRPSTACK_TOKEN is not set. The check `env | grep -c '^CHIRPSTACK_TOKEN='` returned 0 [S4].
- No readings or mapping files were supplied. The workspace listing at the start showed none [S1].

## probe_averages (from probe_averages.csv [S4])
Header: probe_id,n_readings,expected_readings,coverage_pct,avg_vwc_pct,below_20,status

| probe_id | n_readings | expected_readings | coverage_pct | avg_vwc_pct | below_20 | status |
|---|---|---|---|---|---|---|
| PROBE_ID_UNKNOWN_01 | | 24 | | | | NOT PULLED |
| PROBE_ID_UNKNOWN_02 | | 24 | | | | NOT PULLED |
| PROBE_ID_UNKNOWN_03 | | 24 | | | | NOT PULLED |
| PROBE_ID_UNKNOWN_04 | | 24 | | | | NOT PULLED |
| PROBE_ID_UNKNOWN_05 | | 24 | | | | NOT PULLED |
| PROBE_ID_UNKNOWN_06 | | 24 | | | | NOT PULLED |
| PROBE_ID_UNKNOWN_07 | | 24 | | | | NOT PULLED |
| PROBE_ID_UNKNOWN_08 | | 24 | | | | NOT PULLED |
| PROBE_ID_UNKNOWN_09 | | 24 | | | | NOT PULLED |
| PROBE_ID_UNKNOWN_10 | | 24 | | | | NOT PULLED |
| PROBE_ID_UNKNOWN_11 | | 24 | | | | NOT PULLED |
| PROBE_ID_UNKNOWN_12 | | 24 | | | | NOT PULLED |

The probe IDs are placeholders, not real DevEUIs. The expected count of 24 is one reading per hour over 24 hours.

## Code
The scripts were written to the workspace as fetch_chirpstack.py [S2] and analyse_vwc.py [S3]. The blocks below are compact versions that show the same logic. If they differ from the workspace files, the workspace files are the ones that were written. **fetch_chirpstack.py was never run and is untested. Its endpoint paths and response shape are from my own knowledge of the ChirpStack v4 REST API [unverified] and must be checked against the real server.** analyse_vwc.py was run only on the no-data path [S4]. Its OK, LOW COVERAGE and exclusion logic is untested. No synthetic test was run.

```python
# fetch_chirpstack.py  (token only from env CHIRPSTACK_TOKEN; never printed or stored)
import os, sys, csv, argparse, datetime as dt, requests
p = argparse.ArgumentParser()
p.add_argument("--host", default="10.20.0.5:8090")   # REST port: confirm on site
p.add_argument("--app-id", required=True)             # Field 7 application ID
p.add_argument("--key", default="vwc")                # decoded payload key, used as reported
p.add_argument("--hours", type=int, default=24)
a = p.parse_args()
tok = os.environ.get("CHIRPSTACK_TOKEN")
if not tok: sys.exit("CHIRPSTACK_TOKEN not set")
H = {"Authorization": f"Bearer {tok}"}
base = f"http://{a.host}/api"
end = dt.datetime.now(dt.timezone.utc); start = end - dt.timedelta(hours=a.hours)
devs = requests.get(f"{base}/devices", headers=H, timeout=30,
        params={"applicationId": a.app_id, "limit": 100}).json().get("result", [])
print("devices found:", len(devs), "(expected 12)")
rows = []
for d in devs:
    eui = d["devEui"]
    m = requests.get(f"{base}/devices/{eui}/metrics", headers=H, timeout=30,
        params={"start": start.isoformat(), "end": end.isoformat(),
                "aggregation": "HOUR"}).json().get("metrics", {})
    mk = m.get(a.key)
    if not mk: print("WARN no key", a.key, "for", eui); continue
    ts = mk.get("timestamps", []); data = mk["datasets"][0]["data"]
    for t, v in zip(ts, data):
        if v is not None: rows.append((eui, t, v))   # no conversion
with open("readings.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["probe_id", "timestamp_utc", "vwc_pct"]); w.writerows(rows)
# Fallback if metrics are not retained: export a CSV with the same 3 columns.
```

```python
# analyse_vwc.py
import csv, os, statistics as st
EXPECTED = 24
ids = [f"PROBE_ID_UNKNOWN_{i:02d}" for i in range(1, 13)]   # replace with real DevEUIs
data = {}
if os.path.exists("readings.csv"):
    for r in csv.DictReader(open("readings.csv")):
        data.setdefault(r["probe_id"], []).append(float(r["vwc_pct"]))
    ids = sorted(set(ids) | set(data)) if data and not set(data) & set(ids) is False else ids
    if data and not set(data) & set(ids): ids = sorted(data)
with open("probe_averages.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["probe_id","n_readings","expected_readings","coverage_pct","avg_vwc_pct","below_20","status"])
    for pid in ids:
        if not os.path.exists("readings.csv"):
            w.writerow([pid,"",EXPECTED,"","","","NOT PULLED"]); continue
        vals = data.get(pid, [])
        ok = [v for v in vals if 0 <= v <= 100]
        print(pid, "excluded out-of-range:", len(vals) - len(ok))
        if not ok:
            w.writerow([pid,0,EXPECTED,0.0,"","","NOT PULLED"]); continue
        cov = 100 * len(ok) / EXPECTED; mean = st.mean(ok)
        w.writerow([pid, len(ok), EXPECTED, round(cov,1), round(mean,2),
                    mean < 20.0,                      # strictly below, unrounded mean
                    "LOW COVERAGE" if cov < 75 else "OK"])
```

## run_status.md (saved to the workspace [S5])
- Date of run: Friday 23 October 2026, America/Chicago.
- Source intended: ChirpStack v4 API at 10.20.0.5, Field 7 application or device group.
- Pulled or NOT PULLED: **NOT PULLED**. No network and no token [S4].
- Payload key for VWC: `vwc` (default, configurable). It is the decoded payload value as reported, in %, and is never derived from raw counts. Probes without the key are flagged.
- Window: last 24 hours, [now-24h, now] in UTC, hourly. Expected readings: 24 per probe.
- Actual device count versus 12: unknown.
- Testing: fetch not run. Analysis run only on the no-data path. No synthetic test.
- **Missing inputs:**
  1. The API token, set as env CHIRPSTACK_TOKEN.
  2. The Field 7 application or device-group ID, and confirmation of the 12-device count.
  3. The real probe DevEUIs.
  4. The probe-to-row mapping, which is needed for the irrigation order.
  5. A network route to 10.20.0.5.
  6. Confirmation that the codec outputs the key `vwc`, or the real key name.
- On site: `export CHIRPSTACK_TOKEN=...; python3 fetch_chirpstack.py --app-id <ID>; python3 analyse_vwc.py`

## Not confirmed
- Whether Field 7 has 12 devices on the server.
- The payload key name.
- That the fetch script works against the real API.
- Any VWC value.
BLOCKED: network access — could not reach ChirpStack at 10.20.0.5, so fetch_chirpstack.py was not run and no readings were pulled
BLOCKED: ChirpStack API token (CHIRPSTACK_TOKEN) — not present in the environment, so no authenticated pull was possible
MISSING DATA: 24h VWC readings for the 12 Field 7 probes — no data file in the workspace [S1], no network
MISSING DATA: Real probe IDs (DevEUIs) — no supplied file; workspace listing showed none [S1]
MISSING DATA: Field 7 application/group ID and probe-to-row mapping — not supplied
