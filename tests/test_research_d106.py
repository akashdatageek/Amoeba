"""D106 — research steps (mocked provider, no network): a packed query is split into one search per packed query,
place and year (or year range); each search reads its top 3 results itself, official domains first, and shows
excerpts; a data file a read page links (or a fetch_url of one) is fetched and parsed into a table; limits hold; the
helpers are told to search one entity at a time; off (and for the baselines) nothing changes."""
import io

from amoeba.interp.trace import TraceWriter
from amoeba.tools.research import data_links, excerpt, official, parse_table, rank_official, split_query
from amoeba.tools.web import WebLimits, WebTools
from scripts.run_task import build_box3_tools, parse_args

CSV = b"Year,United States,Indiana\n2022,74580,67173\n2023,80610,70051\n"


class Provider:
    name = "fake"

    def __init__(self):
        self.searches, self.fetches, self.data = [], [], []

    def search(self, query, max_results):
        self.searches.append(query)
        return [{"title": "News story", "url": "https://news.example.com/a", "snippet": "income rose"},
                {"title": "Census table page", "url": "https://www.census.gov/hist", "snippet": "historical tables"},
                {"title": "Blog", "url": "https://blog.example.org/b", "snippet": "my view"},
                {"title": "BLS CPI", "url": "https://www.bls.gov/cpi/", "snippet": "CPI-U annual average"}]

    def fetch(self, url):
        self.fetches.append(url)
        links = "Download [h08.csv](/content/h08.csv) and the [workbook](https://www2.census.gov/h08.xlsx)" \
            if "census.gov" in url else "no links here"
        return {"url": url, "title": f"Page {url}", "text": f"Median household income by state\nIndiana 67,173\n{links}"}

    def fetch_data(self, url):
        self.data.append(url)
        return {"url": url, "title": url.rsplit("/", 1)[-1], "ext": "csv", "table": parse_table(CSV, "csv")}


def tools(research=True, **limits):
    web = WebTools(Provider(), WebLimits(**limits), research=research)
    web.begin_step(1, TraceWriter(None))
    return web


def test_split_query():
    h2 = ('US Census Bureau nominal median household income USA Indiana 2015 2016 2017 2018 2019 2020 2021 2022 2023" '
          '"BLS CPI-U annual average 2015 2016 2017 2018 2019 2020 2021 2022 2023')
    assert split_query(h2) == ["US Census Bureau nominal median household income United States 2015-2023",
                               "US Census Bureau nominal median household income Indiana 2015-2023",
                               "BLS CPI-U annual average 2015-2023"]
    assert split_query("median income USA and Indiana 2015-2023") == ["median income United States 2015-2023",
                                                                      "median income Indiana 2015-2023"]
    assert split_query("CPI-U annual average 2022 2023") == ["CPI-U annual average 2022", "CPI-U annual average 2023"]
    assert split_query("diesel truck price Indiana 2026") == ["diesel truck price Indiana 2026"]   # nothing packed
    assert split_query("median income in Ohio, Indiana and Texas") == [
        "median income in Ohio", "median income in Indiana", "median income in Texas"]
    assert len(split_query("income " + " ".join(f"State{i}" for i in range(9)) + " Ohio Texas Utah Iowa Idaho")) <= 4


def test_official_first_excerpts_and_links():
    assert official("https://www.census.gov/x") and official("https://ec.europa.eu/eurostat") and \
        official("https://fred.stlouisfed.org/series/X") and not official("https://news.example.com/a")
    ranked = rank_official([{"url": "https://news.example.com"}, {"url": "https://www.bls.gov"}])
    assert ranked[0]["url"] == "https://www.bls.gov"
    page = "Intro\nIndiana median household income 67,173 in 2022\nunrelated footer\n"
    assert excerpt(page, "Indiana median income", 200).startswith("Indiana median household income 67,173")
    links = data_links("see [t](/content/h08.csv) or https://x.gov/a.xlsx?raw=1 or a.pdf", "https://www.census.gov/hist",
                       "h08")
    assert links == ["https://www.census.gov/content/h08.csv", "https://x.gov/a.xlsx?raw=1"]


def test_parse_tables():
    t = parse_table(CSV, "csv")
    assert t["rows"][1] == ["2022", "74580", "67173"] and t["n_rows"] == 3
    from openpyxl import Workbook
    wb = Workbook()
    wb.active.append(["Table H-8"])
    wb.active.append(["Year", "Indiana"])
    wb.active.append([2023, 70051])
    buf = io.BytesIO()
    wb.save(buf)
    x = parse_table(buf.getvalue(), "xlsx")
    assert x["rows"] == [["Table H-8"], ["Year", "Indiana"], ["2023", "70051"]] and x["sheets"]
    j = parse_table(b'{"data": [{"year": 2023, "value": 1.5}]}', "json")
    assert j["rows"] == [["year", "value"], ["2023", "1.5"]]


def test_a_packed_search_is_split_and_the_top_official_sources_are_read():
    web = tools()
    out = web.web_search("median income USA and Indiana 2015-2023")
    p = web.provider
    assert p.searches == ["median income United States 2015-2023", "median income Indiana 2015-2023"]
    assert out.startswith("(plain code split your query into 2 searches")
    assert p.fetches[:3] == ["https://www.census.gov/hist", "https://www.bls.gov/cpi/", "https://news.example.com/a"]
    assert len(p.fetches) == 3                              # the second search finds them already read
    assert "read by plain code: [S1] (official)" in out and "Median household income by state" in out
    assert "(not an official domain)" in out and "already read in this run: [S1], [S2], [S3]" in out
    assert p.data == ["https://www.census.gov/content/h08.csv", "https://www2.census.gov/h08.xlsx"]
    assert "data file [S" in out and "2023 | 80610 | 70051" in out
    rec = web.data_files[0]
    assert rec["table"]["rows"][0] == ["Year", "United States", "Indiana"] and rec["parent"].startswith("S")
    src = next(s for s in web.sources if s["id"] == rec["source"])
    assert src["fetched"] and src["data"] and "80610" in src["seen"]


def test_limits_hold():
    web = tools(max_auto_fetches_per_step=2, max_data_files_per_step=1)
    out = web.web_search("median income USA and Indiana 2015-2023")
    assert len(web.provider.fetches) == 2 and len(web.provider.data) == 1
    assert "no more" in out and "not read (limit of 1 per step)" in out


def test_fetch_url_of_a_data_file_reads_a_table():
    web = tools()
    out = web.fetch_url("https://www2.census.gov/h08.csv")
    assert out.startswith("data file [S1] h08.csv (csv, 3 rows") and web.provider.fetches == []


def test_off_changes_nothing(monkeypatch):
    web = tools(research=False)
    out = web.web_search("median income USA and Indiana 2015-2023")
    assert web.provider.searches == ["median income USA and Indiana 2015-2023"] and web.provider.fetches == []
    assert "read by plain code" not in out
    monkeypatch.setenv("TAVILY_API_KEY", "test-not-a-key")
    from amoeba.tools.registry import default_registry
    for topo, want in (("flat", False), ("boss_reviewers", False), ("plan", True)):
        a = parse_args(["x", "--web-tools", "--topology", topo])
        assert build_box3_tools(a, default_registry()).web.research is want, topo     # baselines: never
    a = parse_args(["x", "--web-tools", "--topology", "plan", "--research", "off"])
    assert build_box3_tools(a, default_registry()).web.research is False
