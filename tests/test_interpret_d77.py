"""D77 — task understanding before planning: one call lists the readings of the task's key names and terms, plain
code takes a clear winner, asks ONE multiple-choice question (--interactive) or makes the answer open with its
assumption; the user context (--context, read-only) is read by that step. Offline, with the mock LLM."""
import json

import pytest

from amoeba.config.prompts import PROMPT
from amoeba.memory.context import load_context
from amoeba.task.interpret import decide, enforce_opening, parse_entities, route_open_questions
from amoeba.task.models import Task
from scripts.run_task import run_one
from tests.conftest import fx, mock

TASK = "How to pay the P and W universities parking citation?"
APPROVE = fx("observer_d24_approve")


def entities(pnw, wash, wisc):
    body = [{"entity": "P and W", "readings": [
        {"reading": "Purdue University Northwest (PNW)", "why": "'P and W' is how 'PNW' sounds when dictated",
         "confidence": pnw},
        {"reading": "University of Washington", "why": "'W' may be Washington", "confidence": wash},
        {"reading": "Purdue University and University of Wisconsin", "why": "two universities", "confidence": wisc}]}]
    return f"## Thought\nA name that could be dictated letters.\n\n## Entities\n```json\n{json.dumps(body)}\n```\n"


def interpreter(messages, seed):
    """Reads the user context: with PNW there, that reading dominates; without it the readings are close."""
    text = messages[-1]["content"]
    return entities(0.9, 0.05, 0.05) if "organisation: Purdue University Northwest" in text else entities(0.45, 0.3, 0.25)


def team(**extra):
    return mock(interpreter=interpreter, planner=[fx("draft_d24_full")], agent_observer=[APPROVE],
                plan_observer=[APPROVE], **extra)


def run(tmp_path, envelope, tools, llm, **kw):
    return run_one(Task(prompt=TASK, id="pnw"), "flat", llm, envelope, tools, tmp_path, draft_prompts="d24",
                   interpret=True, **kw)


def no_ask(prompt):
    raise AssertionError("the user must not be asked")


def test_the_decision_rule():
    clear = decide(parse_entities(entities(0.9, 0.05, 0.05)))
    assert clear["working"][0]["settled"] == "dominant" and clear["ambiguous"] == []
    close = decide(parse_entities(entities(0.45, 0.3, 0.25)))
    assert close["working"][0]["settled"] == "assumed" and close["ambiguous"] == ["P and W"]
    assert close["working"][0]["alternatives"] == ["University of Washington",
                                                   "Purdue University and University of Wisconsin"]
    assert decide(parse_entities("## Entities\n```json\n[]\n```")) ["working"] == []


def test_with_the_pnw_context_pnw_is_chosen_without_asking(tmp_path, envelope, tools, monkeypatch):
    ctx_file = tmp_path / "user.yaml"
    ctx_file.write_text("organization: Purdue University Northwest\nlocation: Hammond, Indiana\nshoe_size: 9\n")
    ctx = load_context(ctx_file)
    assert dict(ctx) == {"organisation": "Purdue University Northwest", "location": "Hammond, Indiana"}
    with pytest.raises(TypeError):
        ctx["role"] = "student"                                              # read-only
    llm = team(worker=[fx("worker_final_output")])
    r = run(tmp_path, envelope, tools, llm, context=ctx, ask=None)
    w = r.interpretation["working"][0]
    assert (w["reading"], w["settled"]) == ("Purdue University Northwest (PNW)", "dominant")
    assert r.interpretation["opening_line"] is None and r.interpretation["question"] is None
    assert "organisation: Purdue University Northwest" in llm.calls_of("interpreter")[0]["messages"][-1]["content"]
    planner = llm.calls_of("planner")[0]["messages"][-1]["content"]
    assert 'Working interpretation' in planner and '"P and W" means Purdue University Northwest (PNW)' in planner
    helpers = [c["messages"][-1]["content"] for c in llm.calls_of("worker")]
    assert helpers and all("Purdue University Northwest (PNW)" in h for h in helpers)     # Box 3 reads it too
    assert not r.answer.startswith("I read")


def test_without_context_and_interactive_one_question_is_asked(tmp_path, envelope, tools, capsys):
    asked = []

    def ask(prompt):
        asked.append(prompt)
        return "1" if len(asked) == 1 else "continue"                        # then the D53 intake review
    llm = team(worker=[fx("worker_final_output")])
    r = run(tmp_path, envelope, tools, llm, ask=ask)
    q = asked[0]
    assert 'What did you mean by "P and W"?' in q and "1. Purdue University Northwest (PNW)" in q
    assert "4. other (type what you meant)" in q and len([a for a in asked if "What did you mean" in a]) == 1
    w = r.interpretation["working"][0]
    assert (w["reading"], w["settled"]) == ("Purdue University Northwest (PNW)", "user")
    assert r.interpretation["opening_line"] is None


def test_without_context_non_interactive_the_answer_states_the_assumption(tmp_path, envelope, tools):
    llm = team(worker=[fx("worker_final_output")])
    r = run(tmp_path, envelope, tools, llm)
    first = r.answer.splitlines()[0]
    assert first.startswith('I read "P and W" as Purdue University Northwest (PNW); if you meant University of '
                            'Washington or Purdue University and University of Wisconsin')
    assert "## Limitations" in r.answer and '- Other reading of "P and W": University of Washington' in r.answer
    assert r.interpretation["added_by_code"]["opening_line_added"] is True
    # the helpers were told to open with it; one that did is not given a second copy
    line = r.interpretation["opening_line"]
    same, added = enforce_opening(f"{line}\n\nPay online.\n\n## Limitations\n- University of Washington; "
                                  f"Purdue University and University of Wisconsin", {"working": [
                                      {**r.interpretation["working"][0]}]})
    assert added == {"opening_line_added": False, "alternatives_added": []} and same.count("I read") == 1


def test_the_planner_cannot_settle_the_subject_by_guessing_and_the_plan_observer_checks_it():
    interp = decide(parse_entities(entities(0.9, 0.05, 0.05)))
    qs, routed = route_open_questions([
        {"question": 'Which specific universities are "P and W"?', "assumption": "Princeton and Washington"},
        {"question": "Is the citation already overdue?", "assumption": "no"}], interp)
    assert routed == ['Which specific universities are "P and W"?']
    assert qs[0]["assumption"] == 'settled before planning: "P and W" means Purdue University Northwest (PNW)'
    assert qs[1]["assumption"] == "no"
    assert "10. Interpretation" in PROMPT.d24_review_plan and "Working interpretation" in PROMPT.d24_create_team
