"""The claude-sonnet profile: Claude Sonnet 5.5 through Claude's OpenAI-compatible endpoint. Its `temperature: omit`
keeps the field out of every request (the endpoint rejects values below 1); every other profile still sends 0.2.
--profile limits the plan runner's router (D97) to the registry entry with the profile's model. Offline."""
import pytest

from amoeba.llm.profiles import get_profile, load_profiles, temperature_setting
from amoeba.llm.router import load_registry
from scripts import list_models
from scripts.run_task import build_llm, parse_args
from tests.test_profiles import clean_env  # noqa: F401  (fixture)
from tests.test_rate_limits import client


def test_the_profile_and_its_registry_entry():
    p = get_profile("claude-sonnet")
    assert (p.base_url, p.model, p.api_key_env) == ("https://api.anthropic.com/v1/", "claude-sonnet-5-5", "CLAUDE_API_KEY")
    assert p.temperature is None and p.reasoning_effort is None and not p.merge_system
    reg, policy = load_registry()
    e = reg["claude-sonnet-5-5"]
    assert e.temperature is None and e.family == "claude" and e.price["input"] == 2.0 and e.price["output"] == 10.0
    assert e.price["cache_read"] == 0.2 and e.provider == "anthropic"                 # D134
    assert get_profile("claude-sonnet").provider == "anthropic" and get_profile("claude-sonnet-compat").provider is None
    assert policy["default_model"] == "gemma-4-31b"                      # Gemma stays the default


def test_every_other_profile_and_entry_keeps_temperature_0_2():
    _, profiles = load_profiles()
    claude = {"claude-sonnet", "claude-sonnet-compat"}
    assert {n: p.temperature for n, p in profiles.items() if n not in claude} == \
        {n: 0.2 for n in profiles if n not in claude}
    assert load_registry()[0]["gemma-4-31b"].temperature == 0.2


def test_the_setting_is_a_number_or_omit():
    assert temperature_setting({}, "x") == 0.2 and temperature_setting({"temperature": 1}, "x") == 1.0
    assert temperature_setting({"temperature": "omit"}, "x") is None
    with pytest.raises(ValueError, match="number or omit"):
        temperature_setting({"temperature": "low"}, "x")


def test_the_client_omits_temperature_only_when_told():
    claude, _, sent = client(["ok"], temperature=None)
    claude.chat("You are X.", "Do Y.")
    assert "temperature" not in sent[0] and "reasoning_effort" not in sent[0]
    gemma, _, sent2 = client(["ok"], merge_system=True)                   # the gemma-api settings
    gemma.chat("You are X.", "Do Y.")
    assert sent2[0]["temperature"] == 0.2


def test_the_profile_limits_the_plan_router_to_its_model(clean_env):
    clean_env.setenv("CLAUDE_API_KEY", "test-key")
    clean_env.setenv("GEMINI_API_KEY", "test-key")
    plan = ["--llm", "openai", "--topology", "plan", "--tasks", "x.jsonl"]
    claude = build_llm(parse_args([*plan, "--profile", "claude-sonnet"]))
    assert claude.profile_allowed == ["claude-sonnet-5-5"]
    assert claude.make(claude.registry["claude-sonnet-5-5"]).temperature is None
    from amoeba.llm.anthropic_client import AnthropicClient
    from amoeba.llm.client import OpenAICompatibleClient
    assert isinstance(claude.make(claude.registry["claude-sonnet-5-5"]), AnthropicClient)           # D134
    compat = build_llm(parse_args([*plan, "--profile", "claude-sonnet-compat"]))
    assert compat.profile_allowed == ["claude-sonnet-5-5-compat"]
    assert isinstance(compat.make(compat.registry["claude-sonnet-5-5-compat"]), OpenAICompatibleClient)
    for argv in ([*plan, "--profile", "gemma-api"], plan):                 # Gemma: never routed to Claude, even
        r = build_llm(parse_args(argv))                                    # with CLAUDE_API_KEY set (verify steps)
        assert r.profile_allowed == ["gemma-4-31b"]
        assert r.make(r.registry["gemma-4-31b"]).temperature == 0.2


def test_the_model_list_sends_the_anthropic_version_header_to_claude_only():
    assert list_models.anthropic_headers("https://api.anthropic.com/v1/") == {"anthropic-version": "2023-06-01"}
    assert list_models.anthropic_headers("https://generativelanguage.googleapis.com/v1beta/openai/") == {}


def test_the_usage_label_is_the_model_the_calls_asked_for():
    """A routed Claude run was labelled with the registry's default model (gemma-4-31b) in result.json."""
    from amoeba.llm.limits import estimate
    from scripts.run_task import models_of
    span = {"name": "chat", "gen_ai.request.model": "claude-sonnet-5-5", "gen_ai.response.model": "claude-sonnet-5-5",
            "gen_ai.usage.input_tokens": 1_000_000, "gen_ai.usage.output_tokens": 100_000}
    u = estimate([span, dict(span)], "gemma-4-31b")
    assert u["model"] == "claude-sonnet-5-5" and u["cost_usd"] == 2 * (2.0 + 1.0)    # $2/M in, $10/M out, two calls
    assert estimate([], "gemma-4-31b")["model"] == "gemma-4-31b"                   # no call: the caller's name

    class Router:
        registry, models, model = {}, {"all": "gemma-4-31b-it"}, "gemma-4-31b"

    class Trace:
        def spans(self, name):
            return [span]
    assert models_of(Router(), Trace()) == {"requested": {"all": "claude-sonnet-5-5"}, "returned": ["claude-sonnet-5-5"]}
