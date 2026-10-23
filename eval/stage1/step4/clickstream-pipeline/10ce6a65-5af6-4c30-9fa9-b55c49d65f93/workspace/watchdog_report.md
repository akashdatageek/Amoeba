# watchdog_report.md - late-job watchdog simulation (NOT SENT)

Rule: page when the job has not finished by SLA deadline + 30 min. Exactly +30 min is not a page; +31 min is. Simulated SLA deadline = 2026-10-22T04:00:00+00:00 (example), run_date = 2026-10-21.

Simulation was run with Python (`python3 sim_watchdog.py`). Result: ALL PASS (15/15).

## Scenario x expected x actual
| Scenario | Expected | Actual | Result | Note |
|---|---|---|---|---|
| 1 On time: success at SLA-10 min, checked at SLA+5 | no page | no page | PASS |  |
| 1b On time: success at SLA-10 min, checked at SLA+45 | no page | no page | PASS |  |
| 2 Not finished, checked at SLA+29 min | no page | no page | PASS |  |
| 3 Not finished, checked at exactly SLA+30 min | no page | no page | PASS |  |
| 4 Not finished, checked at SLA+31 min | page | page | PASS |  |
| 5 Finished late at SLA+31 min, checked at SLA+31 | page | page | PASS |  |
| 6 Finished at SLA+29 min, checked at SLA+45 | no page | no page | PASS |  |
| 7 Never started, no run row, at SLA+30 | no page | no page | PASS | exactly +30 is not a page |
| 7b Never started, at SLA+30 min 1 s | page | page | PASS |  |
| 8 Still running (no SUCCESS row) at SLA+30 | no page | no page | PASS |  |
| 8b Still running (no SUCCESS row) at SLA+31 | page | page | PASS | payload last_stage shows where it is |
| 9 Repeated checks at +31,+36,+41: distinct dedup_key values (PagerDuty folds same key into one incident) | 1 distinct key, 3 identical triggers | 1 distinct key, 3 identical triggers | PASS | dedup_key=dau-nightly-2026-10-21 |
| 10 Naive (timezone-less) datetime passed | ValueError | ValueError | PASS |  |
| 11 Resolve payload carries same dedup_key as trigger | True | True | PASS |  |
| 12 Trigger payload fields (event_action trigger, severity critical, placeholder routing key) | True | True | PASS |  |

## Payload files (all marked NOT SENT)
- payloads/trigger.NOT_SENT.json
- payloads/resolve.NOT_SENT.json

Trigger payload (NOT SENT):
```json
{
  "routing_key": "<PAGERDUTY_ROUTING_KEY_PLACEHOLDER>",
  "event_action": "trigger",
  "dedup_key": "dau-nightly-2026-10-21",
  "payload": {
    "summary": "DAU nightly job for 2026-10-21 not finished 30 min after SLA 2026-10-22T04:00:00+00:00; last stage: dedup (MERGE CLEAN.EVENTS)",
    "source": "dau-nightly-watchdog",
    "severity": "critical",
    "custom_details": {
      "run_date": "2026-10-21",
      "sla_deadline_utc": "2026-10-22T04:00:00+00:00",
      "grace_minutes": 30,
      "last_stage": "dedup (MERGE CLEAN.EVENTS)",
      "runbook": "runbook.md"
    }
  }
}
```
Resolve payload (NOT SENT):
```json
{
  "routing_key": "<PAGERDUTY_ROUTING_KEY_PLACEHOLDER>",
  "event_action": "resolve",
  "dedup_key": "dau-nightly-2026-10-21"
}
```

## How the dedup_key works
Every check for the same run date builds the same dedup_key (`dau-nightly-<run_date>`). Repeated triggers within the same open incident are folded by PagerDuty into one incident (PagerDuty behaviour, not exercised here: nothing was sent). The watchdog may re-send every 5 min; scenario 9 shows 3 triggers with 1 distinct key. Success sends a resolve with the same key.

## watchdog.py
```python
"""Late-job watchdog for the nightly DAU pipeline.  NOTHING IS SENT from this module.

Rule: the job must have succeeded by sla_deadline + grace (grace = 30 min).
  * now <= sla_deadline + grace            -> never a page (exactly +30 min is NOT a page)
  * now >  sla_deadline + grace            -> page, unless a success at or before sla_deadline + grace exists
All datetimes must be timezone-aware (UTC recommended).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

ROUTING_KEY_PLACEHOLDER = "<PAGERDUTY_ROUTING_KEY_PLACEHOLDER>"
EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"
GRACE = timedelta(minutes=30)


def _check_aware(*vals):
    for v in vals:
        if v is not None and (v.tzinfo is None or v.utcoffset() is None):
            raise ValueError("naive datetime not allowed; pass timezone-aware values")


def should_page(now: datetime, sla_deadline: datetime,
                last_success_ts: Optional[datetime],
                grace: timedelta = GRACE) -> bool:
    """Pure function. True when a page is warranted at time `now`.

    last_success_ts = finish time of the SUCCESS row for this run_date in OPS.JOB_RUNS
    (None if there is none: never started, still running, or failed).
    """
    _check_aware(now, sla_deadline, last_success_ts)
    limit = sla_deadline + grace
    if now <= limit:                      # strictly greater than +30 min is required
        return False
    if last_success_ts is not None and last_success_ts <= limit:
        return False                      # finished within SLA + grace
    return True                           # not finished by limit (or finished late)


def dedup_key(run_date: str) -> str:
    return f"dau-nightly-{run_date}"


def build_trigger_payload(run_date: str, sla_deadline: datetime, last_stage: str,
                          routing_key: str = ROUTING_KEY_PLACEHOLDER,
                          grace: timedelta = GRACE) -> dict:
    """PagerDuty Events API v2 'trigger' body (not sent)."""
    _check_aware(sla_deadline)
    sla_iso = sla_deadline.astimezone(timezone.utc).isoformat()
    return {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": dedup_key(run_date),
        "payload": {
            "summary": (f"DAU nightly job for {run_date} not finished "
                        f"{int(grace.total_seconds() // 60)} min after SLA {sla_iso}; last stage: {last_stage}"),
            "source": "dau-nightly-watchdog",
            "severity": "critical",
            "custom_details": {
                "run_date": run_date,
                "sla_deadline_utc": sla_iso,
                "grace_minutes": int(grace.total_seconds() // 60),
                "last_stage": last_stage,
                "runbook": "runbook.md",
            },
        },
    }


def build_resolve_payload(run_date: str, routing_key: str = ROUTING_KEY_PLACEHOLDER) -> dict:
    """PagerDuty Events API v2 'resolve' body (same dedup_key as the trigger; not sent)."""
    return {"routing_key": routing_key, "event_action": "resolve", "dedup_key": dedup_key(run_date)}

```

Limitations: nothing was sent; Snowflake and PagerDuty were not reached. The routing key is a placeholder, last_success_ts is passed in by the test rather than read from OPS.JOB_RUNS, and PagerDuty-side dedup is assumed from the Events API v2 contract, not observed. The 04:00 UTC SLA is an example value.
