"""Capability requests (D19), the summariser flag (D20), BLOCKED and unknown tools at run time (D21)."""
import json

from amoeba.config.prompts import KEEP_REQUESTS
from amoeba.interp.runtime import UNAVAILABLE, Interpreter
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from amoeba.task.models import Task
from scripts.run_task import run_one
from tests.conftest import fx, mock

CAP = "draft_capability_requests"


def by_key(reqs):
    return {(q.name, q.for_role): q for q in reqs}


# ---- drafting -------------------------------------------------------------------------------------------------
def test_invented_tool_is_recorded_not_dropped(task, envelope, trace):
    d = draft_team(task, mock(planner=[fx("draft_round_ok")]), envelope, trace)
    calc = d.created_roles[0]
    assert calc.tools == ["calc"] and calc.missing_tools == ["web_search"]
    [q] = d.capability_requests
    assert (q.name, q.for_role, q.kind, q.source) == ("web_search", "Calculator", "tool", "unregistered_tool")
    [ev] = trace.events("capability_request")
    assert ev["capability.name"] == "web_search" and ev["capability.source"] == "unregistered_tool"


def test_planner_requests_section_is_parsed(task, envelope, trace):
    llm = mock(planner=[fx(CAP)])
    d = draft_team(task, llm, envelope, trace)
    reqs = by_key(d.capability_requests)
    assert set(reqs) == {("web_search", "Researcher"), ("unit_conversion", "Writer")}   # no resolver duplicate
    web = reqs["web_search", "Researcher"]
    assert web.source == "planner" and web.what_it_does.startswith("searches the web")
    assert json.loads(web.example_output)["results"][0]["snippet"] == "68 million"   # nested example survives
    assert reqs["unit_conversion", "Writer"].kind == "skill"
    assert d.created_roles[0].tools == ["calc"] and d.created_roles[0].missing_tools == ["web_search"]
    assert len(trace.events("capability_request")) == 2
    # both observers see the requests and are asked to critique them
    for kind in ("agent_observer", "plan_observer"):
        prompt = llm.calls_of(kind)[0]["messages"][1]["content"]
        assert "# Capability Requests\n" in prompt and '"name": "unit_conversion"' in prompt
        assert KEEP_REQUESTS in prompt and "whether an existing tool is enough" not in prompt


def test_missing_requests_section_costs_no_repair_call(task, envelope, trace):
    llm = mock(planner=[fx("draft_round_ok")])
    draft_team(task, llm, envelope, trace)
    assert len(llm.calls_of("planner")) == 1
    assert "# Capability Requests\nNone\n" in llm.calls_of("agent_observer")[0]["messages"][1]["content"]


def test_planner_prompt_asks_for_requests(task, envelope, trace):
    llm = mock(planner=[fx("draft_round_ok")])
    draft_team(task, llm, envelope, trace)
    prompt = llm.calls_of("planner")[0]["messages"][1]["content"]
    assert "do NOT invent new tools" not in prompt
    assert "## Capability Requests" in prompt and "example_input, example_output" in prompt


# ---- summariser flag ------------------------------------------------------------------------------------------
def test_explicit_summariser_flag_wins_over_last_step(task, envelope, trace):
    text = fx(CAP).replace('"name": "Researcher",', '"name": "Researcher",\n    "is_summariser": true,')
    d = draft_team(task, mock(planner=[text]), envelope, trace)
    assert [(r.name, r.is_summariser) for r in d.created_roles] == [("Researcher", True), ("Writer", False)]


def test_boss_solver_is_the_flagged_role_not_the_toolless_one(task, envelope, trace):
    # both roles have tools: the old "first role without tools" rule found none and appended a Language Expert
    d = draft_team(task, mock(planner=[fx("draft_no_summariser")]), envelope, trace)
    cfg = instantiate(d, "boss_reviewers", task, envelope)
    solver = cfg.agents[cfg.exit]
    assert solver.name == "Checker" and solver.role == "solver" and solver.is_summariser
    assert len(cfg.agents) == 2


# ---- run time -------------------------------------------------------------------------------------------------
def run_flat(task, envelope, trace, tools, worker):
    llm = mock(planner=[fx(CAP)], worker=worker)
    cfg = instantiate(draft_team(task, llm, envelope, trace), "flat", task, envelope)
    return llm, Interpreter(llm, tools, trace).run(cfg, task, seed=0)


def test_missing_tool_line_reaches_only_that_helper(task, envelope, trace, tools):
    llm, ep = run_flat(task, envelope, trace, tools, [fx("worker_final_output")])
    researcher, writer = [c["messages"][1]["content"] for c in llm.calls_of("worker")]
    line = UNAVAILABLE.format(name="web_search")
    assert line == "Tool web_search is unavailable this run; proceed without it or answer BLOCKED: web_search"
    assert line in researcher and "unavailable this run" not in writer
    assert "# Tools ['calc', 'Print', 'Final Output']" in researcher   # the missing tool is not offered
    assert ep.answer == "396" and ep.error is None and ep.blocked_steps == []


def test_blocked_step_is_recorded_and_the_run_goes_on(task, envelope, trace, tools):
    llm, ep = run_flat(task, envelope, trace, tools, [fx("worker_blocked"), fx("worker_final_output")])
    assert ep.answer == "396" and ep.error is None           # step 2 still answered
    [b] = ep.blocked_steps
    assert (b["step"], b["agent"], b["tool"]) == (0, "Researcher", "web_search")
    [ev] = trace.events("blocked")
    assert ev["gen_ai.agent.name"] == "Researcher" and ev["gen_ai.tool.name"] == "web_search"
    assert len(llm.calls_of("worker")) == 2                  # BLOCKED ends the helper's step like Final Output
    assert ">>>> BLOCKED: web_search" in llm.calls_of("worker")[1]["messages"][1]["content"]


def test_blocked_last_step_is_an_error_not_an_answer(task, envelope, trace, tools):
    llm, ep = run_flat(task, envelope, trace, tools, [fx("worker_blocked")])
    assert ep.error == "blocked" and "BLOCKED: web_search" in ep.answer
    assert [b["agent"] for b in ep.blocked_steps] == ["Researcher", "Writer"]


def test_unknown_tool_is_an_event_not_a_silent_echo(task, envelope, trace, tools):
    llm, ep = run_flat(task, envelope, trace, tools, [fx("worker_unknown_tool"), fx("worker_final_output")])
    [ev] = trace.events("unknown_tool")
    assert ev["gen_ai.tool.name"] == "web_search" and ev["amoeba.tool.registered"] is False
    assert ev["gen_ai.agent.name"] == "Researcher"
    assert trace.spans("execute_tool") == []                 # nothing ran
    [q] = ep.requested_capabilities
    assert (q.name, q.for_role, q.source) == ("web_search", "Researcher", "runtime_unknown_tool")
    second = llm.calls_of("worker")[1]["messages"][1]["content"]
    assert "['web_search' is not a tool Researcher can use; nothing was run]" in second


def test_registered_tool_the_helper_lacks_is_an_event_but_not_a_request(task, envelope, trace, tools):
    echo = fx("worker_unknown_tool").replace("## Action\nweb_search", "## Action\necho")
    llm, ep = run_flat(task, envelope, trace, tools, [echo, fx("worker_final_output")])
    [ev] = trace.events("unknown_tool")
    assert ev["gen_ai.tool.name"] == "echo" and ev["amoeba.tool.registered"] is True
    assert ep.requested_capabilities == [] and trace.spans("execute_tool") == []


def test_run_one_writes_capability_requests_json(tmp_path, envelope, tools):
    llm = mock(planner=[fx(CAP)], worker=[fx("worker_unknown_tool"), fx("worker_final_output")])
    task = Task(prompt="Compute 17 * 23 + 5.", ground_truth="396")
    r = run_one(task, "flat", llm, envelope, tools, tmp_path)
    saved = json.loads((tmp_path / r.run_id / "capability_requests.json").read_text())
    assert [(q["name"], q["for_role"], q["source"]) for q in saved] == [
        ("web_search", "Researcher", "planner"), ("unit_conversion", "Writer", "planner"),
        ("web_search", "Researcher", "runtime_unknown_tool")]
    assert [q.model_dump() for q in r.requested_capabilities] == saved
    assert r.blocked_steps == [] and r.score == 1.0
    saved = json.loads((tmp_path / r.run_id / "result.json").read_text())
    assert (saved["requests_proposed"], saved["requests_dropped_by_observers"]) == (2, 0)


# ---- observers keep requests (box comment a1a2f8ad) -----------------------------------------------------------
def observer(first_reply):
    """A scripted observer that does what its prompt says: without the keep-requests rule it tells the planner to
    drop web_search (what the verbatim AutoAgents wording invites); with it, it critiques something else, then agrees."""
    replies = []

    def reply(messages, seed):
        prompt = messages[-1]["content"]
        if KEEP_REQUESTS not in prompt:
            text = "## Suggestions\n1. Remove web_search from the Researcher; the calc tool is enough.\n"
        else:
            text = first_reply if not replies else fx("observer_no_suggestions")
        replies.append(text)
        return text
    reply.replies = replies
    return reply


def test_observers_do_not_talk_the_planner_out_of_requests(task, envelope, trace):
    agent_obs = observer("## Suggestions\n1. The Researcher's prompt should say where each figure came from.\n")
    plan_obs = observer(fx("observer_no_suggestions"))
    llm = mock(planner=[fx(CAP)], agent_observer=agent_obs, plan_observer=plan_obs)
    d = draft_team(task, llm, envelope, trace)
    assert d.rounds_used == 2
    said = agent_obs.replies + plan_obs.replies
    assert said and not any("remove web_search" in r.lower() for r in said)
    prompt = llm.calls_of("agent_observer")[0]["messages"][1]["content"]
    assert "tell the Planner to ADD a Capability Request for it" in prompt and "remove any that are" not in prompt
    assert "or requested under Capability Requests" in prompt
    assert ("web_search", "Researcher") in by_key(d.capability_requests)       # still requested in the final draft
    assert (d.requests_proposed, d.requests_dropped_by_observers) == (2, 0)


def test_requests_dropped_after_round_1_are_counted(task, envelope, trace):
    dropped = (fx(CAP).replace('"tools": ["web_search", "calc"]', '"tools": ["calc"]')
               .split("## Capability Requests:")[0] + "## Execution Plan:" + fx(CAP).split("## Execution Plan:")[1])
    llm = mock(planner=[fx(CAP), dropped],
               agent_observer=[fx("observer_complaint"), fx("observer_no_suggestions")])
    d = draft_team(task, llm, envelope, trace)
    assert d.rounds_used == 2 and d.capability_requests == []
    assert (d.requests_proposed, d.requests_dropped_by_observers) == (2, 2)
