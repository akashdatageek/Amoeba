"""D162 — Box 4 saves every round: one row per round (scoped, and the single rung with one probe) in
<run>/rounds.jsonl and as a `round` event in the hash-chained events.jsonl, and a closing `run_end` row with the run's
sim_score. No model call and no change in behaviour. Offline (MockLLMClient, fault injection)."""
import json

from amoeba.adapt.evidence import verify
from amoeba.adapt.rounds import close_rounds, read_rounds
from amoeba.interp.plan_runner import PlanOptions, PlanRunner
from tests.test_proposer_d117 import edit as single_edit, run as run_single
from tests.test_scoped_proposers_d154 import RULE_NO, RULE_OK, run, stall_until

FIELDS = {"kind", "task_id", "niche", "step", "cause", "mode", "signals", "edits", "probes", "pick", "pick_reason",
          "step_status", "outcome"}


def test_a_scoped_round_with_an_injected_fault_writes_a_row_that_matches_the_trace(task, envelope, trace, tools,
                                                                                    tmp_path, monkeypatch):
    monkeypatch.setattr(PlanRunner, "allowed_edits", lambda self, n, d, ops=(): ["add_role_rule"])
    opts = PlanOptions(adapt="on", failed_step="run", proposer="scoped", faults=("tool_error:1:30",), contract="on")

    def script(messages, seed):
        from tests.test_plan_runner import step_no
        from tests.test_proposer_d117 import good, reply
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and "FINISH NOW" not in user:
            return reply("calc", "1 + 1")
        return good(n)
    llm, cfg, ep = run(task, envelope, trace, tools, script, [RULE_OK], [RULE_NO], opts=opts, tmp_path=tmp_path)
    rows = [r for r in read_rounds(tmp_path) if r["kind"] == "round"]
    evs = trace.events("box4_round")
    fixes = [f for f in ep.adaptation["fixes"] if f.get("round")]
    assert rows and len(rows) == len(evs) == len(fixes)                 # one row per round, in order
    events = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [e["data"] for e in events if e["event"] == "round"] == rows
    for row, ev, fix in zip(rows, evs, fixes):
        assert FIELDS <= set(row)
        assert (row["task_id"], row["niche"], row["mode"], row["step"]) == (task.id, "general", "scoped", 1)
        assert row["pick"] == ev.get("amoeba.pick") and len(row["probes"]) == ev["amoeba.probes"]
        assert row["cause"] == fix["cause"] and row["step_status"] == fix["status_after"]
        assert [(e["scope"], e["op"], e["because"]) for e in row["edits"]] == \
            [(c["scope"], c["op"], c["because"]) for c in fix["round"]["candidates"] if c["op"]]
        for p, q in zip(row["probes"], fix["round"]["probes"]):
            assert {k: p[k] for k in ("scope", "op", "status", "cleared", "kept", "new", "tokens", "samples")} == \
                {k: q[k] for k in ("scope", "op", "status", "cleared", "kept", "new", "tokens", "samples")}
    assert verify(tmp_path)["ok"]                                  # scripts/verify_evidence.py's check still holds


def test_the_single_rung_is_recorded_in_the_same_shape_with_one_probe(task, envelope, trace, tools, tmp_path):
    single = PlanOptions(adapt="on", failed_step="run", proposer="single")
    llm, cfg, ep = run_single(task, envelope, trace, tools, stall_until("FINISH NOW"),
                              [single_edit("add_role_rule", role="Cost Analyst", text="FINISH NOW with your output.")],
                              tmp_path=tmp_path, opts=single)
    [row] = [r for r in read_rounds(tmp_path) if r["kind"] == "round"]
    assert row["mode"] == "single" and row["pick"] == "single" and len(row["edits"]) == 1
    [p] = row["probes"]
    assert (p["op"], p["status"], p["samples"]) == ("add_role_rule", "done", 1) and p["cleared"]
    assert row["step_status"] == "done" and verify(tmp_path)["ok"]


def test_no_round_no_file_and_run_end_closes_the_record(tmp_path):
    assert close_rounds(tmp_path, "t1", {"score": 1.0}, "abc", "ok") is None        # no round: nothing written
    assert not (tmp_path / "rounds.jsonl").exists()
    (tmp_path / "rounds.jsonl").write_text(json.dumps({"kind": "round", "step": 1}) + "\n")
    row = close_rounds(tmp_path, "t1", {"score": 0.75, "delta": 0.25}, "abc", "ok")
    rows = read_rounds(tmp_path)
    assert rows[-1] == row and (row["kind"], row["task_id"], row["sim_score"]["score"], row["judge_hash"]) == \
        ("run_end", "t1", 0.75, "abc")
    events = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert events[-1]["event"] == "run_end" and verify(tmp_path)["ok"]


def test_run_task_closes_the_record():
    import inspect
    import scripts.run_task as rt
    assert "close_rounds(" in inspect.getsource(rt.run_one)
