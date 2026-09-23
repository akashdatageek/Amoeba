"""D24 step 2 — role/step/draft fields, parse_plan_d24, D22 brace-balanced roles, D23 '---' fence, Verdict."""
from amoeba.task.draft import draft_team
from amoeba.task.models import DraftedRole
from amoeba.task.parsers import (parse_bullets, parse_plan, parse_plan_d24, parse_requirements, parse_sections,
                                 parse_verdict)
from tests.conftest import fx, mock

FULL = fx("draft_d24_full")


def test_parse_plan_d24_keeps_the_indented_lines_and_the_first_line_of_parse_plan():
    steps = parse_plan_d24(parse_sections(FULL)["Execution Plan"])
    assert [(n, t) for n, t, _ in steps] == parse_plan(parse_sections(FULL)["Execution Plan"])   # names unchanged
    names, first, f = steps[0]
    assert names == ["Cost Analyst"] and f["title"] == "Price both databases"
    assert f["covers"] == ["R1", "R2"] and f["depends_on"] == []
    assert f["do"] == "1) search current pricing\n2) compute 10 TB storage and peak compute"   # continuation kept
    assert f["output"] == "cost table (markdown)" and f["done_when"] == "every cell sourced"
    assert steps[2][2]["depends_on"] == [1, 2] and steps[2][0] == ["Schema Engineer", "Cost Analyst"]


def test_requirements_givens_risks():
    sec = parse_sections(FULL)
    assert parse_requirements(sec["Requirements"]) == {
        "R1": "gather current benchmark results for PostgreSQL and MongoDB",
        "R2": "estimate the monthly cost for 50 tenants at 200 GB each",
        "R3": "prototype and test the event schema in both databases",
        "R4": "deliver a recommendation memo with a risk table"}
    assert parse_bullets(sec["Givens and Assumptions"])[1] == "derived: 50 x 200 GB = 10,000 GB = 10 TB"
    assert len(parse_bullets(sec["Risks and Decisions"])) == 2 and parse_bullets("None\n...\n") == []


def test_d23_fence_is_not_a_section_and_not_part_of_the_last_one():
    sec = parse_sections(FULL)
    assert "---" not in sec and sec["PlanFeedback"] == "None."
    assert parse_sections("---\n## Action\nFinal Output\n\n## ActionInput\nEPOLEVNE\n---")["ActionInput"] == "EPOLEVNE"


def test_verdict():
    v = lambda t: parse_verdict(parse_sections(t))
    assert v(fx("observer_d24_approve")) == "APPROVE" and v(fx("observer_d24_revise")) == "REVISE"
    assert v("## Suggestions\nNone\n## Verdict\n**APPROVE**.") == "APPROVE"
    assert v("## Suggestions\nNone\n## Verdict\nAPPROVE with minor changes") == "OTHER"
    assert v("## Suggestions\nNone\n") is None


def test_drafted_role_keeps_the_d24_record():
    r = DraftedRole(name="X", skills="one skill", outputs={"artifact": "a", "format": "f"}, covers=None,
                    success_criteria=["ok"], goal=None)
    assert r.skills == ["one skill"] and r.outputs == [{"artifact": "a", "format": "f"}] and r.covers == [] and r.goal == ""


def test_d24_draft_keeps_every_field(task, envelope, trace):
    llm = mock(planner=[FULL], agent_observer=[fx("observer_d24_approve")], plan_observer=[fx("observer_d24_approve")])
    d = draft_team(task, llm, envelope, trace, prompts="d24")
    assert [r.name for r in d.created_roles] == ["Cost Analyst", "Schema Engineer", "Memo Writer"]   # D22: nested + {x}
    cost = d.created_roles[0]
    assert cost.outputs == [{"artifact": "cost table", "format": "markdown table: provider x db x monthly USD"}]
    assert cost.skills == ["TCO modelling", "managed-database pricing"] and cost.covers == ["R1", "R2"]
    assert cost.tools == ["calc"] and cost.missing_tools == ["web_search"] and "{provider}" in cost.prompt
    assert d.created_roles[2].is_summariser
    assert [s.depends_on for s in d.plan] == [[], [], [1, 2], [3]] and d.plan[1].done_when.startswith("p95")
    assert list(d.requirements) == ["R1", "R2", "R3", "R4"] and len(d.givens) == 3 and len(d.risks) == 2
    assert {q.name for q in d.capability_requests} == {"web_search", "database_sandbox"}
    assert d.rounds[0].plan[2]["depends_on"] == [1, 2]      # the per-round record keeps the detail too


def test_d22_applies_to_d19_as_well(task, envelope, trace):
    braces = fx("draft_round_ok").replace('"You are a Calculator.', '"You are a Calculator. Evaluate {expression}.')
    d = draft_team(task, mock(planner=[braces]), envelope, trace)
    assert [r.name for r in d.created_roles] == ["Calculator", "Writer"]


def test_capability_request_without_the_d19_keys_is_kept():
    from amoeba.task.draft import parse_capability_requests
    [q] = parse_capability_requests('[{"request": "Database Sandbox Environment", "reason": "to run benchmarks"}]')
    assert (q.name, q.what_it_does, q.source) == ("Database Sandbox Environment", "to run benchmarks", "planner")


def test_d24_prompt_names_the_request_keys():
    from amoeba.config.prompts import PROMPT
    assert "request as a JSON\n   blob with keys: name, kind (tool|skill), for_role" in PROMPT.d24_create_team
