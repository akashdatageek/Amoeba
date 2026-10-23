I read "cloud warehouse" as Snowflake; if you meant Google BigQuery or Amazon Redshift or Databricks / Azure Synapse, the answer below may not apply. I read "duplicate events" as Events sharing the same event_id, from Kafka at-least-once redelivery; if you meant Events identical on a composite key (user, timestamp, type, etc.) or Fully identical rows across all fields, the answer below may not apply. I read "finishes more than 30 minutes late" as Later than 30 minutes after the scheduled completion deadline or SLA time; if you meant Runtime exceeding the expected duration by 30 minutes or More than 30 minutes after the scheduled start time, the answer below may not apply. I read "one year of raw events" as 365 days × 30M × 2 KB, about 180 GB (3 days × 30M events × 2 KB, decimal KB). The worker' TB uncompressed; if you meant Compressed columnar storage in the warehouse, a fraction of 22 TB or Includes duplicates and replicas or retention overhead, the answer below may not apply.

# Step 5: late-job watchdog and PagerDuty payloads (watchdog_report.md)

**The simulation was run.** I ran it with Python 3 (`python3 sim_watchdog.py`). All 15 checks passed [S49]. Nothing was sent. The SLA deadline in the simulation is an example, 2026-10-22 04:00 UTC. The run_date is 2026-10-21.

**Rule.** Page when the job has not finished by SLA deadline + 30 min. Exactly +30 min is not a page. +31 min is a page.

## Files saved in the workspace
- `watchdog.py` has `should_page(now, sla_deadline, last_success_ts, grace=30 min)`, `build_trigger_payload(run_date, sla_deadline, last_stage, routing_key, grace)` and `build_resolve_payload(run_date, routing_key)` [S48, S49].
- `sim_watchdog.py` is the scenario runner.
- `watchdog_report.md` is 6,606 bytes [S49]. It holds the table, both payloads, the dedup explanation, the full watchdog.py source and the Limitations line.
- `payloads/trigger.NOT_SENT.json` and `payloads/resolve.NOT_SENT.json`. Each file carries `"STATUS": "NOT SENT - simulation only; routing_key is a placeholder"` [S49].

## Core logic (from watchdog.py [S48])
```python
limit = sla_deadline + grace
if now <= limit:                      # strictly greater than +30 min is required
    return False
if last_success_ts is not None and last_success_ts <= limit:
    return False                      # finished within SLA + grace
return True                           # not finished by limit (or finished late)
```
- `should_page` is pure. It raises ValueError if any datetime has no timezone (scenario 10).
- `last_success_ts` is the finish time of the SUCCESS row for this run_date in OPS.JOB_RUNS. It is None when the job never started, is still running, or failed.
- The trigger payload has these fields [S48, S49]:
  - `event_action` = trigger.
  - `severity` = critical.
  - `dedup_key` = `dau-nightly-<run_date>`.
  - `routing_key` = `<PAGERDUTY_ROUTING_KEY_PLACEHOLDER>`.
  - A summary and custom_details with run date, SLA and last stage.
- The resolve payload has `event_action` = resolve and the same dedup_key [S48].

## Scenario x expected page x actual page [S49]
| Scenario | Expected | Actual | Result |
|---|---|---|---|
| 1 On time: success at SLA-10 min, checked at SLA+5 | no page | no page | PASS |
| 1b On time: success at SLA-10 min, checked at SLA+45 | no page | no page | PASS |
| 2 Not finished, checked at SLA+29 min | no page | no page | PASS |
| 3 Not finished, checked at exactly SLA+30 min | no page | no page | PASS |
| 4 Not finished, checked at SLA+31 min | page | page | PASS |
| 5 Finished late at SLA+31 min, checked at SLA+31 | page | page | PASS |
| 6 Finished at SLA+29 min, checked at SLA+45 | no page | no page | PASS |
| 7 Never started (no run row), at SLA+30 | no page | no page | PASS |
| 7b Never started, at SLA+30 min 1 s | page | page | PASS |
| 8 Still running (no SUCCESS row) at SLA+30 | no page | no page | PASS |
| 8b Still running at SLA+31 | page | page | PASS |
| 9 Repeated checks at +31, +36, +41: dedup_key values | 1 distinct key, 3 identical triggers | 1 distinct key, 3 identical triggers (dedup_key=dau-nightly-2026-10-21) | PASS |
| 10 Naive (timezone-less) datetime passed | ValueError | ValueError | PASS |
| 11 Resolve payload carries same dedup_key as trigger | True | True | PASS |
| 12 Trigger has event_action trigger, severity critical, placeholder routing key | True | True | PASS |

Key results:
- SLA+29 min gives no page.
- SLA+31 min gives a page.
- A job that never finished gives no page at exactly SLA+30 min and a page 1 s later. This follows the settled rule that exactly +30 min is not a page.

## How dedup works
- Every check for one run date builds the same dedup_key, `dau-nightly-<run_date>`. The watchdog can re-send every 5 min.
- Scenario 9 shows 3 triggers with 1 distinct key.
- PagerDuty folding same-key triggers into one incident is the Events API v2 contract. It was not observed, because nothing was sent.
- On success, send a resolve with the same key.

## Behaviour to know for the runbook
- `should_page` stays True after a run that finished late (scenario 5). It does not turn False on its own.
- The page is therefore cleared by the resolve payload, which the pipeline's finalizer or the on-call engineer must send. The runbook's resolve step must say so.

**Limitations:** nothing was sent; Snowflake and PagerDuty were not reached. The routing key is a placeholder. `last_success_ts` is passed in by the test and not read from OPS.JOB_RUNS. PagerDuty-side dedup is assumed from the API contract and was not observed. The 04:00 UTC SLA is an example value. How the 5-minute scheduler is deployed and monitored was not tested.
BLOCKED: PagerDuty and Snowflake network access — real trigger delivery, PagerDuty-side dedup and reading OPS.JOB_RUNS could not be tested; payloads are marked NOT SENT
