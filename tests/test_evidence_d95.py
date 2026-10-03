"""D95 — evidence logging outside the agents' reach: one append-only, hash-chained events.jsonl written by the harness;
each row carries the SHA-256 of the row before and of the run folders it names; verify_evidence finds the first break;
finished runs are key-scanned and queued for the bucket copy (unshipped ones kept in loop_state.json); no agent path,
Bash command or environment reaches the log, the ledger, a run record or a cloud credential. Offline."""
import json
from pathlib import Path

import pytest

from amoeba.adapt.evidence import (GENESIS, EvidenceLog, Shipper, key_scan, refuse_cloud_vars, run_env, sha256_text,
                                   verify)
from amoeba.adapt.loop import run_loop
from amoeba.llm.client import MockLLMClient
from amoeba.localtools.gate import inside, screen_command
from tests.test_loop_d89 import GOOD, Runs, stream


def folder(tmp, name, text="result"):
    d = tmp / name
    d.mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({"answer": text}))
    return d


def test_the_chain_and_the_manifests_hold_and_breaks_are_found(tmp_path):
    ev = EvidenceLog(tmp_path)
    run = folder(tmp_path, "practice/01-p1/run1")
    ev.append("practice_run", {"order": 1}, [run], key="practice:1")
    ev.append("alarm", {"order": 1, "inputs": {"window_scores": [0.5]}})
    ev.append("decision", {"hypothesis_id": "h"})
    rows = ev.rows()
    assert [r["seq"] for r in rows] == [0, 1, 2] and rows[0]["prev_sha"] == GENESIS
    assert rows[1]["prev_sha"] == sha256_text(ev.lines()[0]) and rows[0]["manifests"][0]["path"] == "practice/01-p1/run1"
    assert (run / "MANIFEST.sha256.json").exists()
    assert verify(tmp_path) == {"ok": True, "rows": 3, "manifests": 1, "first_break": None}
    assert ev.append("practice_run", {"order": 1}, [run], key="practice:1") is None and len(ev.rows()) == 3
    # a changed run file
    (run / "result.json").write_text(json.dumps({"answer": "edited"}))
    assert verify(tmp_path)["first_break"]["kind"] == "manifest"
    (run / "result.json").write_text(json.dumps({"answer": "result"}))
    # a changed row: the next row's prev_sha no longer matches
    lines = ev.lines()
    lines[1] = lines[1].replace('"order": 1', '"order": 9')
    ev.path.write_text("\n".join(lines) + "\n")
    b = verify(tmp_path)["first_break"]
    assert (b["line"], b["kind"]) == (3, "chain")
    # a removed row
    ev.path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert verify(tmp_path)["first_break"]["kind"] == "seq"


def test_verify_evidence_script_exit_codes(tmp_path, capsys):
    from scripts.verify_evidence import main
    EvidenceLog(tmp_path).append("x", {})
    assert main(["--root", str(tmp_path)]) == 0
    (tmp_path / "events.jsonl").write_text("not json\n")
    assert main(["--root", str(tmp_path)]) == 1 and '"kind": "parse"' in capsys.readouterr().out


def test_a_whole_loop_logs_every_event_and_queues_its_runs(tmp_path, gate_v2):
    run_loop(stream(), Runs(), tmp_path, lambda hid: MockLLMClient(script={"architect": [GOOD]}), repeats=2,
             parallel_until=8, log=lambda *_: None, secrets=["sk-not-a-real-key-123456789012345"])
    rows = EvidenceLog(tmp_path).rows()
    kinds = [r["event"] for r in rows]
    assert kinds.count("practice_run") == 14
    for k in ("alarm", "diagnosis", "architect", "hypothesis", "experiment", "decision", "kept"):
        assert k in kinds, k
    alarm = next(r for r in rows if r["event"] == "alarm")["data"]
    assert {"window_scores", "reference_scores", "reference_mean", "reference_sd", "score_threshold"} <= \
        set(alarm["inputs"])
    arch = next(r for r in rows if r["event"] == "architect")["data"]
    assert "You propose one change to a team recipe" in arch["prompt"] and arch["attempts"][0]["reply"] == GOOD
    exp = next(r for r in rows if r["event"] == "experiment")
    assert len(exp["manifests"]) > 2                                   # experiment.json, pairs.jsonl, run folders
    assert verify(tmp_path)["ok"]
    state = json.loads((tmp_path / "loop_state.json").read_text())
    assert state["unshipped"] and all(u["error"] == "no bucket configured" for u in state["unshipped"])
    assert {u["kind"] for u in state["unshipped"]} == {"run", "events"} and state["ship_blocked"] == []
    n = len(rows)
    run_loop(stream(), Runs(), tmp_path, lambda hid: MockLLMClient(script={"architect": [GOOD]}), repeats=2,
             parallel_until=8, log=lambda *_: None)
    assert len(EvidenceLog(tmp_path).rows()) == n                       # a resumed loop logs nothing again


def test_the_shipper_scans_retries_and_keeps_what_failed(tmp_path):
    good, bad = folder(tmp_path, "practice/a/run"), folder(tmp_path, "practice/b/run", "key AIza" + "x" * 35)
    EvidenceLog(tmp_path).append("x", {})
    sent, fails = [], {"n": 0}

    def upload(path, name):
        if "flaky" in name and fails["n"] < 2:
            fails["n"] += 1
            raise OSError("503")
        sent.append(name)
    s = Shipper(tmp_path, upload, secrets=[], prefix="m2/")
    s.queue_run(good)
    s.queue_run(bad)
    s.queue_events()
    assert s.blocked == [{"kind": "run", "path": "practice/b/run", "key_scan_hits": ["result.json"]}]
    assert s.flush() == [] and "m2/practice/a/run/result.json" in sent and "m2/events/events.000001.jsonl" in sent
    flaky = folder(tmp_path, "practice/flaky/run")
    s.queue_run(flaky)
    assert s.flush() == [] and fails["n"] == 2                          # two failures, then it went through

    def down(path, name):
        raise ConnectionError("no route")
    s2 = Shipper(tmp_path, down, retries=2)
    s2.queue_run(good)
    left = s2.flush()
    assert left[0]["path"] == "practice/a/run" and left[0]["error"].startswith("ConnectionError")


def test_key_scan_finds_shapes_and_secret_values(tmp_path):
    d = folder(tmp_path, "r", "value s3cr3t-value-long-enough here")
    assert key_scan(d, ["s3cr3t-value-long-enough"]) and not key_scan(d, ["another-secret-value"])


def test_cloud_credentials_never_reach_a_run(tmp_path, monkeypatch):
    from scripts.run_experiment import load_env
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/secret/sa.json")
    monkeypatch.setenv("AMOEBA_GCS_BUCKET", "bucket")
    keys = tmp_path / "keys.env"
    keys.write_text("GEMINI_API_KEY=abc\n")
    env = load_env([str(keys)])
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in env and "AMOEBA_GCS_BUCKET" not in env and env["GEMINI_API_KEY"]
    gcs = tmp_path / "gcs.env"
    gcs.write_text("AMOEBA_GCS_BUCKET=b\nGOOGLE_APPLICATION_CREDENTIALS=/x.json\n")
    with pytest.raises(ValueError):
        load_env([str(gcs)])
    assert run_env({"AWS_SECRET_ACCESS_KEY": "x", "PATH": "/bin"}) == {"PATH": "/bin"}
    with pytest.raises(ValueError):
        refuse_cloud_vars("f", {"CLOUDSDK_CONFIG": "x"})


def test_the_local_tool_server_gets_no_credentials(tmp_path, monkeypatch):
    from amoeba.localtools.toolbox import LocalSetup, LocalToolbox
    from amoeba.interp.trace import TraceWriter
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/secret/sa.json")
    monkeypatch.setenv("GEMINI_API_KEY", "abc")
    box = LocalToolbox(LocalSetup(env={"AMOEBA_SANDBOX": "1"}), tmp_path / "run", TraceWriter(tmp_path / "t.jsonl"))
    env = box.server_env()
    assert set(env) == {"PATH", "HOME", "LANG", "MPLBACKEND", "PYTHONDONTWRITEBYTECODE", "AMOEBA_SANDBOX"}


def test_an_agent_path_or_command_cannot_reach_the_evidence(tmp_path):
    root = tmp_path / "eval" / "loop" / "m2"
    run = root / "practice" / "01-p1" / "run1"
    ws = run / "workspace"
    ws.mkdir(parents=True)
    for f in ("events.jsonl", "ledger.jsonl", "loop_state.json"):
        (root / f).write_text("{}\n")
    for f in ("result.json", "trace.jsonl"):
        (run / f).write_text("{}\n")
    targets = [root / "events.jsonl", root / "ledger.jsonl", run / "result.json", run / "trace.jsonl"]
    for t in targets:
        assert inside(str(t), ws) is None                                      # absolute
        assert inside(str(Path("..") / ".." / ".." / ".." / t.name) if t.parent == root else f"../{t.name}", ws) is None
    (ws / "link").symlink_to(root / "events.jsonl")                            # a symlink is followed, then refused
    assert inside("link", ws) is None
    assert inside("notes.txt", ws) == (ws / "notes.txt").resolve()
    for cmd in (f"cat {root / 'events.jsonl'}", "cat ../trace.jsonl", "cat ../../../../ledger.jsonl",
                "cd .. && cat result.json", "python3 -c \"print(open('../result.json').read())\"",
                f"echo x >> {root / 'events.jsonl'}", "cp ~/x .", "cat $HOME/.config/gcloud"):
        assert screen_command(cmd, ws) is not None, cmd
    assert screen_command("python3 make_chart.py", ws) is None
