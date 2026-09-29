"""D75 — the run's clock: today's date, weekday and time zone, given to every Box 3 step prompt.

A model does not know what day it is; asked about "today" it guesses (a BMV run decided it was "Tuesday, May 14,
2024"). The run passes the date instead. The time zone is the run's (``--timezone``, an IANA name; default the
machine's local zone). Only the date is given, not the time of day, so a crashed run resumed the same day replays its
prompts from the cache (D73).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


# box: plan_step
def run_clock(tz: str | None = None, today: date | None = None, now: datetime | None = None) -> dict:
    """{"date": date, "weekday": "Tuesday", "tz": "America/Chicago", "line": "Today is Tuesday, 29 September 2026 …"}."""
    zone = None
    if tz:
        try:
            zone = ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"unknown time zone {tz!r}: use an IANA name such as America/Chicago or UTC") from e
    moment = now or datetime.now(timezone.utc)
    moment = moment.astimezone(zone) if zone else moment.astimezone()      # the date where the run is
    day = today or moment.date()
    name = tz or moment.tzname() or "local"
    line = (f"Today is {day:%A}, {day.day} {day:%B} {day.year} (time zone of this run: {name}). Use this date for "
            f"anything the task says about today, now, current or latest; do not guess the date.")
    return {"date": day, "weekday": f"{day:%A}", "tz": name, "line": line}
