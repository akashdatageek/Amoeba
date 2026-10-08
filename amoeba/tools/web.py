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
from typing import Callable, Protocol

from amoeba.tools.research import (data_ext, data_links, excerpt, official, parse_table, rank_official, split_query,
                                   table_excerpt)

WEB_TOOLS = ("web_search", "fetch_url")
TAVILY_URL = "https://api.tavily.com"
TAVILY_KEY_ENV = "TAVILY_API_KEY"
USER_AGENT = "Mozilla/5.0 (compatible; amoeba-research/1.0; +https://github.com/akashdatageek/amoeba)"


# box: tools
def http_get(url: str, max_bytes: int, timeout_s: float = 20.0) -> tuple[bytes, str]:
    """D106: one direct GET (a data file or a page's links), at most max_bytes; (content, content type)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        body = r.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise WebToolError(f"{url} is larger than {max_bytes:,} bytes")
        return body, r.headers.get("Content-Type", "")


class WebToolError(RuntimeError):
    pass


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int) -> list[dict]:
        """[{title, url, snippet}], best first."""

    def fetch(self, url: str) -> dict:
        """{url, title, text}: the page as clean text."""


# box: tools
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

    def fetch_data(self, url: str, max_bytes: int = 8_000_000) -> dict:
        """D106: a data file read directly and parsed into a table."""
        body, ctype = http_get(url, max_bytes, self.timeout_s)
        ext = data_ext(url) or ("xlsx" if "spreadsheet" in ctype else "csv" if "csv" in ctype else
                                "json" if "json" in ctype else None)
        if ext is None:
            raise WebToolError(f"{url} is not a data file ({ctype or 'unknown type'})")
        return {"url": url, "title": url.rstrip("/").rsplit("/", 1)[-1], "ext": ext, "bytes": len(body),
                "table": parse_table(body, ext)}

    def page_links(self, url: str) -> list[str]:
        """D106: the data-file links of a page's HTML (the extracted text has no links)."""
        body, _ = http_get(url, 3_000_000, self.timeout_s)
        return data_links(body.decode("utf-8", errors="replace"), url, limit=40)


@dataclass
class WebLimits:
    max_results: int = 5            # results per web_search
    max_searches_per_step: int = 4
    max_fetches_per_step: int = 3
    max_fetch_chars: int = 6000     # characters of one fetched page passed to the helper
    snippet_chars: int = 300
    timeout_s: float = 20.0
    # D106 (research on): a packed query becomes at most this many searches; each reads its top `auto_fetch` results
    # (official domains first); per step at most `max_auto_fetches_per_step` such reads and `max_data_files_per_step`
    # data files; each read is shown as an excerpt of `excerpt_chars`
    max_subqueries: int = 4
    auto_fetch: int = 3
    max_auto_fetches_per_step: int = 9
    max_data_files_per_step: int = 4
    data_links_per_page: int = 2
    excerpt_chars: int = 700

    def as_trace(self) -> dict:
        return {f"amoeba.web.{k}": v for k, v in self.__dict__.items()}


# box: tools
def note_seen(source: dict, text: str) -> None:
    """D74: the text a helper was shown for a source (search snippets, the fetched page, a tool's output), so plain
    code can check that what a step cites [S#] for is really in S#."""
    if text:
        source["seen"] = (source.get("seen", "") + "\n" + text)[-60_000:]


# box: tools
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# box: tools
@dataclass
class WebTools:
    """The two tools for one run: the provider, the limits, the run's source list and per-step counters."""

    provider: SearchProvider
    limits: WebLimits = field(default_factory=WebLimits)
    sources: list[dict] = field(default_factory=list)
    step: int | None = None
    trace: object | None = None
    _used: dict = field(default_factory=dict)
    research: bool = False                          # D106: split packed queries, read top sources, parse data files
    data_files: list = field(default_factory=list)  # D106: every data file read {source, url, ext, table, parent}
    on_data: Callable | None = None                 # D107: called with each data file and fetched page as it arrives

    def begin_step(self, step: int, trace=None) -> None:
        self.step, self._used = step, {"web_search": 0, "fetch_url": 0, "auto_fetch": 0, "data": 0}
        if trace is not None:
            self.trace = trace

    def sources_for(self, step: int) -> list[dict]:
        return [s for s in self.sources if step in s["steps"]]

    def source_texts(self) -> dict[str, str]:
        """D74: S# -> the text helpers were shown for it."""
        return {s["id"]: s.get("seen", "") for s in self.sources if s.get("seen")}

    def _source(self, url: str, title: str, kind: str, query: str = "", at: str | None = None) -> dict:
        """The source record for a url: reused when the url was seen before (same S# across the run). at: when the
        provider really fetched it (D73: kept with a cached result, so a resumed run shows the same time)."""
        for s in self.sources:
            if s["url"] == url:
                if self.step is not None and self.step not in s["steps"]:
                    s["steps"].append(self.step)
                if kind == "fetch":   # the page itself was read now
                    s["fetched"] = True
                    s["fetched_at"] = at or now_iso()
                return s
        s = {"id": f"S{len(self.sources) + 1}", "url": url, "title": title, "kind": kind, "query": query,
             "fetched_at": at or now_iso(), "fetched": kind == "fetch",
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
        subs = split_query(query, self.limits.max_subqueries) if self.research else [query]
        if len(subs) > 1:                             # D106: one search per packed query, place and year
            self._event("query_split", {"amoeba.query": query, "amoeba.subqueries": subs})
        out = [self._search_one(q) for q in subs]
        if len(subs) > 1:
            out.insert(0, f"(plain code split your query into {len(subs)} searches — one per place, year or packed "
                          f"query: {'; '.join(subs)})")
        return "\n\n".join(out)

    def _search_one(self, query: str) -> str:
        try:
            results = self.provider.search(query, self.limits.max_results)
        except (WebToolError, urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
            return self._fail("web_search", f"{type(e).__name__}: {e}")
        if not results:
            return f'No results for "{query}".'
        if self.research:
            results = rank_official(results)          # D106: official domains first
        lines = [f'Search results for "{query}" (cite a fact by its [S#]; fetch_url a result to read the page):']
        ids, shown = [], results[: self.limits.max_results]
        for r in shown:
            s = self._source(r["url"], r["title"], "search", query, r.get("fetched_at"))
            ids.append(s["id"])
            snippet = re.sub(r"\s+", " ", r.get("snippet", ""))[: self.limits.snippet_chars]
            lines.append(f"[{s['id']}] {r['title']} — {r['url']}\n    {snippet}")
            note_seen(s, f"{r['title']}\n{snippet}")
        self._event("web_search", {"amoeba.query": query, "amoeba.results": len(results), "amoeba.source_ids": ids})
        if self.research:
            lines += self._read_top(shown, query)
        return "\n".join(lines)

    def _read_top(self, results: list[dict], query: str) -> list[str]:
        """D106: plain code reads the top results itself (official first) and any data files they link."""
        lines, read, again = [], 0, []
        for r in results:
            if read >= self.limits.auto_fetch:
                break
            if self._used.get("auto_fetch", 0) >= self.limits.max_auto_fetches_per_step:
                lines.append(f"(plain code read {self.limits.max_auto_fetches_per_step} pages this step; no more)")
                break
            known = next((x for x in self.sources if x["url"] == r["url"]), None)
            if known is not None and known.get("fetched"):
                read += 1                             # already read in this run: it counts, not read again
                again.append(known["id"])
                continue
            self._used["auto_fetch"] = self._used.get("auto_fetch", 0) + 1
            read += 1
            try:
                page = self.provider.fetch(r["url"])
            except (WebToolError, urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
                lines.append(f"  could not read {r['url']}: {type(e).__name__}")
                continue
            text = re.sub(r"\n{3,}", "\n\n", page.get("text", "")).strip()
            s = self._source(page.get("url", r["url"]), page.get("title", "") or r["url"], "fetch",
                             at=page.get("fetched_at"))
            ex = excerpt(text, query, self.limits.excerpt_chars)
            note_seen(s, f"{s['title']}\n{ex}")
            self._event("auto_fetch", {"amoeba.url": s["url"], "amoeba.source_id": s["id"], "amoeba.chars": len(text),
                                       "amoeba.official": official(s["url"])})
            self._page(s, text)
            tag = "official" if official(s["url"]) else "not an official domain"
            lines.append(f"  read by plain code: [{s['id']}] ({tag}), the lines that match your query:\n"
                         + "\n".join("    " + ln for ln in ex.splitlines()))
            lines += self._linked_data(text, s, query)
        if again:
            lines.append(f"  already read in this run: {', '.join(f'[{i}]' for i in again)}")
        return lines

    def _linked_data(self, text: str, page: dict, query: str) -> list[str]:
        """D106: the data files a fetched page links, read and parsed (the best matches to the query)."""
        links = data_links(text, page["url"], query, self.limits.data_links_per_page)
        if not links and hasattr(self.provider, "page_links"):
            try:
                links = data_links("\n".join(self.provider.page_links(page["url"])), page["url"], query,
                                   self.limits.data_links_per_page)
            except (WebToolError, urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError):
                links = []
        return [self._read_data(u, query, page["id"]) for u in links]

    def _read_data(self, url: str, query: str, parent: str | None = None) -> str:
        """D106: one data file, parsed; an excerpt for the helper, the whole table kept (D107 writes it out)."""
        if self._used.get("data", 0) >= self.limits.max_data_files_per_step or not hasattr(self.provider, "fetch_data"):
            return f"  data file {url}: not read (limit of {self.limits.max_data_files_per_step} per step)"
        self._used["data"] = self._used.get("data", 0) + 1
        try:
            d = self.provider.fetch_data(url)
        except Exception as e:                        # a bad file is a line for the helper, never a crash
            self._event("tool_error", {"gen_ai.tool.name": "data_file", "error.type": f"{type(e).__name__}: {e}"[:300]})
            return f"  data file {url}: could not read it ({type(e).__name__}: {str(e)[:120]})"
        s = self._source(url, d.get("title") or url, "fetch", query, d.get("fetched_at"))
        s["data"] = True
        table = d.get("table") or {}
        ex = table_excerpt(table, query)
        note_seen(s, "\n".join(" | ".join(r) for r in (table.get("rows") or [])[:400]))
        rec = {"source": s["id"], "url": url, "ext": d.get("ext"), "table": table, "parent": parent, "step": self.step}
        self.data_files.append(rec)
        self._event("data_file", {"amoeba.url": url, "amoeba.source_id": s["id"], "amoeba.rows": table.get("n_rows"),
                                  "amoeba.parent": parent})
        if self.on_data is not None:
            self.on_data({"kind": "data", **rec})
        sheets = f", sheets {', '.join(table['sheets'][:5])}" if table.get("sheets") else ""
        return (f"  data file [{s['id']}] {s['title']} ({d.get('ext')}, {table.get('n_rows', 0)} rows{sheets}; "
                f"linked from {parent or 'your fetch'}):\n" + "\n".join("    " + ln for ln in ex.splitlines()))

    def _page(self, source: dict, text: str) -> None:
        if self.on_data is not None and text:          # D107: the page's text goes to the workspace too
            self.on_data({"kind": "page", "source": source["id"], "url": source["url"], "title": source["title"],
                          "text": text, "step": self.step})

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
        if self.research and data_ext(url):            # D106: a data file is read as a table
            return self._read_data(url, "", None).lstrip()
        try:
            page = self.provider.fetch(url)
        except (WebToolError, urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
            return self._fail("fetch_url", f"{type(e).__name__}: {e}")
        text = re.sub(r"\n{3,}", "\n\n", page.get("text", "")).strip()
        cut = text[: self.limits.max_fetch_chars]
        s = self._source(page.get("url", url), page.get("title", "") or url, "fetch", at=page.get("fetched_at"))
        note_seen(s, f"{s['title']}\n{cut}")
        self._event("fetch_url", {"amoeba.url": url, "amoeba.source_id": s["id"], "amoeba.chars": len(text),
                                  "amoeba.chars_passed": len(cut)})
        more = f", first {len(cut)} of {len(text)} characters" if len(text) > len(cut) else ""
        out = f"[{s['id']}] {s['title']} ({s['url']}), fetched {s['fetched_at']}{more}:\n{cut}"
        self._page(s, text)                            # D107: the page's text to the workspace (when on)
        if self.research:                              # D106: the data files the page links
            data = self._linked_data(text, s, s["title"])
            if data:
                out += "\n\nData files this page links, read by plain code:\n" + "\n".join(data)
        return out


# box: tools
def web_registry(provider: SearchProvider | None = None, limits: WebLimits | None = None, research: bool = False):
    """A fresh Box 3 registry for one run: echo, calc, web_search and fetch_url (Tavily unless a provider is given).
    research: D106 (split packed queries, read the top sources, parse linked data files)."""
    from amoeba.tools.registry import default_registry
    reg = default_registry()
    register_web_tools(reg, WebTools(provider or TavilyProvider(), limits or WebLimits(), research=research))
    return reg


def register_web_tools(registry, web: WebTools) -> None:
    """Adds web_search and fetch_url to a Box 3 registry; `registry.web` keeps the run's WebTools."""
    registry.register("web_search", "searches the web; input: a query; returns titles, urls and snippets as [S#]",
                      web.web_search)
    registry.register("fetch_url", "reads one web page; input: a url (or an [S#] from web_search); returns its text",
                      web.fetch_url)
    registry.web = web
