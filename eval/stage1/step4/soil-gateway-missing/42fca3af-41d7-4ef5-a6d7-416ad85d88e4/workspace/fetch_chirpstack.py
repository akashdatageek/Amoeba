#!/usr/bin/env python3
"""Pull last-24h VWC per probe from ChirpStack v4 REST API -> readings.csv (probe_id,timestamp_utc,vwc_pct).
Token only from env CHIRPSTACK_TOKEN (never hard-coded, never printed). VWC = decoded payload key as reported
(default 'vwc'); no conversion from raw counts.
Usage: CHIRPSTACK_TOKEN=... python3 fetch_chirpstack.py --app-id <APPLICATION_UUID> [--host 10.20.0.5 --port 8090 --key vwc --hours 24]
Fallback if device metrics are not retained: export uplinks (decoded object) to CSV from the ChirpStack UI/DB
and convert to readings.csv with the same three columns.
NOTE: REST endpoint paths follow the ChirpStack v4 REST gateway (/api/devices, /api/devices/{dev_eui}/metrics);
verify against the server's /api swagger page on site. NOT TESTED against a live server."""
import argparse, csv, os, sys, datetime as dt
import requests

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--host", default="10.20.0.5"); a.add_argument("--port", default="8090")
    a.add_argument("--app-id", required=True); a.add_argument("--key", default="vwc")
    a.add_argument("--hours", type=int, default=24); a.add_argument("--out", default="readings.csv")
    a.add_argument("--probes-out", default="probes.txt"); a.add_argument("--expect", type=int, default=12)
    a = a.parse_args()
    tok = os.environ.get("CHIRPSTACK_TOKEN")
    if not tok:
        sys.exit("CHIRPSTACK_TOKEN not set in environment - nothing pulled")
    base = f"http://{a.host}:{a.port}/api"; H = {"Authorization": f"Bearer {tok}"}
    end = dt.datetime.now(dt.timezone.utc).replace(microsecond=0); start = end - dt.timedelta(hours=a.hours)
    iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get(f"{base}/devices", headers=H, params={"applicationId": a.app_id, "limit": 100}, timeout=30)
    r.raise_for_status()
    devs = [d["devEui"] for d in r.json().get("result", [])]
    print(f"devices found: {len(devs)} (expected {a.expect})")
    rows, nokey = [], []
    for eui in devs:
        m = requests.get(f"{base}/devices/{eui}/metrics", headers=H, timeout=30,
                         params={"start": iso(start), "end": iso(end), "aggregation": "HOUR"})
        m.raise_for_status(); found = False
        for name, met in (m.json().get("metrics") or {}).items():
            ts = met.get("timestamps", [])
            for ds in met.get("datasets", []):
                if a.key in (name, met.get("name"), ds.get("label")):   # payload key as reported
                    found = True
                    for t, v in zip(ts, ds.get("data", [])):
                        rows.append((eui, t, "" if v is None else v))
        if not found:
            nokey.append(eui)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["probe_id", "timestamp_utc", "vwc_pct"]); w.writerows(rows)
    open(a.probes_out, "w").write("\n".join(devs) + "\n")
    print(f"window UTC {iso(start)} .. {iso(end)}; rows={len(rows)}")
    if nokey:
        print("WARNING payload lacks key", repr(a.key), "for:", ", ".join(nokey))
    if len(devs) != a.expect:
        print(f"WARNING device count {len(devs)} != {a.expect}")

main()
