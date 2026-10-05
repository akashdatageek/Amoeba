"""D111: proxy settings read fresh when a connection drops.

A process keeps the HTTPS proxy it started with. When the proxy restarts on another port (a cloud session restart
does this), every call from a process started before it fails with a connection error. `AMOEBA_PROXY_FILE` names a
file that always holds the current proxy (a line `HTTPS_PROXY=<url>`, else the first `http://127.0.0.1:<port>` or
`http://localhost:<port>` URL in it). On a dropped connection the client reads it, and when the proxy moved it sets
the new value in its environment and rebuilds its HTTP client before the next try; the harness does the same for the
environment it hands each run. Unset (the default, and on a machine without a moving proxy) nothing changes.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

PROXY_FILE_VAR = "AMOEBA_PROXY_FILE"
PROXY_VARS = ("HTTPS_PROXY", "https_proxy")
_LINE = re.compile(r"^\s*(?:export\s+)?HTTPS_PROXY=['\"]?(\S+?)['\"]?\s*$", re.M | re.I)
_URL = re.compile(r"https?://(?:127\.0\.0\.1|localhost):\d+")


# box: client
def fresh_proxy(env=None) -> str | None:
    """The current proxy from the file `AMOEBA_PROXY_FILE` names; None when unset, unreadable or without one."""
    env = os.environ if env is None else env
    path = env.get(PROXY_FILE_VAR)
    if not path:
        return None
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = _LINE.search(text) or _URL.search(text)
    return (m.group(1) if m.re is _LINE else m.group(0)).rstrip("/") if m else None


# box: client
def refresh_proxy(env=None) -> str | None:
    """Set the fresh proxy in `env` (default this process) when it differs from the one there; return it, or None
    when nothing changed. Every variable that held the old value (YARN_, npm_config_, …) gets the new one too."""
    env = os.environ if env is None else env
    new = fresh_proxy(env)
    old = env.get("HTTPS_PROXY") or env.get("https_proxy")
    if not new or (old or "").rstrip("/") == new:
        return None
    for k in list(env):
        if old and env[k] == old:
            env[k] = new
    for k in PROXY_VARS:
        env[k] = new
    return new
