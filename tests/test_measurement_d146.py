"""D146 — measurement and verifier independence: stuck episodes in events.jsonl carry every signal and
ground_truth null, scripts.grade_episodes records hand grades, a profile may name a verifier model (verify steps and
the plan observer), result.json says per verify step whether it was independent, and the verifier's own-result loop
works from a clean sources folder. Offline."""
import json
from pathlib import Path
from types import SimpleNamespace

from amoeba.interp.plan_runner import PlanOptions, model_family, verifier_independence
from amoeba.interp.runtime import Interpreter
from amoeba.interp.trace import TracedLLM, TraceWriter
from amoeba.llm.client import MockLLMClient
from amoeba.llm.profiles import RoleRouter, attach_verifier, get_profile
from scripts.grade_episodes import grade
from tests.test_ladder_d145 import runner
from tests.test_plan_runner import plan_team, step_no

STALL = "## Thought\nhm\n\n## CurrentStep\nthink\n\n## Action\nPrint\n\n## ActionInput\nthinking\n"


def stuck_run(task, envelope, trace, tools, tmp_path):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=lambda m, s: STALL, fix_proposer=["I cannot see a fix."])
    Interpreter(llm, tools, trace, run_dir=str(tmp_path),
                plan_options=PlanOptions(adapt="on", failed_step="run")).run(cfg, task, seed=0)


def test_a_stuck_episode_is_recorded_for_hand_grading(task, envelope, trace, tools, tmp_path):
    stuck_run(task, envelope, trace, tools, tmp_path)
    rows = [json.loads(l) for l in (tmp_path / "events.jsonl").read_text().splitlines()]
    stuck = [r["data"] for r in rows if r["event"] == "stuck"]
    assert stuck and stuck[0]["ground_truth"] is None and stuck[0]["cause"] == "max_turns"
    assert stuck[0]["signals_detail"][0]["signal"] == "max_turns" and stuck[0]["signals_detail"][0]["evidence"]
    answers = iter(["x", "p", "evidence was thin"] + ["s"] * 20)
    lines = []
    g = grade(tmp_path, ask=lambda q: next(answers), out=lines.append)
    assert g["episodes"][0]["grade"] == "partly" and g["episodes"][0]["note"] == "evidence was thin"
    assert json.loads((tmp_path / "grades.json").read_text()) == g
    again = iter(["s"] * 20)                                  # an earlier grade is kept when skipped later
    assert grade(tmp_path, ask=lambda q: next(again), out=lines.append)["episodes"][0]["grade"] == "partly"


def test_verifier_independence_per_verify_step():
    assert model_family("claude-sonnet-5-5") == "anthropic" and model_family("gemma-4-31b-it") == "google"
    steps = [{"step": 1, "models": ["claude-sonnet-5-5"]}, {"step": 2, "models": ["claude-sonnet-5-5"]},
             {"step": 3, "verification": True, "depends_on": [1, 2], "models": ["gemma-4-31b-it"]},
             {"step": 4, "verification": True, "depends_on": [1], "models": ["claude-sonnet-5-5"]},
             {"step": 5, "verification": True, "depends_on": [2], "models": ["claude-opus-5-5"]}]
    got = {x["step"]: x["independence"] for x in verifier_independence(steps)}
    assert got == {3: "independent", 4: "same_model", 5: "same_family"}


def test_a_profile_names_its_verifier():
    p = get_profile("claude-sonnet+gemma-verify")
    assert p.verifier == "gemma-api" and p.provider == "anthropic"
    team = MockLLMClient(model="claude-sonnet-5-5", responses=["ok"] * 3)
    gemma = MockLLMClient(model="gemma-4-31b-it", responses=["ok"] * 3)
    r = RoleRouter(p.name, team)
    assert "not set" in attach_verifier(r, p, lambda vp: None) and r.route("reviewers")[0] is team
    assert "use gemma" in attach_verifier(r, p, lambda vp: gemma)
    assert r.route("reviewers")[0] is gemma and r.route("observers", "plan_observer")[0] is gemma
    assert r.route("observers", "agent_observer")[0] is team and r.route("workers")[0] is team
    tl = TracedLLM(r, TraceWriter(None))
    tl.chat_messages([{"role": "user", "content": "x"}], agent_name="plan_observer")
    assert gemma.calls and not team.calls
    assert attach_verifier(r, get_profile("claude-sonnet"), lambda vp: gemma) == "none"


def test_the_verifier_works_out_its_own_result_from_a_clean_sources_folder(task, envelope, trace, tools, tmp_path):
    pr, _ = runner(task, envelope, trace, tools)
    src = tmp_path / "sources"
    src.mkdir()
    (src / "S1.txt").write_text("producer page")
    pr.local = SimpleNamespace(workspace=tmp_path)
    with pr.clean_sources(3):
        assert list(src.iterdir()) == []                     # the producers' files are out of sight
        (src / "S9.txt").write_text("the verifier's own page")
    assert sorted(p.name for p in src.iterdir()) == ["S1.txt", "S9.txt"]
    assert not any(p.name.startswith(".sources_before") for p in tmp_path.iterdir())
    assert trace.events("verifier_clean_sources")
