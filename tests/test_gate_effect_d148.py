"""D148 — the gate judges effect, not text: a path a Bash command names is resolved (from the workspace, after any cd)
and refused only when it lands outside the workspace; every refusal names the exact part that matched and one line on
how to rewrite it. Offline."""
import pytest

from tests.test_localtools import box, skills  # noqa: F401  (fixtures)

from amoeba.interp.trace import TraceWriter
from amoeba.localtools.gate import screen_command
from amoeba.localtools.toolbox import LocalSetup, LocalToolbox


@pytest.fixture
def ws(tmp_path):
    w = tmp_path / "workspace"
    (w / "sources").mkdir(parents=True)
    return w


@pytest.mark.parametrize("cmd", [
    "cd sources && python3 -c \"open('../x.csv','w')\"",          # lands in the workspace
    "cd sources && cat ../notes.txt",
    "python3 -c \"print(open('sources/../data.csv').read())\"",
    "cd sources/sub/.. && ls",
])
def test_paths_that_stay_inside_are_allowed(ws, cmd):
    assert screen_command(cmd, ws) is None, cmd


@pytest.mark.parametrize("cmd,part", [
    ("cat ../../etc/passwd", "../../etc/passwd"),
    ("cd / && ls", "cd /"),
    ("cd sources && cat ../../x", "../../x"),
    ("cd .. && cat result.json", "cd .."),
])
def test_paths_that_leave_are_refused_naming_the_part(ws, cmd, part):
    why = screen_command(cmd, ws)
    assert why is not None and why[0] == "unsafe_command" and part in why[1], (cmd, why)


def test_the_refusal_says_how_to_rewrite_it(box):
    out = box.call("Bash", "cat ../../etc/passwd")
    assert out.startswith("refused: local:Bash — unsafe_command") and "../../etc/passwd" in out
    assert "write paths from the workspace root" in out
