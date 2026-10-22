"""Part 2 Step 2 finding: a claude-sonnet+gemma-verify run printed "no price" and Box 4's USD limit was off, because
prices.yaml held null for gemma-4-31b-it while the router's registry (models.yaml) prices it at 0 (free tier). The two
tables must agree, so a mixed run gets one cost."""
import yaml

from amoeba.llm.limits import PRICES, estimate, load_prices

REGISTRY = yaml.safe_load((PRICES.parent / "models.yaml").read_text(encoding="utf-8"))["registry"]


def test_every_priced_registry_model_has_the_same_price_in_prices_yaml():
    table = load_prices()
    for name, e in REGISTRY.items():
        p = e.get("price") or {}
        if p.get("input") is None or p.get("output") is None:
            continue
        got = table.get(e["model"]) or {}
        assert (got.get("input"), got.get("output")) == (p["input"], p["output"]), (name, e["model"], got, p)


def test_a_sonnet_and_gemma_run_has_a_cost():
    spans = [{"gen_ai.request.model": "claude-sonnet-5-5", "gen_ai.usage.input_tokens": 1_000_000,
              "gen_ai.usage.output_tokens": 100_000},
             {"gen_ai.request.model": "gemma-4-31b-it", "gen_ai.usage.input_tokens": 500_000,
              "gen_ai.usage.output_tokens": 10_000}]
    assert estimate(spans, "claude-sonnet-5-5")["cost_usd"] == 3.0


def test_a_refused_call_with_no_tokens_does_not_unprice_the_run():
    spans = [{"gen_ai.request.model": "claude-sonnet-5-5", "gen_ai.usage.input_tokens": 1_000_000,
              "gen_ai.usage.output_tokens": 0},
             {"gen_ai.request.model": "some-unpriced-label"}]     # NoModelAvailable: the call never ran
    assert estimate(spans, "claude-sonnet-5-5")["cost_usd"] == 2.0
