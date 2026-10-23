# Run status: Field 7 VWC pull

- Date of run: Friday 23 October 2026, America/Chicago.
- Source intended: ChirpStack v4 API at 10.20.0.5 (REST/gRPC), Field 7 application or device group.
- Pulled or NOT PULLED: **NOT PULLED**. No network from the sandbox and CHIRPSTACK_TOKEN is not set (env check returned 0).
- Payload key for VWC: `vwc` (default; configurable in fetch_chirpstack.py). It is the decoded payload value as reported, in %. It is never derived from raw counts. Probes whose payload lacks the key are flagged.
- Window: last 24 hours, [now-24h, now] in UTC, hourly. Expected readings: 24 per probe.
- Result: probe_averages.csv has 12 placeholder rows (PROBE_ID_UNKNOWN_01..12), all NOT PULLED, averages blank.
- Actual device count versus 12: unknown.
- Testing: fetch_chirpstack.py was NOT run. analyse_vwc.py was run only on the no-data path. No synthetic test was run.

## Missing inputs the farm must supply
1. The ChirpStack API token, set as env CHIRPSTACK_TOKEN (never paste it into files or chat).
2. The Field 7 application or device-group ID, and confirmation of the 12-device count.
3. The real probe IDs (DevEUIs) for the 12 probes.
4. The probe-to-row mapping (farm layout or probe-location list); needed for the irrigation order.
5. A network route to 10.20.0.5 for whoever runs the scripts.
6. Confirmation that the payload codec outputs the key `vwc`, or the real key name.

## To run on site
`export CHIRPSTACK_TOKEN=...; python3 fetch_chirpstack.py <args>; python3 analyse_vwc.py`
Fallback if metrics are not retained: export a CSV (probe_id,timestamp_utc,vwc_pct) and run analyse_vwc.py on it.
