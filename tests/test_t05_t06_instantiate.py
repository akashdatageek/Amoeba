"""T5 / T6 — instantiate() for both topologies."""
import uuid

from amoeba.config.prompts import GROUP_PREFIX
from amoeba.config.validate import validate
from amoeba.interp.runtime import Interpreter
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from tests.conftest import fx, mock


def test_flat(task, envelope, trace, tools):
    llm = mock(planner=[fx("draft_three_roles")], worker=[fx("worker_final_output")])
    draft = draft_team(task, llm, envelope, trace)
    cfg = instantiate(draft, "flat", task, envelope)
    assert validate(cfg, envelope) == []
    by_name = {a.name: a for a in cfg.agents.values()}
    for a in cfg.agents.values():
        uuid.UUID(a.agent_id)
        assert a.created_by == "drafter" and a.role == "worker"
    assert [s.agent_ids for s in cfg.plan] == [[by_name["Mathematician"].agent_id, by_name["Auditor"].agent_id],
                                               [by_name["Writer"].agent_id]]
    # edges follow plan order: every step-0 agent → every step-1 agent
    assert {(e.src, e.dst, e.type) for e in cfg.edges} == {
        (by_name["Mathematician"].agent_id, by_name["Writer"].agent_id, "sequential"),
        (by_name["Auditor"].agent_id, by_name["Writer"].agent_id, "sequential")}
    assert cfg.entry == cfg.plan[0].agent_ids and cfg.exit == by_name["Writer"].agent_id
    # role prompt appears in the USER message; system is GROUP_PREFIX
    Interpreter(llm, tools, trace).run(cfg, task)
    first_worker_call = llm.calls_of("worker")[0]["messages"]
    assert first_worker_call[0]["content"] == GROUP_PREFIX
    assert first_worker_call[1]["content"].startswith("\n-----\nYou are a Mathematician. Based on prior agents")


def test_boss_reviewers(task, envelope, trace):
    draft = draft_team(task, mock(planner=[fx("draft_three_roles")]), envelope, trace)
    cfg = instantiate(draft, "boss_reviewers", task, envelope)
    assert validate(cfg, envelope) == []
    solver = cfg.agents[cfg.exit]
    assert solver.name == "Writer" and solver.role == "solver" and solver.max_history == 5   # the summariser (last step)
    assert solver.prompt.format == "history+append" and solver.prompt.system == "seed:agentverse_solver_prepend"
    critics = [a for a in cfg.agents.values() if a.role == "critic"]
    assert {c.name for c in critics} == {"Mathematician", "Auditor"} and all(c.max_history == 3 for c in critics)
    assert cfg.entry == [solver.agent_id]
    review = {(e.src, e.dst) for e in cfg.edges if e.type == "review"}
    revise = {(e.src, e.dst, e.condition) for e in cfg.edges if e.type == "revise"}
    assert review == {(solver.agent_id, c.agent_id) for c in critics}
    assert revise == {(c.agent_id, solver.agent_id, "critic_disagrees") for c in critics}
    assert cfg.max_inner_turns == 3
    assert solver.description == "a plain-language writer who states the final answer"
