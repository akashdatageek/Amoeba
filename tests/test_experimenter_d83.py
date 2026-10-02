"""D83 — Box 7, the Experimenter: a transform edit runs both arms on the same saved draft; a planner rule edit lets
each arm draft with its own rules; the arm-A cache is hit for a second hypothesis and filled by the calibration;
honesty flags are counted from the run folder. Offline (mock LLM, in-process runner)."""
import json
from pathlib import Path

from amoeba.adapt.experimenter import InProcessRunner, SubprocessRunner, Job, calibrate, experiment, honesty_flags
from amoeba.adapt.recipe import Edit, seed_recipe
from amoeba.adapt.stream import Stream, StreamTask
from tests.conftest import mock
from tests.test_plan_runner import APPROVE, DIAMOND, finish

NUM = {"expected_numbers": [{"name": "result", "value": 396, "unit": "", "tolerance": 0}]}
POST = {**NUM, "required_deliverables": [{"name": "assumptions section", "any_of": ["(?im)^#+ assumptions"]}]}


def stream():
    tasks = [StreamTask(id="p1", prompt="Compute 17 * 23 + 5.", family="calc", split="practice", phase="pre", order=1,
                        rubric=NUM),
             StreamTask(id="h-post-1", prompt="Compute 17 * 23 + 5.", family="calc", split="heldout", phase="post",
                        rubric=POST),
             StreamTask(id="h-post-2", prompt="Compute 23 * 17 + 5.", family="calc", split="heldout", phase="post",
                        rubric=POST),
             StreamTask(id="h-pre-1", prompt="Compute 5 + 17 * 23.", family="calc", split="heldout", phase="pre",
                        rubric=NUM)]
    return Stream(name="fx", tasks=tasks,
                  shifts=[{"after": 1, "family": "calc", "kind": "feedback", "items": ["assumptions section"]}])


class Runner(InProcessRunner):
    def __init__(self):
        self.llms = {}
        super().__init__(self.make)

    def make(self, job):
        m = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=finish)
        self.llms[(job.arm, job.task.id, job.k)] = m
        return m


TRANSFORM = Edit(op="revoke_tool", params={"select": {"all_roles": True}, "tool": "calc"})
RULE = Edit(op="add_planner_rule", params={"text": "End the answer with a section headed Assumptions."})


def test_a_transform_edit_runs_both_arms_on_the_same_saved_draft(tmp_path):
    runner = Runner()
    res = experiment(seed_recipe("calc"), TRANSFORM, "h-revoke", stream(), runner, tmp_path, repeats=2)
    assert res.mode == "same_draft" and len(res.post()) == 4 and len(res.pre()) == 2
    b_jobs = [j for j in runner.jobs if j.arm == "B"]
    a_runs = {(p.task_id, p.k): p.run_A for p in res.pairs}
    assert all(str(j.drafts_from) == a_runs[(j.task.id, j.k)] for j in b_jobs)
    for j in b_jobs:
        assert not runner.llms[("B", j.task.id, j.k)].calls_of("planner")             # arm B drafts nothing
        run_b = next(Path(p.run_B) for p in res.pairs if (p.task_id, p.k) == (j.task.id, j.k))
        box2_b = json.loads((run_b / "draft.json").read_text())
        plan_a = json.loads((Path(a_runs[(j.task.id, j.k)]) / "plan.json").read_text())
        assert box2_b["plan"] == plan_a["plan"] and box2_b["created_roles"] == plan_a["created_roles"]
        b_plan = json.loads((run_b / "plan.json").read_text())
        assert all("calc" not in r["tools"] for r in b_plan["created_roles"])         # the only difference
    assert {(p.seed, p.k) for p in res.pairs} == {(0, 0), (1, 1)}                      # same seed in both arms
    saved = tmp_path / "experiments" / "h-revoke"
    assert len((saved / "pairs.jsonl").read_text().splitlines()) == 6
    assert json.loads((saved / "experiment.json").read_text())["recipe_to"] == 2


def test_a_planner_rule_edit_lets_each_arm_draft_with_its_own_rules(tmp_path):
    runner = Runner()
    res = experiment(seed_recipe("calc"), RULE, "h-rule", stream(), runner, tmp_path, repeats=1)
    assert res.mode == "own_draft"
    for (arm, tid, k), m in runner.llms.items():
        prompt = m.calls_of("planner")[0]["messages"][-1]["content"]
        assert ("# Lessons for this kind of task" in prompt) == (arm == "B")
    assert all(j.drafts_from is None for j in runner.jobs)


def test_the_arm_a_cache_is_hit_for_a_second_hypothesis_and_filled_by_the_calibration(tmp_path):
    runner = Runner()
    cal = calibrate(seed_recipe("calc"), stream(), runner, tmp_path, repeats=2)
    assert cal.kind == "calibration" and len(cal.pairs) == 4 and cal.arm_a_cache_hits == 0
    assert {j.arm for j in runner.jobs} == {"A", "A'"} and {j.seed for j in runner.jobs if j.arm == "A'"} == {1000, 1001}
    n = len(runner.jobs)
    first = experiment(seed_recipe("calc"), TRANSFORM, "h1", stream(), runner, tmp_path, repeats=2)
    a_new = [j for j in runner.jobs[n:] if j.arm == "A"]
    assert first.arm_a_cache_hits == 4 and [j.task.id for j in a_new] == ["h-pre-1", "h-pre-1"]   # post was cached
    n = len(runner.jobs)
    second = experiment(seed_recipe("calc"), RULE, "h2", stream(), runner, tmp_path, repeats=2)
    assert second.arm_a_cache_hits == 6 and {j.arm for j in runner.jobs[n:]} == {"B"}         # arm B only
    assert [p.run_A for p in second.pairs] == [p.run_A for p in first.pairs]


def test_honesty_flags_count_what_the_run_left(tmp_path):
    d = tmp_path / "run"
    (d / "artifacts").mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({"error": "max_turns", "provenance": {"total": {"hallucinated_citations": 2}}}))
    (d / "artifacts" / "step_1.json").write_text(json.dumps({"mislabelled_citations": [{}, {}], "unverified_check": True}))
    (d / "artifacts" / "step_2.json").write_text(json.dumps({"claimed_files_missing": ["a.xlsx"]}))
    assert honesty_flags(d) == 2 + 2 + 1 + 1 + 1


def test_the_subprocess_runner_builds_one_run_task_command_per_job(tmp_path):
    t = stream().heldout("calc", "post")[0]
    job = Job(arm="B", task=t, k=1, seed=1, store=tmp_path / "s", out=tmp_path / "o", namespace="ns",
              drafts_from=tmp_path / "a" / "run1", disabled_tools=["local:Bash"])
    cmd = SubprocessRunner(["--profile", "gemma-api"], scratch=tmp_path / "jobs").command(job)
    joined = " ".join(cmd)
    for part in ("-m scripts.run_task", "--topology plan", f"--recipes {tmp_path / 's'}", "--seed 1",
                 "--llm-cache-namespace ns", "--profile gemma-api", f"--drafts-from {tmp_path / 'a' / 'run1'}",
                 "--disable-tools local:Bash"):
        assert part in joined
    line = json.loads((tmp_path / "jobs" / "ns.jsonl").read_text())
    assert line["id"] == "h-post-1" and line["split"] == "heldout"       # Box 1–3 read it as a plain Task


def test_scores_are_recomputed_from_the_saved_answer(tmp_path):
    """A run's score comes from the current scorer and its saved answer, not the stored number (D80a)."""
    from amoeba.adapt.experimenter import score_of
    t = StreamTask(id="h", prompt="p", family="calc", split="heldout", phase="pre",
                   rubric={"expected_numbers": [{"name": "area", "value": 32.4, "unit": "", "tolerance": 0.01}]})
    assert score_of({"answer": "Floor Area: 32.4 m²", "score": 0.0}, t) == 1.0
