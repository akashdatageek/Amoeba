"""D135 — check a model before Amoeba uses it: one tiny call per call type, then one structured call per output mode.

    python -m scripts.model_check <profile> [--budget-usd 0.25] [--protocol v2|legacy] [--write]

Each probe uses Amoeba's real prompt builders on a toy task and stops right after its own call (a gate in front of the
client refuses every other call): the task reading (Box 1), the planner (one round) and its first observer (Box 2), one
native-tools step turn (Box 3), the fix proposer (Box 4) and the pool pick. Then one call per output mode, in order:
`schema` (the API's structured output), `submit_tool` (a tool named submit_<kind>, not forced) and `json_prompt` (JSON
asked for in the prompt, validated by pydantic, one repair call). Each probe records ok / blocked (+ refusal category)
/ unreadable, latency, tokens and cost; the result goes to data/model_checks/<entry>.json and a table is printed.
--write sets the registry entry's supports.tools, supports.output_mode and checked_at in models.yaml (the diff is
shown). A refusal because a prompt asks for written-out reasoning (`reasoning_extraction`) fails the check (exit 2)
and names the prompt file. The key comes only from the environment (the profile's api_key_env); it is never printed.
Never run by pytest (tests/test_model_check_d135.py runs it on the mock).
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from amoeba.config.prompts import PROMPT, render
from amoeba.config.schema import AgentSpec, PlanStep, PromptRef, TeamConfig
from amoeba.interp.trace import TracedLLM, TraceWriter, prompt_sources
from amoeba.llm.anthropic_client import claude_schema, is_anthropic, make_client
from amoeba.llm.cache import is_blocked
from amoeba.llm.client import ChatResponse, LLMClient, MockLLMClient, parse_schema_reply
from amoeba.llm.limits import estimate, load_prices
from amoeba.llm.profiles import MODELS, get_profile

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "model_checks"
TOY = ("A delivery van drives 120 km a day, 5 days a week, and uses 9 litres of diesel per 100 km. Diesel costs 1.80 "
       "EUR per litre. What is the van's weekly fuel cost?")
MODES = ("schema", "submit_tool", "json_prompt")


# box: client
class Probed(RuntimeError):
    """The gate stopped the pipeline after the probe's own call."""


# box: client
class ToyAnswer(BaseModel):
    """The structured reply every output-mode probe asks for."""
    weekly_cost_eur: float = Field(description="the weekly fuel cost in EUR")
    working: str = Field(description="the calculation, in one line")
    unit: str = Field(description="the currency")


# box: client
class Gate(LLMClient):
    """Lets through only `allow` calls of each kind (MockLLMClient's classification of the prompt) and keeps each
    reply; any other call raises Probed, so a pipeline stops right after the probe's own call."""

    def __init__(self, inner: LLMClient):
        self.inner, self.model = inner, inner.model
        self.allow: Counter = Counter()
        self.replies: list[tuple[str, list, ChatResponse]] = []
        self.stopped_at: str | None = None

    def chat_messages(self, messages, seed=0, max_tokens=None, **kw):
        kind = MockLLMClient.classify(messages)
        if self.allow[kind] <= 0:
            self.stopped_at = kind
            raise Probed(kind)
        self.allow[kind] -= 1
        resp = self.inner.chat_messages(messages, seed, max_tokens=max_tokens, **kw)
        self.replies.append((kind, messages, resp))
        return resp


# box: client
def toy_team() -> TeamConfig:
    """One helper, one step, the calculator: enough for one real step turn."""
    a = AgentSpec(agent_id="a1", name="Fuel Cost Analyst", role="worker", model="m", tools=["calc"],
                  prompt=PromptRef(system="seed:plan_step_system", user="seed:plan_step"),
                  goal="Work out the van's weekly fuel cost", skills=["arithmetic"])
    step = PlanStep(index=0, agent_ids=["a1"], text="[Fuel Cost Analyst]: Compute the weekly fuel cost",
                    do="compute litres per week from the distance and consumption, then the cost; use calc",
                    output="the weekly cost in EUR with the calculation", done_when="the cost and its calculation are given")
    return TeamConfig(team_id="model-check", name="model check", topology="plan", agents={"a1": a}, edges=[],
                      entry=["a1"], exit="a1", plan=[step])


# box: client
def outcome(resp: ChatResponse | None, readable: bool) -> tuple[str, str | None]:
    if resp is None:
        return "error", None
    if is_blocked(resp):
        return "blocked", resp.refusal_category
    return ("ok" if readable else "unreadable"), None


# ---- the probes ---------------------------------------------------------------------------------------------------
# box: client
def probe_reading(llm: TracedLLM, gate: Gate, seed: int):
    from amoeba.task.interpret import parse_entities, read_task
    gate.allow["interpreter"] = 1
    try:
        read_task(TOY, llm, seed=seed)
    except Probed:
        pass
    resp = last(gate, "interpreter")
    try:
        parse_entities(resp.content if resp else "")
        ok = True
    except Exception:
        ok = False
    return resp, ok, "interpret.txt"


# box: client
def probe_planner_and_observer(llm: TracedLLM, gate: Gate, seed: int):
    """The planner's first draft and the first observer's review (draft_team, the CLI's default d19 prompts)."""
    from amoeba.safety.envelope import Envelope
    from amoeba.task.draft import draft_team
    from amoeba.task.models import Task
    from amoeba.tools.registry import default_registry
    gate.allow.update({"planner": 1, "agent_observer": 1})
    try:
        draft_team(Task(id="model-check", prompt=TOY), gate, Envelope.from_registry(default_registry()), llm.trace,
                   seed=seed, max_rounds=1)
    except Probed:
        pass
    except Exception:
        pass                       # a draft that fails to parse: the replies below say which call
    planner, observer = last(gate, "planner"), last(gate, "agent_observer")
    # a reply is readable when the pipeline went on past it (a repair call of the same kind means it was not)
    planner_ok = planner is not None and (observer is not None or gate.stopped_at not in (None, "planner"))
    observer_ok = observer is not None and gate.stopped_at != "agent_observer"
    return (planner, planner_ok, "autoagents_create_roles.txt"), (observer, observer_ok, "autoagents_check_roles.txt")


# box: client
def probe_step(llm: TracedLLM, gate: Gate, seed: int, protocol: str):
    from amoeba.interp.plan_runner import PlanOptions
    from amoeba.interp.runtime import Interpreter
    from amoeba.task.models import Task
    from amoeba.tools.registry import default_registry
    gate.allow["plan_worker"] = 1
    opts = PlanOptions(native_tools="on", protocol=protocol, tool_access="asked")
    try:
        Interpreter(gate, default_registry(), llm.trace, plan_options=opts).run(toy_team(), Task(id="mc", prompt=TOY),
                                                                                 seed=seed)
    except Probed:
        pass
    resp = last(gate, "plan_worker")
    ok = bool(resp and resp.tool_calls)
    note = f"tool call: {resp.tool_calls[0]['name']}" if ok else ("text, no tool call" if resp and resp.content else "")
    return resp, ok, ("plan_step_v2.txt" if protocol == "v2" else "plan_step.txt"), note


# box: client
def probe_proposer(llm: TracedLLM, gate: Gate, seed: int):
    from amoeba.adapt.proposer import allowed_text, parse_fix
    gate.allow["fix_proposer"] = 1
    user = render(PROMPT.fix_proposer, task=TOY, step="1", card="Name: Fuel Cost Analyst\nGoal: the weekly fuel cost",
                  cause="max_turns", evidence="- turns used: 5; no Final Output from every helper",
                  attempt="status: incomplete (max_turns)\nturns used: 5", team="- Fuel Cost Analyst: computes costs",
                  tools="tools: calc, echo\nskills: none", allowed=allowed_text(["add_role_rule", "split_step"], 2),
                  tried="None yet.")
    try:
        resp = llm.chat_messages([{"role": "user", "content": user}], seed, agent_name="fix_proposer", role="planner",
                                 max_tokens=4096)
    except Probed:
        resp = None
    try:
        parse_fix(resp.content if resp else "")
        ok = True
    except Exception:
        ok = False
    return resp, ok, "fix_proposer.txt"


# box: client
def probe_pick(llm: TracedLLM, gate: Gate, seed: int):
    from amoeba.pool.stock import pick
    from amoeba.task.models import CapabilityRequest
    gate.allow["pool_picker"] = 1
    q = CapabilityRequest(name="spreadsheet writer", what_it_does="writes an .xlsx workbook with formulas",
                          input="rows of data", output="an .xlsx file")
    cands = [{"id": "skill-xlsx", "name": "xlsx", "kind": "skill", "description": "create and edit Excel workbooks"},
             {"id": "tool-weather", "name": "weather", "kind": "tool", "description": "current weather by city"}]
    try:
        got = pick(llm, q, "Fuel Cost Analyst", "1. build the workbook", cands, seed, max_tokens=1024)
    except Probed:
        got = None
    return last(gate, "pool_picker"), got is not None, "pool_pick.txt"


# box: client
def schema_messages(extra: str = "") -> list[dict]:
    return [{"role": "system", "content": "You answer with the requested structure only."},
            {"role": "user", "content": TOY + extra}]


# box: client
def probe_mode(llm: TracedLLM, gate: Gate, mode: str, seed: int):
    """One call (json_prompt: plus one repair call) in one output mode; ok when the reply validates as ToyAnswer."""
    gate.allow["other"] += 2
    if mode == "schema":
        resp = llm.chat_messages(schema_messages(), seed, agent_name="model_check", max_tokens=1024, schema=ToyAnswer)
        return resp, resp.parsed is not None, ""
    if mode == "submit_tool":
        spec = {"type": "function", "function": {"name": "submit_toy_answer",
                                                 "description": "submit the answer (call it once when done)",
                                                 "parameters": claude_schema(ToyAnswer)}}
        resp = llm.chat_messages(schema_messages(" Submit the answer with the submit_toy_answer tool."), seed,
                                 agent_name="model_check", max_tokens=1024, tools=[spec])
        call = next((c for c in resp.tool_calls if c["name"] == "submit_toy_answer"), None)
        return resp, bool(call and parse_schema_reply(ToyAnswer, call.get("input") or "") is not None), ""
    ask = (f"\n\nReply with only one JSON object that matches this JSON schema, nothing else:\n"
           f"{json.dumps(claude_schema(ToyAnswer))}")
    resp = llm.chat_messages(schema_messages(ask), seed, agent_name="model_check", max_tokens=1024)
    if parse_schema_reply(ToyAnswer, resp.content) is not None or is_blocked(resp):
        return resp, parse_schema_reply(ToyAnswer, resp.content) is not None, ""
    again = llm.chat_messages(schema_messages(ask) + [{"role": "assistant", "content": resp.content},
                                                      {"role": "user", "content": "That was not valid JSON for the "
                                                       "schema. Reply with only the JSON object."}],
                              seed, agent_name="model_check", max_tokens=1024)
    return again, parse_schema_reply(ToyAnswer, again.content) is not None, "after one repair call"


# box: client
def last(gate: Gate, kind: str) -> ChatResponse | None:
    return next((r for k, _, r in reversed(gate.replies) if k == kind), None)


# ---- the run ------------------------------------------------------------------------------------------------------
# box: client
def registry_entry(profile) -> str | None:
    """The registry entry of a profile: same model, same route (D134)."""
    from amoeba.llm.router import load_registry
    reg, _ = load_registry()
    return next((n for n, e in reg.items() if e.model == profile.model
                 and is_anthropic(e.provider) == is_anthropic(profile.provider)), None)


# box: client
def spent(trace: TraceWriter, model: str) -> float:
    return estimate(trace.spans("chat"), model).get("cost_usd") or 0.0


# box: client
def run_checks(client: LLMClient, model: str, budget: float, protocol: str = "v2", seed: int = 0,
               clock=time.perf_counter) -> dict:
    """Every probe on `client` (the real client, or a mock in the test). Stops before a probe once the budget is
    spent; the rest are recorded as skipped."""
    trace = TraceWriter(None, log_content=True)
    gate = Gate(client)
    llm = TracedLLM(gate, trace)
    rows: list[dict] = []
    calls: list[tuple[str, object]] = [
        ("reading", lambda: probe_reading(llm, gate, seed)),
        ("planner+observer", lambda: probe_planner_and_observer(llm, gate, seed)),
        ("step (native tools)", lambda: probe_step(llm, gate, seed, protocol)),
        ("fix proposer", lambda: probe_proposer(llm, gate, seed)),
        ("pool pick", lambda: probe_pick(llm, gate, seed)),
        *((f"output mode: {m}", (lambda m=m: probe_mode(llm, gate, m, seed))) for m in MODES)]
    for name, fn in calls:
        if spent(trace, model) >= budget:
            rows.append({"probe": name, "status": "skipped", "note": f"budget ${budget:.2f} spent"})
            continue
        before, t0 = len(trace.spans("chat")), clock()
        try:
            got = fn()
        except Exception as e:                       # an API error: recorded, the next probe still runs
            rows.append({"probe": name, "status": "error", "note": f"{type(e).__name__}: {' '.join(str(e).split())[:160]}"})
            continue
        spans = trace.spans("chat")[before:]
        results = got if name == "planner+observer" else (got,)
        for label, res in zip(("planner", "observer") if name == "planner+observer" else (name,), results):
            resp, ok, prompt_file, *note = res
            status, category = outcome(resp, ok)
            span = next((s for s in spans if s.get("gen_ai.agent.name") == {"planner": "planner",
                                                                              "observer": "agent_observer"}.get(label)),
                        None) if name == "planner+observer" else None
            mine = [span] if span else spans
            rows.append({"probe": label, "status": status, "category": category,
                         "prompt_file": prompt_file or None,
                         "prompt_files_found": prompt_sources(next((m for k, m, r in gate.replies if r is resp), []))
                         if status == "blocked" else None,
                         "latency_ms": int((clock() - t0) * 1000) if not span else span.get("latency_ms"),
                         "input_tokens": sum(s.get("gen_ai.usage.input_tokens", 0) for s in mine),
                         "output_tokens": sum(s.get("gen_ai.usage.output_tokens", 0)
                                              + s.get("amoeba.usage.reasoning_tokens", 0) for s in mine),
                         "cost_usd": estimate(mine, model).get("cost_usd"), "note": (note[0] if note else "") or None})
    modes = {r["probe"].split(": ")[1]: r["status"] for r in rows if r["probe"].startswith("output mode")}
    step = next((r for r in rows if r["probe"] == "step (native tools)"), {})
    submit = modes.get("submit_tool") == "ok"
    return {"model": model, "checked_at": date.today().isoformat(), "protocol": protocol, "budget_usd": budget,
            "spent_usd": round(spent(trace, model), 6), "probes": rows,
            "supports": {"tools": step.get("status") == "ok" or submit,
                         "output_mode": next((m for m in MODES if modes.get(m) == "ok"), None)},
            "reasoning_refusals": [r for r in rows if r.get("category") == "reasoning_extraction"]}


# box: client
def table(result: dict) -> str:
    head = f"{'probe':<26} {'status':<11} {'category':<21} {'ms':>6} {'in':>7} {'out':>6} {'usd':>8}  note"
    lines = [head, "-" * len(head)]
    for r in result["probes"]:
        usd = r.get("cost_usd")
        lines.append(f"{r['probe']:<26} {r['status']:<11} {(r.get('category') or ''):<21} "
                     f"{r.get('latency_ms') or '':>6} {r.get('input_tokens') or '':>7} {r.get('output_tokens') or '':>6} "
                     f"{'' if usd is None else f'{usd:.4f}':>8}  {r.get('note') or ''}")
    s = result["supports"]
    lines.append(f"supports.tools={s['tools']}  supports.output_mode={s['output_mode']}  "
                 f"spent=${result['spent_usd']:.4f} (budget ${result['budget_usd']:.2f})")
    return "\n".join(lines)


# box: client
def write_supports(entry: str, supports: dict, checked_at: str, path: Path = MODELS) -> str:
    """Set supports.tools / supports.output_mode / checked_at of one registry entry in models.yaml, keeping every
    comment; returns the unified diff."""
    old = path.read_text(encoding="utf-8")
    lines = old.splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines) if re.match(rf"^  {re.escape(entry)}:\s*(#.*)?$", l))
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^  \S", lines[i]) or re.match(r"^\S", lines[i])),
               len(lines))
    block = lines[start:end]
    sup = next(i for i, l in enumerate(block) if re.match(r"^    supports:", l))
    m = re.match(r"^(    supports:\s*)\{(.*?)\}(.*)$", block[sup].rstrip("\n"))
    fields = dict(kv.split(":", 1) for kv in m.group(2).split(",")) if m else {}
    fields = {k.strip(): v.strip() for k, v in fields.items()}
    fields["tools"] = "true" if supports["tools"] else "false"
    fields["output_mode"] = supports["output_mode"] or "none"
    block[sup] = f"{m.group(1)}{{{', '.join(f'{k}: {v}' for k, v in fields.items())}}}{m.group(3)}\n"
    when = next((i for i, l in enumerate(block) if re.match(r"^    checked_at:", l)), None)
    stamp = f"    checked_at: {checked_at}            # D135: scripts/model_check.py\n"
    if when is None:
        at = sup + 1
        while at < len(block) and re.match(r"^\s+#", block[at]):      # the supports line's comment continues here
            at += 1
        block.insert(at, stamp)
    else:
        block[when] = stamp
    new = "".join(lines[:start] + block + lines[end:])
    path.write_text(new, encoding="utf-8")
    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        "models.yaml", "models.yaml"))


# box: client
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("profile")
    p.add_argument("--budget-usd", type=float, default=0.25)
    p.add_argument("--protocol", choices=["v2", "legacy"], default="v2", help="the step turn's protocol (D136)")
    p.add_argument("--write", action="store_true", help="set supports and checked_at in models.yaml")
    p.add_argument("--out-dir", default=str(OUT_DIR))
    args = p.parse_args(argv)
    prof = get_profile(args.profile)
    key = os.environ.get(prof.api_key_env or "", "")
    if not key:
        print(f"model_check: {prof.api_key_env} is not set (the key comes only from the environment)")
        return 1
    client = make_client(prof.provider, base_url=prof.base_url, api_key=key, model=prof.model,
                         max_tokens=prof.max_tokens or 2048, merge_system=prof.merge_system,
                         reasoning_effort=prof.reasoning_effort, temperature=prof.temperature)
    if not load_prices().get(prof.model) and args.budget_usd:
        print(f"note: no price for {prof.model} in prices.yaml; spend shows as 0")
    result = run_checks(client, prof.model, args.budget_usd, args.protocol)
    entry = registry_entry(prof) or prof.model
    result.update(profile=args.profile, entry=entry, provider=prof.provider or "openai-compatible")
    out = Path(args.out_dir) / f"{entry}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"== model check: profile {args.profile} → {entry} ({result['provider']}), step protocol {args.protocol}")
    print(table(result))
    print(f"written: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    if args.write:
        if registry_entry(prof) is None:
            print(f"--write: no registry entry for {prof.model} on this route; models.yaml unchanged")
        else:
            print(write_supports(entry, result["supports"], result["checked_at"]) or "models.yaml: no change")
    for line in failures(result):
        print(line)
    return 2 if result["reasoning_refusals"] else 0


# box: client
def failures(result: dict) -> list[str]:
    """The loud lines for probes refused because their prompt asks for written-out reasoning."""
    return [f"FAIL: {r['probe']} was refused as reasoning_extraction — the prompt asks for written-out reasoning "
            f"(prompt file: {', '.join(r.get('prompt_files_found') or []) or r.get('prompt_file') or '?'})"
            for r in result["reasoning_refusals"]]


if __name__ == "__main__":
    sys.exit(main())
