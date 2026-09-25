"""D53 — the Planner's optional "## Open Questions" (ambiguities settled by assumption) and run_task --interactive."""
import json

import pytest

from amoeba.config.prompts import PROMPT
from amoeba.task.draft import draft_team
from amoeba.task.models import Task
from amoeba.task.parsers import parse_open_questions
from scripts.run_task import ask_user, intake_text, parse_args, run_one
from tests.conftest import DB_PROMPT, fx, mock

FULL = fx("draft_d24_full")
APPROVE = fx("observer_d24_approve")
OPEN = FULL.replace("## Selected Roles List:", "## Open Questions:\n"
                    "- question: is the 200 GB per tenant compressed? | assumption: uncompressed\n"
                    "- Which cloud region?\n  assumption: eu-west-1\n\n## Selected Roles List:")


def test_parse_open_questions():
    assert parse_open_questions("- question: A? | assumption: x\n- Q: B?\n  assumption: y\n- C?") == [
        {"question": "A?", "assumption": "x"}, {"question": "B?", "assumption": "y"}, {"question": "C?", "assumption": ""}]
    assert parse_open_questions("None") == [] and parse_open_questions("") == []
    assert parse_open_questions("- question: ... | assumption: ...   (optional; None if nothing was ambiguous)") == []


def test_planner_is_asked_for_it_and_it_is_optional(envelope, trace):
    assert "## Open Questions:" in PROMPT.d24_create_team_format and '"## Open Questions"' in PROMPT.d24_create_team
    d = draft_team(Task(prompt=DB_PROMPT), mock(planner=[FULL], agent_observer=[APPROVE], plan_observer=[APPROVE]),
                   envelope, trace, prompts="d24")
    assert d.consensus and d.open_questions == []                          # no section: no repair call, nothing stored
    d = draft_team(Task(prompt=DB_PROMPT), mock(planner=[OPEN], agent_observer=[APPROVE], plan_observer=[APPROVE]),
                   envelope, trace, prompts="d24")
    assert d.open_questions == [{"question": "is the 200 GB per tenant compressed?", "assumption": "uncompressed"},
                                {"question": "Which cloud region?", "assumption": "eu-west-1"}]


def test_intake_text_shows_requirements_assumptions_and_questions(envelope, trace):
    d = draft_team(Task(prompt=DB_PROMPT), mock(planner=[OPEN], agent_observer=[APPROVE], plan_observer=[APPROVE]),
                   envelope, trace, prompts="d24")
    text = intake_text(d)
    assert "  R3: prototype and test the event schema in both databases" in text
    assert "  - assumption: 30% yearly data growth" in text and "given: 50 tenants" not in text
    assert "  Q2. Which cloud region?\n      assumed: eu-west-1" in text


def test_ask_user_waits_for_continue_or_an_edit():
    replies = iter(["", "  ", "Continue"])
    assert ask_user(lambda _: next(replies)) is None
    replies = iter(["", "the data is compressed 4:1"])
    assert ask_user(lambda _: next(replies)) == "the data is compressed 4:1"

    def eof(_):
        raise EOFError
    assert ask_user(eof) is None


def run(tmp_path, envelope, tools, ask, planners):
    llm = mock(planner=planners, agent_observer=[APPROVE] * 4, plan_observer=[APPROVE] * 4,
               worker=[fx("worker_final_output")])
    return llm, run_one(Task(id="db", prompt=DB_PROMPT), "flat", llm, envelope, tools, tmp_path,
                        draft_prompts="d24", ask=ask)


def test_continue_runs_the_draft_as_it_is(tmp_path, envelope, tools, capsys):
    llm, r = run(tmp_path, envelope, tools, lambda _: "continue", [OPEN])
    assert len(llm.calls_of("planner")) == 1 and r.clarification is None and r.error is None
    assert "Open questions (settled by assumption):" in capsys.readouterr().out
    ev = [json.loads(l) for l in (tmp_path / r.run_id / "trace.jsonl").read_text().splitlines()]
    assert [e["amoeba.redraft"] for e in ev if e["name"] == "intake_review"] == [False]


def test_an_edit_is_appended_and_drafted_once_more(tmp_path, envelope, tools):
    llm, r = run(tmp_path, envelope, tools, lambda _: "the data is compressed 4:1", [OPEN, FULL])
    first, second = llm.calls_of("planner")
    assert "User clarification" not in first["messages"][1]["content"]
    user = second["messages"][1]["content"]
    assert DB_PROMPT + "\n\nUser clarification: the data is compressed 4:1" in user
    assert "is the 200 GB per tenant compressed?" in user                  # the previous draft, as history
    assert len(llm.calls_of("planner")) == 2 and r.clarification == "the data is compressed 4:1"
    saved = json.loads((tmp_path / r.run_id / "result.json").read_text())
    assert saved["clarification"] == "the data is compressed 4:1" and saved["draft_rounds"] == 1
    assert json.loads((tmp_path / r.run_id / "plan.first.json").read_text())["open_questions"][0]["assumption"] == "uncompressed"
    assert json.loads((tmp_path / r.run_id / "plan.json").read_text())["open_questions"] == []


def test_off_by_default_and_never_with_saved_drafts():
    assert parse_args(["--toy"]).interactive is False
    with pytest.raises(SystemExit):
        parse_args(["--toy", "--interactive", "--drafts-from", "runs"])


def test_eval_scripts_have_no_interactive_flag():
    from scripts.eval_draft import main
    with pytest.raises(SystemExit):
        main(["--tasks", "x.jsonl", "--interactive"])
