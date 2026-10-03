"""D92 — three task sets per family: practice (the loop's), gate (held-out, Experimenter and Gate only) and final audit
(tasks/audit/, read by no loop component; scripts/run_audit.py only, once per claim, logged). The stream loader
refuses the audit file and audit tasks; a whole mock loop opens no audit file; the audit script refuses a used claim."""
import builtins
import io
import json
from pathlib import Path

import pytest

from amoeba.adapt.experimenter import InProcessRunner
from amoeba.adapt.loop import run_loop
from amoeba.adapt.stream import AuditLeak, HeldOutLeak, Stream, StreamTask, assert_practice, load_stream
from amoeba.llm.client import MockLLMClient
from tests.conftest import ROOT
from tests.test_loop_d89 import GOOD, NUM, POST, Runs, stream as loop_stream

AUDIT_REFS = ("tasks/audit", '/ "audit"', ".audit.", "run_audit", "load_audit", "audit_path", "audit_log", "AuditTask")
LOOP_FILES = [*sorted((ROOT / "amoeba" / "adapt").glob("*.py")), *sorted((ROOT / "amoeba" / "memory").glob("*.py")),
              ROOT / "scripts" / "run_loop.py", ROOT / "scripts" / "run_experiment.py", ROOT / "scripts" / "run_task.py"]


def write_stream(folder: Path, split="gate") -> Path:
    s = loop_stream()
    lines = []
    for t in s.tasks:
        d = t.model_dump(mode="json", exclude_none=True)
        if d["split"] == "heldout":
            d["split"] = split
        lines.append(json.dumps(d))
    p = folder / "stream_fx.jsonl"
    p.write_text("\n".join(lines) + "\n")
    (folder / "stream_fx.shifts.yaml").write_text(
        "shifts:\n  - after: 8\n    family: calc\n    kind: feedback\n    items: [\"assumptions section\"]\n")
    return p


def test_gate_is_the_held_out_set():
    t = StreamTask(id="g1", prompt="Compute 2 + 2.", family="calc", split="gate", phase="post", rubric=POST)
    s = Stream(name="x", tasks=[t])
    assert s.heldout("calc", "post") == [t] and s.practice() == []
    with pytest.raises(HeldOutLeak):
        assert_practice(t)
    with pytest.raises(ValueError):
        StreamTask(id="a1", prompt="x", family="calc", split="audit", phase="post", rubric=POST)


def test_the_loader_refuses_the_audit_file_and_audit_tasks(tmp_path, monkeypatch):
    p = write_stream(tmp_path)
    assert len(load_stream(p).heldout("calc")) == 4
    audit = tmp_path / "stream_fx.audit.jsonl"
    audit.write_text(json.dumps({"id": "a1", "prompt": "x", "family": "calc", "split": "audit", "phase": "post",
                                 "rubric": NUM}) + "\n")
    with pytest.raises(AuditLeak):
        load_stream(audit)
    mixed = tmp_path / "stream_mixed.jsonl"
    mixed.write_text(p.read_text() + audit.read_text())
    with pytest.raises(AuditLeak):
        load_stream(mixed)
    import amoeba.adapt.stream as st
    monkeypatch.setattr(st, "TASKS_DIR", tmp_path)
    (tmp_path / "audit").mkdir()
    inside = tmp_path / "audit" / "stream_fx.jsonl"
    inside.write_text(p.read_text())
    with pytest.raises(AuditLeak):
        load_stream(inside)


def test_no_loop_component_names_the_audit_set():
    for f in LOOP_FILES:
        text = f.read_text(encoding="utf-8")
        if f.name == "stream.py":                    # the loader's refusal is the one place that names it
            body = text[text.index("def load_stream"):]
            assert body.index("raise AuditLeak") < body.index("read_text")   # refused before anything is read
            continue
        hits = [p for p in AUDIT_REFS if p in text]
        assert not hits, (f, hits)


def test_a_whole_loop_opens_no_audit_file(tmp_path, monkeypatch, gate_v2):
    folder = tmp_path / "tasks"
    folder.mkdir()
    p = write_stream(folder)
    (folder / "audit").mkdir()
    (folder / "audit" / "stream_fx.audit.jsonl").write_text(
        json.dumps({"id": "a1", "prompt": "Compute 9 * 9.", "family": "calc", "split": "audit", "phase": "post",
                    "rubric": NUM}) + "\n")
    opened = []
    real_open, real_io_open = builtins.open, io.open

    def spy(file, *a, **k):
        opened.append(str(file))
        return real_open(file, *a, **k)

    def spy_io(file, *a, **k):
        opened.append(str(file))
        return real_io_open(file, *a, **k)
    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy_io)
    s = run_loop(load_stream(p), Runs(), tmp_path / "loop", lambda hid: MockLLMClient(script={"architect": [GOOD]}),
                 repeats=2, parallel_until=8, log=lambda *_: None)
    assert s["decisions"] and opened
    assert not [f for f in opened if "audit" in f]


def test_the_audit_script_uses_each_claim_once_and_logs_first(tmp_path):
    from scripts.run_audit import AuditTask, load_audit, run_audit
    from tests.test_experimenter_d83 import Runner
    path = tmp_path / "stream_fx.audit.jsonl"
    path.write_text("".join(json.dumps({"id": f"a{i}", "prompt": "Compute 17 * 23 + 5.", "family": "calc",
                                        "split": "audit", "phase": "post", "rubric": NUM}) + "\n" for i in (1, 2)))
    tasks = load_audit("fx", "calc", path)
    assert [t.id for t in tasks] == ["a1", "a2"] and isinstance(tasks[0], AuditTask)
    out = tmp_path / "eval"
    row = run_audit("fx", "calc", "C1", "B beats A on unseen tasks", Runner(), out, tmp_path / "noB", repeats=1,
                    tasks=tasks)
    log = [json.loads(l) for l in (out / "audit_log.jsonl").read_text().splitlines()]
    assert [r["event"] for r in log] == ["claim", "result"] and log[0]["statement"] == "B beats A on unseen tasks"
    assert log[0]["tasks"] == ["a1", "a2"] and row["n_tasks"] == 2 and row["mean_task_d"] == 0.0
    with pytest.raises(SystemExit):
        run_audit("fx", "calc", "C1", "again", Runner(), out, tmp_path / "noB", repeats=1, tasks=tasks)
    assert len((out / "audit_log.jsonl").read_text().splitlines()) == 2
