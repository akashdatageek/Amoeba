"""D116 — never assume a reading: with --ask-assumed on, every entity the interpretation step would only assume (no
reading leads the next by 0.3, a tie included) is asked about before planning; with nobody to ask the run stops
before Box 2 with needs_clarification and writes clarification.json; --clarify answers ahead of time; off keeps D77.
Offline, with the mock LLM."""
import json

import pytest

import scripts.run_task as rt
from amoeba.task.interpret import apply_clarify, ask_all, decide, open_questions, parse_entities
from amoeba.task.models import Task, run_status
from amoeba.adapt.experimenter import experiment_flags
from scripts.run_task import parse_args, parse_clarify, run_one
from tests.conftest import fx, mock

TASK = "How to pay the P and W universities parking citation in the PNW lot?"
APPROVE = fx("observer_d24_approve")


def entities(pw, lot):
    """Two entities: "P and W" with readings at pw, and "PNW lot" with readings at lot (confidences of the top two)."""
    body = [{"entity": "P and W", "readings": [
                {"reading": "Purdue University Northwest", "why": "dictated PNW", "confidence": pw[0]},
                {"reading": "University of Washington", "why": "W", "confidence": pw[1]}]},
            {"entity": "PNW lot", "readings": [
                {"reading": "the PNW campus lot", "why": "campus", "confidence": lot[0]},
                {"reading": "a Pacific Northwest lot", "why": "region", "confidence": lot[1]}]}]
    return f"## Thought\nNames.\n\n## Entities\n```json\n{json.dumps(body)}\n```\n"


def team(reply):
    return mock(interpreter=[reply], planner=[fx("draft_d24_full")], agent_observer=[APPROVE],
                plan_observer=[APPROVE], worker=[fx("worker_final_output")])


def run(tmp_path, envelope, tools, llm, **kw):
    return run_one(Task(prompt=TASK, id="pnw"), "flat", llm, envelope, tools, tmp_path, draft_prompts="d24",
                   interpret=True, **kw)


def test_a_tie_and_a_close_call_are_both_asked_least_certain_first(tmp_path, envelope, tools):
    asked = []

    def ask(prompt):
        asked.append(prompt)
        return {1: "1", 2: "2"}.get(len(asked), "continue")
    llm = team(entities((0.5, 0.5), (0.6, 0.4)))                     # a tie (lead 0) and a lead of 0.2
    r = run(tmp_path, envelope, tools, llm, ask=ask, ask_assumed="on")
    qs = [a for a in asked if "What did you mean" in a]
    assert len(qs) == 2 and '"P and W"' in qs[0] and '"PNW lot"' in qs[1]       # the tie first
    w = {x["entity"]: x for x in r.interpretation["working"]}
    assert (w["P and W"]["reading"], w["P and W"]["settled"]) == ("Purdue University Northwest", "user")
    assert (w["PNW lot"]["reading"], w["PNW lot"]["settled"]) == ("a Pacific Northwest lot", "user")
    assert r.interpretation["opening_line"] is None and r.interpretation["ambiguous"] == []
    assert len(r.interpretation["questions"]) == 2 and r.status == "ok"
    planner = llm.calls_of("planner")[0]["messages"][-1]["content"]
    assert '"P and W" means Purdue University Northwest (the user chose this)' in planner


def test_a_dominant_reading_is_not_asked(tmp_path, envelope, tools):
    def ask(prompt):
        assert "What did you mean" not in prompt
        return "continue"
    r = run(tmp_path, envelope, tools, team(entities((0.9, 0.1), (0.8, 0.2))), ask=ask, ask_assumed="on")
    assert {w["settled"] for w in r.interpretation["working"]} == {"dominant"} and "questions" not in r.interpretation


def test_the_terminal_is_asked_without_interactive(tmp_path, envelope, tools, monkeypatch):
    monkeypatch.setattr(rt, "can_ask", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "1")
    r = run(tmp_path, envelope, tools, team(entities((0.5, 0.5), (0.9, 0.1))), ask_assumed="on")
    w = r.interpretation["working"][0]
    assert (w["reading"], w["settled"]) == ("Purdue University Northwest", "user") and r.status == "ok"


def test_with_nobody_to_ask_the_run_stops_before_planning(tmp_path, envelope, tools, monkeypatch):
    monkeypatch.setattr(rt, "can_ask", lambda: False)
    llm = team(entities((0.5, 0.5), (0.6, 0.4)))
    r = run(tmp_path, envelope, tools, llm, ask_assumed="on")
    assert r.status == "needs_clarification" and r.error.startswith("needs_clarification:")
    assert llm.calls_of("planner") == [] and r.answer is None                  # no guess, no Box 2, no Box 3
    out = json.loads(next(tmp_path.glob("*/clarification.json")).read_text())
    assert [q["entity"] for q in out["questions"]] == ["P and W", "PNW lot"]
    assert out["questions"][0]["options"][:2] == ["Purdue University Northwest", "University of Washington"]
    assert [q["entity"] for q in r.interpretation["pending"]] == ["P and W", "PNW lot"]
    trace = [json.loads(l) for l in next(tmp_path.glob("*/trace.jsonl")).read_text().splitlines()]
    assert any(t["name"] == "clarification_needed" for t in trace)


def test_clarify_answers_ahead_of_time(tmp_path, envelope, tools, monkeypatch):
    monkeypatch.setattr(rt, "can_ask", lambda: False)
    llm = team(entities((0.5, 0.5), (0.6, 0.4)))
    r = run(tmp_path, envelope, tools, llm, ask_assumed="on",
            clarify=parse_clarify(['"p and w"=2', "PNW lot=the PNW campus lot"]))
    w = {x["entity"]: x for x in r.interpretation["working"]}
    assert w["P and W"]["reading"] == "University of Washington" and w["P and W"]["settled"] == "user"
    assert w["PNW lot"]["reading"] == "the PNW campus lot" and r.status == "ok" and llm.calls_of("planner")
    assert len(r.interpretation["clarified"]) == 2


def test_a_partial_clarify_still_stops_for_the_rest(tmp_path, envelope, tools, monkeypatch):
    monkeypatch.setattr(rt, "can_ask", lambda: False)
    r = run(tmp_path, envelope, tools, team(entities((0.5, 0.5), (0.6, 0.4))), ask_assumed="on",
            clarify={"P and W": "1"})
    assert r.status == "needs_clarification" and [q["entity"] for q in r.interpretation["pending"]] == ["PNW lot"]


def test_off_keeps_the_d77_behaviour(tmp_path, envelope, tools, monkeypatch):
    monkeypatch.setattr(rt, "can_ask", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: pytest.fail("off must not ask"))
    r = run(tmp_path, envelope, tools, team(entities((0.5, 0.5), (0.9, 0.1))), ask_assumed="off")
    assert r.answer.startswith('I read "P and W" as Purdue University Northwest') and r.status == "ok"


def test_a_blank_reply_keeps_the_assumption_and_the_answer_states_it():
    interp = decide(parse_entities(entities((0.5, 0.5), (0.9, 0.1))))
    ask_all(interp, lambda prompt: "")
    assert interp["working"][0]["settled"] == "assumed" and interp["ambiguous"] == ["P and W"]
    assert open_questions(interp)[0]["entity"] == "P and W"
    apply_clarify(interp, {"P AND W": "University of Washington"})
    assert interp["working"][0]["settled"] == "user" and open_questions(interp) == []


def test_flags_status_and_the_experiment_harness():
    a = parse_args(["--tasks", "x.jsonl", "--topology", "plan"])
    assert a.ask_assumed == "on" and a.clarify is None                        # on by default from the CLI
    b = parse_args(["--tasks", "x.jsonl", "--clarify", "A=1", "--clarify", "B=two words", "--ask-assumed", "off"])
    assert parse_clarify(b.clarify) == {"A": "1", "B": "two words"} and b.ask_assumed == "off"
    with pytest.raises(ValueError):
        parse_clarify(["no equals sign"])
    assert run_status("needs_clarification: x") == "needs_clarification"
    flags = experiment_flags()                                                # nobody answers in an experiment
    assert flags[flags.index("--ask-assumed") + 1] == "off"
