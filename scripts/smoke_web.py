"""One real call to each web tool (D32). Not part of pytest: it needs TAVILY_API_KEY and network access to
api.tavily.com (in the Claude Code cloud environment, add that domain to the network allowlist).

    python -m scripts.smoke_web "Amazon RDS for PostgreSQL storage price per GB-month"
"""
from __future__ import annotations

import sys

from amoeba.interp.trace import TraceWriter
from amoeba.tools.web import TavilyProvider, WebLimits, WebTools


def main(argv: list[str] | None = None) -> int:
    query = " ".join(argv if argv is not None else sys.argv[1:]) or "Amazon RDS for PostgreSQL pricing"
    trace = TraceWriter(None)
    web = WebTools(TavilyProvider(), WebLimits(max_fetch_chars=1500))
    web.begin_step(1, trace)
    print(web.web_search(query), "\n")
    first = web.sources[0]["id"] if web.sources else None
    if first:
        print(web.fetch_url(first)[:1800], "\n")
    for ev in trace.events():
        print(ev["name"], {k: v for k, v in ev.items() if k.startswith("amoeba.") or k.startswith("error")})
    return 1 if trace.events("tool_error") else 0


if __name__ == "__main__":
    sys.exit(main())
