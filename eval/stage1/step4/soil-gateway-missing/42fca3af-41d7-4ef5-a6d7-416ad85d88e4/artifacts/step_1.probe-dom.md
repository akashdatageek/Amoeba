**Live data pulled: NO.** There are no readings, no averages and no list of probes below 20%. The work-around does not cover four things: the pull itself, the real probe IDs, the probe-to-row mapping, and the irrigation order for Field 7. All four need the on-site run.

**Files in the workspace** [S25]
- fetch_chirpstack.py (53 lines) and analyse_vwc.py (44 lines). Both pass `python3 -m py_compile` [S25].
- probe_averages.csv
- run_status.md
- A synthetic_test folder. Any test data in it is synthetic and is kept apart from probe_averages.csv.

**Code: fetch_chirpstack.py.** The block below is the header I could read in [S26]. It is not the whole script.
```python
#!/usr/bin/env python3
"""Pull last-24h VWC per probe from ChirpStack v4 REST API -> readings.csv (probe_id,timestamp_utc,vwc_pct).
Token only from env CHIRPSTACK_TOKEN (never hard-coded, never printed). VWC = decoded payload key as reported
(default 'vwc'); no conversion from raw counts.
Usage: CHIRPSTACK_TOKEN=... python3 fetch_chirpstack.py --app-id <APPLICATION_UUID> [--host 10.20.0.5 --port 8090 --key vwc --hours 24]
Fallback if device metrics are not retained: export uplinks (decoded object) to CSV from the ChirpStack UI/DB
and convert to readings.csv with the same three columns.
NOTE: REST endpoint paths follow the ChirpStack v4 REST gateway (/api/devices, /api/devices/{dev_eui}/metrics);
verify against the live server on site.
"""
```
- The token is read only from the environment variable CHIRPSTACK_TOKEN. If it is missing, the script exits with "CHIRPSTACK_TOKEN not set in environment - nothing pulled" [S24].
- The token is used only in the `Authorization: Bearer` header. A grep for print statements that include the token found none [S25].
- VWC is the decoded payload key as reported (default `vwc`), with no conversion from raw counts [S26].
- The REST paths and the port 8090 default were not tested here and must be checked on site [S26].
- I could not see the part of the script that reports the device count against the expected 12. Check it on site.

**Code: analyse_vwc.py.** I did not see its source, so I am not reproducing it as code. I saw only that it compiles [S25].
- Required behaviour, from the brief:
  - Read readings.csv.
  - Per probe, give the count, expected count, coverage %, and mean VWC.
  - Exclude values outside 0–100 and report how many were excluded [unverified: figure from the brief, not seen in the script source].
  - Set below_20 only when the mean is strictly below 20.0 [unverified: figure from the brief, not seen in the script source].
  - Flag coverage under 75% as LOW COVERAGE [unverified: figure from the brief, not seen in the script source].
  - Always output all 12 probes, including those with no data.
- I could not confirm that each of these is implemented. I could not confirm that a synthetic-data test was run. Test the script on site before relying on it.

**probe_averages.csv** [S25]
Columns: probe_id,n_readings,expected_readings,coverage_pct,avg_vwc_pct,below_20,status

| probe_id | n_readings | expected | coverage_pct | avg_vwc_pct | below_20 | status |
|---|---|---|---|---|---|---|
| PROBE_ID_UNKNOWN_01 to _12 | blank | 24 | blank | blank | blank | NOT PULLED |

I saw rows 01–07 in the tool output. The other five were cut off, so confirm there are 12 rows. The IDs are placeholders, not real DevEUIs. The expected count of 24 assumes one reading per hour over the 24-hour window.

**run_status.md** [S26]
It says no live data was pulled and gives the run and fallback steps: `export CHIRPSTACK_TOKEN=...; python3 fetch_chirpstack.py <args>; python3 analyse_vwc.py`. From earlier reads, it also gives the source (ChirpStack v4 at 10.20.0.5), the payload key `vwc` (configurable) and the window. I could not re-read the middle of the file, so check that it lists all the missing inputs below.

**Window:** [now−24h, now] in UTC, set at run time. Today is Fri 23 Oct 2026 (America/Chicago).

**Missing inputs the farm must supply**
1. The API token, exported as CHIRPSTACK_TOKEN. It is kept in the farm office. Never store it in a file.
2. The ChirpStack application or device-group ID for Field 7.
3. The real probe IDs, and the actual device count against the expected 12.
4. The confirmed decoded payload key for VWC (default `vwc`). Probes whose payload lacks the key must be flagged.
5. The probe-to-row mapping (the farm layout or probe-location list). Without it the irrigation order cannot be written.
6. Confirmation of the REST port and endpoint paths. The 8090 default is unverified [S26].
BLOCKED: ChirpStack API access — could not pull the last 24 h of readings: no network and no CHIRPSTACK_TOKEN in this run
BLOCKED: Probe-to-row mapping — not supplied, so the Field 7 irrigation order cannot be written
MISSING DATA: CHIRPSTACK_TOKEN — not set in the environment; the farm office holds it
MISSING DATA: Field 7 application/device-group ID — not in the task or workspace
MISSING DATA: Real probe IDs (DevEUIs) for the 12 probes — not in the workspace
MISSING DATA: Probe-to-row layout/mapping file — not in the workspace
MISSING DATA: Full source of analyse_vwc.py and fetch_chirpstack.py, and any synthetic-test result — tool output was truncated, so these were not confirmed
