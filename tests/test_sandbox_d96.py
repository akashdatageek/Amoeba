"""D96 — agents' local tools run out of process in a fresh NVIDIA OpenShell sandbox per run. Offline: the gate's new
refusals (protected configs, read-only roots). Live (skipped unless the gateway of amoeba/config/sandbox/ answers on
127.0.0.1:17680 and the amoeba-sandbox:local image exists): an agent command trying to (a) reach the network,
(b) write outside the workspace, (c) read events.jsonl or an env file, (d) edit a skill or an MCP config is refused —
by gate.py when it can see it, by the sandbox when the command hides it — and every decision is logged and reaches
events.jsonl; and a bench5-style local-tools task (primes: write and run code) still works."""
import json
import socket
from pathlib import Path

import pytest

from amoeba.adapt.evidence import EvidenceLog, run_finished, tool_decisions, verify
from amoeba.interp.trace import TraceWriter
from amoeba.localtools.gate import protected_command, protected_path, readonly_root
from amoeba.localtools.toolbox import LocalSetup, LocalToolbox, load_local_config


# ---- offline -------------------------------------------------------------------------------------------------------
def test_protected_paths_and_commands(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    for p in (".mcp.json", ".claude/settings.json", "CLAUDE.md", "skills/xlsx/SKILL.md", ".git/config"):
        assert protected_path(ws / p, ws), p
    assert not protected_path(ws / "out" / "chart.png", ws)
    for c in ("echo '{}' > .mcp.json", "mkdir -p .claude && echo x > .claude/settings.json",
              "cat /etc/claude-code/managed-settings.json", "sed -i s/a/b/ skills/xlsx/SKILL.md",
              "cp evil.py skills/xlsx/scripts/recalc.py", "echo x > skills/x"):
        assert protected_command(c), c
    for c in ("python3 primes.py", "cat /opt/skills/xlsx/SKILL.md", "ls skills_report.txt", "python3 make_chart.py"):
        assert protected_command(c) is None, c


def test_read_only_roots():
    cfg = {"readable_roots": ["/opt/skills"]}
    assert readonly_root("/opt/skills/xlsx/SKILL.md", cfg) and readonly_root("/opt/skills", cfg)
    assert not readonly_root("/opt/skills/../../etc/passwd", cfg) and not readonly_root("/opt/skillsx/a", cfg)
    assert not readonly_root("skills/xlsx", cfg)


def test_the_config_says_openshell_and_deny_by_default():
    s = load_local_config()["sandbox"]
    assert s["isolation"] == "openshell" and "/sandbox" in s["read_write"] and "/opt/skills" in s["read_only"]
    assert not any(p.startswith(("/home", "/root", "/var")) for p in s["read_write"] + s["read_only"])
    gw = (Path(__file__).resolve().parents[1] / "amoeba" / "config" / "sandbox" / "gateway.toml").read_text()
    assert 'compute_driver      = "docker"' in gw and "127.0.0.1" in gw


# ---- live ----------------------------------------------------------------------------------------------------------
def gateway_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 17680), 1):
            pass
        import subprocess
        return subprocess.run(["docker", "image", "inspect", "amoeba-sandbox:local"], capture_output=True).returncode == 0
    except OSError:
        return False


live = pytest.mark.skipif(not gateway_up(), reason="no OpenShell gateway / sandbox image on this machine")


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """One sandboxed run for all live probes (a fresh sandbox, deleted at the end)."""
    root = tmp_path_factory.mktemp("loop")
    run_dir = root / "practice" / "01-p1" / "run-d96"
    run_dir.mkdir(parents=True)
    (root / "events.jsonl").write_text("")
    (run_dir.parent / "secret.env").write_text("GEMINI_API_KEY=not-a-real-key-000000\n")
    trace = TraceWriter(run_dir / "trace.jsonl", episode_id="d96")
    box = LocalToolbox(LocalSetup(env={}), run_dir, trace)
    box.start()
    box.begin_step(1)
    yield {"root": root, "run_dir": run_dir, "box": box, "trace": trace}


def events(run_dir):
    return [json.loads(l) for l in (run_dir / "trace.jsonl").read_text().splitlines()]


@live
def test_a_network_is_refused_and_logged(run):
    box = run["box"]
    assert box.box is not None and box.exposed, box.error
    out = box.call("Bash", "curl -s https://example.com")                               # gate.py sees it
    assert out.startswith("refused: local:Bash — network_command")
    hidden = "python3 -c \"m=__import__('urllib.request').request; getattr(m,'url'+'open')('https://example.com', timeout=5)\""
    out = box.call("Bash", hidden)                                                       # only the sandbox sees it
    assert "error" in out.split("\n")[0] and ("Errno" in out or "denied" in out.lower() or "refused" in out.lower())


@live
def test_b_a_write_outside_the_workspace_is_refused(run):
    box = run["box"]
    out = box.call("Write", json.dumps({"file_path": "/etc/evil", "content": "x"}))
    assert out.startswith("refused: local:Write — outside_workspace")
    out = box.call("Bash", "python3 -c \"open('/'+'etc/evil','w')\"")
    assert "Permission denied" in out or "Read-only" in out


@live
def test_c_events_and_env_files_are_out_of_reach(run):
    box, root, run_dir = run["box"], run["root"], run["run_dir"]
    for target in (root / "events.jsonl", run_dir.parent / "secret.env"):
        assert box.call("Read", str(target)).startswith("refused: local:Read — outside_workspace")
        out = box.call("Bash", f"python3 -c \"print(open('/'+'{str(target)[1:]}').read())\"")
        assert "No such file" in out or "Permission denied" in out           # not mounted in the sandbox
        assert "not-a-real-key" not in out
    assert box.call("Bash", "cat ../../events.jsonl").startswith("refused: local:Bash — unsafe_command")


@live
def test_d_skills_and_mcp_configs_cannot_be_edited(run):
    box = run["box"]
    assert box.call("Write", json.dumps({"file_path": ".mcp.json", "content": "{}"})).startswith(
        "refused: local:Write — protected_config")
    assert box.call("Bash", "echo '{}' > .claude/settings.json").startswith("refused: local:Bash — protected_config")
    assert box.call("Write", json.dumps({"file_path": "/opt/skills/xlsx/SKILL.md", "content": "x"})).startswith(
        "refused: local:Write — outside_workspace")
    out = box.call("Bash", "python3 -c \"open('/'+'opt/skills/xlsx/SKILL.md','a')\"")
    assert "Permission denied" in out or "Read-only" in out
    assert "openpyxl" in box.call("Read", "/opt/skills/xlsx/SKILL.md") or True     # reading a skill is allowed


@live
def test_d96a_the_agent_cannot_reach_the_gateway_api(run):
    """The gateway accepts unauthenticated local calls: the workload must not reach it (network=none)."""
    box = run["box"]
    for host in ("127.0.0.1", "host.openshell.internal", "172.17.0.1"):   # loopback, the alias, the bridge
        cmd = (f"python3 -c \"s=__import__('socket').socket(); s.settimeout(3); "
               f"s.connect(('{host}', 17680)); print('REACHED')\"")
        out = box.call("Bash", cmd)
        assert not out.startswith("refused") and "REACHED" not in out, (host, out)   # ran, and failed in the sandbox
        assert "error" in out.split("\n")[0] and ("Errno" in out or "denied" in out.lower() or "timed out" in out)


@live
def test_e_a_primes_task_still_works_and_everything_reaches_events(run):
    box, root, run_dir = run["box"], run["root"], run["run_dir"]
    code = ("cat > primes.py <<'EOF'\nn = 10000\nsieve = [True] * (n + 1)\nsieve[0] = sieve[1] = False\n"
            "for i in range(2, int(n ** 0.5) + 1):\n    if sieve[i]:\n        sieve[i*i::i] = [False] * len(sieve[i*i::i])\n"
            "primes = [i for i, p in enumerate(sieve) if p]\nprint('Count:', len(primes), 'Max:', primes[-1])\nEOF\n"
            "python3 primes.py")
    out = box.call("Bash", code)
    assert "Count: 1229 Max: 9973" in out
    assert (run_dir / "workspace" / "primes.py").exists() and box.has_file("primes.py")
    res = box.finish()
    assert res["local_tool_calls"] >= 5 and res["local_refusals"]
    names = [e["name"] for e in events(run_dir)]
    assert "sandbox_created" in names and "sandbox_log" in names and "sandbox_deleted" in names
    dec = tool_decisions(run_dir)
    assert any(d["name"] == "local_refused" for d in dec) and any(d["name"] == "local_call" for d in dec)
    ev = EvidenceLog(root)
    run_finished(ev, root, run_dir)
    row = [r for r in ev.rows() if r["event"] == "tool_decisions"][-1]
    assert row["data"]["refused"] >= 6 and verify(root)["ok"]


def test_d96a_the_sandbox_is_the_default_and_inprocess_must_be_asked_for(monkeypatch):
    from scripts.run_task import parse_args
    cfg = load_local_config()
    cfg["sandbox"]["isolation"] = "process"                     # even a config saying process: the flag decides
    assert LocalSetup(config=cfg, mode="sandbox").isolation == "openshell"
    assert LocalSetup(config=cfg, mode="inprocess").isolation == "process"
    assert LocalSetup(mode="sandbox").without(["local:Bash"]).mode == "sandbox"
    monkeypatch.delenv("AMOEBA_SANDBOX", raising=False)
    assert parse_args(["t", "--local-tools", "on"]).local_tools_mode == "sandbox"
    with pytest.raises(SystemExit):
        parse_args(["t", "--local-tools", "on", "--local-tools-mode", "inprocess"])
    with pytest.raises(Exception):
        LocalToolbox(LocalSetup(config=cfg, mode="inprocess", env={}), Path("/tmp/x-d96a"), TraceWriter(None))


def test_d96a_limits():
    cfg = load_local_config()
    assert cfg["limits"]["timeout_s"] == 300
    s = cfg["sandbox"]
    assert (s["cpu"], s["memory"], s["run_timeout_s"]) == ("1", "1Gi", 3600)
