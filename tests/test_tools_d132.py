"""D132 — helpers choose their tools: native tool calling, the core tools and find_tool, and no stale "unavailable"
lines for a tool the helper holds. Offline (MockLLMClient answers a native-tools call with its scripted action)."""
import json

import yaml

from amoeba.config.schema import AgentSpec
from amoeba.interp.plan_runner import FIND_TOOL, NATIVE_FORMAT, PlanOptions, held_tool
from amoeba.interp.runtime import Interpreter
from amoeba.llm.client import mock_tool_calls, tool_fn_name
from amoeba.llm.router import CallSpec, ModelRouter, load_registry
from tests.test_fixes_d117 import BODY, fake_stock, good, reply
from tests.test_plan_runner import plan_team, step_no

RUN2_TEAM = "eval/manual/probe_box4/e981a833-6cfe-4dbb-8df9-6784ff3312cf/team.yaml"


def agent(**kw) -> AgentSpec:
    return AgentSpec.model_validate({"agent_id": "a1", "name": "Fleet Cost Analyst", "role": "worker", "model": "m",
                                     "prompt": {"template_id": "x"}, **kw})


def test_a_wish_is_held_when_the_helper_has_a_tool_that_does_it():
    t = yaml.safe_load(open(RUN2_TEAM, encoding="utf-8"))          # the probe run where "Bash" stayed missing
    fca = next(AgentSpec.model_validate(a) for a in t["agents"].values() if a["name"] == "Fleet Cost Analyst")
    assert fca.missing_tools == ["Bash", "Edit"] and "local:Bash" in fca.tools
    got = {n: held_tool(fca, n) for n in ("Bash", "Edit", "local", "python_interpreter", "code runner", "xlsx skill",
                                           "spreadsheet", "docx", "web_search", "headless_office_converter")}
    assert got == {"Bash": "local:Bash", "Edit": "local:Edit", "local": "local:Read", "python_interpreter": "local:Bash",
                   "code runner": "local:Bash", "xlsx skill": "skill xlsx", "spreadsheet": "skill xlsx",
                   "docx": None, "web_search": None, "headless_office_converter": None}


def test_tool_names_become_function_names_and_the_mock_answers_with_a_call():
    assert tool_fn_name("local:Bash") == "local_Bash" and tool_fn_name("Final Output") == "Final_Output"
    calls = mock_tool_calls(reply("local:Bash", "ls -la"), [{}])
    assert calls == [{"name": "local_Bash", "input": json.dumps({"input": "ls -la"})}]
    assert mock_tool_calls("plain text, no action", [{}]) == []


def test_the_router_says_whether_every_model_can_call_tools(monkeypatch):
    registry, policy = load_registry()
    env = {"CLAUDE_API_KEY": "x", "GEMINI_API_KEY": "x"}
    claude = ModelRouter(registry, policy, make=None, mode="routed", profile_allowed=["claude-sonnet-5-5"], env=env)
    both = ModelRouter(registry, policy, make=None, mode="routed", env=env)
    assert claude.can_use("tools") and not both.can_use("tools")


def run(task, envelope, trace, tools, script, opts, stock=None, setup=None):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script)
    if setup:
        setup(cfg)
    ep = Interpreter(llm, tools, trace, plan_options=opts, stock=stock).run(cfg, task, seed=0)
    return llm, cfg, ep


def test_a_held_tool_is_never_announced_unavailable_nor_counted_as_lacked(task, envelope, trace, tools):
    def wish(cfg):                       # Box 2 wrote "Bash" while the helper holds local:Bash (the probe's case)
        for a in cfg.agents.values():
            if a.name == "Cost Analyst":
                a.tools.append("local:Bash")
                a.missing_tools = ["Bash"]

    def script(messages, seed):
        n = step_no(messages)
        if n == "1":
            assert "Tool Bash is unavailable" not in messages[-1]["content"]
            return reply("Final Output", f"OUT-1\n{BODY}\nBLOCKED: Bash — did it by hand")
        return good(n)
    _, _, ep = run(task, envelope, trace, tools, script, PlanOptions(contract="on"), setup=wish)
    s1 = next(m for m in ep.steps if m["step"] == 1)
    assert "Bash" not in s1["status_reason"]          # web_search is really missing here; Bash is not
    assert trace.events("blocked_but_held")[0]["amoeba.items"] == {"Bash": "local:Bash"}


def test_native_turns_send_tools_and_read_the_call_back(task, envelope, trace, tools):
    _, _, ep = run(task, envelope, trace, tools, lambda m, s: good(step_no(m)), PlanOptions(native_tools="on"))
    llm_calls = [c for c in ep_llm(trace)]
    assert ep.error is None and llm_calls
    first = llm_calls[0]
    assert first["amoeba.native_tools"] >= 1
    assert all(m["status"] == "done" for m in ep.steps)


def ep_llm(trace):
    return [s for s in trace.spans("chat") if s.get("amoeba.native_tools")]


def test_a_native_prompt_has_no_text_protocol(task, envelope, trace, tools):
    seen = []

    def script(messages, seed):
        seen.append(messages[-1]["content"])
        return good(step_no(messages))
    run(task, envelope, trace, tools, script, PlanOptions(native_tools="on"))
    assert seen and all("## ActionInput" not in u and NATIVE_FORMAT.splitlines()[0] in u for u in seen)


def test_core_access_gives_every_helper_the_core_tools_and_find_tool(task, envelope, trace, tools):
    calls = []
    _, cfg, ep = run(task, envelope, trace, tools, lambda m, s: good(step_no(m)), PlanOptions(tool_access="core"),
                     stock=fake_stock(calls))
    ev = trace.events("core_tools")[0]
    assert ev["amoeba.core"] == ["calc"] and ev["amoeba.find_tool"] is True


def test_find_tool_attaches_what_it_finds_and_the_helper_uses_it_next_turn(task, envelope, trace, tools):
    calls = []

    def script(messages, seed):
        n, text = step_no(messages), messages[-1]["content"]
        if n == "1" and "pool:fx" not in text:
            return reply(FIND_TOOL, "currency exchange rates")
        if n == "1" and "pool:fx · rate" not in text:
            return reply("pool:fx", "EUR/USD")
        return good(n)
    _, cfg, ep = run(task, envelope, trace, tools, script, PlanOptions(tool_access="core"), stock=fake_stock(calls))
    assert calls[0]["names"] == ["currency exchange rates"]
    found = trace.events("find_tool")[0]
    assert found["amoeba.attached"] == ["pool:fx"] and found["amoeba.need"] == "currency exchange rates"
    assert any(r.get("source") == "find_tool" for r in cfg.meta["capability_requests"])
