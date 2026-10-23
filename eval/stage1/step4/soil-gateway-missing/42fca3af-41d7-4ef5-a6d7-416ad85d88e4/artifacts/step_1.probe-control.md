# Field 7 VWC pull: step output

## Status
**NOT PULLED.** No live ChirpStack data was pulled and no readings were supplied. The sandbox has no network, and the API token is in the farm office. I could not confirm that `CHIRPSTACK_TOKEN` is set, because that check was cut off in the first listing [S11]. So there are no real averages, and no probe is flagged below 20%. No irrigation order can be written until the farm supplies the data and the probe-to-row map.

**What I could not confirm:**
- The last command (a rewrite of both scripts, `run_status.md` and a synthetic test) was refused by the sandbox because it contained `import requests`. Nothing in it ran.
- The earlier turns left four files in the workspace: `fetch_chirpstack.py`, `analyse_vwc.py`, `probe_averages.csv` and `run_status.md` [S14]. I only saw the start of `fetch_chirpstack.py`. Its header says the token comes from `CHIRPSTACK_TOKEN` and the default key is `vwc` [S14].
- I could not re-read the full contents of the other three files. Treat the code below as the intended version and diff it against the workspace files.
- Neither script has been tested. The synthetic test did not run, so I am not claiming it passed.

## probe_averages (intended content of probe_averages.csv)
The real probe IDs are unknown, so the rows are placeholders. No numbers were invented. The brief sets the 24-hour window, the 20% threshold and the 75% coverage limit.

| probe_id | n_readings | expected_readings | coverage_pct | avg_vwc_pct | below_20 | status |
|---|---|---|---|---|---|---|
| UNKNOWN_SLOT_01 | 0 | 24 | blank | blank | blank | NOT PULLED |
| UNKNOWN_SLOT_02 | 0 | 24 | blank | blank | blank | NOT PULLED |
| UNKNOWN_SLOT_03 | 0 | 24 | blank | blank | blank | NOT PULLED |
| UNKNOWN_SLOT_04 | 0 | 24 | blank | blank | blank | NOT PULLED |
| UNKNOWN_SLOT_05 | 0 | 24 | blank | blank | blank | NOT PULLED |
| UNKNOWN_SLOT_06 | 0 | 24 | blank | blank | blank | NOT PULLED |
| UNKNOWN_SLOT_07 | 0 | 24 | blank | blank | blank | NOT PULLED |
| UNKNOWN_SLOT_08 | 0 | 24 | blank | blank | blank | NOT PULLED |
| UNKNOWN_SLOT_09 | 0 | 24 | blank | blank | blank | NOT PULLED |
| UNKNOWN_SLOT_10 | 0 | 24 | blank | blank | blank | NOT PULLED |
| UNKNOWN_SLOT_11 | 0 | 24 | blank | blank | blank | NOT PULLED |
| UNKNOWN_SLOT_12 | 0 | 24 | blank | blank | blank | NOT PULLED |

Whether the workspace `probe_averages.csv` matches this table is not confirmed. Regenerate it with `python3 analyse_vwc.py --in none.csv --probes /dev/null`. With no input file and no probe list, that command writes 12 placeholder rows.

## Code

### fetch_chirpstack.py
This is for on-site use. The token comes only from the environment and is never printed or stored. VWC is the decoded payload key as reported, with no conversion. The REST paths follow the ChirpStack v4 REST gateway but are untested. Port 8090 is the script's default, and I have not confirmed it against 10.20.0.5.

```python
#!/usr/bin/env python3
"""Pull last-N-hours VWC per probe from ChirpStack v4 REST API -> readings.csv.
Token ONLY from env CHIRPSTACK_TOKEN (never printed/stored). VWC = decoded payload key as reported, no conversion.
Usage: CHIRPSTACK_TOKEN=... python3 fetch_chirpstack.py --app-id <UUID> [--host 10.20.0.5 --port 8090 --key vwc --hours 24]
REST paths are untested (no network): verify on the farm server. Fallback if metrics are not retained:
export uplinks (decoded object) to probe_id,timestamp_utc,vwc_pct and run analyse_vwc.py on that CSV."""
import argparse, csv, os, sys, datetime as dt
import requests
p = argparse.ArgumentParser()
p.add_argument("--host", default="10.20.0.5"); p.add_argument("--port", default="8090")
p.add_argument("--app-id", required=True); p.add_argument("--key", default="vwc")
p.add_argument("--hours", type=int, default=24); p.add_argument("--out", default="readings.csv")
a = p.parse_args()
tok = os.environ.get("CHIRPSTACK_TOKEN")
if not tok: sys.exit("CHIRPSTACK_TOKEN not set; nothing pulled")
H = {"Authorization": "Bearer " + tok}; base = f"http://{a.host}:{a.port}/api"
end = dt.datetime.now(dt.timezone.utc).replace(microsecond=0); start = end - dt.timedelta(hours=a.hours)
r = requests.get(f"{base}/devices", headers=H, params={"applicationId": a.app_id, "limit": 100}, timeout=30)
r.raise_for_status(); devs = r.json().get("result", [])
print(f"devices found: {len(devs)} (expected 12)")
rows, nokey = [], []
for d in devs:
    eui, name = d["devEui"], d.get("name") or d["devEui"]
    m = requests.get(f"{base}/devices/{eui}/metrics", headers=H, timeout=30,
                     params={"start": start.isoformat(), "end": end.isoformat(), "aggregation": "HOUR"})
    m.raise_for_status(); met = m.json().get("metrics", {}).get(a.key)
    if not met: nokey.append(name); continue
    ts, data = met.get("timestamps", []), met["datasets"][0]["data"]
    rows += [(name, t, v) for t, v in zip(ts, data) if v is not None]
with open(a.out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["probe_id", "timestamp_utc", "vwc_pct"]); w.writerows(rows)
print(f"{len(rows)} readings -> {a.out}; probes lacking key '{a.key}': {nokey or 'none'}")
```

### analyse_vwc.py
Per-probe count, expected count, coverage %, mean VWC after excluding values outside 0–100 (with a count of exclusions), and `below_20 = mean < 20.0` (strictly less than). Coverage under 75% is marked LOW COVERAGE. It always writes 12 rows, and probes with no data get NOT PULLED.

```python
#!/usr/bin/env python3
"""readings.csv -> probe_averages.csv (12 rows). Usage: analyse_vwc.py [--in readings.csv] [--probes ids.txt] [--hours 24] [--out probe_averages.csv]"""
import argparse, csv, os, statistics as st
p = argparse.ArgumentParser()
p.add_argument("--in", dest="inp", default="readings.csv"); p.add_argument("--probes")
p.add_argument("--hours", type=int, default=24); p.add_argument("--out", default="probe_averages.csv")
a = p.parse_args()
data = {}
if os.path.exists(a.inp):
    for r in csv.DictReader(open(a.inp)):
        try: data.setdefault(r["probe_id"], []).append(float(r["vwc_pct"]))
        except (ValueError, KeyError): pass
ids = [l.strip() for l in open(a.probes) if l.strip()] if a.probes else sorted(data)
ids += [f"UNKNOWN_SLOT_{i:02d}" for i in range(len(ids) + 1, 13)]   # always 12 rows
out = []
for pid in ids:
    v = data.get(pid, []); ok = [x for x in v if 0 <= x <= 100]; ex = len(v) - len(ok)
    if ex: print(f"{pid}: excluded {ex} value(s) outside 0-100")
    if not ok:
        out.append([pid, 0, a.hours, "", "", "", "NOT PULLED"]); continue
    cov = round(100 * len(ok) / a.hours, 1); m = st.mean(ok)
    out.append([pid, len(ok), a.hours, cov, round(m, 2), m < 20.0, "LOW COVERAGE" if cov < 75 else "OK"])
with open(a.out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["probe_id","n_readings","expected_readings","coverage_pct","avg_vwc_pct","below_20","status"]); w.writerows(out)
print(f"wrote {a.out}: {len(out)} rows")
```

Suggested test, once someone can run it: build a file clearly labelled SYNTHETIC with probes at 19.9 and 20.0. Only the 19.9 probe should be flagged. Keep that file in `synthetic/` and out of `probe_averages.csv`.

## run_status.md (memo)

### Result
NOT PULLED. No live data. There is no network in the run, and the token (`CHIRPSTACK_TOKEN`) is held in the farm office.

### Parameters
- **Source:** ChirpStack v4 REST API at 10.20.0.5 (not reached).
- **Payload key:** `vwc`. It is the decoded payload value as reported, with no conversion, and can be changed with `--key`. The script flags probes whose payload lacks the key.
- **Window:** the last 24 hours in UTC, ending at run time. The run date is Friday 23 October 2026 (America/Chicago).
- **Device count:** unknown. The script prints the actual count against the expected 12.

### Missing inputs
1. `CHIRPSTACK_TOKEN`, exported on a machine that can reach 10.20.0.5.
2. The Field 7 application UUID or device-group ID.
3. The 12 probe IDs, and confirmation that the app holds exactly 12 devices.
4. The decoded payload key for VWC, if it is not `vwc`.
5. The probe-to-row map (farm layout or probe-location list).
6. Confirmation that device metrics are kept for 24 hours. If they are not, supply a CSV export (probe_id,timestamp_utc,vwc_pct).

### Next step for the farm
1. Run `fetch_chirpstack.py` on-site.
2. Run `analyse_vwc.py` on the resulting `readings.csv`.
3. Replace `probe_averages.csv` with the real result.
4. Use the row map to write the irrigation order for the rows holding probes with an average below 20%.

Note: the workspace copy of `run_status.md` was not re-read, so its contents are unconfirmed.
BLOCKED: ChirpStack API access (network and token) — could not reach 10.20.0.5 or pull the 24h readings
BLOCKED: Script execution in sandbox — the final command was refused because it contained 'import requests', so the rewrite of both scripts and the synthetic test did not run
BLOCKED: File re-verification — could not re-read analyse_vwc.py, probe_averages.csv and run_status.md in full
MISSING DATA: ChirpStack API token (CHIRPSTACK_TOKEN) — not available; the env check output was cut off [S11]
MISSING DATA: Field 7 application/device-group ID — workspace listing showed no mapping or readings files [S14]
MISSING DATA: 12 probe IDs (DevEUIs) — not supplied
MISSING DATA: Probe-to-row layout mapping — not supplied
MISSING DATA: 24h VWC readings — not pulled
