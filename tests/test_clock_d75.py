"""D75 — every Box 3 step prompt gets today's date, weekday and time zone (the plan runner through its templates, the
baselines on the task text, so their papers' prompts stay as they are), and the plan step prompt carries general
research rules. Offline, with the mock LLM."""
import re
from datetime import date, datetime, timezone

import pytest

from amoeba.config.prompts import PROMPT
from amoeba.interp.clock import run_clock
from amoeba.interp.runtime import Interpreter
from amoeba.task.models import Task
from scripts.run_task import parse_args
from tests.conftest import fx, mock
from tests.test_plan_runner import finish, plan_team

MONDAY = date(2026, 9, 28)
LINE = "Today is Monday, 28 September 2026 (time zone of this run: America/Chicago)"


def test_the_clock_line_names_the_date_weekday_and_zone():
    c = run_clock("America/Chicago", MONDAY)
    assert (c["weekday"], c["tz"]) == ("Monday", "America/Chicago") and c["line"].startswith(LINE)
    late = run_clock("America/Chicago", now=datetime(2026, 9, 29, 2, 0, tzinfo=timezone.utc))   # 21:00 in Chicago
    assert late["date"] == MONDAY
    with pytest.raises(ValueError, match="unknown time zone"):
        run_clock("Mars/Olympus")


def test_a_today_question_gets_the_date_in_every_plan_step_prompt(envelope, trace, tools, tmp_path):
    task = Task(id="t", prompt="Is the BMV open in Hammond, Indiana today?")
    llm, cfg = plan_team(task, envelope, trace, plan_worker=finish)
    Interpreter(llm, tools, trace, run_dir=tmp_path, today=MONDAY, timezone="America/Chicago").run(cfg, task, seed=0)
    prompts = [c["messages"][-1]["content"] for c in llm.calls_of("plan_worker") + llm.calls_of("plan_summariser")]
    assert prompts and all(LINE in p for p in prompts)
    assert trace.events("run_clock")[0]["amoeba.weekday"] == "Monday"


@pytest.mark.parametrize("topology", ["flat", "boss_reviewers"])
def test_the_baselines_see_the_date_on_the_task_text(topology, envelope, trace, tools, tmp_path):
    from amoeba.task.draft import draft_team
    from amoeba.task.instantiate import instantiate
    task = Task(id="t", prompt="Is the BMV open in Hammond, Indiana today?")
    llm = mock(planner=[fx("draft_round_ok")], worker=[fx("worker_final_output")] * 12,
               solver=[fx("worker_final_output")] * 12, critic=["Agree"] * 24)
    cfg = instantiate(draft_team(task, llm, envelope, trace), topology, task, envelope)
    Interpreter(llm, tools, trace, run_dir=tmp_path, today=MONDAY, timezone="America/Chicago").run(cfg, task, seed=0)
    box3 = [c for c in llm.calls if c.get("kind") not in ("planner", "agent_observer", "plan_observer")]
    assert box3 and all(LINE in "\n".join(m["content"] for m in c["messages"]) for c in box3)


def test_research_rules_are_general_and_the_cli_takes_a_zone():
    text = PROMPT.plan_step
    assert "specific thing the task asks about" in text and "Never infer a specific fact from a general page" in text
    assert "If sources disagree, say so" in text and "${today}" in text
    for name in ("plan_step", "plan_summarise", "plan_replan", "plan_critique"):
        body = getattr(PROMPT, name)
        assert "${today}" in body
        assert not re.search(r"(?i)\b(bmv|hammond|indiana|diesel|maersk)\b", body)      # no task-specific wording
    assert parse_args(["--toy", "--timezone", "America/Chicago"]).timezone == "America/Chicago"
