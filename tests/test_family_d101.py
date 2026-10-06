"""D101 — the task family of a free-text task (offline, mock LLM): keyword rules first; only when no rule decides,
one routed call (role family_classifier) choosing from the list or "new", checked by code; result.json records the
family and how it was chosen (D117: nothing else follows from it); the baselines and tasks that already have a family
are untouched."""
import json

from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.trace import TraceWriter, TracedLLM
from amoeba.llm.client import MockLLMClient
from amoeba.safety.envelope import Envelope
from amoeba.task.interpret import classify_family, family_by_rule, load_families
from amoeba.task.models import Task
from amoeba.tools.registry import default_registry
from scripts.run_task import family_classify_on, parse_args, run_one


FAM = load_families()


def traced(tmp_path, reply):
    m = MockLLMClient(script={"family_classifier": [reply]})
    return m, TracedLLM(m, TraceWriter(tmp_path / "t.jsonl", episode_id="f"))


def test_the_families_file_and_the_rules():
    assert set(FAM) >= {"calc", "research", "document", "code"}
    assert family_by_rule("Calculate the monthly payment on a 30-year loan.", FAM)[0] == "calc"
    assert family_by_rule("Make a slide deck from this spreadsheet.", FAM)[0] == "document"
    assert family_by_rule("Tell me a story about a dragon.", FAM) == (None, [])
    assert family_by_rule("Compute the total and find sources.", FAM)[0] is None             # a tie decides nothing


def test_a_rule_decides_without_a_model_call(tmp_path):
    m, t = traced(tmp_path, '{"family": "research"}')
    out = classify_family("What is the total cost of 3 items at $4 each?", t, FAM)
    assert out["family"] == "calc" and out["how"] == "rule" and "total" in out["keywords"] and m.calls == []


def test_one_routed_call_only_when_no_rule_matches_and_code_checks_it(tmp_path):
    m, t = traced(tmp_path, 'Sure: {"family": "research", "why": "facts"}')
    out = classify_family("Tell me about the dragons of Komodo.", t, FAM)
    assert out == {"family": "research", "how": "llm", "keywords": []} and len(m.calls) == 1
    assert m.calls[0]["kind"] == "family_classifier"
    route = [json.loads(l) for l in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert any(e.get("amoeba.agent") == "family_classifier" or "family_classifier" in json.dumps(e) for e in route)
    for bad in ('{"family": "poetry"}', "no json at all"):
        _, t2 = traced(tmp_path, bad)
        assert classify_family("Tell me about the dragons of Komodo.", t2, FAM)["family"] == "new"
    _, t3 = traced(tmp_path, '{"family": "new"}')
    assert classify_family("Tell me about the dragons of Komodo.", t3, FAM)["how"] == "llm"


def test_defaults_on_for_amoeba_off_for_the_baselines():
    assert parse_args(["x"]).family_classify == "auto"
    assert family_classify_on("auto", "plan") and not family_classify_on("auto", "flat")
    assert not family_classify_on("auto", "boss_reviewers") and family_classify_on("on", "flat")


def run(tmp_path, name, task, **kw):
    from tests.conftest import mock
    from tests.test_plan_runner import APPROVE, DIAMOND, finish
    m = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=finish,
             family_classifier=['{"family": "new", "why": "no family fits"}'])
    r = run_one(task, "plan", m, Envelope.from_registry(default_registry()), default_registry(), tmp_path / name,
                draft_prompts="d24", plan_options=PlanOptions(), **kw)
    return m, r, json.loads((tmp_path / name / r.run_id / "result.json").read_text())


def test_the_family_is_recorded_and_changes_nothing_else(tmp_path):
    """D117: no recipe follows from the family any more; it is recorded in result.json only."""
    task = Task(id="free-1", prompt="Compute 17 * 23 + 5.")
    assert task.family == "freeform"
    m, r, res = run(tmp_path, "rule", task, family_classify=True)
    assert res["family"]["family"] == "calc" and res["family"]["how"] == "rule" and "recipe_version" not in res["family"]
    assert res.get("recipe") is None and "Lessons for this kind of task" not in m.calls_of("planner")[0]["messages"][-1]["content"]
    _, _, off = run(tmp_path, "off", task, family_classify=False)
    assert off.get("family") is None
    m, r, res = run(tmp_path, "new", Task(id="free-2", prompt="Tell me a story about a dragon."), family_classify=True)
    assert res["family"]["family"] == "new" and res["family"]["how"] == "llm" and len(m.calls_of("family_classifier")) == 1
    _, _, given = run(tmp_path, "given", Task(id="g", prompt="Compute 2 + 2.", family="calc"), family_classify=True)
    assert given.get("family") is None                                                    # the source named it
