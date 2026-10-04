"""D97 — the per-call model router (plain code; mock providers, no network): the registry holds only Gemma 4 31B;
allowlists, missing keys, 429 cooldown and fallback within a tier, sensitive data, the USD cap, no candidate →
no_model, fixed mode, every decision logged, the three verifier-independence settings, the shared rate bucket, and a
second model added to the registry ONLY (no code change) that the router then uses — for the verifier too."""
import json
from pathlib import Path

import pytest

from amoeba.interp.trace import TraceWriter, TracedLLM
from amoeba.llm.client import MockLLMClient
from amoeba.llm.router import CallSpec, ModelEntry, ModelRouter, NoModelAvailable, SharedBucket, load_registry


class RateLimited(Exception):
    status_code = 429


def entry(name, family="gemma", tier="large", price=(0.0, 0.0), privacy="cloud", key="K_" + "X", ctx=100000,
          supports=None, rpm=None):
    return ModelEntry(name=name, provider="mock", model=f"{name}-id", family=family, size_tier=tier,
                      api_key_env=key, context_window=ctx, max_output=8000,
                      supports=supports or {"json": True, "tools": False, "vision": False},
                      price={"input": price[0], "output": price[1]}, rate={"rpm": rpm}, privacy=privacy)


def router(entries, tmp_path, policy=None, env=None, **kw):
    clients = {}
    given = kw.pop("_client_for", {})

    def make(e):
        clients[e.name] = given.get(e.name) or MockLLMClient(responder=lambda m, s, n=e.name: f"from {n}")
        return clients[e.name]
    r = ModelRouter({e.name: e for e in entries}, {"verifier_independence": "preferred", **(policy or {})}, make,
                    env=env if env is not None else {"K_X": "1"}, rate_dir=tmp_path / "rate",
                    sleep=lambda s: None, **kw)
    r._mock_clients = clients
    return r


MSG = [{"role": "user", "content": "hello"}]


def test_the_registry_holds_only_gemma_with_its_limits_and_price():
    reg, policy = load_registry()
    assert list(reg) == ["gemma-4-31b"]
    g = reg["gemma-4-31b"]
    assert (g.family, g.model, g.api_key_env, g.privacy) == ("gemma", "gemma-4-31b-it", "GEMINI_API_KEY", "cloud")
    assert g.rate["rpm"] == 15 and g.price == {"input": 0.0, "output": 0.0} and g.context_window >= 128000
    assert policy["verifier_independence"] == "preferred" and policy["default_model"] == "gemma-4-31b"


def test_allowlists_and_missing_keys(tmp_path):
    a, b, c = entry("a", price=(1, 1)), entry("b", price=(2, 2)), entry("c", key="K_MISSING", price=(0.1, 0.1))
    r = router([a, b, c], tmp_path, allowed=["b", "c"])
    name, dec = r.route(CallSpec(role="worker"))
    assert name == "b" and dec["filtered"]["a"] == "not in --allowed-models" and dec["filtered"]["c"].startswith("no key")
    r = router([a, b], tmp_path, profile_allowed=["a"])
    assert r.route(CallSpec(role="worker"))[0] == "a"
    assert router([a, b, c], tmp_path).route(CallSpec(role="worker"))[0] == "a"        # cheapest with a key


def test_a_429_cools_the_model_down_and_the_next_of_its_tier_is_used(tmp_path):
    class Limited(MockLLMClient):
        def chat_messages(self, messages, seed=0, max_tokens=None):
            raise RateLimited("429 too many requests")
    a, b = entry("a", price=(1, 1)), entry("b", price=(2, 2))
    r = router([a, b], tmp_path, _client_for={"a": Limited(responder=lambda m, s: "x")})
    resp, dec = r.call(CallSpec(role="worker"), MSG, 0, 100)
    assert resp.content == "from b" and r.bucket("a").cooling() > 0
    assert any(f["reason"] == "429" for f in dec["fallbacks"] + r.decisions[0]["fallbacks"])


def test_with_one_model_a_cooldown_is_waited_out(tmp_path):
    waits = []
    r = router([entry("a")], tmp_path)
    r.sleep = waits.append
    r.bucket("a").cooldown(30)
    resp, dec = r.call(CallSpec(role="worker"), MSG, 0, 100)
    assert resp.content == "from a" and dec["cooldown_wait_s"] > 0 and waits and waits[0] > 0


def test_sensitive_data_goes_to_local_models_only(tmp_path):
    r = router([entry("cloud"), entry("local", privacy="local", price=(5, 5))], tmp_path)
    assert r.route(CallSpec(role="worker", data_class="sensitive"))[0] == "local"
    r = router([entry("cloud")], tmp_path)
    with pytest.raises(NoModelAvailable):
        r.route(CallSpec(role="worker", data_class="sensitive"))
    assert r.decisions[-1]["cause"] == "no_model" and "sensitive" in r.decisions[-1]["filtered"]["cloud"]


def test_the_usd_cap_stops_calls(tmp_path):
    r = router([entry("a", price=(1000.0, 1000.0))], tmp_path, usd_cap=0.5)
    r.call(CallSpec(role="worker", prompt_tokens=100, max_output=100), MSG, 0, 100)    # $0.2 estimated
    r.usage["a"]["usd"] = 0.45
    with pytest.raises(NoModelAvailable):
        r.route(CallSpec(role="worker", prompt_tokens=100, max_output=100))
    assert "over the run USD cap" in r.decisions[-1]["filtered"]["a"]


def test_context_and_features_are_hard_filters(tmp_path):
    r = router([entry("small", ctx=1000), entry("big", ctx=100000, price=(9, 9))], tmp_path)
    assert r.route(CallSpec(role="worker", prompt_tokens=900, max_output=500))[0] == "big"
    with pytest.raises(NoModelAvailable):
        r.route(CallSpec(role="worker", needs=frozenset({"vision"})))


def test_fixed_mode_uses_one_model_for_every_call(tmp_path):
    r = router([entry("a", price=(1, 1)), entry("b", price=(0.1, 0.1))], tmp_path, mode="fixed", fixed_model="a")
    for role in ("planner", "worker", "verifier", "architect"):
        assert r.route(CallSpec(role=role))[0] == "a"
    assert all(d["mode"] == "fixed" for d in r.decisions)


def test_verifier_independence_required_preferred_and_off(tmp_path):
    g, q = entry("gemma", family="gemma"), entry("qwen", family="qwen", price=(3, 3))
    for setting, models, expect, same in (("preferred", [g, q], "qwen", None),
                                          ("preferred", [g], "gemma", "no alternative"),
                                          ("required", [g, q], "qwen", None),
                                          ("off", [g, q], "gemma", None)):
        r = router(models, tmp_path, policy={"verifier_independence": setting})
        r.step_family[1] = "gemma"                                    # step 1's work was done by Gemma
        name, dec = r.route(CallSpec(role="verifier", step=2, checks=(1,)))
        assert name == expect and dec.get("verifier_same_family") == same, (setting, dec)
    r = router([g], tmp_path, policy={"verifier_independence": "required"})
    r.step_family[1] = "gemma"
    with pytest.raises(NoModelAvailable):
        r.route(CallSpec(role="verifier", step=2, checks=(1,)))
    assert "verifier independence required" in r.decisions[-1]["filtered"]["gemma"]


def test_the_recipe_preference_and_the_role_default_come_first(tmp_path):
    a, b = entry("a", price=(1, 1)), entry("b", price=(2, 2))
    r = router([a, b], tmp_path, policy={"role_defaults": {"planner": "b"}}, recipe_prefs={"worker": "b"})
    assert r.route(CallSpec(role="worker"))[1]["why"] == "recipe preference"
    assert r.route(CallSpec(role="planner"))[1]["why"] == "role default"
    assert r.route(CallSpec(role="summariser"))[0] == "a"


def test_repeated_5xx_marks_a_model_failing_for_the_run(tmp_path):
    class Down(MockLLMClient):
        def chat_messages(self, messages, seed=0, max_tokens=None):
            e = RuntimeError("503")
            e.status_code = 503
            raise e
    r = router([entry("a", price=(1, 1)), entry("b", price=(2, 2))], tmp_path, failing_after=1,
               _client_for={"a": Down(responder=lambda m, s: "x")})
    resp, _ = r.call(CallSpec(role="worker"), MSG, 0, 100)
    assert resp.content == "from b" and "a" in r.failing
    assert r.route(CallSpec(role="worker"))[1]["filtered"]["a"] == "failing in this run"


def test_the_shared_bucket_keeps_to_the_per_minute_limit(tmp_path):
    now = [1000.0]
    slept = []

    def sleep(s):
        slept.append(s)
        now[0] += s
    b = SharedBucket(tmp_path, "m", rpm=2, tpm=None, clock=lambda: now[0], sleep=sleep)
    assert b.acquire() == 0 and b.acquire() == 0
    waited = b.acquire()
    assert waited > 0 and abs(waited - 30) < 5.1                     # 2 per minute: the third waits ~30 s
    b2 = SharedBucket(tmp_path, "m", rpm=2, tpm=None, clock=lambda: now[0], sleep=sleep)   # another process
    assert b2.acquire() > 0


def test_every_decision_is_logged_and_result_gets_usd(tmp_path):
    r = router([entry("a", price=(1.0, 2.0))], tmp_path)
    trace = TraceWriter(tmp_path / "t.jsonl")
    tl = TracedLLM(r, trace)
    for name in ("planner", "agent_observer"):
        tl.chat_messages(MSG, agent_name=name, max_tokens=50)
    tl.chat_messages(MSG, role="workers", step=1, max_tokens=50)
    tl.chat_messages(MSG, role="reviewers", step=2, checks=(1,), max_tokens=50)
    routes = trace.events("route")
    assert len(routes) == 4 and routes[-1]["amoeba.route.role"] == "verifier"
    assert routes[-1]["amoeba.route.verifier_same_family"] == "no alternative"
    s = r.summary()
    assert s["per_model"]["a"]["calls"] == 4 and s["verifier_same_family"] == 1 and s["usd"] > 0


def test_no_model_is_logged_and_raised(tmp_path):
    r = router([entry("a", key="K_NONE")], tmp_path)
    trace = TraceWriter(tmp_path / "t.jsonl")
    with pytest.raises(NoModelAvailable):
        TracedLLM(r, trace).chat_messages(MSG, agent_name="planner")
    assert trace.events("no_model") and trace.events("route")[0]["amoeba.route.cause"] == "no_model"


def test_a_second_model_in_the_registry_only_is_used_with_no_code_change(tmp_path):
    reg_file = tmp_path / "models.yaml"
    real = Path("amoeba/config/models.yaml").read_text()
    reg_file.write_text(real.replace("routing:\n", "  mock-qwen:\n    provider: mock\n    model: qwen-mock\n"
                                     "    api_key_env: MOCK_KEY\n    family: qwen\n    size_tier: large\n"
                                     "    context_window: 131072\n    max_output: 8192\n"
                                     "    supports: {json: true, tools: false, vision: false}\n"
                                     "    price: {input: 0.0, output: 0.0}\n    rate: {rpm: 60, tpm: null}\n"
                                     "    privacy: cloud\n\nrouting:\n", 1))
    reg, policy = load_registry(reg_file)
    assert set(reg) == {"gemma-4-31b", "mock-qwen"}
    r = ModelRouter(reg, policy, lambda e: MockLLMClient(responder=lambda m, s, n=e.name: f"from {n}"),
                    env={"GEMINI_API_KEY": "k", "MOCK_KEY": "k"}, rate_dir=tmp_path / "rate", sleep=lambda s: None)
    resp, dec = r.call(CallSpec(role="worker", step=1), MSG, 0, 100)
    produced = dec["family"]
    other = "qwen" if produced == "gemma" else "gemma"
    name, vdec = r.route(CallSpec(role="verifier", step=2, checks=(1,)))
    assert reg[name].family == other and "verifier_same_family" not in vdec      # preferred: a different family
    r2 = ModelRouter(reg, policy, lambda e: MockLLMClient(responder=lambda m, s: "x"),
                     env={"GEMINI_API_KEY": "k", "MOCK_KEY": "k"}, rate_dir=tmp_path / "rate", allowed=["mock-qwen"],
                     sleep=lambda s: None)
    assert r2.route(CallSpec(role="planner"))[0] == "mock-qwen"


def test_routing_modes_by_default(monkeypatch):
    from scripts.run_task import parse_args, routing_mode
    assert routing_mode(parse_args(["t", "--topology", "plan"])) == "routed"
    assert routing_mode(parse_args(["t", "--topology", "flat"])) == "fixed"
    assert routing_mode(parse_args(["t", "--topology", "boss_reviewers"])) == "fixed"
    assert routing_mode(parse_args(["t", "--topology", "plan", "--routing", "role"])) == "role"


def test_a_run_through_run_one_records_routing_and_events(tmp_path, envelope, tools):
    """The whole run goes through the router: result.json gets per-model calls and USD; events.jsonl a routing row."""
    from amoeba.adapt.evidence import EvidenceLog, run_finished, verify
    from amoeba.llm.toy_mock import toy_mock_client
    from amoeba.task.source import ToyTaskSource
    from scripts.run_task import run_one
    toy = toy_mock_client()
    r = ModelRouter({"g": entry("g", price=(0.5, 1.0))}, {"verifier_independence": "preferred"}, lambda e: toy,
                    env={"K_X": "1"}, rate_dir=tmp_path / "rate", sleep=lambda s: None)
    task = ToyTaskSource(seed=1, n=1).tasks()[0]
    res = run_one(task, "flat", r, envelope, tools, tmp_path / "runs")
    assert res.routing["per_model"]["g"]["calls"] == res.n_llm_calls and res.routing["usd"] > 0
    saved = json.loads((tmp_path / "runs" / res.run_id / "result.json").read_text())
    assert saved["routing"]["mode"] == "routed"
    root = tmp_path / "runs"
    ev = EvidenceLog(root)
    run_finished(ev, root, root / res.run_id)
    row = [x for x in ev.rows() if x["event"] == "routing"][0]
    assert len(row["data"]["decisions"]) == res.n_llm_calls and verify(root)["ok"]


def test_a_plan_step_without_a_model_is_blocked_not_crashed(task, envelope, trace, tools):
    """No model passes the filters for the helpers: the step records BLOCKED no_model, like a missing capability."""
    from amoeba.interp.plan_runner import PlanOptions
    from amoeba.interp.runtime import Interpreter
    from tests.test_plan_runner import plan_team, finish
    llm, cfg = plan_team(task, envelope, trace, plan_worker=finish)
    reg = {"g": entry("g")}

    class OnlyBox2(ModelRouter):
        def route(self, spec):
            if spec.role in ("worker", "verifier", "summariser"):
                self.decisions.append({"role": spec.role, "cause": "no_model", "filtered": {"g": "test"}})
                raise NoModelAvailable("no model for " + spec.role)
            return super().route(spec)
    r = OnlyBox2(reg, {"verifier_independence": "off"}, lambda e: llm, env={"K_X": "1"},
                 rate_dir=Path(__import__("tempfile").mkdtemp()), sleep=lambda s: None)
    ep = Interpreter(r, tools, trace, plan_options=PlanOptions()).run(cfg, task, seed=0)
    assert ep.steps and all("no_model" in (s.get("blocked") or []) or s.get("answer_step") for s in ep.steps)
    assert any("no_model" in (s.get("blocked") or []) for s in ep.steps)


def test_rule_4_uses_usd_when_both_arms_have_prices():
    from amoeba.adapt.experimenter import Pair, ReplayResult
    from amoeba.adapt.gate import decide
    from amoeba.adapt.recipe import apply_edit, seed_recipe
    from tests.test_gate_d84 import ENV, hyp

    def res(usd_a, usd_b):
        pairs = [Pair(task_id=f"t{i}", phase="post", k=0, seed=0, score_A=0.5, score_B=0.9, tokens_A=1000,
                      tokens_B=1000, honesty_A=0, honesty_B=0, usd_A=usd_a, usd_B=usd_b) for i in range(15)]
        return ReplayResult(hypothesis_id="h", family="calc", recipe_from=1, recipe_to=2, recipe_A_hash="a",
                            mode="own_draft", pairs=pairs)
    a = seed_recipe("calc")
    d = decide(a, apply_edit(a, hyp().edit), hyp(), res(0.01, 0.05), 0.0, 1, [], ENV, version="v3", hypothesis_index=1)
    assert d.cost_basis == "usd" and d.cost_ratio == 5.0 and any(r.startswith("4 cost not justified: USD") for r in d.reasons)
    d = decide(a, apply_edit(a, hyp().edit), hyp(), res(0.0, 0.0), 0.0, 1, [], ENV, version="v3", hypothesis_index=1)
    assert d.cost_basis == "tokens" and d.cost_ratio == 1.0
