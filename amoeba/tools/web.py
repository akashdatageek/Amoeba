"""D32 — the first real tools: web_search and fetch_url, behind one provider interface (Tavily for now).

Every result gets a source id (S1, S2, ... per run) with url, title and the time fetched, so a step's artifact can
list its sources and later checks (D33) can tell a cited fact from an invented one. Limits live here, in code:
results per search, searches and fetches per step, characters per fetched page, and a timeout. A failure never
raises into the run: the helper gets an "error: ..." string and the trace gets a `tool_error` event.

The key is read from the TAVILY_API_KEY environment variable, never from a file. In the Claude Code cloud
environment, `api.tavily.com` must be on the network allowlist (search and page extraction both go through it).
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

WEB_TOOLS = ("web_search", "fetch_url")
TAVILY_URL = "https://api.tavily.com"
TAVILY_KEY_ENV = "TAVILY_API_KEY"


class WebToolError(RuntimeError):
    pass


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int) -> list[dict]:
        """[{title, url, snippet}], best first."""

    def fetch(self, url: str) -> dict:
        """{url, title, text}: the page as clean text."""


class TavilyProvider:
    """Tavily search (/search) and page extraction (/extract); both on api.tavily.com."""

    name = "tavily"

    def __init__(self, api_key: str | None = None, timeout_s: float = 20.0):
        self.api_key = api_key or os.environ.get(TAVILY_KEY_ENV, "")
        if not self.api_key:
            raise WebToolError(f"{TAVILY_KEY_ENV} is not set")
        self.timeout_s = timeout_s

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(f"{TAVILY_URL}/{path}", data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
            return json.loads(r.read().decode("utf-8"))

    def search(self, query: str, max_results: int) -> list[dict]:
        data = self._post("search", {"query": query, "max_results": max_results, "search_depth": "basic"})
        return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")}
                for x in data.get("results", [])]

    def fetch(self, url: str) -> dict:
        data = self._post("extract", {"urls": [url]})
        ok = data.get("results") or []
        if not ok:
            why = (data.get("failed_results") or [{}])[0].get("error", "no content")
            raise WebToolError(f"could not extract {url}: {why}")
        return {"url": ok[0].get("url", url), "title": ok[0].get("title", "") or url, "text": ok[0].get("raw_content", "")}


@dataclass
class WebLimits:
    max_results: int = 5            # results per web_search
    max_searches_per_step: int = 4
    max_fetches_per_step: int = 3
    max_fetch_chars: int = 6000     # characters of one fetched page passed to the helper
    snippet_chars: int = 300
    timeout_s: float = 20.0

    def as_trace(self) -> dict:
        return {f"amoeba.web.{k}": v for k, v in self.__dict__.items()}


@dataclass
class WebTools:
    """The two tools for one run: the provider, the limits, the run's source list and per-step counters."""

    provider: SearchProvider
    limits: WebLimits = field(default_factory=WebLimits)
    sources: list[dict] = field(default_factory=list)
    step: int | None = None
    trace: object | None = None
    _used: dict = field(default_factory=dict)

    def begin_step(self, step: int, trace=None) -> None:
        self.step, self._used = step, {"web_search": 0, "fetch_url": 0}
        if trace is not None:
            self.trace = trace

    def sources_for(self, step: int) -> list[dict]:
        return [s for s in self.sources if step in s["steps"]]

    def _source(self, url: str, title: str, kind: str, query: str = "") -> dict:
        """The source record for a url: reused when the url was seen before (same S# across the run)."""
        for s in self.sources:
            if s["url"] == url:
                if self.step is not None and self.step not in s["steps"]:
                    s["steps"].append(self.step)
                if kind == "fetch":   # the page itself was read now
                    s["fetched"] = True
                    s["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                return s
        s = {"id": f"S{len(self.sources) + 1}", "url": url, "title": title, "kind": kind, "query": query,
             "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fetched": kind == "fetch",
             "steps": [self.step] if self.step is not None else []}
        self.sources.append(s)
        return s

    def _event(self, name: str, attrs: dict) -> None:
        if self.trace is not None:
            self.trace.event(name, {"amoeba.step": self.step, **attrs})

    def _fail(self, tool: str, why: str) -> str:
        self._event("tool_error", {"gen_ai.tool.name": tool, "error.type": why[:300]})
        return f"error: {tool} failed: {why}"

    def _quota(self, tool: str, cap: int) -> str | None:
        if self._used.get(tool, 0) >= cap:
            self._event("tool_limit", {"gen_ai.tool.name": tool, "amoeba.limit": cap})
            return f"error: {tool} limit reached ({cap} per step); work with the sources you have"
        self._used[tool] = self._used.get(tool, 0) + 1
        return None

    def web_search(self, query: str) -> str:
        query = query.strip().strip('"')
        if not query:
            return "error: web_search needs a query"
        if (stop := self._quota("web_search", self.limits.max_searches_per_step)):
            return stop
        try:
            results = self.provider.search(query, self.limits.max_results)
        except (WebToolError, urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
            return self._fail("web_search", f"{type(e).__name__}: {e}")
        if not results:
            return f'No results for "{query}".'
        lines = [f'Search results for "{query}" (cite a fact by its [S#]; fetch_url a result to read the page):']
        ids = []
        for r in results[: self.limits.max_results]:
            s = self._source(r["url"], r["title"], "search", query)
            ids.append(s["id"])
            snippet = re.sub(r"\s+", " ", r.get("snippet", ""))[: self.limits.snippet_chars]
            lines.append(f"[{s['id']}] {r['title']} — {r['url']}\n    {snippet}")
        self._event("web_search", {"amoeba.query": query, "amoeba.results": len(results), "amoeba.source_ids": ids})
        return "\n".join(lines)

    def fetch_url(self, url: str) -> str:
        url = url.strip().strip("<>\"'")
        m = re.match(r"^\[?(S\d+)\]?$", url)          # a helper may name a source id instead of its url
        if m:
            known = next((s for s in self.sources if s["id"] == m.group(1)), None)
            if known is None:
                return f"error: fetch_url: no source {m.group(1)} in this run"
            url = known["url"]
        if not re.match(r"^https?://", url):
            return "error: fetch_url needs an http(s) url"
        if (stop := self._quota("fetch_url", self.limits.max_fetches_per_step)):
            return stop
        try:
            page = self.provider.fetch(url)
        except (WebToolError, urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
            return self._fail("fetch_url", f"{type(e).__name__}: {e}")
        text = re.sub(r"\n{3,}", "\n\n", page.get("text", "")).strip()
        cut = text[: self.limits.max_fetch_chars]
        s = self._source(page.get("url", url), page.get("title", "") or url, "fetch")
        self._event("fetch_url", {"amoeba.url": url, "amoeba.source_id": s["id"], "amoeba.chars": len(text),
                                  "amoeba.chars_passed": len(cut)})
        more = f", first {len(cut)} of {len(text)} characters" if len(text) > len(cut) else ""
        return f"[{s['id']}] {s['title']} ({s['url']}), fetched {s['fetched_at']}{more}:\n{cut}"


def web_registry(provider: SearchProvider | None = None, limits: WebLimits | None = None):
    """A fresh Box 3 registry for one run: echo, calc, web_search and fetch_url (Tavily unless a provider is given)."""
    from amoeba.tools.registry import default_registry
    reg = default_registry()
    register_web_tools(reg, WebTools(provider or TavilyProvider(), limits or WebLimits()))
    return reg


def register_web_tools(registry, web: WebTools) -> None:
    """Adds web_search and fetch_url to a Box 3 registry; `registry.web` keeps the run's WebTools."""
    registry.register("web_search", "searches the web; input: a query; returns titles, urls and snippets as [S#]",
                      web.web_search)
    registry.register("fetch_url", "reads one web page; input: a url (or an [S#] from web_search); returns its text",
                      web.fetch_url)
    registry.web = web
