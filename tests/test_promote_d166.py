"""D166 — the outer loop, run by hand (scripts/promote.py): a lesson that kept helping becomes a GENERAL config
change, tested first on the replay set (two arms through stage_e, today's config against a temporary copy with the
change), accepted only by plain code's rule, and never applied without the user. General: no niche is chosen, and
the change surface is adapt.yaml's allowed_edits order, promoted.planner_rules and promoted.tool_guidance. Offline:
the mock LLM, the stand-in scorer and an injected arm runner."""
import json
from pathlib import Path

import pytest
import yaml

from amoeba.adapt.config import CONFIG, adapt_config
from amoeba.adapt.lessons import LessonLibrary, key_of, round_verdicts
from amoeba.eval.judge import judge_hash
from scripts import promote as P
from tests.conftest import mock
from tests.test_lessons_d163 import p, row

ROOT = Path(__file__).resolve().parents[1]
CAUSE, OP, SCOPE = "tool_error", "add_tool_guidance", "inv"


def library(root, helped=3, tasks=2, hurt=0, status="approved"):
    lib = LessonLibrary(root)
    for k in range(helped):
        [v] = round_verdicts(row(dict(p("done"), op=OP, scope=SCOPE), cause=CAUSE, task_id=f"t{k % tasks}"))
        lib.record(v, "general", f"t{k % tasks}", f"r{k}")
    for _ in range(hurt):
        [v] = round_verdicts(row(dict(p(new=["x"]), op=OP, scope=SCOPE), cause=CAUSE))
        lib.record(v, "calc", "t9", "r9")
    eid = key_of(CAUSE, OP, SCOPE)
    lib.add_lesson(eid, "A tool keeps failing on its input format.",
                   "add_tool_guidance (inv): say on the tool how its input must look.", "medium", "r0")
    lib.set_status(eid, status)
    return lib, eid


def test_the_trigger_is_plain_code(tmp_path):
    lib, eid = library(tmp_path / "a")
    assert [e["id"] for e in P.candidates(lib)] == [eid]
    assert P.candidates(library(tmp_path / "b", helped=2)[0]) == []                # helped < 3
    assert P.candidates(library(tmp_path / "c", tasks=1)[0]) == []                 # one task only
    assert P.candidates(library(tmp_path / "d", hurt=1, helped=5)[0]) == []        # hurt anywhere
    assert P.candidates(library(tmp_path / "e", status="unreviewed")[0]) == []     # the user has not approved it
    lib, eid = library(tmp_path / "f")
    lib.set_status(eid, "promotion_failed")
    assert P.candidates(lib) == []                                                  # never tried again


def test_the_config_can_be_a_temporary_copy(tmp_path, monkeypatch):
    copy = tmp_path / "adapt.yaml"
    copy.write_text(CONFIG.read_text().replace("enabled: false", "enabled: true", 1))
    monkeypatch.setenv("AMOEBA_ADAPT_CONFIG", str(copy))
    assert adapt_config()["compose"]["enabled"] is True
    monkeypatch.delenv("AMOEBA_ADAPT_CONFIG")
    assert adapt_config()["compose"]["enabled"] is False
    assert adapt_config()["promoted"] == {"planner_rules": [], "tool_guidance": {}}    # empty: today's behaviour


GOOD = {"kind": "tool_guidance", "tool": "calc", "text": "Write the expression only, such as 12 * (3 + 4)."}


def test_the_change_surface_is_checked_by_plain_code():
    cfg = yaml.safe_load(CONFIG.read_text())
    tools = ["calc", "echo"]
    assert P.change_problems(GOOD, cfg, tools) == []
    order = list(reversed(cfg["diagnoser"]["allowed_edits"][CAUSE]))
    assert P.change_problems({"kind": "reorder_allowed_edits", "cause": CAUSE, "order": order}, cfg, tools) == []
    assert P.change_problems({"kind": "planner_rule", "text": "Read every input in full before you write."},
                             cfg, tools) == []
    bad = [{**GOOD, "file": "amoeba/task/quality.py"}, {**GOOD, "file": "amoeba/interp/plan_runner.py"},
           {**GOOD, "file": "amoeba/config/prompts/planner.txt"}, {**GOOD, "file": "amoeba/config/frozen.yaml"},
           {"kind": "rewrite_code", "text": "x"}, {**GOOD, "tool": "rm_rf"},
           {**GOOD, "text": "Skip the check when it fails."}, {**GOOD, "text": "x" * 301},
           {"kind": "reorder_allowed_edits", "cause": CAUSE, "order": order[:-1]},
           {"kind": "reorder_allowed_edits", "cause": "nope", "order": order}, {**GOOD, "extra": 1}]
    for b in bad:
        assert P.change_problems(b, cfg, tools), b


def test_the_change_is_written_to_text_and_keeps_the_comments():
    text = CONFIG.read_text()
    for change in (GOOD, {"kind": "planner_rule", "text": "Read every input in full before you write."},
                   {"kind": "reorder_allowed_edits", "cause": CAUSE,
                    "order": list(reversed(yaml.safe_load(text)["diagnoser"]["allowed_edits"][CAUSE]))}):
        new = P.apply_change_text(text, change)
        cfg = yaml.safe_load(new)
        assert new.count("#") >= text.count("#") - 1                              # the comments stay
        if change["kind"] == "tool_guidance":
            assert cfg["promoted"]["tool_guidance"] == {"calc": GOOD["text"]}
        elif change["kind"] == "planner_rule":
            assert cfg["promoted"]["planner_rules"] == [change["text"]]
        else:
            assert cfg["diagnoser"]["allowed_edits"][CAUSE] == change["order"]
        rest = {k: v for k, v in cfg.items() if k not in ("promoted", "diagnoser")}
        assert rest == {k: v for k, v in yaml.safe_load(text).items() if k not in ("promoted", "diagnoser")}


def fake_runner(scores_b, contract_b=1.0, judge=None):
    """Arms without subprocesses: each run folder gets result.json and sim_score.json from the given scores."""
    def run(tasks, ids, seeds, out, config_b, passthrough):
        assert Path(config_b).exists() and Path(config_b) != CONFIG
        rows = []
        for t in ids:
            for s in seeds:
                for arm, score, rate in (("current", 0.5, 1.0), ("changed", scores_b[t], contract_b)):
                    d = Path(out) / arm / f"{t}.s{s}" / "run"
                    d.mkdir(parents=True, exist_ok=True)
                    h = judge or judge_hash()["sha256"]
                    sim = {"score": score, "baseline": 0.5, "delta": score - 0.5, "seed": s, "judge_hash": h}
                    (d / "result.json").write_text(json.dumps({"judge_hash": h, "sim_score": sim}))
                    (d / "artifacts").mkdir(exist_ok=True)
                    (d / "artifacts" / "step_1.json").write_text(json.dumps(
                        {"meta": {"contract": {"A": {}}, "contract_missing": [] if rate == 1.0 else ["x"]}}))
                    rows.append({"task": t, "seed": s, "arm": arm, "run": str(d)})
        return rows
    return run


def replay_file(tmp_path):
    f = tmp_path / "replay.jsonl"
    f.write_text("".join(json.dumps({"id": t, "set": "replay", "prompt": "Compute 1 + 1. Reply with just the number.",
                                     "sim": {"scorer": "standin", "expected": 2}}) + "\n" for t in ("r1", "r2")))
    return f


def setup(tmp_path, proposal=GOOD):
    lib, eid = library(tmp_path / "lib")
    cfg = tmp_path / "adapt.yaml"
    cfg.write_text(CONFIG.read_text())
    llm = mock(promoter=[json.dumps(proposal)])
    return lib, eid, cfg, llm


def test_a_change_that_helps_is_accepted_but_not_applied(tmp_path):
    lib, eid, cfg, llm = setup(tmp_path)
    before = cfg.read_text()
    out = P.promote(lib, eid, replay_file(tmp_path), llm, tmp_path / "promotions", config=cfg, seeds=[0, 1, 2],
                    runner=fake_runner({"r1": 0.8, "r2": 0.6}), tools=["calc", "echo"])
    assert out["decision"] == "accepted" and lib.get(eid)["status"] == "promoted"
    assert cfg.read_text() == before                                                  # never applied by the loop
    report = Path(out["report"]).read_text()
    assert "accepted" in report and "calc" in report and Path(out["patch"]).read_text().startswith("--- a/")
    events = [json.loads(x) for x in (tmp_path / "promotions" / "events.jsonl").read_text().splitlines()]
    assert events[-1]["event"] == "promotion" and events[-1]["data"]["decision"] == "accepted"
    assert len(llm.calls_of("promoter")) == 1
    prompt = llm.calls_of("promoter")[0]["messages"][-1]["content"]
    assert "no score, no rubric and no answer key" in prompt and "calc" in prompt
    P.apply_report(out["report"], config=cfg)                                          # the user applies it
    assert yaml.safe_load(cfg.read_text())["promoted"]["tool_guidance"] == {"calc": GOOD["text"]}
    with pytest.raises(ValueError):
        P.apply_report(out["report"], config=cfg)                                      # the file changed since


def test_a_change_that_hurts_one_task_is_rejected(tmp_path):
    lib, eid, cfg, llm = setup(tmp_path)
    out = P.promote(lib, eid, replay_file(tmp_path), llm, tmp_path / "promotions", config=cfg, seeds=[0, 1, 2],
                    runner=fake_runner({"r1": 0.95, "r2": 0.35}), tools=["calc", "echo"])
    assert out["decision"] == "rejected" and "r2" in out["why"]
    assert lib.get(eid)["status"] == "promotion_failed" and lib.get(eid)["lesson"]   # the lesson is never deleted


def test_a_lower_contract_pass_rate_is_rejected(tmp_path):
    lib, eid, cfg, llm = setup(tmp_path)
    out = P.promote(lib, eid, replay_file(tmp_path), llm, tmp_path / "promotions", config=cfg, seeds=[0],
                    runner=fake_runner({"r1": 0.9, "r2": 0.9}, contract_b=0.0), tools=["calc", "echo"])
    assert out["decision"] == "rejected" and "contract" in out["why"]


def test_a_proposal_touching_a_frozen_file_is_refused_before_any_run(tmp_path):
    lib, eid, cfg, llm = setup(tmp_path, proposal={**GOOD, "file": "amoeba/task/quality.py"})
    called = []
    out = P.promote(lib, eid, replay_file(tmp_path), llm, tmp_path / "promotions", config=cfg, seeds=[0],
                    runner=lambda *a: called.append(a) or [], tools=["calc", "echo"])
    assert out["decision"] == "refused" and not called and "frozen" in out["why"]
    assert lib.get(eid)["status"] == "approved"                                       # never tested: unchanged


def test_runs_scored_by_different_judges_are_refused(tmp_path):
    lib, eid, cfg, llm = setup(tmp_path)
    runner = fake_runner({"r1": 0.9, "r2": 0.9})

    def mixed(tasks, ids, seeds, out, config_b, passthrough):
        rows = runner(tasks, ids, seeds, out, config_b, passthrough)
        r = json.loads((Path(rows[1]["run"]) / "result.json").read_text())
        (Path(rows[1]["run"]) / "result.json").write_text(json.dumps({**r, "judge_hash": "other"}))
        return rows
    out = P.promote(lib, eid, replay_file(tmp_path), llm, tmp_path / "promotions", config=cfg, seeds=[0],
                    runner=mixed, tools=["calc", "echo"])
    assert out["decision"] == "refused" and "judge" in out["why"]


def test_only_the_replay_set_is_run(tmp_path):
    f = tmp_path / "mixed.jsonl"
    f.write_text("".join(json.dumps({"id": t, "set": s, "prompt": "x"}) + "\n"
                         for t, s in (("a", "stream"), ("b", "replay"), ("c", None))))
    assert P.replay_ids(f) == ["b"]


def test_promoted_settings_reach_the_planner_and_the_helpers(tmp_path, monkeypatch, envelope, tools):
    from amoeba.task.models import Task
    from scripts.run_task import run_one
    from tests.conftest import fx
    cfg = tmp_path / "adapt.yaml"
    text = P.apply_change_text(CONFIG.read_text(), {"kind": "planner_rule", "text": "Read every input in full."})
    cfg.write_text(P.apply_change_text(text, GOOD))
    monkeypatch.setenv("AMOEBA_ADAPT_CONFIG", str(cfg))
    llm = mock(planner=[fx("draft_d24_full")], agent_observer=[fx("observer_d24_approve")],
               plan_observer=[fx("observer_d24_approve")],
               plan_worker=["## Thought\nok\n\n## CurrentStep\nw\n\n## Action\ncalc\n\n## ActionInput\n1 + 1\n",
                            "## Thought\nok\n\n## Final_Output\n1\n"] * 9)
    run_one(Task(prompt="Estimate the monthly cost for 50 tenants at 200 GB each."), "plan", llm, envelope, tools,
            tmp_path / "runs", draft_prompts="d24")
    assert all("# Rules learned from earlier tasks" in json.dumps(c["messages"]) for c in llm.calls_of("planner"))
    helpers = [json.dumps(c["messages"]) for c in llm.calls_of("plan_worker") if "calc" in json.dumps(c["messages"])]
    assert helpers and any(GOOD["text"] in h for h in helpers)


def test_stage_e_has_a_config_arm_pair(tmp_path):
    from scripts.stage_e import CONFIG_ARMS, arm_command, arm_env
    assert CONFIG_ARMS == ("current", "changed")
    cmd = arm_command("changed", Path("t.jsonl"), 1, tmp_path, tmp_path / "p.json", tmp_path / "first", [])
    assert "--drafts-from" in cmd and "--adapt" not in cmd
    assert arm_env(None, config_b="/tmp/x.yaml", arm="changed")["AMOEBA_ADAPT_CONFIG"] == "/tmp/x.yaml"
    assert arm_env(None, config_b="/tmp/x.yaml", arm="current") is None


def test_the_real_pair_runner_with_the_mock_rejects_a_change_that_changes_nothing(tmp_path):
    lib, eid, cfg, llm = setup(tmp_path)
    tasks = ROOT / "tasks" / "general_example.jsonl"
    out = P.promote(lib, eid, tasks, llm, tmp_path / "promotions", config=cfg, seeds=[0],
                    passthrough=["--topology", "flat", "--llm", "mock"], tools=["calc", "echo"])
    assert out["decision"] == "rejected" and "mean" in out["why"]                    # the arms score the same
    summary = json.loads(Path(out["report"]).with_suffix(".json").read_text())["arms"]
    assert {r["task"] for r in summary["per_task"]} == {"gen-replay-1", "gen-replay-2"}   # the replay set only
