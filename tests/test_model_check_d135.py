"""D135 — scripts/model_check.py on the mock: every probe runs through the real prompt builders, stops after its own
call, and is recorded; a reasoning refusal fails the check and names the prompt file; --write edits only the entry's
supports and checked_at. Offline: never a real model."""
import json
import shutil

from amoeba.llm.client import ChatResponse, MockLLMClient
from scripts import model_check as mc
from tests.conftest import fx

ENTITIES = '## Thought\nnothing in doubt\n\n## Entities\n```json\n[]\n```'
ANSWER = {"weekly_cost_eur": 97.2, "working": "120*5*9/100*1.8", "unit": "EUR"}
SUBMIT = ChatResponse("", tool_calls=[{"name": "submit_toy_answer", "input": json.dumps(ANSWER)}],
                      finish_reason="tool_calls")
STEP = "## Thought\nuse calc\n\n## CurrentStep\nsum\n\n## Action\ncalc\n\n## ActionInput\n120*5*9/100*1.8"
FIX = ('```json\n{"edit": {"op": "add_role_rule", "params": {"role": "Fuel Cost Analyst", "text": "Use calc for '
       'every product."}}, "reason": "the helper ran out of turns doing sums by hand"}\n```')


def mock(**over):
    script = {"interpreter": [ENTITIES], "planner": [fx("manager_output_real")],
              "agent_observer": [fx("observer_no_suggestions")], "plan_worker": [STEP], "fix_proposer": [FIX],
              "pool_picker": ["skill-xlsx"], "other": [ANSWER, SUBMIT, json.dumps(ANSWER)], **over}
    return MockLLMClient(script={k: list(v) for k, v in script.items()})


def test_every_probe_runs_once_and_is_recorded():
    client = mock()
    r = mc.run_checks(client, "mock", budget=0.25)
    by = {x["probe"]: x for x in r["probes"]}
    assert list(by) == ["reading", "planner", "observer", "step (native tools)", "fix proposer", "pool pick",
                        "output mode: schema", "output mode: submit_tool", "output mode: json_prompt"]
    assert {k: v["status"] for k, v in by.items()} == {k: "ok" for k in by}
    assert by["step (native tools)"]["note"] == "tool call: calc"
    assert r["supports"] == {"tools": True, "output_mode": "schema"} and r["reasoning_refusals"] == []
    kinds = [c["kind"] for c in client.calls]
    assert kinds.count("planner") == 1 and kinds.count("plan_worker") == 1          # the gate stopped each pipeline
    step_call = next(c for c in client.calls if c["kind"] == "plan_worker")
    assert step_call["tools"] and "## ActionInput" not in step_call["messages"][-1]["content"]   # v2, native
    assert "weekly_cost_eur" in json.dumps(next(c for c in client.calls if c.get("schema")) and ANSWER)
    out = mc.table(r)
    assert "supports.tools=True" in out and "output mode: json_prompt" in out


def test_a_reasoning_refusal_fails_and_names_the_prompt_file():
    refused = ChatResponse("", finish_reason="refusal", refusal_category="reasoning_extraction")
    r = mc.run_checks(mock(interpreter=[refused]), "mock", budget=0.25)
    reading = r["probes"][0]
    assert reading["status"] == "blocked" and reading["category"] == "reasoning_extraction"
    assert reading["prompt_files_found"][0] == "interpret.txt"
    lines = mc.failures(r)
    assert lines and "reading" in lines[0] and "interpret.txt" in lines[0]


def test_output_modes_fall_through_in_order():
    r = mc.run_checks(mock(other=["not json", SUBMIT, "still not json", "nope"]), "mock", budget=0.25)
    modes = {x["probe"]: x["status"] for x in r["probes"] if x["probe"].startswith("output mode")}
    assert modes == {"output mode: schema": "unreadable", "output mode: submit_tool": "ok",
                     "output mode: json_prompt": "unreadable"}
    assert r["supports"]["output_mode"] == "submit_tool"


def test_the_budget_skips_the_remaining_probes(monkeypatch):
    monkeypatch.setattr(mc, "spent", lambda trace, model: 1.0 if trace.spans("chat") else 0.0)
    r = mc.run_checks(mock(), "mock", budget=0.25)
    assert r["probes"][0]["status"] == "ok" and all(x["status"] == "skipped" for x in r["probes"][1:])


def test_write_sets_only_the_entry_supports(tmp_path):
    path = tmp_path / "models.yaml"
    shutil.copy(mc.MODELS, path)
    before = path.read_text()
    diff = mc.write_supports("claude-sonnet-5-5", {"tools": True, "output_mode": "submit_tool"}, "2031-01-02", path)
    after = path.read_text()
    assert "output_mode: submit_tool" in diff and "checked_at: 2031-01-02" in diff
    changed = [l for l in diff.splitlines() if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
    assert all("supports:" in l or "checked_at:" in l for l in changed)      # nothing else moves
    assert before.count("gemma-4-31b:") == after.count("gemma-4-31b:")
    import yaml
    data = yaml.safe_load(after)["registry"]
    e = data["claude-sonnet-5-5"]
    assert e["supports"] == {"json": True, "tools": True, "vision": True, "output_mode": "submit_tool"}
    assert str(e["checked_at"]) == "2031-01-02"
    assert data["gemma-4-31b"] == yaml.safe_load(before)["registry"]["gemma-4-31b"]
    from amoeba.llm.router import load_registry
    load_registry(path)                                         # the registry still loads
