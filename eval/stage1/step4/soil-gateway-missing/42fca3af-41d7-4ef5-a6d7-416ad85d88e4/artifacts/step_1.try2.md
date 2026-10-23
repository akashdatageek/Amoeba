# Step 1 result: ChirpStack pull and VWC analysis

## Status
**NOT PULLED.** No live ChirpStack data was pulled from 10.20.0.5. The sandbox has no network, and CHIRPSTACK_TOKEN is not set because the token is kept in the farm office. Both scripts are written. analyse_vwc.py was run only on labelled synthetic data. It has not been run on real data. No probe can be named as below 20%, and no irrigation order can be written.

## probe_averages.csv (12 rows, all NOT PULLED)
Columns in the file: probe_id,n_readings,expected_readings,coverage_pct,avg_vwc_pct,below_20,status. Its first rows were re-checked in [S20]. The 12 IDs are placeholders, not real probe IDs. Real DevEUIs or names must come from ChirpStack.

| probe_id | n_readings | expected_readings | coverage_pct | avg_vwc_pct | below_20 | status |
|---|---|---|---|---|---|---|
| PROBE_ID_UNKNOWN_01 | blank | 24 | blank | blank | blank | NOT PULLED |
| PROBE_ID_UNKNOWN_02 | blank | 24 | blank | blank | blank | NOT PULLED |
| PROBE_ID_UNKNOWN_03 | blank | 24 | blank | blank | blank | NOT PULLED |
| PROBE_ID_UNKNOWN_04 | blank | 24 | blank | blank | blank | NOT PULLED |
| PROBE_ID_UNKNOWN_05 | blank | 24 | blank | blank | blank | NOT PULLED |
| PROBE_ID_UNKNOWN_06 | blank | 24 | blank | blank | blank | NOT PULLED |
| PROBE_ID_UNKNOWN_07 | blank | 24 | blank | blank | blank | NOT PULLED |
| PROBE_ID_UNKNOWN_08 | blank | 24 | blank | blank | blank | NOT PULLED |
| PROBE_ID_UNKNOWN_09 | blank | 24 | blank | blank | blank | NOT PULLED |
| PROBE_ID_UNKNOWN_10 | blank | 24 | blank | blank | blank | NOT PULLED |
| PROBE_ID_UNKNOWN_11 | blank | 24 | blank | blank | blank | NOT PULLED |
| PROBE_ID_UNKNOWN_12 | blank | 24 | blank | blank | blank | NOT PULLED |

I confirmed the file has 12 rows in [S18]. In [S20] I saw the header and the first two data rows; the rest follow the same pattern.

## Code
Both scripts are in the workspace. I did not re-read the full text of either in this last turn, so only the confirmed excerpts are shown here.

```python
# fetch_chirpstack.py  (header, as seen in [S19]) -- for ON-SITE use
# Usage: CHIRPSTACK_TOKEN=... python3 fetch_chirpstack.py --app-id <APPLICATION_UUID> \
#        [--host 10.20.0.5 --port 8090 --key vwc --hours 24]
# - token is read only from the env var CHIRPSTACK_TOKEN (never hard-coded, never printed)
# - VWC is read as reported from the decoded payload key (default 'vwc'); no conversion
# - writes readings.csv (probe_id,timestamp_utc,vwc_pct)
# - fallback: if device metrics are not retained, export uplinks (decoded object) to CSV
#   and convert to the same three columns
# - REST paths (/api/devices, /api/devices/{dev_eui}/metrics) are NOT tested; verify them on site

# analyse_vwc.py  (docstring, as seen in [S20])
# Per-probe VWC stats from readings.csv (probe_id,timestamp_utc,vwc_pct). Always writes 12 probe rows.
# VWC is used exactly as reported in the payload; values outside 0-100 are excluded and counted.
# below_20 = mean < 20.0 (strict, tested on the unrounded mean). coverage < 75% -> LOW COVERAGE.
# If readings.csv is missing -> every row is NOT PULLED with blank averages.
# Options: --readings --probes --out --expected (default 24) --n-probes (default 12) --min-cov (default 75.0)
```

On-site run:
```bash
export CHIRPSTACK_TOKEN=...   # supplied by the farm office
python3 fetch_chirpstack.py --app-id <FIELD7_APPLICATION_UUID> --key vwc --hours 24
python3 analyse_vwc.py --readings readings.csv --probes <probe_list.txt> --out probe_averages.csv
```

## Tests
- py_compile passed on both scripts [S18].
- I ran analyse_vwc.py on `synthetic_test/SYNTHETIC_readings.csv` with `--n-probes 3` [S20]. These numbers are synthetic and are not in probe_averages.csv.
  - SYN_2: 24 readings, 24 expected, 100.0% coverage, mean 25.0, below_20 FALSE, OK.
  - SYN_3: 10 readings, 24 expected, 41.7% coverage, mean 19.9, below_20 TRUE, LOW COVERAGE.
  - SYN_1: mean 15.0, below_20 TRUE, OK. Only the end of this row was visible, so I did not read its count or coverage.
- That run supports the strict below-20 flag and the LOW COVERAGE flag in practice. The synthetic file also holds one out-of-range value to exercise the 0-100 exclusion. I did not read the output that reports how many values were excluded, so that count is not confirmed.
- I did not test fetch_chirpstack.py against a server. There is no network.

## Window and payload key
- Window: the last 24 hours, [now-24h, now] in UTC, hourly. That gives 24 expected readings per probe. The run date is Fri 23 Oct 2026, America/Chicago.
- Payload key: `vwc`, the decoded payload value in %, used as reported. It is configurable with `--key`. This is an assumption: no sample payload was supplied. Probes whose payload lacks the key must be flagged.

## run_status.md
The file was written and is listed in the workspace [S18]. I could not re-read all of it this session. It should state the source used, the payload key, the window, NOT PULLED, and the missing inputs below.

## Missing inputs (the farm must supply)
1. The ChirpStack API token, exported as CHIRPSTACK_TOKEN.
2. The Field 7 application or device-group ID. The device count compared with 12 is unknown until the pull.
3. The real probe IDs, and the confirmed decoded payload key if it is not `vwc`.
4. The probe-to-row mapping (farm layout or probe-location list). Without it the irrigation order cannot be written.
5. Confirmation that the REST port and paths match the script (default port 8090, unverified) and that metrics are retained for 24 hours.
BLOCKED: ChirpStack API access (network and token) — could not list devices or pull the last 24 h of VWC readings from 10.20.0.5
BLOCKED: Farm layout / probe-location list — not supplied, so probes cannot be mapped to irrigation rows
MISSING DATA: CHIRPSTACK_TOKEN API token — kept in the farm office, not in the workspace
MISSING DATA: Field 7 application or device-group ID and the 12 real probe IDs — not in the workspace
MISSING DATA: Probe-to-row mapping for Field 7 — not in the workspace
MISSING DATA: Confirmed decoded payload key for VWC (assumed 'vwc') — no sample payload supplied
