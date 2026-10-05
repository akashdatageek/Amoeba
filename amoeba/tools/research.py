"""D106 — research steps: packed queries split, the top primary sources read, linked data files parsed.

The hard probe showed research steps packing every entity, year and series into one query ("US Indiana median
household income 2015 2016 … 2023 CPI-U") and fetching almost nothing; the data sat in linked .xlsx tables a page view
never reaches. With research on (plan runner, web tools on), plain code:

- splits a packed query (`split_query`): several quoted queries in one string become separate queries; several places
  (US states, countries, the US itself) become one query per place; several years become one query per year when that
  stays within `max_subqueries`, else one year range per query;
- reads the top `auto_fetch` results of each query itself, official domains first (`official`: .gov, .mil, .edu,
  .int, statistical agencies), and shows a short excerpt of each under the results;
- when a fetched page (or a fetch_url) links data files (.csv, .tsv, .xlsx, .xlsm, .json), fetches the ones that best
  match the query and parses them into a table (`parse_table`), shown as an excerpt and kept whole for the workspace
  (D107).
"""
from __future__ import annotations

import csv
import io
import json
import re
from urllib.parse import urljoin, urlparse

STATES = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
          "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas",
          "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
          "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York",
          "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
          "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
          "West Virginia", "Wisconsin", "Wyoming"]
COUNTRIES = ["United States", "United Kingdom", "Canada", "Mexico", "Brazil", "Argentina", "Germany", "France", "Italy",
             "Spain", "Netherlands", "Belgium", "Sweden", "Norway", "Denmark", "Finland", "Poland", "Austria",
             "Switzerland", "Ireland", "Portugal", "Greece", "China", "Japan", "India", "South Korea", "Indonesia",
             "Australia", "New Zealand", "Russia", "Turkey", "Saudi Arabia", "South Africa", "Nigeria", "Egypt",
             "European Union", "Euro area"]
US_ALIASES = ["U.S.A.", "U.S.", "USA", "US"]          # case-sensitive; "US" only before a place or at a list's end
PLACE = re.compile(r"\b(" + "|".join(re.escape(p) for p in sorted(STATES + COUNTRIES, key=len, reverse=True)) + r")\b",
                   re.I)
ALIAS = re.compile(r"(?<![\w.])(U\.S\.A\.|U\.S\.|USA|US)(?![\w])")
YEAR = re.compile(r"\b((?:19|20)\d{2})\s*(?:-|–|—|\.\.|to|through)\s*((?:19|20)\d{2})\b|\b((?:19|20)\d{2})\b")
COORD = re.compile(r"^(?:\s*(?:,|and|&|vs\.?|versus|/|or)\s*)+$", re.I)
OFFICIAL = re.compile(r"(?:^|\.)(?:[a-z0-9-]+\.)*(?:gov|mil|edu|int)(?:\.[a-z]{2})?$|(?:^|\.)(?:europa\.eu|gc\.ca|"
                      r"un\.org|oecd\.org|worldbank\.org|imf\.org|stlouisfed\.org|ons\.gov\.uk|destatis\.de|"
                      r"insee\.fr|abs\.gov\.au|statcan\.gc\.ca)$", re.I)
DATA_EXT = ("csv", "tsv", "xlsx", "xlsm", "json")
DATA_LINK = re.compile(r"""(?:https?://[^\s"'<>()\]]+|(?<=\()/?[^\s"'<>()]+|(?<=href=["'])[^"']+)"""
                       r"""\.(?:csv|tsv|xlsx|xlsm|json)(?:\?[^\s"'<>()\]]*)?""", re.I)
STOP = {"the", "and", "for", "with", "from", "data", "table", "tables", "annual", "average", "nominal", "real",
        "official", "site", "about", "over", "each", "year", "years"}


# box: tools
def official(url: str) -> bool:
    """A primary source by its domain: government, military, education, international and statistical agencies."""
    return bool(OFFICIAL.search((urlparse(url).hostname or "").lower()))


# box: tools
def rank_official(results: list[dict]) -> list[dict]:
    """Official domains first, each group in the provider's order."""
    return sorted(results, key=lambda r: not official(r.get("url", "")))


def _places(q: str) -> list[tuple[int, int, str]]:
    found = [(m.start(), m.end(), m.group(1)) for m in PLACE.finditer(q)]
    for m in ALIAS.finditer(q):
        after = q[m.end():].lstrip()
        nxt = re.match(r"[A-Z][\w.-]*", after)
        is_place = nxt is None or PLACE.match(after) or COORD.match(after[:5] or " ") or after[:1] in ",&/"
        if is_place and not any(s <= m.start() < e for s, e, _ in found):
            found.append((m.start(), m.end(), "United States"))
    return sorted(found)


def _years(q: str) -> tuple[list[int], list[tuple[int, int]]]:
    years, spans = set(), []
    for m in YEAR.finditer(q):
        if m.group(3):
            years.add(int(m.group(3)))
        else:
            a, b = sorted((int(m.group(1)), int(m.group(2))))
            years.update(range(a, b + 1))
        spans.append(m.span())
    return sorted(years), spans


def _cut(q: str, spans: list[tuple[int, int]]) -> str:
    out, last = [], 0
    for s, e in sorted(spans):
        out.append(q[last:s])
        last = e
    out.append(q[last:])
    text = " ".join(out)
    text = re.sub(r"\s*(?:,|&|/)\s*(?=\s|$)", " ", text)
    text = re.sub(r"\b(?:and|vs\.?|versus|or)\s+(?=(?:and|vs\.?|versus|or)?\s*$)", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip(" ,&/")


def _one(q: str, max_sub: int) -> list[str]:
    places = _places(q)
    names = list(dict.fromkeys(p[2] for p in places))
    spans = []
    for s, e, _ in places:                         # "USA and Indiana": the coordinator between places goes too
        if spans and (not q[spans[-1][1]:s].strip() or COORD.match(q[spans[-1][1]:s])):
            spans[-1] = (spans[-1][0], e)
        else:
            spans.append((s, e))
    base = _cut(q, spans) if len(names) >= 2 else q
    subs = [f"{base} {n}".strip() for n in names] if len(names) >= 2 else [q]
    years, _ = _years(q)
    if len(years) >= 2:
        out = []
        for s in subs:
            _, spans = _years(s)
            core = _cut(s, spans)
            out += [f"{core} {y}" for y in years] if len(subs) * len(years) <= max_sub else \
                [f"{core} {years[0]}-{years[-1]}"]
        subs = out
    return subs


# box: tools
def split_query(query: str, max_sub: int = 4) -> list[str]:
    """One query per packed query, place and year (or year range): at most max_sub, in order, without repeats."""
    q = re.sub(r"\s+", " ", query or "").strip()
    parts = [p.strip(' "') for p in re.split(r'"\s+"', q) if p.strip(' "')]
    out: list[str] = []
    for p in parts or [q]:
        for s in _one(p.replace('"', ""), max_sub):
            if s and s.lower() not in {x.lower() for x in out}:
                out.append(s)
    return out[:max_sub] or [q]


# box: tools
def terms(query: str) -> list[str]:
    """The words of a query that a relevant line, link or table row should contain."""
    return [w for w in dict.fromkeys(re.findall(r"[a-z][a-z0-9-]{2,}", (query or "").lower())) if w not in STOP]


# box: tools
def excerpt(text: str, query: str, limit: int) -> str:
    """The lines of a page that share the most query words (numbers kept), in page order, up to `limit` chars."""
    words = terms(query)
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    scored = [(sum(w in ln.lower() for w in words) + (0.5 if re.search(r"\d", ln) else 0), i, ln)
              for i, ln in enumerate(lines)]
    keep, size = [], 0
    for sc, i, ln in sorted(scored, key=lambda x: (-x[0], x[1])):
        if sc < 1 or size >= limit:
            break
        keep.append((i, ln[:300]))
        size += min(len(ln), 300) + 1
    if not keep:
        return (text or "")[:limit].strip()
    return "\n".join(ln for _, ln in sorted(keep))[:limit]


# box: tools
def data_links(text: str, base_url: str, query: str = "", limit: int = 2) -> list[str]:
    """Links to data files in a page's text or HTML, absolute, best match to the query first."""
    words = terms(query)
    seen, out = set(), []
    for m in DATA_LINK.finditer(text or ""):
        url = urljoin(base_url, m.group(0).strip())
        if url.startswith("http") and url not in seen:
            seen.add(url)
            out.append(url)
    out.sort(key=lambda u: -sum(w in u.lower() for w in words))
    return out[:limit]


# box: tools
def data_ext(url: str) -> str | None:
    m = re.search(r"\.(" + "|".join(DATA_EXT) + r")(?:$|\?)", urlparse(url).path.lower() + "?")
    return m.group(1) if m else None


# box: tools
def parse_table(content: bytes, ext: str, max_rows: int = 3000, max_cols: int = 40) -> dict:
    """{kind, sheets, rows} from a data file: CSV/TSV, the first sheet of an XLSX workbook, a JSON list of records
    (or any JSON as text). Cells are strings; numbers keep their written form."""
    if ext in ("csv", "tsv"):
        text = content.decode("utf-8-sig", errors="replace")
        rows = list(csv.reader(io.StringIO(text), delimiter="\t" if ext == "tsv" else ","))
        return {"kind": ext, "sheets": [], "rows": [r[:max_cols] for r in rows[:max_rows]], "n_rows": len(rows)}
    if ext in ("xlsx", "xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = []
        for r in ws.iter_rows(values_only=True):
            if len(rows) >= max_rows:
                break
            cells = ["" if v is None else str(v) for v in r[:max_cols]]
            while cells and not cells[-1]:
                cells.pop()
            if cells:
                rows.append(cells)
        return {"kind": ext, "sheets": wb.sheetnames, "rows": rows, "n_rows": len(rows)}
    data = json.loads(content.decode("utf-8", errors="replace"))
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), data)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        keys = list(dict.fromkeys(k for d in data[:max_rows] for k in d))[:max_cols]
        rows = [keys] + [[str(d.get(k, "")) for k in keys] for d in data[:max_rows]]
        return {"kind": "json", "sheets": [], "rows": rows, "n_rows": len(data)}
    return {"kind": "json", "sheets": [], "rows": [[json.dumps(data)[:4000]]], "n_rows": 1}


# box: tools
def table_excerpt(table: dict, query: str, head: int = 8, matches: int = 12) -> str:
    """The first rows (titles and header) and the rows that name a query word, as pipe-separated lines."""
    rows = table.get("rows") or []
    words = terms(query)
    pick = list(range(min(head, len(rows))))
    pick += [i for i, r in enumerate(rows) if i >= head and any(w in " ".join(r).lower() for w in words)][:matches]
    out = [" | ".join(c.strip()[:40] for c in rows[i]) for i in pick]
    more = f"\n[{len(pick)} of {table.get('n_rows', len(rows))} rows shown]"
    return "\n".join(out) + more
