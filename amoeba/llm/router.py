"""D97 — the per-call model router. Plain code decides; no model takes part in the decision.

Every LLM call of Boxes 1–9 states a CallSpec (caller role, step, estimated prompt tokens and reply limit, needed
features, data class, the steps it checks) and `ModelRouter.route(spec)` picks the model, in this fixed order:

  a. candidates = registry ∩ allowed (the niche profile's model list ∩ --allowed-models) ∩ available (key present,
     not cooling down after a 429, not marked failing in this run);
  b. hard filters, never relaxed: context window ≥ prompt + reply; the needed features (json, tools, vision);
     sensitive data → privacy local only; estimated USD ≤ what is left of the run USD cap; verifier independence
     (`required` keeps only models of another family than the one that produced the checked work);
  c. choice: the recipe's preference for the role if still a candidate; else the role's default from the profile;
     else the cheapest candidate in the role's size tier (tie → the lowest current load); under verifier
     independence `preferred` a different family wins when one is left, else the same family is used and the
     decision says `verifier_same_family: no alternative`;
  d. failure: retries per D73 stay in the client; a 429 puts the model in cooldown and the next candidate of the same
     tier is tried (with one model: wait for the cooldown); repeated 5xx mark the model failing for the run. No
     candidate left → NoModelAvailable (cause `no_model`, recorded like a blocked capability).

Rate-aware: one token bucket per model (requests and tokens per minute, from the registry), shared by every process
of the machine through a locked file, replaces --min-seconds-between-calls and the fixed 4-at-a-time limit.
Modes (--routing): fixed (one model for every call), role (D54's static per-role profile), routed (this router).
A new model is a registry entry in amoeba/config/models.yaml — no code change.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml

from amoeba.llm.client import ChatResponse, LLMClient, Messages

MODELS = Path(__file__).resolve().parents[1] / "config" / "models.yaml"
ROLES = ("interpreter", "planner", "agent_observer", "plan_observer", "worker", "verifier", "action_observer",
         "summariser", "architect", "pool_picker", "family_classifier")
# the trace's agent names and role groups → the router's caller roles
AGENT_ROLE = {"interpreter": "interpreter", "planner": "planner", "agent_observer": "agent_observer",
              "plan_observer": "plan_observer", "action_observer": "action_observer", "architect": "architect",
              "family_classifier": "family_classifier", "pool_picker": "pool_picker"}
GROUP_ROLE = {"workers": "worker", "reviewers": "verifier", "summariser": "summariser", "pool": "pool_picker",
              "planner": "planner", "observers": "plan_observer"}


# box: router
class NoModelAvailable(RuntimeError):
    """No model passed the hard filters: the call is not made (cause `no_model`)."""
    code = "no_model"


# box: router
@dataclass
class ModelEntry:
    name: str
    provider: str
    model: str
    family: str
    size_tier: str = "large"
    base_url: str | None = None
    api_key_env: str | None = None
    context_window: int = 32768
    max_output: int = 8192
    supports: dict = field(default_factory=dict)
    price: dict = field(default_factory=dict)            # USD per 1M tokens: {input, output}
    rate: dict = field(default_factory=dict)             # {rpm, tpm, rpd}
    privacy: str = "cloud"
    merge_system: bool = False
    reasoning_effort: str | None = None

    def usd(self, input_tokens: int, output_tokens: int) -> float:
        p_in, p_out = (self.price or {}).get("input") or 0.0, (self.price or {}).get("output") or 0.0
        return (input_tokens * p_in + output_tokens * p_out) / 1e6


# box: router
def load_registry(path: str | Path = MODELS) -> tuple[dict[str, ModelEntry], dict]:
    """(name → ModelEntry, routing policy) from models.yaml's `registry` and `routing` blocks."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    reg = {}
    for name, e in (data.get("registry") or {}).items():
        reg[name] = ModelEntry(name=name, **e)
    policy = {"verifier_independence": "preferred", "role_tiers": {}, "role_defaults": {}, "default_model": None,
              **(data.get("routing") or {})}
    if policy["verifier_independence"] not in ("required", "preferred", "off"):
        raise ValueError("routing.verifier_independence must be required | preferred | off")
    return reg, policy


# box: router
@dataclass
class CallSpec:
    role: str
    step: int | None = None
    prompt_tokens: int = 0
    max_output: int = 0
    needs: frozenset = frozenset()
    data_class: str = "normal"
    checks: tuple = ()                                   # verify calls: the steps whose work they check


# box: router
class SharedBucket:
    """Requests and tokens per minute for one model, shared by every process through a locked JSON file."""

    def __init__(self, folder: Path, model: str, rpm: float | None, tpm: float | None, clock=time.time,
                 sleep=time.sleep):
        self.path = Path(folder) / f"{model.replace('/', '_')}.json"
        self.rpm, self.tpm, self.clock, self.sleep = rpm, tpm, clock, sleep
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _wait_needed(self, st: dict, tokens: int) -> float:
        now = self.clock()
        waits = [0.0]
        for kind, cap, need in (("r", self.rpm, 1), ("t", self.tpm, tokens)):
            if not cap:
                continue
            level = min(cap, st.get(kind, cap) + (now - st.get("at", now)) * cap / 60.0)
            st[kind] = level
            if level < need:
                waits.append((need - level) * 60.0 / cap)
        st["at"] = now
        return max(waits)

    def acquire(self, tokens: int = 0) -> float:
        """Block until one request (and `tokens`) fit; returns the seconds waited."""
        if not (self.rpm or self.tpm):
            return 0.0
        waited = 0.0
        while True:
            with open(self.path, "a+", encoding="utf-8") as fh:
                fcntl.flock(fh, fcntl.LOCK_EX)
                fh.seek(0)
                try:
                    st = json.loads(fh.read() or "{}")
                except ValueError:
                    st = {}
                wait = self._wait_needed(st, min(tokens, self.tpm or tokens))
                if wait <= 0:
                    if self.rpm:
                        st["r"] -= 1
                    if self.tpm:
                        st["t"] -= min(tokens, self.tpm)
                    fh.seek(0)
                    fh.truncate()
                    fh.write(json.dumps(st))
                    return waited
            self.sleep(min(wait, 5.0))
            waited += min(wait, 5.0)

    def cooldown(self, seconds: float) -> None:
        """A 429: every process holds off this model for `seconds`."""
        with open(self.path, "a+", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.seek(0)
            try:
                st = json.loads(fh.read() or "{}")
            except ValueError:
                st = {}
            st["cool_until"] = max(st.get("cool_until", 0), self.clock() + seconds)
            fh.seek(0)
            fh.truncate()
            fh.write(json.dumps(st))

    def cooling(self) -> float:
        try:
            st = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except (OSError, ValueError):
            return 0.0
        return max(0.0, st.get("cool_until", 0) - self.clock())


# box: router
def estimate_tokens(messages: Messages) -> int:
    return sum(len(m.get("content") or "") for m in messages) // 4 + 8


# box: router
class ModelRouter(LLMClient):
    """The router of one run. make(entry) builds a client for a registry entry (endpoint, key, options, cache)."""

    def __init__(self, registry: dict[str, ModelEntry], policy: dict, make: Callable[[ModelEntry], LLMClient],
                 mode: str = "routed", allowed: list[str] | None = None, profile_allowed: list[str] | None = None,
                 usd_cap: float | None = None, env=None, rate_dir: str | Path | None = None,
                 recipe_prefs: dict | None = None, fixed_model: str | None = None, clock=time.time, sleep=time.sleep,
                 failing_after: int = 3):
        if mode not in ("fixed", "routed"):
            raise ValueError("ModelRouter modes: fixed | routed (role mode is the D54 RoleRouter)")
        self.registry, self.policy, self.make, self.mode = registry, policy, make, mode
        self.allowed, self.profile_allowed = allowed, profile_allowed
        self.usd_cap, self.env = usd_cap, os.environ if env is None else env
        self.rate_dir = Path(rate_dir or os.environ.get("AMOEBA_RATE_DIR") or Path.home() / ".cache" / "amoeba" / "rate")
        self.recipe_prefs = dict(recipe_prefs or {})
        self.clock, self.sleep, self.failing_after = clock, sleep, failing_after
        self.fixed = fixed_model or policy.get("default_model") or next(iter(registry), None)
        self._clients: dict[str, LLMClient] = {}
        self._buckets: dict[str, SharedBucket] = {}
        self.failures: dict[str, int] = {}
        self.failing: set[str] = set()
        self.step_family: dict[int, str] = {}
        self.usage: dict[str, dict] = {}
        self.decisions: list[dict] = []
        self.data_class = "normal"
        self.model = self.fixed or ""

    def begin_run(self, data_class: str = "normal", recipe_prefs: dict | None = None,
                  usd_cap: float | None = None) -> None:
        """A fresh account for one run (the router object is shared by the runs of one command)."""
        self.data_class = data_class
        self.recipe_prefs = dict(recipe_prefs or {})
        if usd_cap is not None:
            self.usd_cap = usd_cap
        self.usage, self.decisions, self.step_family = {}, [], {}
        self.failures, self.failing = {}, set()

    # -- pieces
    def client(self, name: str) -> LLMClient:
        if name not in self._clients:
            self._clients[name] = self.make(self.registry[name])
        return self._clients[name]

    def bucket(self, name: str) -> SharedBucket:
        if name not in self._buckets:
            r = self.registry[name].rate or {}
            self._buckets[name] = SharedBucket(self.rate_dir, name, r.get("rpm"), r.get("tpm"), self.clock, self.sleep)
        return self._buckets[name]

    def spent_usd(self) -> float:
        return sum(u["usd"] for u in self.usage.values())

    def load(self, name: str) -> int:
        return self.usage.get(name, {}).get("calls", 0)

    def role_tier(self, role: str) -> str:
        return (self.policy.get("role_tiers") or {}).get(role, "large")

    # -- the decision
    def route(self, spec: CallSpec) -> tuple[str, dict]:
        """(model name, decision record). Raises NoModelAvailable when no candidate is left."""
        dec: dict = {"role": spec.role, "step": spec.step, "mode": self.mode, "filtered": {}, "fallbacks": []}
        names = list(self.registry)
        if self.mode == "fixed":
            names = [self.fixed] if self.fixed in self.registry else []
        # a. candidates
        cand = []
        for n in names:
            e = self.registry[n]
            why = None
            if self.profile_allowed is not None and n not in self.profile_allowed:
                why = "not in the niche profile's models"
            elif self.allowed is not None and n not in self.allowed:
                why = "not in --allowed-models"
            elif e.api_key_env and not self.env.get(e.api_key_env):
                why = f"no key ({e.api_key_env})"
            elif n in self.failing:
                why = "failing in this run"
            if why:
                dec["filtered"][n] = why
            else:
                cand.append(n)
        # b. hard filters
        produced = {self.step_family[s] for s in spec.checks if s in self.step_family}
        indep = (self.policy.get("verifier_independence") or "off") if spec.role == "verifier" else "off"
        left = []
        for n in cand:
            e = self.registry[n]
            why = None
            if e.context_window < spec.prompt_tokens + spec.max_output:
                why = f"context {e.context_window} < {spec.prompt_tokens + spec.max_output}"
            elif any(not (e.supports or {}).get(f) for f in spec.needs):
                why = "lacks " + ", ".join(f for f in spec.needs if not (e.supports or {}).get(f))
            elif spec.data_class == "sensitive" and e.privacy != "local":
                why = "sensitive data: local models only"
            elif self.usd_cap is not None and \
                    self.spent_usd() + e.usd(spec.prompt_tokens, spec.max_output) > self.usd_cap + 1e-12:
                why = f"over the run USD cap (${self.usd_cap:.4f})"
            elif indep == "required" and produced and e.family in produced:
                why = f"verifier independence required: same family as the checked work ({e.family})"
            if why:
                dec["filtered"][n] = why
            else:
                left.append(n)
        dec["candidates"] = left
        if not left:
            dec["chosen"] = None
            dec["cause"] = "no_model"
            self.decisions.append(dec)
            raise NoModelAvailable(f"no model for {spec.role}: " + "; ".join(f"{k}: {v}" for k, v in
                                                                              dec["filtered"].items()) or "registry empty")
        # c. choice
        chosen, how = None, ""
        pref = self.recipe_prefs.get(spec.role)
        if self.mode == "fixed":
            chosen, how = left[0], "fixed"
        elif pref in left:
            chosen, how = pref, "recipe preference"
        elif (self.policy.get("role_defaults") or {}).get(spec.role) in left:
            chosen, how = self.policy["role_defaults"][spec.role], "role default"
        else:
            tier = self.role_tier(spec.role)
            pool = [n for n in left if self.registry[n].size_tier == tier] or left
            if indep == "preferred" and produced:
                other = [n for n in pool if self.registry[n].family not in produced] or \
                        [n for n in left if self.registry[n].family not in produced]
                pool = other or pool
            chosen = min(pool, key=lambda n: (self.registry[n].usd(1e6, 1e6), self.load(n), n))
            how = f"cheapest in tier {tier}"
        if indep in ("preferred", "required") and produced:
            if self.registry[chosen].family in produced:
                alt = any(self.registry[n].family not in produced for n in left)
                dec["verifier_same_family"] = "recipe preference" if alt and how == "recipe preference" else \
                    "no alternative"
            dec["checked_family"] = sorted(produced)
        dec.update(chosen=chosen, why=how, family=self.registry[chosen].family)
        self.decisions.append(dec)
        return chosen, dec

    # -- a call
    def call(self, spec: CallSpec, messages: Messages, seed: int, max_tokens: int | None) -> tuple[ChatResponse, dict]:
        while True:
            name, dec = self.route(spec)
            cool = self.bucket(name).cooling()
            if cool > 0:
                others = [n for n in dec["candidates"] if n != name and self.bucket(n).cooling() <= 0
                          and self.registry[n].size_tier == self.registry[name].size_tier]
                if others and self.mode == "routed":           # the next candidate of the same tier
                    dec["fallbacks"].append({"from": name, "to": others[0], "reason": "cooldown"})
                    name = others[0]
                    dec["chosen"], dec["family"] = name, self.registry[name].family
                else:                                          # one model (or fixed mode): wait for the cooldown
                    dec["cooldown_wait_s"] = round(cool, 2)
                    self.sleep(cool)
            dec["rate_wait_s"] = round(self.bucket(name).acquire(spec.prompt_tokens + (max_tokens or 0)), 2)
            try:
                resp = self.client(name).chat_messages(messages, seed, max_tokens=max_tokens)
            except Exception as e:
                status = getattr(e, "status_code", None)
                if status == 429:
                    self.bucket(name).cooldown(60.0)
                    dec["fallbacks"].append({"from": name, "reason": "429", "cooldown_s": 60})
                    if len([n for n in dec["candidates"] if n != name]) == 0:
                        raise                                   # one model: the client already waited and retried
                    continue
                if status is not None and status >= 500 or getattr(e, "amoeba_retries", None):
                    self.failures[name] = self.failures.get(name, 0) + 1
                    if self.failures[name] >= self.failing_after:
                        self.failing.add(name)
                        dec["fallbacks"].append({"from": name, "reason": "failing in this run"})
                        if any(n != name for n in dec["candidates"]):
                            continue
                raise
            if any(r.get("status") == 429 for r in resp.retries or []):
                self.bucket(name).cooldown(min(60.0, max(r.get("wait_s") or 0 for r in resp.retries)))
                dec["rate_limited"] = sum(r.get("status") == 429 for r in resp.retries)
            e = self.registry[name]
            billed_out = resp.output_tokens + (resp.reasoning_tokens or 0)
            usd = 0.0 if resp.cached else e.usd(resp.input_tokens, billed_out)
            u = self.usage.setdefault(name, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0})
            u["calls"] += 1
            u["input_tokens"] += resp.input_tokens
            u["output_tokens"] += billed_out
            u["usd"] = round(u["usd"] + usd, 8)
            dec["usd"] = round(usd, 8)
            if spec.step is not None and spec.role in ("worker", "summariser"):
                self.step_family[spec.step] = e.family
            return resp, dec

    def chat_messages(self, messages: Messages, seed: int = 0, max_tokens: int | None = None) -> ChatResponse:
        resp, _ = self.call(CallSpec(role="worker", prompt_tokens=estimate_tokens(messages),
                                     max_output=max_tokens or 0), messages, seed, max_tokens)
        return resp

    def summary(self) -> dict:
        """For result.json: per-model calls, tokens and USD, and the counts that matter."""
        return {"mode": self.mode, "per_model": self.usage, "usd": round(self.spent_usd(), 6),
                "decisions": len(self.decisions),
                "verifier_same_family": sum(1 for d in self.decisions if d.get("verifier_same_family")),
                "no_model": sum(1 for d in self.decisions if d.get("cause") == "no_model"),
                "fallbacks": sum(len(d.get("fallbacks") or []) for d in self.decisions),
                "cooldown_wait_s": round(sum(d.get("cooldown_wait_s") or 0 for d in self.decisions), 2),
                "rate_wait_s": round(sum(d.get("rate_wait_s") or 0 for d in self.decisions), 2)}

    @property
    def models(self) -> dict[str, str]:
        return {r: self.registry[self.fixed].model if self.fixed in self.registry else "" for r in ("all",)}


# box: router
def spec_for(agent_name: str | None, group: str | None, messages: Messages, max_tokens: int | None,
             step: int | None = None, checks=(), needs=(), data_class: str = "normal") -> CallSpec:
    role = AGENT_ROLE.get(agent_name or "") or GROUP_ROLE.get(group or "") or "worker"
    return CallSpec(role=role, step=step, prompt_tokens=estimate_tokens(messages), max_output=max_tokens or 0,
                    needs=frozenset(needs), data_class=data_class, checks=tuple(checks or ()))
