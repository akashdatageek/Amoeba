"""D29 — capability request names normalised through amoeba/capabilities/aliases.yaml."""
import json

from amoeba.capabilities import normalise, snake
from amoeba.task.draft import parse_capability_requests, request_survival
from amoeba.task.models import CapabilityRequest, Task
from scripts.eval_draft import attempt, summarise
from scripts.run_task import run_one
from tests.conftest import fx, mock


def test_the_four_names_are_one_capability():
    assert {normalise(n) for n in ("Web Search", "web_search", "Web Research", "Market Research Tool")} == \
        {("web_search", True)}
    assert snake("AWS Simple Monthly Calculator / Pricing API") == "aws_simple_monthly_calculator_pricing_api"
    assert normalise("AWS Simple Monthly Calculator / Pricing API") == ("pricing_api", True)


def test_starting_canonicals_exist():
    for c in ("web_search", "code_execution", "database_sandbox", "pricing_api", "spreadsheet", "load_testing",
              "trade_database"):
        assert normalise(c) == (c, True)


def test_unknown_names_are_kept_as_written_and_unmapped():
    assert normalise("UL 2849 Standard Directory") == ("UL 2849 Standard Directory", False)


def test_request_keeps_raw_and_canonical_names():
    [q] = parse_capability_requests('{"name": "Web Research", "kind": "tool", "for_role": "Analyst"}')
    assert (q.name, q.canonical, q.mapped) == ("Web Research", "web_search", True)
    assert q.model_dump()["name"] == "Web Research" and q.model_dump()["canonical"] == "web_search"


def test_survival_compares_canonical_names():
    first = [CapabilityRequest(name="Web Search"), CapabilityRequest(name="Docker")]
    final = [CapabilityRequest(name="web_research")]
    assert request_survival(first, final) == (2, 1)     # web search kept under another name; Docker dropped


def test_reports_list_canonical_counts_and_unmapped(tmp_path, task, envelope, tools):
    text = fx("draft_capability_requests").replace('"name": "unit_conversion"', '"name": "Unit Conversion Skill"')
    row = attempt(task, 0, mock(planner=[text]), envelope, tmp_path, 0)
    assert row["canonical_names"] == ["Unit Conversion Skill", "web_search"]
    assert row["unmapped_names"] == ["Unit Conversion Skill"]
    s = summarise([row])[-1]
    assert s["canonical_counts"] == "Unit Conversion Skill:1 web_search:1" and s["unmapped_names"] == "Unit Conversion Skill"
    r = run_one(Task(prompt="Compute 17 * 23 + 5.", ground_truth="396"), "flat",
                mock(planner=[text], worker=[fx("worker_final_output")]), envelope, tools, tmp_path / "r")
    saved = json.loads((tmp_path / "r" / r.run_id / "capability_requests.json").read_text())
    assert {(q["name"], q["canonical"], q["mapped"]) for q in saved} == {
        ("web_search", "web_search", True), ("Unit Conversion Skill", "Unit Conversion Skill", False)}
    assert r.unmapped_capabilities == ["Unit Conversion Skill"]
