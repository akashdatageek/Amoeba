"""D117 keeps the single-edit proposal format and its checks (from D87): one strict JSON object with one typed edit;
plain code checks it is allowed for the cause, the edited recipe passes V1-V6, and it is not a repeat."""
import json

import pytest
from pydantic import ValidationError

from amoeba.adapt.architect import allowed_text, check, parse_reply
from amoeba.adapt.recipe import Recipe

REPLY = {"edit": {"op": "add_role_rule", "params": {"select": {"last_work_step": True},
                                                   "text": "End with a section headed Assumptions."}},
         "rationale": "the answer step left out the assumptions", "predicted_delta": 0.1}


def test_a_valid_reply_parses_and_passes():
    r = parse_reply("<thought>x</thought>\n```json\n" + json.dumps(REPLY) + "\n```")
    assert r.edit.op == "add_role_rule"
    assert check(r, ["add_role_rule", "tighten_done_when"], Recipe(family="calc"), []) == []


def test_a_disallowed_edit_and_a_repeat_are_refused():
    r = parse_reply(json.dumps(REPLY))
    assert any("not allowed" in p for p in check(r, ["grant_tool"], Recipe(family="calc"), []))
    assert any("already tried" in p for p in check(r, ["add_role_rule"], Recipe(family="calc"), [{"edit": REPLY["edit"]}]))


def test_a_rule_that_tells_the_team_to_skip_checks_fails_validation():
    bad = {**REPLY, "edit": {"op": "add_role_rule", "params": {"select": {"last_work_step": True},
                                                                "text": "Skip the verification."}}}
    assert any(p.startswith("V4") for p in check(parse_reply(json.dumps(bad)), ["add_role_rule"],
                                                 Recipe(family="calc"), []))


def test_strict_format():
    with pytest.raises(ValueError):
        parse_reply("no json here")
    with pytest.raises(ValidationError):
        parse_reply(json.dumps({**REPLY, "predicted_delta": 3}))
    with pytest.raises(ValidationError):
        parse_reply(json.dumps({**REPLY, "surprise": 1}))
    assert "add_role_rule: params" in allowed_text(["add_role_rule"]) and "SELECTOR =" in allowed_text(["add_role_rule"])
