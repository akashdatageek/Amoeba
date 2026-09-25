"""D54 — named model profiles (amoeba/config/models.yaml), per-role models, and the profile and returned model name
on every trace line and in result.json. No network: clients are built but never called; calls go to the mock."""
import json
from types import SimpleNamespace

import pytest

from amoeba.interp.runtime import Interpreter
from amoeba.llm.client import ChatResponse, LLMClient, OpenAICompatibleClient
from amoeba.llm.limits import estimate
from amoeba.llm.profiles import ROLE_GROUPS, RoleRouter, build_router, get_profile, load_profiles, role_group
from amoeba.task.models import Task
from scripts import list_models
from scripts.run_task import build_llm, parse_args, run_one
from tests.conftest import DB_PROMPT
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from tests.conftest import mock
from tests.test_plan_runner import APPROVE, DIAMOND, finish

ENV = ("AMOEBA_BASE_URL", "AMOEBA_MODEL", "AMOEBA_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY")


@pytest.fixture
def clean_env(monkeypatch):
    for k in ENV:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_shipped_profiles():
    default, profiles = load_profiles()
    assert default == "gemma-api" and set(profiles) >= {"gemma-api", "gemma-openrouter", "gemini-flash-lite", "gemini-flash"}
    g = profiles["gemma-api"]
    assert (g.base_url, g.model, g.merge_system, g.reasoning_effort) == (
        "https://generativelanguage.googleapis.com/v1beta/openai/", "gemma-4-31b-it", True, None)   # D57: Gemma rejects it
    o = profiles["gemma-openrouter"]
    assert (o.base_url, o.model, o.merge_system, o.reasoning_effort) == (
        "https://openrouter.ai/api/v1", "google/gemma-4-31b-it:free", True, None)
    assert profiles["gemini-flash-lite"].model == "gemini-3.1-flash-lite" and profiles["gemini-flash"].model == "gemini-3.5-flash"
    assert not profiles["gemini-flash"].merge_system and profiles["gemini-flash"].reasoning_effort is None


@pytest.mark.parametrize("body,msg", [
    ("default: a\nprofiles:\n  a: {base_url: u, model: m, temprature: 0}\n", "unknown key"),
    ("default: a\nprofiles:\n  a: {base_url: u, model: m, roles: {writers: {model: x}}}\n", "unknown role group"),
    ("default: a\nprofiles:\n  a: {base_url: u, model: m, roles: {planner: {modle: x}}}\n", "unknown key"),
    ("default: b\nprofiles:\n  a: {base_url: u, model: m}\n", "default profile 'b'"),
])
def test_bad_profile_files_are_refused(tmp_path, body, msg):
    (tmp_path / "m.yaml").write_text(body)
    with pytest.raises(ValueError, match=msg):
        load_profiles(tmp_path / "m.yaml")


def test_unknown_profile_name():
    with pytest.raises(ValueError, match="unknown profile 'nope'"):
        get_profile("nope")


def test_default_is_gemma_api(clean_env):
    clean_env.setenv("GEMINI_API_KEY", "k-gemini")
    llm = build_llm(parse_args(["--toy", "--llm", "openai"]))
    c = llm.default
    assert isinstance(llm, RoleRouter) and llm.profile == "gemma-api" and llm.model == "gemma-4-31b-it"
    assert isinstance(c, OpenAICompatibleClient) and str(c._client.base_url).startswith(
        "https://generativelanguage.googleapis.com/v1beta/openai")
    assert c.merge_system and c.reasoning_effort is None and c._client.api_key == "k-gemini"


def test_mock_stays_the_default_and_is_not_routed():
    llm = build_llm(parse_args(["--toy"]))
    assert not hasattr(llm, "route") and getattr(llm, "profile", None) is None


def test_env_vars_and_flags_still_override(clean_env):
    clean_env.setenv("AMOEBA_BASE_URL", "http://localhost:8000/v1")
    clean_env.setenv("AMOEBA_MODEL", "qwen2.5")
    clean_env.setenv("AMOEBA_API_KEY", "k-amoeba")
    clean_env.setenv("GEMINI_API_KEY", "k-gemini")
    llm = build_llm(parse_args(["--toy", "--llm", "openai", "--no-merge-system", "--reasoning-effort", "unset"]))
    c = llm.default
    assert llm.profile == "gemma-api" and c.model == "qwen2.5" and str(c._client.base_url).startswith("http://localhost:8000")
    assert c._client.api_key == "k-amoeba" and not c.merge_system and c.reasoning_effort is None
    llm = build_llm(parse_args(["--toy", "--llm", "openai", "--profile", "gemma-openrouter", "--model", "m2"]))
    assert llm.profile == "gemma-openrouter" and llm.model == "m2" and llm.default.reasoning_effort is None


def test_profile_key_variable(clean_env):
    clean_env.setenv("OPENROUTER_API_KEY", "k-or")
    llm = build_llm(parse_args(["--toy", "--llm", "openai", "--profile", "gemma-openrouter"]))
    assert llm.default._client.api_key == "k-or" and str(llm.default._client.base_url).startswith("https://openrouter.ai")


def test_eval_draft_takes_a_profile(clean_env):
    from scripts.eval_draft import parse_args as eval_args
    assert build_llm(eval_args(["--llm", "openai", "--profile", "gemini-flash"])).model == "gemini-3.5-flash"


def test_role_groups():
    assert role_group("planner") == "planner" and role_group("plan_observer") == "observers"
    assert role_group("Cost Analyst") == "workers" and role_group("X", is_summariser=True) == "summariser"
    assert role_group("X", role="critic") == "reviewers" and role_group("X", reviewing=True) == "reviewers"


class Named(LLMClient):
    """A stand-in for one endpoint model: the mock answers, the API 'returns' a dated model name."""

    def __init__(self, base, model):
        self.base, self.model = base, model

    def chat_messages(self, messages, seed=0, max_tokens=None) -> ChatResponse:
        r = self.base.chat_messages(messages, seed, max_tokens=max_tokens)
        r.model = f"{self.model}-001"
        return r


PROFILE = SimpleNamespace(name="test-profile", model="m-work", roles={
    "planner": {"model": "m-plan", "max_tokens": 1234}, "observers": {"model": "m-obs"},
    "reviewers": {"model": "m-rev"}, "summariser": {"model": "m-sum", "max_tokens": 999}})


def test_each_role_group_gets_its_model(task, envelope, trace, tools):
    base = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=finish)
    made = []
    llm = build_router(PROFILE, lambda m: made.append(m) or Named(base, m))
    cfg = instantiate(draft_team(task, llm, envelope, trace, prompts="d24"), "plan", task, envelope)
    Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    assert sorted(made) == ["m-obs", "m-plan", "m-rev", "m-sum", "m-work"]          # one client per model
    seen = {}
    for s in trace.spans("chat"):
        seen.setdefault(s["amoeba.role_group"], set()).add(
            (s["gen_ai.request.model"], s["gen_ai.response.model"], s["gen_ai.request.max_tokens"]))
    assert seen["planner"] == {("m-plan", "m-plan-001", 1234)}                     # profile's reply limit wins
    assert {m for m, _, _ in seen["observers"]} == {"m-obs"}
    assert {m for m, _, _ in seen["workers"]} == {"m-work"}                          # steps 1, 2
    assert {m for m, _, _ in seen["reviewers"]} == {"m-rev"}                         # step 3 cross-checks
    assert seen["summariser"] == {("m-sum", "m-sum-001", 999)}                     # step 4
    assert llm.models == {"planner": "m-plan", "observers": "m-obs", "workers": "m-work", "reviewers": "m-rev",
                          "summariser": "m-sum", "pool": "m-work"}   # D56: pool defaults to workers


def test_command_line_reply_limits_win_over_the_profile():
    llm = build_router(PROFILE, lambda m: Named(None, m), keep_max_tokens=set(ROLE_GROUPS) - {"planner"})
    assert llm.route("planner")[1] is None and llm.route("summariser")[1] == 999


def test_profile_and_returned_model_on_every_trace_line_and_in_result_json(tmp_path, envelope, tools):
    base = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=finish)
    llm = build_router(PROFILE, lambda m: Named(base, m))
    r = run_one(Task(id="db", prompt=DB_PROMPT), "plan", llm, envelope, tools, tmp_path, draft_prompts="d24")
    lines = [json.loads(x) for x in (tmp_path / r.run_id / "trace.jsonl").read_text().splitlines()]
    assert lines and all(x["amoeba.profile"] == "test-profile" for x in lines)
    assert all(x["gen_ai.response.model"].endswith("-001") for x in lines if x["name"] == "chat")
    saved = json.loads((tmp_path / r.run_id / "result.json").read_text())
    assert saved["profile"] == "test-profile"
    assert saved["models"]["requested"]["reviewers"] == "m-rev"
    assert saved["models"]["returned"] == ["m-obs-001", "m-plan-001", "m-rev-001", "m-sum-001", "m-work-001"]


def test_mock_runs_record_no_profile(tmp_path, envelope, tools):
    from amoeba.llm.toy_mock import toy_mock_client
    r = run_one(Task(prompt="Compute 17 * 23 + 5.", ground_truth="396"), "flat", toy_mock_client(), envelope, tools,
                tmp_path)
    saved = json.loads((tmp_path / r.run_id / "result.json").read_text())
    assert saved["profile"] is None and saved["models"]["requested"] == {"default": "toy-mock"}


def test_cost_is_priced_per_model():
    spans = [{"gen_ai.request.model": "a", "gen_ai.usage.input_tokens": 1_000_000, "gen_ai.usage.output_tokens": 0},
             {"gen_ai.request.model": "b", "gen_ai.usage.input_tokens": 1_000_000, "gen_ai.usage.output_tokens": 0}]
    u = estimate(spans, "a", {"a": {"input": 1.0, "output": 2.0}, "b": {"input": 3.0, "output": 4.0}})
    assert u["cost_usd"] == 4.0 and u["models"] == ["a", "b"]
    assert estimate(spans, "a", {"a": {"input": 1.0, "output": 2.0}})["cost_usd"] is None   # b has no price


def test_list_models_marks_the_profile_models(clean_env, capsys):
    ids = ["models/gemma-4-31b-it", "models/gemini-3.5-flash", "models/embedding-001"]
    fake = SimpleNamespace(models=SimpleNamespace(list=lambda: [SimpleNamespace(id=i) for i in ids]))
    assert list_models.main(["--profile", "gemma-api"], make_client=lambda: fake) == 0
    out = capsys.readouterr().out
    assert "* models/gemma-4-31b-it" in out and "  models/gemini-3.5-flash" in out
    assert list_models.main(["--profile", "gemma-openrouter", "--filter", "gemma"], make_client=lambda: fake) == 1
    out = capsys.readouterr().out
    assert "not offered here: google/gemma-4-31b-it:free" in out and "embedding" not in out
