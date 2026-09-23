"""T3 — parsers vs the original regexes (environment.py:60-84, output_parser.py:541-561)."""
import json
import re

import pytest

from amoeba.task.parsers import ParseError, parse_critic, parse_plan, parse_role_blobs, parse_sections
from tests.conftest import fx


# --- the originals, transcribed line for line (MIT) so the comparison is against the real behaviour --------
def original_parser_roles(text):                                  # environment.py:60-73
    agents_args = []
    for agent in re.findall(r"{[\s\S]*?}", text):
        agent = json.loads(agent.strip())
        if len(agent.keys()) > 0:
            agents_args.append(agent)
    return agents_args


def original_parser_plan(context):                                # environment.py:75-84
    plan_context = re.findall(r"## Execution Plan([\s\S]*?)##", str(context))[0]
    steps = [v.split("\n")[0] for v in re.split(r"\n\d+\. ", plan_context)[1:]]
    steps.insert(0, "")
    return steps


def test_parsers_reproduce_environment_py_on_manager_output():
    raw = fx("manager_output_real")
    sec = parse_sections(raw)
    # a real gemini-3.1-flash-lite Planner reply (see tests/fixtures/README.md); it wraps the whole answer in '---'
    # lines copied from the FORMAT_EXAMPLE and adds the D19 Capability Requests section
    assert set(sec) >= {"Thought", "Question or Task", "Selected Roles List", "Created Roles List",
                        "Execution Plan", "Capability Requests", "RoleFeedback", "PlanFeedback"}
    # roles: original scans the whole text; ours the Created section — identical here (Selected is 'None')
    assert parse_role_blobs(sec["Created Roles List"]) == original_parser_roles(raw)
    assert [r["name"] for r in parse_role_blobs(sec["Created Roles List"])] == ["StringManipulator", "LanguageExpert"]
    # plan: original keeps a leading '' sentinel; ours does not, and adds the parsed bracket
    ours = parse_plan(sec["Execution Plan"])
    assert [text for _, text in ours] == original_parser_plan(raw)[1:]
    assert [names for names, _ in ours] == [["StringManipulator"], ["LanguageExpert"]]


def test_parse_sections_strips_colon_and_first_fence():
    sec = parse_sections("## A:\n```json\n{\"x\": 1}\n```\n## B\nplain\n")
    assert sec == {"A": '{"x": 1}\n', "B": "plain"}


def test_parse_role_blobs_skips_bad_json_where_original_crashes():
    text = '{"name": "Bad",}\n{"name": "Good", "tools": []}'
    with pytest.raises(json.JSONDecodeError):
        original_parser_roles(text)
    assert parse_role_blobs(text) == [{"name": "Good", "tools": []}]


def test_parse_critic_cases():
    assert parse_critic("Action: Agree.") == (True, "")
    assert parse_critic(fx("critic_agree_with_period")) == (True, "")
    assert parse_critic("Action: Disagree\nAction Input: x\ny") == (False, "x\ny")
    assert parse_critic("Action: Disagree\n") == (False, "I think it is not correct. Please think carefully and improve it.")
    with pytest.raises(ParseError):
        parse_critic("Thought: ..\nAction: Agree")
    with pytest.raises(ParseError):
        parse_critic("action: agree")
