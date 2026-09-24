"""D26 — every fenced block of a section is read (AutoAgents keeps only the first, common.py:53)."""
from amoeba.task.draft import draft_team
from amoeba.task.parsers import parse_json_objects, parse_sections
from tests.conftest import fx, mock

REAL = fx("draft_roles_in_separate_fences")   # gemini-3.5-flash d19, clickstream-pipeline #0: 4 roles, 4 ```json blocks


def names(sec):
    return [b["name"] for b in parse_json_objects(sec["Created Roles List"])]


def test_the_original_rule_loses_roles_2_to_n():
    assert len(names(parse_sections(REAL))) == 1


def test_all_fences_keeps_every_role_in_order():
    assert names(parse_sections(REAL, all_fences=True)) == \
        ["Data_Architect", "Data_Engineer", "Site_Reliability_Engineer", "Language_Expert"]


def test_single_fence_sections_are_unchanged():
    text = "## A:\n```json\n{\"x\": 1}\n```\n## B\nplain\n"
    assert parse_sections(text, all_fences=True) == parse_sections(text) == {"A": '{"x": 1}\n', "B": "plain"}


def test_d19_draft_of_that_reply_is_accepted_now(task, envelope, trace):
    d = draft_team(task, mock(planner=[REAL]), envelope, trace)
    assert len(d.created_roles) == 4 and d.rounds[0].roles[3]["name"] == "Language_Expert"
