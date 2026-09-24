"""D47 — opt-in per-run limits and the cost estimate.

Phase 1 recorded tokens and never enforced them (spec §2). This module is the only place that reads the token
count to stop a run, and only when the user sets --max-tokens-per-run or --max-calls-per-run: the check runs before
each LLM call, and when a limit is reached the call is not made, a `budget_stop` event is logged and RunLimitReached
ends the run with error "budget" (everything so far is saved). Replies served from the response cache (D46) cost
nothing and do not count. The cost estimate prices billed tokens from amoeba/config/prices.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

PRICES = Path(__file__).resolve().parents[1] / "config" / "prices.yaml"


class RunLimitReached(RuntimeError):
    code = "budget"          # the run's error field


@dataclass
class RunLimits:
    max_tokens: int | None = None      # billed tokens: input + output + reasoning of live (not cached) calls
    max_calls: int | None = None       # live LLM calls

    def active(self) -> bool:
        return bool(self.max_tokens or self.max_calls)

    def check(self, trace) -> None:
        """Called before an LLM call; raises when the next call would start past a limit."""
        used = billed(trace.spans("chat"))
        over = (self.max_calls and used["calls"] >= self.max_calls) or \
               (self.max_tokens and used["tokens"] >= self.max_tokens)
        if over:
            trace.event("budget_stop", {"amoeba.limit.max_tokens": self.max_tokens,
                                        "amoeba.limit.max_calls": self.max_calls,
                                        "amoeba.used.tokens": used["tokens"], "amoeba.used.calls": used["calls"]})
            raise RunLimitReached(f"run limit reached after {used['calls']} calls and {used['tokens']} tokens "
                                  f"(max_calls={self.max_calls}, max_tokens={self.max_tokens})")


def billed(chat_spans: list[dict]) -> dict:
    """Token use of the live calls (cache hits excluded)."""
    live = [s for s in chat_spans if not s.get("amoeba.cache_hit")]
    ins = sum(s.get("gen_ai.usage.input_tokens", 0) for s in live)
    outs = sum(s.get("gen_ai.usage.output_tokens", 0) for s in live)
    reas = sum(s.get("amoeba.usage.reasoning_tokens", 0) for s in live)
    return {"calls": len(live), "input": ins, "output": outs, "reasoning": reas, "tokens": ins + outs + reas,
            "cached_calls": len(chat_spans) - len(live)}


def load_prices(path: str | Path = PRICES) -> dict:
    p = Path(path)
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}


def estimate(chat_spans: list[dict], model: str, prices: dict | None = None) -> dict:
    """Billed tokens and, when the model has prices, the estimated cost in USD (else cost_usd is None)."""
    use = billed(chat_spans)
    price = (load_prices() if prices is None else prices).get(model) or {}
    pin, pout = price.get("input"), price.get("output")
    cost = None if pin is None or pout is None else \
        round(use["input"] / 1e6 * pin + (use["output"] + use["reasoning"]) / 1e6 * pout, 6)
    return {**use, "model": model, "cost_usd": cost}


def describe(u: dict) -> str:
    cost = f"est. cost ${u['cost_usd']:.4f}" if u["cost_usd"] is not None else \
        f"no price for {u['model']} in amoeba/config/prices.yaml (tokens only)"
    cached = f", {u['cached_calls']} cached call(s) free" if u["cached_calls"] else ""
    return (f"tokens: {u['input']:,} in, {u['output']:,} out, {u['reasoning']:,} reasoning over {u['calls']} "
            f"call(s){cached} · {cost}")
