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
