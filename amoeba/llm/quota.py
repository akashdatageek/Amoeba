"""D156/D160 — reading a quota reply. A 429 from Gemini's API says which quota ran out (quotaId: ...PerMinute... or
...PerDay...), its limit (quotaValue) and how long to wait (RetryInfo retryDelay, or "Please retry in 39.6s"). A
per-minute quota clears in seconds and is retried (D48); a daily one does not clear until the next day, so retrying
it only wastes the waits (D160 stops the run instead)."""
from __future__ import annotations

import re


# box: client
def parse_quota(text: str) -> dict | None:
    """{kind: "minute" | "daily", quota_id, limit, retry_s} for a quota reply, or None for any other error."""
    s = str(text or "")
    ids = re.findall(r"quotaId['\"]?\s*[:=]\s*['\"]?([\w.-]+)", s)
    if not ids and "RESOURCE_EXHAUSTED" not in s and "exceeded your current quota" not in s.lower():
        return None
    kind = None
    for q in ids:                                     # a daily quota anywhere in the reply wins: it will not clear
        if re.search(r"Per ?Day|Daily", q, re.I):
            kind = "daily"
            break
        if re.search(r"Per ?Minute", q, re.I):
            kind = "minute"
    if kind is None:
        kind = "daily" if re.search(r"per ?day|daily", s, re.I) else "minute"
    value = re.search(r"quotaValue['\"]?\s*[:=]\s*['\"]?(\d+)", s) or re.search(r"limit:\s*(\d+)", s)
    delay = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?([\d.]+)s", s) or re.search(r"retry in ([\d.]+)\s*s", s)
    return {"kind": kind, "quota_id": ids[0] if ids else None, "limit": int(value.group(1)) if value else None,
            "retry_s": float(delay.group(1)) if delay else None}
