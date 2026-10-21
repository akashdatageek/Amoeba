"""D158 — the sandbox image holds what the checks need: one library list for the image and for in-process mode,
LibreOffice Calc and Writer, and Glob / Grep served through Bash by plain code when the server no longer offers them.
Offline: the fake `claude mcp serve` (it has no Glob or Grep, like Claude Code's current server)."""
import json
import re
from pathlib import Path

from amoeba.interp.trace import TraceWriter
from amoeba.localtools.toolbox import LocalToolbox
from scripts.preflight import LIBS, PIP
from tests.test_localtools import lsetup, skills  # noqa: F401  (skills is a fixture)

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = ROOT / "amoeba" / "config" / "sandbox"


def lib_list() -> list[str]:
    return [l.split("#")[0].strip() for l in (SANDBOX / "libs.txt").read_text().splitlines() if l.split("#")[0].strip()]


def test_one_library_list_for_the_image_and_in_process_mode():
    names = {re.split(r"[<>=]", x)[0].lower() for x in lib_list()}
    for m in LIBS:                                           # every import preflight checks is installed
        assert PIP.get(m, m).lower() in names, m
    assert {"scipy", "pytest", "pillow"} <= names
    docker = (SANDBOX / "Dockerfile").read_text()
    assert "libs.txt" in docker and "pip install --no-cache-dir -r" in docker
    assert "libreoffice-calc" in docker and "libreoffice-writer" in docker
    setup = (ROOT / "scripts" / "setup_office.sh").read_text()   # in-process mode: the same list, the same office
    assert "libreoffice-writer" in setup and "amoeba/config/sandbox/libs.txt" in setup


def test_build_stages_the_list_next_to_the_dockerfile():
    assert "libs.txt" in (SANDBOX / "Dockerfile").read_text()
    assert (SANDBOX / "libs.txt").is_file()                  # the build context is this folder


def start(skills, tmp_path):
    b = LocalToolbox(lsetup(skills), tmp_path / "run", TraceWriter(None))
    b.start()
    b.begin_step(1)
    return b


def test_glob_and_grep_are_served_through_bash_when_the_server_lacks_them(skills, tmp_path):
    b = start(skills, tmp_path)
    try:
        assert b.exposed == ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
        assert b.served_by_bash == ["Glob", "Grep"]
        b.call("Write", json.dumps({"file_path": "data/a.csv", "content": "zone,ndvi\nA,0.5\n"}))
        b.call("Write", json.dumps({"file_path": "notes.txt", "content": "nothing here"}))
        out = b.call("Glob", "**/*.csv")
        assert out.startswith("[local:Glob]") and "data/a.csv" in out and "notes.txt" not in out
        out = b.call("Grep", json.dumps({"pattern": "ndvi", "path": "."}))
        assert out.startswith("[local:Grep]") and "a.csv" in out and "zone,ndvi" in out
        assert "no matches" in b.call("Grep", "nowhere-to-be-found")
        calls = b.trace.events("local_call")
        assert [c["gen_ai.tool.name"] for c in calls][-3:] == ["local:Glob", "local:Grep", "local:Grep"]
    finally:
        b.finish()


def test_the_served_calls_keep_every_gate(skills, tmp_path):
    b = start(skills, tmp_path)
    try:
        assert b.call("Grep", json.dumps({"pattern": "root", "path": "/etc"})).startswith("refused")
        keep = b.workspace / "keep.txt"
        keep.write_text("x")
        b.call("Glob", "*.txt; rm -f keep.txt")              # the pattern is quoted, never run as shell
        b.call("Grep", json.dumps({"pattern": "x' ; rm -f keep.txt; echo '", "path": "."}))
        assert keep.exists()
    finally:
        b.finish()
