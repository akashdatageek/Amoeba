# Field 7 soil-probe pull: status NOT PULLED

**No live ChirpStack data was pulled.** The token is not available and the sandbox has no network. No VWC averages are reported. There is no list of probes below 20%, so the irrigation order cannot be written yet. The scripts and the NOT PULLED files are ready for on-site use.

## Table: probe_averages.csv (12 probes)
The file has a header plus 12 rows [S35]. Every row is NOT PULLED. Expected readings are 24 per probe (hourly over 24 h) [S35]. The IDs `PROBE_ID_UNKNOWN_01` to `_12` are placeholders. They are not real probe IDs, because the farm has not supplied any.

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

## Code: the two scripts (files in the workspace)
- `fetch_chirpstack.py` is 3166 bytes and `analyse_vwc.py` is 2567 bytes [S35]. Only excerpts of their source were visible in my last outputs, so I show how to run them and what I could confirm. The full code is in the files.
- Fetch script:
  - It uses the ChirpStack v4 REST API at 10.20.0.5. The docstring gives port 8090 [S33].
  - It reads the token only from the environment: `tok = os.environ.get("CHIRPSTACK_TOKEN")` [S34]. The token is never hard-coded or printed.
  - VWC comes from the configurable decoded payload key (default `vwc`), with no conversion.
  - It writes `readings.csv` (probe_id,timestamp_utc,vwc_pct).
  - It prints a warning if a probe's payload lacks the key. It also prints a warning if the device count is not the expected 12 [S35].
  - Fallback if device metrics are not retained: export uplinks to a CSV with the same three columns and run `analyse_vwc.py` on it [S33].
  - The REST endpoint paths follow the v4 REST gateway convention and have **not** been tested against the real server [S33].
- Analyse script:
  - Options are --readings, --probes, --out, --expected, --n-probes and --min-cov [S34].
  - It is built to compute count, expected count and coverage %. It is also built to compute the mean VWC after excluding values outside 0-100, and to flag below_20 as a strict mean < 20.0.
  - Coverage under 75% is flagged LOW COVERAGE. All 12 probes are written out, including those with no data.
  - I could not re-read the full source in this step. The exclusion count and the "missing key" handling are therefore not confirmed by me.

```bash
# on a machine that can reach 10.20.0.5
export CHIRPSTACK_TOKEN=...      # from the farm office; never commit it
python3 fetch_chirpstack.py --app-id <FIELD7_APPLICATION_UUID> \
    --host 10.20.0.5 --port 8090 --key vwc --hours 24
python3 analyse_vwc.py           # reads readings.csv, writes probe_averages.csv
```

Synthetic test: the analyser was run on clearly labelled synthetic data in `synthetic_test/` (probe IDs SYN_1, SYN_2). It gave SYN_1 mean 15.0, below_20 TRUE, and SYN_2 mean 25.0, below_20 FALSE, both 24/24 readings and status OK [S33]. This is test data only. It is kept out of probe_averages.csv and is not farm data.

## Memo: run_status.md
`run_status.md` is written (1629 bytes [S35]). It records the following:
- **Source:** ChirpStack v4 at 10.20.0.5.
- **Payload key:** `vwc` (default, set with `--key`), taken as reported by the probe.
- **Window:** last 24 h, [now-24h, now] in UTC. For this run the date is Friday 23 Oct 2026, America/Chicago.
- **Result:** NOT PULLED.
- **Missing inputs:** the list below.

## Missing inputs from the farm
1. The ChirpStack API token, exported as env `CHIRPSTACK_TOKEN` on a machine that can reach 10.20.0.5.
2. The application or device-group ID for Field 7, and the REST port (script default 8090).
3. Confirmation that the decoded payload key for VWC is `vwc`. Probes without the key are flagged, not derived.
4. The probe-to-row layout or probe-location list. It is needed to turn probes with mean below 20.0 into an irrigation order for their rows.
5. The real probe IDs and the actual device count, to compare with the expected 12.

## Next step
Run the fetch script and then the analyse script on site. Then write the irrigation order for the rows of the probes with mean VWC strictly below 20.0.
BLOCKED: ChirpStack API access — no token and no network in the sandbox, so the 24h readings could not be pulled
BLOCKED: Probe-to-row mapping source — no layout or probe-location list was supplied, so the irrigation order could not be written
MISSING DATA: CHIRPSTACK_TOKEN value — held in the farm office, not in the workspace
MISSING DATA: Field 7 application or device-group ID — not in the task or workspace
MISSING DATA: Probe-to-row layout for Field 7 — not found in the workspace
MISSING DATA: Real probe IDs for the 12 probes — none supplied; placeholders used in the CSV
