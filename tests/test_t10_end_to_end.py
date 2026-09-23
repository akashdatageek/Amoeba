"""T10 — the CLI runs 20 toy tasks per topology offline and writes runs/<id>/ with five files."""
import json
import subprocess
import sys

import pytest

from tests.conftest import ROOT


@pytest.mark.parametrize("topology", ["flat", "boss_reviewers"])
def test_cli_toy_run(tmp_path, topology):
    cmd = [sys.executable, "-m", "scripts.run_task", "--toy", "--seed", "0", "--n", "20",
           "--topology", topology, "--runs-dir", str(tmp_path)]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr
    summary = [l for l in proc.stdout.splitlines() if l.startswith("== ")][-1]
    assert f"== {topology}  n=20" in summary
    assert "mean_score=" in summary and "mean_tokens=" in summary and "mean_llm_calls=" in summary
    run_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
    assert len(run_dirs) == 20
    for d in run_dirs:
        assert {p.name for p in d.iterdir()} == {"team.yaml", "plan.json", "trace.jsonl", "capability_requests.json",
                                                 "result.json"}
        assert json.loads((d / "capability_requests.json").read_text()) == []   # the toy team needs nothing it lacks
        result = json.loads((d / "result.json").read_text())
        assert result["topology"] == topology and result["error"] is None, result
        assert result["score"] == 1.0   # the toy mock is a well-behaved model: the pipeline must not lose the answer
