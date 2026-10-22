"""D147 — every cut says where the full copy is: a fetched page cut at max_fetch_chars ends with the saved file
(sources/S#_….txt) and "open it with local:Read"; a data-file excerpt shows its first and last rows and its saved
file. Offline (a fake provider; the local toolbox saves the files as in a run)."""
from amoeba.interp.trace import TraceWriter
from amoeba.localtools.toolbox import LocalSetup, LocalToolbox
from amoeba.tools.research import parse_table
from amoeba.tools.web import WebLimits, WebTools

ROWS = "\n".join(f"2026-{m:02d}-{d:02d},{3 + (m * 31 + d) / 1000:.3f}" for m in range(1, 13) for d in (1, 8, 15, 22))
CSV = "week,price\n" + ROWS


class Provider:
    name = "fake"

    def search(self, query, max_results):
        return []

    def fetch(self, url):
        return {"url": url, "title": "Weekly history", "text": "HEAD " + "x" * 30_000 + " TAIL-MARK"}

    def fetch_data(self, url):
        return {"url": url, "title": "history.csv", "ext": "csv", "table": parse_table(CSV.encode(), "csv")}


def setup(tmp_path, research=False):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    box = LocalToolbox(LocalSetup(env={}), run_dir, TraceWriter(run_dir / "trace.jsonl", episode_id="d147"))
    web = WebTools(Provider(), WebLimits(), research=research)
    web.begin_step(1, TraceWriter(None))
    web.on_data = lambda rec: box.save_source(rec, web)
    return box, web


def test_a_cut_page_names_its_saved_file(tmp_path):
    box, web = setup(tmp_path)
    out = web.fetch_url("https://example.org/history")
    s = web.sources[-1]
    assert s["workspace_file"].startswith("sources/S") and s["workspace_file"].endswith(".txt")
    assert "TAIL-MARK" not in out                                   # the page was cut
    assert s["workspace_file"] in out and "open it with local:Read" in out
    assert (box.workspace / s["workspace_file"]).read_text().rstrip().endswith("TAIL-MARK")


def test_a_short_page_has_no_cut_note(tmp_path):
    box, web = setup(tmp_path)
    web.provider.fetch = lambda url: {"url": url, "title": "Short", "text": "all of it"}
    assert "open it with local:Read" not in web.fetch_url("https://example.org/short")


def test_without_a_workspace_the_cut_is_still_said(tmp_path):
    web = WebTools(Provider(), WebLimits(), research=False)
    web.begin_step(1, TraceWriter(None))
    out = web.fetch_url("https://example.org/history")
    assert "characters cut" in out and "local:Read" not in out


def test_a_table_excerpt_shows_its_last_rows_and_its_file(tmp_path):
    box, web = setup(tmp_path, research=True)
    out = web.fetch_url("https://example.org/history.csv")
    last = CSV.splitlines()[-1].split(",")
    assert " | ".join(last) in out                                  # the newest row is visible
    s = web.sources[-1]
    assert s["workspace_file"] in out and "open it with local:Read" in out
