"""D33 — provenance: tagged, derived, given, inherited and untagged numbers; citations of unseen sources."""
import json
import re

from amoeba.interp.provenance import check_provenance, total
from amoeba.task.models import Task
from amoeba.tools.web import web_registry
from scripts.run_task import run_one
from tests.conftest import fx, mock
from tests.test_web_tools import FakeProvider

TASK = "Estimate the monthly cost for 50 tenants at 200 GB each."


def test_each_number_is_classified_line_by_line():
    text = "\n".join([
        "1. Storage costs $0.115 per GB-month [S1]",           # cited (the list marker is not a number)
        "PostgreSQL 16 is the current major version [unverified]",
        "50 tenants x 200 GB = 10,000 GB",                      # 50, 200 given; 10,000 derived
        "Peak load is 83 queries per second",                   # inherited from an input artifact
        "p95 latency was 12 ms in Step 3 for R2",              # 12 untagged; p95, Step 3, R2 are labels
        "Monthly total 1150 USD",                                # a calc result
        "Egress is $0.09 per GB [S9]",                          # S9 was never seen: hallucinated, not cited
    ])
    p = check_provenance(text, {"S1", "S2"}, TASK, inputs_text="peak 83 qps [S2]", tool_results=["1150"])
    assert {k: p[k] for k in ("cited", "unverified", "given", "derived", "inherited", "untagged")} == {
        "cited": 1, "unverified": 1, "given": 2, "derived": 2, "inherited": 1, "untagged": 2}
    assert p["hallucinated_citations"] == ["S9"] and p["untagged_examples"] == ["12", "$0.09"]
    assert p["numbers"] == 9


def test_total_sums_steps():
    a = {"cited": 2, "unverified": 1, "given": 0, "derived": 1, "inherited": 0, "untagged": 3, "numbers": 7,
         "hallucinated_citations": ["S9"]}
    assert total([a, a])["untagged"] == 6 and total([a, a])["hallucinated_citations"] == 2


def worker(messages, seed):
    user = messages[-1]["content"]
    n = re.search(r"# Your step \(step (\d+)\)", user).group(1)
    tools = (re.search(r"You can use: (.*)", user) or re.search(r"(.*)", "")).group(1)
    if n == "1" and "web_search" in tools and "[S1]" not in user:
        return "## Thought\ns\n\n## CurrentStep\ns\n\n## Action\nweb_search\n\n## ActionInput\nRDS price\n"
    body = {"1": "Storage is $0.115 per GB-month [S1]",
            "3": "Reusing step 1: $0.115 per GB-month [S1]; snippet two says 99.95% [S2]",
            "4": "Uptime 99.99% [S7]"}.get(n, "No figures here.")
    return f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\n{body}\n"


def test_plan_run_records_provenance_per_step_and_in_result_json(tmp_path, envelope):
    APPROVE = fx("observer_d24_approve")
    llm = mock(planner=[fx("draft_d24_full")], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=worker)
    r = run_one(Task(prompt=TASK), "plan", llm, envelope, web_registry(FakeProvider()), tmp_path,
                draft_prompts="d24")
    saved = json.loads((tmp_path / r.run_id / "result.json").read_text())
    steps = saved["provenance"]["steps"]
    assert steps["1"]["cited"] == 1 and steps["1"]["hallucinated_citations"] == []
    # step 3 has two helpers writing the same line: 2 x 2 cited numbers; S1/S2 reach step 3 through step 1
    assert steps["3"]["cited"] == 4 and steps["3"]["hallucinated_citations"] == []
    assert steps["4"]["hallucinated_citations"] == ["S7"]
    assert saved["provenance"]["total"]["hallucinated_citations"] == 1
    meta = json.loads((tmp_path / r.run_id / "artifacts" / "step_3.json").read_text())
    assert meta["visible_source_ids"] == ["S1", "S2", "S3"] and meta["sources"] == []
    prompt = llm.calls_of("plan_worker")[0]["messages"][-1]["content"]
    assert "[unverified] when it comes from your own knowledge" in prompt


def test_flat_result_has_no_provenance(tmp_path, envelope, tools):
    llm = mock(planner=[fx("draft_round_ok")], worker=[fx("worker_final_output")])
    r = run_one(Task(prompt="Compute 17 * 23 + 5.", ground_truth="396"), "flat", llm, envelope, tools, tmp_path)
    assert r.provenance == {}
