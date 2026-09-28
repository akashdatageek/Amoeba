"""D67 — freshness of figures for tasks that ask for today's, the current or the latest value.

Plain code decides whether a task is time-sensitive (its wording), finds the dates the team's outputs give for their
figures ("as of Sep 14, 2026", "Date: 2026-09-14", "09/14/26" …) and, when the newest one is more than
MAX_AGE_DAYS before the run, the answer's Limitations say the figure is possibly not the latest.
"""
from __future__ import annotations

import re
from datetime import date

MAX_AGE_DAYS = 3
TIME_WORDS = re.compile(r"\b(today|today's|todays|current|currently|latest|now|right now|this week|most recent|live)\b",
                        re.I)
MONTHS = {m: i for i, ms in enumerate(("jan january", "feb february", "mar march", "apr april", "may", "jun june",
                                       "jul july", "aug august", "sep sept september", "oct october",
                                       "nov november", "dec december"), 1) for m in ms.split()}
_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|" \
       r"nov(?:ember)?|dec(?:ember)?)\.?"
PATTERNS = [
    (re.compile(rf"\b{_MON}\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I), "mdy_name"),
    (re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MON},?\s+(\d{{4}})\b", re.I), "dmy_name"),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "iso"),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\b"), "us"),
]


# box: plan_summary
def time_sensitive(task_text: str) -> bool:
    """The task asks for today's, the current or the latest value."""
    return bool(TIME_WORDS.search(task_text or ""))


ASOF = re.compile(r"(as of|as at|dated|date|updated|week of|week ending|recorded|published|released|reported|data for|"
                  r"price on|valid on)\W{0,6}$", re.I)


def dates_in(text: str, as_of_only: bool = False) -> list[tuple[date, str]]:
    """Every date written in `text`, with the text it was written as. as_of_only: only a date that says when a
    figure was true ("as of …", "Date: …", "updated …"), not a date that is itself the fact (a start date)."""
    out = []
    for rx, kind in PATTERNS:
        for m in rx.finditer(text or ""):
            try:
                if kind == "mdy_name":
                    d = date(int(m.group(3)), MONTHS[m.group(1).lower()[:3]], int(m.group(2)))
                elif kind == "dmy_name":
                    d = date(int(m.group(3)), MONTHS[m.group(2).lower()[:3]], int(m.group(1)))
                elif kind == "iso":
                    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                else:
                    y = int(m.group(3))
                    d = date(y + 2000 if y < 100 else y, int(m.group(1)), int(m.group(2)))
            except (ValueError, KeyError):
                continue
            if as_of_only and not ASOF.search((text or "")[max(0, m.start() - 30):m.start()]):
                continue
            out.append((d, m.group(0)))
    return out


# box: plan_summary
def stale_figure(texts: list[str], today: date) -> dict | None:
    """The newest as-of date the outputs give for a figure, when it is older than MAX_AGE_DAYS: {date, as, days}.
    Dates after today (a forecast, a deadline) are ignored; None when there is no date or the newest is recent."""
    found = [(d, s) for t in texts for d, s in dates_in(t, as_of_only=True) if d <= today]
    if not found:
        return None
    d, s = max(found)
    age = (today - d).days
    return {"date": d.isoformat(), "as": s, "days": age} if age > MAX_AGE_DAYS else None
