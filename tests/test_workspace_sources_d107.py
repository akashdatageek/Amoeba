"""D107 — fetched data reaches the sandbox (offline with a mocked provider; live part skipped without the OpenShell
gateway): every page and data file the web tools read is saved read-only in the run's workspace under sources/
(tables as CSV, pages as text) with sources/index.json (each file's [S#], url, title, rows, time); the web source
records its file; inputs are never counted as files the team made; writes into sources/ are refused while reading
and copying from it are not; in the sandbox an analyst computes from the files."""
import json
import stat

from amoeba.interp.trace import TraceWriter
from amoeba.localtools.gate import protected_command, protected_path
from amoeba.localtools.toolbox import LocalSetup, LocalToolbox
from amoeba.tools.web import WebLimits, WebTools
from scripts.run_task import parse_args
from tests.test_research_d106 import Provider
from tests.test_sandbox_d96 import live


def setup(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    box = LocalToolbox(LocalSetup(env={}), run_dir, TraceWriter(run_dir / "trace.jsonl", episode_id="d107"))
    web = WebTools(Provider(), WebLimits(), research=True)
    web.begin_step(2, TraceWriter(None))
    web.on_data = lambda rec: box.save_source(rec, web)
    return box, web


def test_pages_and_tables_are_saved_read_only_with_their_provenance(tmp_path):
    box, web = setup(tmp_path)
    web.web_search("median income USA and Indiana 2015-2023")
    src = box.workspace / "sources"
    files = sorted(p.name for p in src.iterdir())
    assert "index.json" in files and any(f.startswith("S1_") and f.endswith(".txt") for f in files)
    table = next(p for p in src.iterdir() if p.name.endswith("_h08.csv"))
    assert table.read_text().splitlines()[0] == "Year,United States,Indiana" and "80610" in table.read_text()
    assert not table.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)       # read-only
    index = json.loads((src / "index.json").read_text())
    data = next(x for x in index if x["kind"] == "data" and x["file"].endswith("_h08.csv"))
    assert data["url"] == "https://www.census.gov/content/h08.csv" and data["rows"] == 3 and data["step"] == 2
    assert data["source"].startswith("S") and data["fetched_at"]
    s = next(x for x in web.sources if x["id"] == data["source"])
    assert s["workspace_file"] == data["file"]
    assert box._snapshot() == {} and box._scan() == []                                   # inputs are not made files
    page = next(x for x in index if x["kind"] == "page")
    assert (box.workspace / page["file"]).read_text().startswith(f"Source: {page['source']}\nURL: https://")


def test_writes_into_sources_are_refused_reading_and_copying_from_it_are_not(tmp_path):
    ws = tmp_path
    assert protected_path(ws / "sources" / "S5_h08.csv", ws)
    for c in ("echo x > sources/S5_h08.csv", "rm sources/S5_h08.csv", "mv sources/a b", "cp x.csv sources/S5_h08.csv",
              "sed -i s/1/2/ sources/S5_h08.csv"):
        assert protected_command(c), c
    for c in ("cat sources/S1_page.txt", "cp sources/S5_h08.csv work.csv",
              "python3 -c \"import csv; print(list(csv.reader(open('sources/S5_h08.csv'))))\""):
        assert protected_command(c) is None, c


def test_the_flag_and_the_step_note():
    assert parse_args(["x"]).workspace_sources == "on"
    from amoeba.interp.plan_runner import SOURCES_NOTE
    assert "sources/index.json" in SOURCES_NOTE and "{files}" in SOURCES_NOTE


@live
def test_live_an_analyst_computes_from_the_files_in_the_sandbox(tmp_path):
    box, web = setup(tmp_path)
    box.start()
    try:
        assert box.box is not None and box.exposed, box.error
        box.begin_step(3)
        web.web_search("median income USA and Indiana 2015-2023")
        name = next(x["file"] for x in box.inputs if x["file"].endswith("_h08.csv"))
        out = box.call("Bash", "python3 -c \"import csv; r=list(csv.reader(open('" + name + "')));"
                               " print('GROWTH', round(int(r[2][2])/int(r[1][2])-1, 4))\"")
        assert "GROWTH 0.0428" in out, out
        bad = box.call("Bash", "python3 -c \"open('" + name + "','a').write('x')\"")
        assert "Permission denied" in bad or "Read-only" in bad, bad                     # read-only in the sandbox too
        assert box.call("Bash", f"echo x > {name}").startswith("refused: local:Bash — protected_config")
    finally:
        out = box.finish()
    assert not any(f["path"].startswith("sources/") for f in out["files_created"])
