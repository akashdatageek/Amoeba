"""D89 — the loop driver end to end with the mock LLM: a scripted feedback shift raises an alarm within 3 tasks, the
Diagnoser names feedback, the Architect proposes one edit, the Experimenter and Gate v2 accept it, recipe v2 is
committed, practice scores recover and the rollback watch keeps it; a resumed loop runs nothing again. Offline."""
import json

from amoeba.adapt.experimenter import InProcessRunner
from amoeba.adapt.ledger import Ledger
from amoeba.adapt.loop import run_loop
from amoeba.adapt.recipe import load_recipe, seed_recipe
from amoeba.adapt.stream import Stream, StreamTask
from amoeba.llm.client import MockLLMClient
from amoeba.memory.recipes import RecipeStore
from tests.conftest import mock
from tests.test_plan_runner import APPROVE, BODY, DIAMOND, step_no

NUM = {"expected_numbers": [{"name": "result", "value": 396, "unit": "", "tolerance": 0}]}
POST = {**NUM, "required_deliverables": [{"name": "assumptions section", "any_of": ["(?im)^#+ assumptions"]}]}
GOOD = json.dumps({"edit": {"op": "add_planner_rule", "params": {"text": "End every answer with a short section "
                                                                          "headed Assumptions."}},
                   "rationale": "The feedback names a missing assumptions section.", "predicted_delta": 0.3})


def stream():
    t = [StreamTask(id=f"p{i}", prompt="Compute 17 * 23 + 5.", family="calc", split="practice",
                    phase="pre" if i <= 8 else "post", order=i, rubric=NUM if i <= 8 else POST) for i in range(1, 15)]
    t += [StreamTask(id=f"hp{i}", prompt=f"Compute 23 * 17 + {i}.", family="calc", split="heldout", phase="post",
                     rubric=POST) for i in (1, 2, 3)]
    t += [StreamTask(id="hq1", prompt="Compute 5 + 17 * 23.", family="calc", split="heldout", phase="pre", rubric=NUM)]
    return Stream(name="fx", tasks=t,
                  shifts=[{"after": 8, "family": "calc", "kind": "feedback", "items": ["assumptions section"]}])


class Runs(InProcessRunner):
    """The summariser writes an Assumptions section when the run's recipe has a planner rule (as if it worked)."""

    def __init__(self):
        super().__init__(self.make)

    def make(self, job):
        rule = bool((load_recipe(job.store, "calc") or seed_recipe("calc")).planner_rules)

        def reply(messages, seed):
            n = step_no(messages)
            extra = "\n\n## Assumptions\n- none beyond the task\n" if rule and n == "4" else ""
            return (f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\n"
                    f"OUT-{n}\nThe result is 396.\n{BODY}{extra}")
        return mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=reply)


def test_the_loop_adapts_to_a_feedback_shift_and_resumes(tmp_path):
    runner, logs = Runs(), []
    archs = []

    def llm_for(hid):
        archs.append(hid)
        return MockLLMClient(script={"architect": [GOOD]})
    s = run_loop(stream(), runner, tmp_path, llm_for, repeats=2, parallel_until=8, log=logs.append)
    led = Ledger(tmp_path / "ledger.jsonl")
    events = [r["event"] for r in led.rows()]
    assert events == ["calibration", "hypothesis", "decision", "calibration"] or events[:3] == \
        ["calibration", "hypothesis", "decision"]
    [alarm] = s["alarms"]
    assert alarm["at_order"] == 9 and alarm["kind"] == "score"                                 # within 3 tasks
    diag = json.loads((tmp_path / "diagnoses" / "o09-calc.json").read_text())
    assert diag["cause"] == "feedback" and diag["symptom"].startswith("feedback: assumptions section missing")
    [dec] = s["decisions"]
    assert dec["decision"] == "accept" and dec["gate_version"] == "v2" and dec["hypothesis_id"] == "fx-calc-o09-h1"
    assert archs == ["fx-calc-o09-h1"]
    st = RecipeStore(tmp_path / "recipes")
    assert st.current("calc").version == 2 and st.experience("calc")[0]["decision"] == "accept"
    scores = {p["order"]: (p["score"], p["recipe_version"]) for p in s["practice"]}
    assert all(scores[o] == (1.0, 1) for o in range(1, 9))                                  # before the shift
    assert scores[9] == (0.5, 1)                                                             # the shift bites
    assert all(scores[o] == (1.0, 2) for o in range(10, 15))                                 # recovery with v2
    state = json.loads((tmp_path / "loop_state.json").read_text())
    assert [e["event"] for e in state["events"]].count("kept") == 1                          # rollback watch kept it
    assert (tmp_path / "summary.json").exists() and "| 11 | p11 | post | v2 | 1.0 |" in (tmp_path / "REPORT.md").read_text()
    # resumed: nothing runs again, nothing is decided again
    n_jobs, n_rows = len(runner.jobs), len(led.rows())
    run_loop(stream(), runner, tmp_path, llm_for, repeats=2, parallel_until=8, log=logs.append)
    assert len(runner.jobs) == n_jobs and len(led.rows()) == n_rows and archs == ["fx-calc-o09-h1"]


def test_three_rejects_leave_the_alarm_unresolved(tmp_path):
    import itertools
    n = itertools.count()

    def useless(hid):
        i = next(n)
        return MockLLMClient(script={"architect": [json.dumps({"edit": {"op": "add_role_rule", "params": {
            "select": {"all_roles": True}, "text": f"Rule number {i}."}}, "rationale": "x", "predicted_delta": 0.1})]})

    class NoEffect(Runs):
        def make(self, job):                       # nothing ever writes the section: no edit can help
            return super().make(job.__class__(**{**job.__dict__, "store": tmp_path / "none"}))
    s = run_loop(stream(), NoEffect(), tmp_path, useless, repeats=2, parallel_until=8, log=lambda m: None)
    first = [d for d in s["decisions"] if d["order"] == s["alarms"][0]["at_order"]]
    assert [d["decision"] for d in first] == ["reject"] * 3                       # three ideas for the first alarm
    assert all(d["decision"] == "reject" for d in s["decisions"])
    assert len(s["unresolved"]) >= 1 and (tmp_path / "human_queue.jsonl").exists()
    # after an unresolved alarm the cool-down (2 tasks) passes before the next alarm
    orders = [a["at_order"] for a in s["alarms"]]
    assert all(b - a > 2 for a, b in zip(orders, orders[1:]))
    assert RecipeStore(tmp_path / "recipes").current("calc").version == 1
