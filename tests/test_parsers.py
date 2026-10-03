"""D72 — Box 2 section parsing (amoeba/task/parsers.py)."""
import json

from amoeba.task.parsers import parse_json_objects, parse_sections


def test_a_heading_inside_a_json_string_does_not_split_the_roles_block():
    """D72 (bench5b loan draft): a role prompt with 'Output format:\\n## Formula' cut the Created Roles List at
    '##' (common.py:33 splits on every '##'), so all three roles were lost and the draft failed as an empty plan."""
    role = {"name": "Analyst", "prompt": "Work it out.\n\nOutput format:\n## Formula\n[F]\n## Result\n$[A]"}
    text = ("## Thought\nok\n\n## Created Roles List:\n```\n[\n" + json.dumps(role) + ",\n"
            + json.dumps({"name": "Writer", "prompt": "Assemble.\n## Answer"}) + "\n]\n```\n\n## Execution Plan:\n"
            "1. [Analyst]: do it\n")
    s = parse_sections(text)
    assert list(s) == ["Thought", "Created Roles List", "Execution Plan"]
    assert [r["name"] for r in parse_json_objects(s["Created Roles List"])] == ["Analyst", "Writer"]
    assert parse_json_objects(s["Created Roles List"])[0]["prompt"].endswith("## Result\n$[A]")


def test_d84a_a_hash_heading_mid_line_is_text():
    """The m1 hand check: the lesson "end with a section headed '## Assumptions'" echoed inside a role's JSON cut
    the Created Roles List apart and the summariser role was lost; only a '##' that starts a line (or follows a
    closing tag, as in Gemma's "</thought>## Thought") is a section break."""
    from amoeba.task.parsers import parse_sections
    raw = ("<thought>plan it</thought>## Thought\nWe end with a section headed '## Assumptions'.\n\n"
           "## Created Roles List:\n```\n[{\"name\": \"Summariser\", \"prompt\": \"End with '## Assumptions'.\"}]\n```\n"
           "  ## Execution Plan:\n1. [Summariser]: write it\n")
    sec = parse_sections(raw, all_fences=True)
    assert list(sec)[1:] == ["Thought", "Created Roles List", "Execution Plan"]
    assert "'## Assumptions'" in sec["Thought"] and "Summariser" in sec["Created Roles List"]
    assert sec["Created Roles List"].strip().endswith("}]")
