"""D100 — recipe expiry, replay and pruning (offline, mock LLM): every N practice tasks of a family the pre-shift
gate tasks are replayed with the current recipe; a drop beyond noise raises an alarm of cause `retention` at once
(scores only reach the Diagnoser); pruning removes each recipe line one at a time on the gate set, drops a line whose
removal loses nothing beyond noise and saves cost, keeps a line that earns its keep, and records each prune as a Gate
decision that counts toward no hypothesis quota."""
import json

import pytest

from amoeba.adapt.experimenter import InProcessRunner
from amoeba.adapt.ledger import Ledger
from amoeba.adapt.loop import run_loop
from amoeba.adapt.recipe import Edit, apply_edit, load_recipe, seed_recipe
from amoeba.adapt.retention import prune_family, remove_line, retention_cfg, retention_check, retention_due
from amoeba.adapt.stream import Stream, StreamTask
from amoeba.llm.client import MockLLMClient
from amoeba.memory.recipes import RecipeStore
from tests.conftest import mock
from tests.test_loop_d89 import NUM, POST, Runs, stream as d89_stream
from tests.test_plan_runner import APPROVE, BODY, DIAMOND, step_no

RULE = Edit(op="add_planner_rule", params={"text": "End every answer with a short section headed Assumptions."})
ACCEPT = {"event": "decision", "decision": "accept"}


def store_with(tmp_path, *edits, family="calc"):
    st = RecipeStore(tmp_path / "recipes")
    st.ensure_seed(family)
    r = st.current(family)
    for i, e in enumerate(edits, 1):
        r = apply_edit(r, e, hypothesis_id=f"h{i}")
        st.commit(r, {**ACCEPT, "hypothesis_id": f"h{i}"})
    return st


class HurtsOldTasks(InProcessRunner):
    """With a planner rule in the recipe, held-out PRE tasks come out wrong (the rule helps new tasks, hurts old)."""

    def __init__(self):
        super().__init__(self.make)

    def make(self, job):
        rule = bool((load_recipe(job.store, "calc") or seed_recipe("calc")).planner_rules)
        wrong = rule and job.task.split != "practice" and job.task.phase == "pre"

        def reply(messages, seed):
            n = step_no(messages)
            return (f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\n"
                    f"OUT-{n}\nThe result is {0 if wrong else 396}.\n{BODY}")
        return mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=reply)


def plain_stream(n=12):
    t = [StreamTask(id=f"p{i}", prompt="Compute 17 * 23 + 5.", family="calc", split="practice", phase="pre",
                    order=i, rubric=NUM) for i in range(1, n + 1)]
    t += [StreamTask(id=f"hp{i}", prompt=f"Compute 23 * 17 + {i}.", family="calc", split="heldout", phase="post",
                     rubric=NUM) for i in (1, 2)]
    t += [StreamTask(id="hq1", prompt="Compute 5 + 17 * 23.", family="calc", split="heldout", phase="pre", rubric=NUM)]
    return Stream(name="fx", tasks=t, shifts=[])


def test_defaults_and_when_a_replay_is_due():
    assert retention_cfg() == {"every": 12, "prune": "end"}
    recs = [type("R", (), {"family": f})() for f in ["calc"] * 12 + ["research"] * 5]
    assert retention_due(recs, "calc", 12) == 12 and retention_due(recs, "research", 12) is None
    assert retention_due(recs, "calc", 0) is None and retention_due(recs[:11], "calc", 12) is None


def test_a_retention_drop_beyond_noise_is_an_alarm(tmp_path):
    st = store_with(tmp_path, RULE)
    row = retention_check(plain_stream(), "calc", st, HurtsOldTasks(), tmp_path, 2, 0.06, 12)
    assert row["alarm"] and row["reference_mean"] > row["mean"] and row["recipe_version"] == 2
    seed_only = RecipeStore(tmp_path / "seed")
    seed_only.ensure_seed("calc")
    assert retention_check(plain_stream(), "calc", seed_only, HurtsOldTasks(), tmp_path, 2, 0.06, 12)["skipped"]


def test_the_loop_raises_a_retention_alarm_at_once(tmp_path, gate_v2):
    store_with(tmp_path, RULE)
    archs = []
    remove = json.dumps({"edit": {"op": "remove_planner_rule", "params": {"id": "L1"}},
                         "rationale": "The rule hurts the old tasks.", "predicted_delta": 0.2})

    def llm_for(hid):
        archs.append(hid)
        return MockLLMClient(script={"architect": [remove]})
    s = run_loop(plain_stream(), HurtsOldTasks(), tmp_path, llm_for, repeats=2, parallel_until=12, log=lambda m: None,
                 prune="off")
    [ret] = s["retention"]
    assert ret["alarm"] and ret["count"] == 12 and ret["order"] == 12
    diag = json.loads((tmp_path / "diagnoses" / "o12r-calc.json").read_text())
    assert diag["cause"] == "retention" and "remove_planner_rule" in diag["allowed_edits"]
    assert "Compute" not in json.dumps(diag) and "hq1" not in json.dumps(diag)       # scores only, no held-out text
    assert archs[0] == "fx-calc-o12r-h1" and all(a.startswith("fx-calc-o12r-h") for a in archs)
    assert s["decisions"][0]["hypothesis_id"] == "fx-calc-o12r-h1"
    tried = list(archs)
    rows = [json.loads(l) for l in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert any(r["event"] == "retention" for r in rows) and any(r["event"] == "alarm" and r["data"]["kind"] ==
                                                               "retention" for r in rows)
    n = len(json.loads((tmp_path / "loop_state.json").read_text())["events"])
    run_loop(plain_stream(), HurtsOldTasks(), tmp_path, llm_for, repeats=2, parallel_until=12, log=lambda m: None,
             prune="off")                                                         # resumed: nothing again
    assert archs == tried and len(json.loads((tmp_path / "loop_state.json").read_text())["events"]) == n


def test_retention_off_runs_no_replay(tmp_path, gate_v2):
    store_with(tmp_path, RULE)
    s = run_loop(plain_stream(), HurtsOldTasks(), tmp_path, lambda h: MockLLMClient(), repeats=2, parallel_until=12,
                 log=lambda m: None, retention_every=0, prune="off")
    assert s["retention"] == [] and s["decisions"] == []


def test_remove_line_for_every_kind():
    r = seed_recipe("calc")
    r = apply_edit(r, RULE)
    r = apply_edit(r, Edit(op="add_verify_step", params={"select": {"kind": "work", "last_work_step": True}}))
    r = apply_edit(r, Edit(op="set_run_option", params={"name": "max_turns", "value": 6}))
    assert r.line_keys() == ["L1", "T1", "run_options.max_turns"]
    for k in r.line_keys():
        b = remove_line(r, k, "p")
        assert k not in b.line_keys() and k not in b.provenance and b.version == r.version + 1 and b.created_by == "prune"
    with pytest.raises(ValueError):
        remove_line(r, "L9")


def test_pruning_drops_a_dead_line_and_keeps_a_useful_one(tmp_path):
    # held-out tasks that do not need the Assumptions section: the rule only costs tokens -> pruned
    st = store_with(tmp_path / "a", RULE, Edit(op="set_run_option", params={"name": "max_turns", "value": 6}))
    led = Ledger(tmp_path / "a" / "ledger.jsonl")
    rows = prune_family(plain_stream(), "calc", st, led, Runs(), tmp_path / "a", 2, 0.06, log=lambda m: None)
    by = {r["line"]: r for r in rows}
    assert by["L1"]["decision"] == "accept" and by["L1"]["cost_B"] < by["L1"]["cost_A"]
    assert by["L1"]["line_provenance"]["hypothesis_id"] == "h1"
    assert by["run_options.max_turns"]["decision"] == "reject"                   # no cost saved
    assert st.current("calc").line_keys() == ["run_options.max_turns"]
    assert led.hypotheses_used("calc") == 0 and led.tried_since_accept("calc") == 0 and led.failed("calc") == []
    n = len(led.rows())
    prune_family(plain_stream(), "calc", st, led, Runs(), tmp_path / "a", 2, 0.06, log=lambda m: None)
    assert len(led.rows()) == n                                                   # resumable: decided lines stay
    # D89's held-out tasks need the section: removing the rule loses score -> kept
    st2 = store_with(tmp_path / "b", RULE)
    led2 = Ledger(tmp_path / "b" / "ledger.jsonl")
    [row] = prune_family(d89_stream(), "calc", st2, led2, Runs(), tmp_path / "b", 2, 0.06, log=lambda m: None)
    assert row["decision"] == "reject" and row["reasons"][0].startswith("score falls without the line")
    assert row["prune"] is True and st2.current("calc").line_keys() == ["L1"]


def test_the_loop_prunes_at_the_end_of_a_stream(tmp_path, gate_v2):
    store_with(tmp_path, RULE)
    s = run_loop(plain_stream(11), Runs(), tmp_path, lambda h: MockLLMClient(), repeats=2, parallel_until=11,
                 log=lambda m: None)
    assert [p["line"] for p in s["prunes"]] == ["L1"] and s["prunes"][0]["decision"] == "accept"
    assert RecipeStore(tmp_path / "recipes").current("calc").is_empty()
    assert any(r["event"] == "prune" for r in map(json.loads, (tmp_path / "events.jsonl").read_text().splitlines()))
