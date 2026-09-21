"""T2 — validate() rejects the shapes the spec lists."""
from uuid import uuid4

from amoeba.config.schema import AgentSpec, Edge, PlanStep, PromptRef, TeamConfig
from amoeba.config.validate import validate


def agent(name, role="worker", tools=(), aid=None):
    aid = aid or str(uuid4())
    return AgentSpec(agent_id=aid, name=name, role=role, model="m", tools=list(tools),
                     prompt=PromptRef(system="s", user="u"))


def flat(agents):
    ids = [a.agent_id for a in agents]
    return TeamConfig(team_id="t", name="t", topology="flat", agents={a.agent_id: a for a in agents},
                      edges=[Edge(src=x, dst=y, type="sequential") for x, y in zip(ids, ids[1:])],
                      entry=[ids[0]], exit=ids[-1],
                      plan=[PlanStep(index=i, agent_ids=[aid], text=f"[{i}]: s") for i, aid in enumerate(ids)])


def test_valid_flat_passes(envelope):
    assert validate(flat([agent("A", tools=["calc"]), agent("B")]), envelope) == []


def test_unknown_edge_id(envelope):
    cfg = flat([agent("A"), agent("B")])
    cfg.edges.append(Edge(src=cfg.entry[0], dst="nobody", type="sequential"))
    assert any(e.startswith("V1") for e in validate(cfg, envelope))


def test_tool_outside_allowlist(envelope):
    errs = validate(flat([agent("A", tools=["web_search"]), agent("B")]), envelope)
    assert any(e.startswith("V5") for e in errs)


def test_too_many_agents(envelope):
    errs = validate(flat([agent(f"A{i}") for i in range(6)]), envelope)
    assert any(e.startswith("V6") for e in errs)


def test_duplicate_and_non_uuid_id(envelope):
    a = agent("A", aid="not-a-uuid")
    b = agent("B")
    cfg = flat([a, b])
    assert any("not a UUID" in e for e in validate(cfg, envelope))
    dup = agent("C", aid=b.agent_id)
    cfg2 = flat([a, b])
    cfg2.agents["extra-key"] = dup
    errs = validate(cfg2, envelope)
    assert any("duplicate agent_id" in e for e in errs)


def test_empty_plan(envelope):
    cfg = flat([agent("A"), agent("B")])
    cfg.plan = []
    assert any("plan is empty" in e for e in validate(cfg, envelope))


def test_boss_reviewers_with_two_solvers(envelope):
    s1, s2, c = agent("S1", "solver"), agent("S2", "solver"), agent("C", "critic")
    cfg = TeamConfig(team_id="t", name="t", topology="boss_reviewers", agents={a.agent_id: a for a in (s1, s2, c)},
                     edges=[Edge(src=s1.agent_id, dst=c.agent_id, type="review")], entry=[s1.agent_id], exit=s1.agent_id)
    assert any("exactly one solver" in e for e in validate(cfg, envelope))
