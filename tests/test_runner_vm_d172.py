"""D172 — Box 4's scoped round must not fall back silently. In the OpenShell sandbox a probe's workspace cannot be
undone, so the scoped round falls back to single (no INV/DOM comparison, no compose, no control, little learning).
Preflight now reports the proposer mode a run will actually get; run_task refuses --lessons-write on when the round
would fall back, unless --allow-single-learning; scripts/vm/ holds a throwaway runner container in which local tools
run in-process (AMOEBA_SANDBOX=1). Offline."""
import re
from pathlib import Path

import pytest

from amoeba.adapt.probe import proposer_mode
from scripts.preflight import check_proposer
from scripts.run_task import cli_plan_options, parse_args
from tests.test_preflight_d156 import Fake

ROOT = Path(__file__).resolve().parents[1]
PLAN = ["x", "--topology", "plan", "--adapt", "on", "--proposer", "scoped", "--local-tools", "on"]


def test_the_mode_a_run_will_get():
    assert proposer_mode("on", "scoped", "on", "sandbox")[0] == "single"
    assert "sandbox" in proposer_mode("on", "scoped", "on", "sandbox")[1]
    assert proposer_mode("on", "scoped", "on", "inprocess") == ("scoped", "")
    assert proposer_mode("on", "scoped", "off", "sandbox") == ("scoped", "")
    assert proposer_mode("on", "single", "on", "inprocess")[0] == "single"
    assert proposer_mode("off", "scoped", "on", "inprocess")[0] == "none"


def test_preflight_shows_the_fallback():
    [row] = check_proposer(Fake(mode="sandbox"))
    assert row.check == "proposer mode" and row.status == "warn" and "single" in row.detail
    assert "scripts/vm" in row.fix and row.needed_by
    [row] = check_proposer(Fake(mode="inprocess"))
    assert row.status == "ok" and row.detail.startswith("scoped")


def test_run_task_refuses_learning_from_a_fallback_unless_allowed(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        parse_args([*PLAN, "--local-tools-mode", "sandbox"])                 # lessons-write is on by default
    assert "--allow-single-learning" in capsys.readouterr().err
    a = parse_args([*PLAN, "--local-tools-mode", "sandbox", "--allow-single-learning"])
    assert cli_plan_options(a).lessons_write == "on"
    assert parse_args([*PLAN, "--local-tools-mode", "sandbox", "--lessons-write", "off"])
    monkeypatch.setenv("AMOEBA_SANDBOX", "1")
    assert parse_args([*PLAN, "--local-tools-mode", "inprocess"])            # the runner container's setting


def test_the_runner_container_mounts_only_an_output_folder_and_takes_keys_from_the_environment():
    docker = (ROOT / "scripts" / "vm" / "Dockerfile").read_text()
    for need in ("libreoffice", "scipy", "pytest", "AMOEBA_SANDBOX=1", "pip install -e"):
        assert need in docker, need
    run = (ROOT / "scripts" / "vm" / "run.sh").read_text()
    mounts = re.findall(r"(?:-v|--volume|--mount)\s+(\S+)", run)
    assert len(mounts) == 1 and mounts[0].strip('"').endswith(":/out")
    for key in ("CLAUDE_API_KEY", "GEMINI_API_KEY", "TAVILY_API_KEY"):
        assert re.search(rf"-e {key}(\s|$)", run), key                   # passed by name: never a value
    assert "--local-tools-mode inprocess" in run and "--rm" in run
    assert not re.search(r"(API_KEY|TOKEN)=\S", run)                     # no key written in the script
