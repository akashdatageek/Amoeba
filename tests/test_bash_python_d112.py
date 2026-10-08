"""D112 — Python sent to local:Bash runs with python3 (offline; live part skipped without the OpenShell gateway): a
fenced block tagged python, or a text whose first line starts like Python, is run as `python3 - <<'AMOEBA_PY' …`
(a quoted heredoc: no shell expansion inside), and the rewrite is logged; shell commands are untouched; the gate
still screens the program; localtools.yaml `bash_python: false` turns it off. (Probe (hard) H1: the verifier's first
call sent a fenced Python block to local:Bash and failed with a shell syntax error.)"""
import json

from amoeba.interp.trace import TraceWriter
from amoeba.localtools.toolbox import LocalSetup, LocalToolbox, as_python_command, load_local_config, python_source
from tests.test_sandbox_d96 import live

FENCED = "```python\nimport itertools\nprint(sum(1 for _ in itertools.product(range(4), repeat=10)))\n```"


def box(tmp_path, **cfg):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    setup = LocalSetup(env={}, config={**load_local_config(), **cfg})
    return LocalToolbox(setup, run_dir, TraceWriter(run_dir / "trace.jsonl", episode_id="d112"))


def test_python_is_recognised_and_shell_is_not():
    assert python_source(FENCED).startswith("import itertools")
    assert python_source("from math import pi\nprint(pi)") == "from math import pi\nprint(pi)"
    assert python_source("for x in range(3):\n    print(x)") is not None
    for shell in ("python3 primes.py", "ls -la", "```bash\nls\n```", "for f in *.csv; do echo $f; done",
                  "cat sources/S1.txt", "echo 'import this'"):
        assert python_source(shell) is None, shell
    assert as_python_command("print(1)") == "python3 - <<'AMOEBA_PY'\nprint(1)\nAMOEBA_PY"
    assert "AMOEBA_PY_" in as_python_command("s = 'AMOEBA_PY'")                  # the delimiter never collides


def test_the_rewrite_is_made_and_logged(tmp_path):
    b = box(tmp_path)
    args = b.arguments("Bash", FENCED)
    assert args["command"].startswith("python3 - <<'AMOEBA_PY'\nimport itertools")
    ev = [json.loads(l) for l in (tmp_path / "run" / "trace.jsonl").read_text().splitlines()]
    assert any(e.get("name") == "bash_python" and e["amoeba.lines"] == 2 for e in ev)
    assert b.arguments("Bash", "ls -la") == {"command": "ls -la"}


def test_off_leaves_the_input_alone(tmp_path):
    b = box(tmp_path, bash_python=False)
    assert b.arguments("Bash", FENCED)["command"].startswith("import itertools")      # D61 unfence only


@live
def test_live_a_fenced_python_block_runs_in_the_sandbox(tmp_path):
    b = box(tmp_path)
    b.start()
    try:
        assert b.box is not None and b.exposed, b.error
        b.begin_step(1)
        out = b.call("Bash", FENCED)
        assert "1048576" in out and "syntax error" not in out, out
        bad = b.call("Bash", "```python\nimport socket\nsocket.create_connection(('example.com', 80))\n```")
        assert bad.startswith("refused: local:Bash — network_command")              # still screened
    finally:
        b.finish()
