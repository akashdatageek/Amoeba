"""D47 — opt-in per-run limits and the cost estimate.

Phase 1 recorded tokens and never enforced them (spec §2). This module is the only place that reads the token
count to stop a run, and only when the user sets --max-tokens-per-run or --max-calls-per-run: the check runs before
each LLM call, and when a limit is reached the call is not made, a `budget_stop` event is logged and RunLimitReached
ends the run with error "budget" (everything so far is saved). Replies served from the response cache (D46) cost
nothing and do not count. The cost estimate prices billed tokens from amoeba/config/prices.yaml.

D122 (Oct 11): a cap must not throw away work that was nearly done.
- Runaway guard (`stall_calls`, on by default from the CLI, adapt.yaml `run_guard`): it counts model calls, never
  tokens, and only once the plan runner has started (a `plan_graph` event), so drafting and the baselines are never
  counted. When that many calls pass with no progress (a step attempt saved for a step not seen before, or a step that
  ends done), the run stops with code "stalled" (`stall_stop` event).
- Finish mode (`finishing`): with a hard cap set, once the run has used `finish_share` of it, the plan runner skips the
  optional extras (in-task fixes, rework after a failed check, dispute resolution, re-planning) and goes straight to the
  steps still owed (`finish_mode` event, once).
- When a cap or the guard stops a plan run, the plan runner assembles the answer from the finished steps by plain code
  instead of returning nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

PRICES = Path(__file__).resolve().parents[1] / "config" / "prices.yaml"


class RunLimitReached(RuntimeError):
    code = "budget"          # the run's error field: "budget" (a cap) or "stalled" (D122: no progress)

    def __init__(self, message: str = "", code: str | None = None):
        super().__init__(message)
        if code:
            self.code = code


# box: client
@dataclass
class RunLimits:
    max_tokens: int | None = None      # billed tokens: input + output + reasoning of live (not cached) calls
    max_calls: int | None = None       # live LLM calls
    stall_calls: int | None = None     # D122: model calls with no progress, once the plan runner started
    finish_share: float = 0.85         # D122: share of a hard cap after which the plan runner finishes
    _armed: bool = field(default=False, repr=False)
    _progress: int = field(default=0, repr=False)
    _mark: int = field(default=0, repr=False)
    _finishing: bool = field(default=False, repr=False)

    def active(self) -> bool:
        return bool(self.max_tokens or self.max_calls or self.stall_calls)

    @staticmethod
    def progress(trace) -> int:
        """D122: progress marks so far: a step attempt saved for a step not seen before, or a step that ends done."""
        seen, n = set(), 0
        for e in trace.events("step_done"):
            k = e.get("amoeba.step")
            if k not in seen or e.get("amoeba.status") == "done":
                n += 1
            seen.add(k)
        return n

    def stalled(self, trace) -> int | None:
        """D122: the calls since the last progress mark when they reach `stall_calls`, else None."""
        if not self.stall_calls:
            return None
        calls = len(trace.spans("chat"))
        if not self._armed:
            if not trace.events("plan_graph"):
                return None
            self._armed, self._mark = True, calls
        p = self.progress(trace)
        if p > self._progress:
            self._progress, self._mark = p, calls
        return calls - self._mark if calls - self._mark >= self.stall_calls else None

    def finishing(self, trace) -> bool:
        """D122: with a hard cap set, whether the run has used `finish_share` of it (logged once)."""
        if not (self.max_tokens or self.max_calls):
            return False
        used = billed(trace.spans("chat"))
        near = bool((self.max_tokens and used["tokens"] >= self.finish_share * self.max_tokens)
                    or (self.max_calls and used["calls"] >= self.finish_share * self.max_calls))
        if near and not self._finishing:
            self._finishing = True
            trace.event("finish_mode", {"amoeba.box": "client", "amoeba.used.tokens": used["tokens"],
                                        "amoeba.used.calls": used["calls"], "amoeba.limit.max_tokens": self.max_tokens,
                                        "amoeba.limit.max_calls": self.max_calls, "amoeba.share": self.finish_share})
        return near

    def check(self, trace) -> None:
        """Called before an LLM call; raises when the next call would start past a limit."""
        used = billed(trace.spans("chat"))
        over = (self.max_calls and used["calls"] >= self.max_calls) or \
               (self.max_tokens and used["tokens"] >= self.max_tokens)
        if over:
            trace.event("budget_stop", {"amoeba.box": "client", "amoeba.limit.max_tokens": self.max_tokens,
                                        "amoeba.limit.max_calls": self.max_calls,
                                        "amoeba.used.tokens": used["tokens"], "amoeba.used.calls": used["calls"]})
            raise RunLimitReached(f"run limit reached after {used['calls']} calls and {used['tokens']} tokens "
                                  f"(max_calls={self.max_calls}, max_tokens={self.max_tokens})")
        quiet = self.stalled(trace)
        if quiet is not None:
            trace.event("stall_stop", {"amoeba.box": "client", "amoeba.limit.stall_calls": self.stall_calls,
                                       "amoeba.calls_without_progress": quiet, "amoeba.used.tokens": used["tokens"],
                                       "amoeba.used.calls": used["calls"]})
            raise RunLimitReached(f"no progress in the last {quiet} model calls (stall_calls={self.stall_calls})",
                                  code="stalled")


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


# box: client
def estimate(chat_spans: list[dict], model: str, prices: dict | None = None) -> dict:
    """Billed tokens and, when every model used has prices, the estimated cost in USD (else cost_usd is None).
    Each call is priced by the model it asked for (D54: a profile may give role groups their own models)."""
    use = billed(chat_spans)
    table = load_prices() if prices is None else prices
    by_model: dict[str, list[dict]] = {}
    for s in chat_spans:
        by_model.setdefault(s.get("gen_ai.request.model") or model, []).append(s)
    cost = 0.0
    for m, spans in (by_model or {model: []}).items():
        price = table.get(m) or {}
        pin, pout = price.get("input"), price.get("output")
        if pin is None or pout is None:
            cost = None
            break
        u = billed(spans)
        cost += u["input"] / 1e6 * pin + (u["output"] + u["reasoning"]) / 1e6 * pout
    # the label is the model the calls asked for (the most-used one when there are several), not the caller's
    # default: a routed Claude run used to be labelled with the registry's default model (gemma-4-31b)
    called = max(by_model, key=lambda m: len(by_model[m])) if chat_spans else model
    out = {**use, "model": called, "cost_usd": None if cost is None else round(cost, 6)}
    if len(by_model) > 1:
        out["models"] = sorted(by_model)
    return out


def describe(u: dict) -> str:
    cost = f"est. cost ${u['cost_usd']:.4f}" if u["cost_usd"] is not None else \
        f"no price for {u['model']} in amoeba/config/prices.yaml (tokens only)"
    cached = f", {u['cached_calls']} cached call(s) free" if u["cached_calls"] else ""
    return (f"tokens: {u['input']:,} in, {u['output']:,} out, {u['reasoning']:,} reasoning over {u['calls']} "
            f"call(s){cached} · {cost}")
