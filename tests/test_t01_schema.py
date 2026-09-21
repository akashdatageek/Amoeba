"""T1 — schema roundtrip and config_hash stability."""
from uuid import uuid4

from amoeba.config.io import config_hash, dump_yaml, load_yaml, to_dict
from amoeba.config.schema import AgentSpec, Edge, PlanStep, PromptRef, TeamConfig


def make_cfg() -> TeamConfig:
    a, b = str(uuid4()), str(uuid4())
    agents = {
        a: AgentSpec(agent_id=a, name="A", role="worker", model="m", tools=["calc"],
                     prompt=PromptRef(system="sys", user="seed:autoagents_custom_action")),
        b: AgentSpec(agent_id=b, name="B", role="worker", model="m",
                     prompt=PromptRef(system="sys", user="seed:autoagents_custom_action")),
    }
    return TeamConfig(team_id=str(uuid4()), name="t", topology="flat", agents=agents,
                      edges=[Edge(src=a, dst=b, type="sequential")], entry=[a], exit=b,
                      plan=[PlanStep(index=0, agent_ids=[a], text="[A]: x"), PlanStep(index=1, agent_ids=[b], text="[B]: y")])


def test_yaml_roundtrip(tmp_path):
    cfg = make_cfg()
    dump_yaml(cfg, tmp_path / "team.yaml")
    assert load_yaml(tmp_path / "team.yaml") == cfg


def test_config_hash_stable_under_key_reordering():
    cfg = make_cfg()
    d = to_dict(cfg)
    reordered = {k: d[k] for k in reversed(list(d))}
    reordered["agents"] = {k: dict(reversed(list(v.items()))) for k, v in reversed(list(d["agents"].items()))}
    assert config_hash(cfg) == config_hash(d) == config_hash(reordered)
    other = make_cfg()
    assert config_hash(other) != config_hash(cfg)
