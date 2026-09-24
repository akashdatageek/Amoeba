"""CLI (spec §10): draft a team for a task, run it, write runs/<run_id>/{team.yaml, plan.json, trace.jsonl,
capability_requests.json, result.json}.

    python -m scripts.run_task "Reverse the string 'adaptive' then uppercase it" --topology flat
    python -m scripts.run_task --toy --seed 0 --n 20 --topology boss_reviewers
    python -m scripts.run_task ... --llm openai --base-url http://localhost:8000/v1 --model qwen2.5
    AMOEBA_BASE_URL=... AMOEBA_API_KEY=... AMOEBA_MODEL=... python -m scripts.run_task --toy --llm openai
    python -m scripts.run_task --toy --llm openai --profile gemini-flash-lite     # D54: amoeba/config/models.yaml
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from uuid import uuid4

from amoeba.config.io import dump_yaml
from amoeba.interp.runtime import Interpreter
from amoeba.interp.trace import TraceWriter
from amoeba.llm.client import LLMClient, OpenAICompatibleClient
from amoeba.llm.toy_mock import toy_mock_client
from amoeba.safety.envelope import Envelope
from amoeba.task.draft import DraftError, draft_team
from amoeba.task.evaluate import rubric_score, score
from amoeba.task.instantiate import instantiate
from amoeba.task.models import RunResult, Task
from amoeba.task.source import ToyTaskSource
from amoeba.tools.registry import ToolRegistry, default_registry
from amoeba.interp.provenance import total as total_provenance
from amoeba.task.saved_drafts import load_saved_drafts, pick
from amoeba.llm.cache import CachedLLM, CachedProvider, CacheMiss
from amoeba.llm.limits import RunLimitReached, RunLimits, describe, estimate
from amoeba.llm.profiles import ROLE_GROUPS, build_router, get_profile
from amoeba.tools.web import TavilyProvider, web_registry


def run_one(task: Task, topology: str, llm: LLMClient, envelope: Envelope, tools: ToolRegistry,
            runs_dir: str | Path, seed: int = 0, log_content: bool = False, draft_prompts: str = "d19",
            max_tokens: dict | None = None, quality_gate: bool = False, plan_options=None,
            saved_draft=None, limits: RunLimits | None = None, ask=None) -> RunResult:
    """One run: Box 2 drafts a team (or `saved_draft`, a SavedDraft, is reused — D45), Box 3 runs it, Box 1 scores.
    ask: D53 --interactive — a function like input(); the user checks the draft before Box 3 and may clarify once."""
    run_id = str(uuid4())
    run_dir = Path(runs_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace = TraceWriter(run_dir / "trace.jsonl", episode_id=run_id, log_content=log_content,
                        stamp={"amoeba.profile": getattr(llm, "profile", None)})   # D54: on every line
    trace.limits = limits          # D47: checked before every LLM call when set
    t0 = time.perf_counter()
    draft = ep = failed = clarification = None
    answer = error = None
    team_id = ""
    try:
        if saved_draft is not None:   # D45: reuse a saved Box 2 draft; no drafting call is made
            draft = saved_draft.draft
            trace.event("draft_reused", {"amoeba.draft_source": saved_draft.source, "amoeba.task_id": task.id})
        else:
            draft = draft_team(task, llm, envelope, trace, seed, prompts=draft_prompts, max_tokens=max_tokens,
                               quality_gate=quality_gate)
            if ask is not None:       # D53: the user reads the draft's intake before Box 3 runs
                print(intake_text(draft))
                clarification = ask_user(ask)
                trace.event("intake_review", {"amoeba.clarification": clarification, "amoeba.redraft": bool(clarification)})
                if clarification:     # appended to the task; one re-draft round revising the draft just shown
                    (run_dir / "plan.first.json").write_text(draft.model_dump_json(indent=2), encoding="utf-8")
                    task = task.model_copy(update={"prompt": f"{task.prompt}\n\nUser clarification: {clarification}"})
                    draft = draft_team(task, llm, envelope, trace, seed, prompts=draft_prompts, max_tokens=max_tokens,
                                       quality_gate=quality_gate, max_rounds=1, history=draft.raw_draft)
        cfg = instantiate(draft, topology, task, envelope)
        team_id = cfg.team_id
        dump_yaml(cfg, run_dir / "team.yaml")
        ep = Interpreter(llm, tools, trace, run_dir=run_dir, plan_options=plan_options).run(cfg, task, seed)
        answer, error = ep.answer, ep.error
    except DraftError as e:
        error = f"draft: {e}"
        failed = e
    except RunLimitReached as e:      # D47: a limit reached while drafting; what exists is saved below
        error = e.code
    except CacheMiss as e:            # D46: replay mode never falls back to a live call
        error = f"cache_miss: {e}"
        trace.event("cache_miss", {"error.type": str(e)[:300]})
    finally:
        # a failed draft is kept too: the error and every round up to it
        saved = draft.model_dump(mode="json") if draft else \
            {"error": error, "rounds": [r.model_dump(mode="json") for r in (failed.rounds if failed else [])]}
        (run_dir / "plan.json").write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
        trace.close()
    # D19/D21: every tool or skill the team asked for and did not get — recorded, never fetched (always written)
    requested = (draft.capability_requests if draft else []) + (ep.requested_capabilities if ep else [])
    (run_dir / "capability_requests.json").write_text(
        json.dumps([q.model_dump() for q in requested], indent=2, ensure_ascii=False), encoding="utf-8")
    # D30: a task with a rubric and no single right answer is scored by the rubric fraction (Box 1, after the run)
    graded = rubric_score(answer, task.rubric) if task.rubric else None
    result = RunResult(
        run_id=run_id, task_id=task.id, team_id=team_id, topology=topology, answer=answer, error=error,
        draft_source=saved_draft.source if saved_draft is not None else None,
        score=score(answer, task.ground_truth) if graded is None or task.ground_truth else graded["score"],
        rubric=graded, provenance=provenance_of(ep), blocked_capabilities=blocked_of(ep),
        answer_assembled_by_code=ep.answer_assembled_by_code if ep else [], figure_ledger=ep.figure_ledger if ep else {},
        refinement=refinement_of(ep, plan_options) if topology == "plan" else {},
        summary_check=next((s["summary_check"] for s in reversed(ep.steps) if "summary_check" in s), {}) if ep else {},
        total_tokens=trace.total_tokens, usage=estimate(trace.spans("chat"), llm.model),
        latency_ms=int((time.perf_counter() - t0) * 1000), n_llm_calls=trace.n_llm_calls,
        draft_rounds=draft.rounds_used if draft else sum(bool(r.plan_observer_raw) for r in (failed.rounds if failed else [])), consensus=draft.consensus if draft else False,
        blocked_steps=ep.blocked_steps if ep else [], requested_capabilities=requested,
        draft_quality=draft.quality if draft else {},
        unmapped_capabilities=sorted({q.name for q in requested if not q.mapped}),
        requests_proposed=draft.requests_proposed if draft else 0,
        requests_dropped_by_observers=draft.requests_dropped_by_observers if draft else 0,
        clarification=clarification, profile=getattr(llm, "profile", None), models=models_of(llm, trace))
    (run_dir / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


def models_of(llm, trace) -> dict:
    """D54: the model each role group was asked for, and the exact model names the API returned."""
    requested = getattr(llm, "models", None) or {"default": llm.model}
    returned = sorted({s["gen_ai.response.model"] for s in trace.spans("chat") if s.get("gen_ai.response.model")})
    return {"requested": requested, "returned": returned}


CONTINUE = "continue"


def intake_text(d) -> str:
    """D53: what --interactive shows after Box 2 — the requirements, the assumptions and the open questions."""
    assumptions = [g for g in d.givens if re.match(r"\W*assum", g, re.I)]
    out = ["", "== Box 2 draft — check it before the team runs (D53)", "Requirements:"]
    out += [f"  {k}: {v}" for k, v in d.requirements.items()] or ["  (none written)"]
    out += ["Assumptions:"] + ([f"  - {a}" for a in assumptions] or ["  (none written)"])
    out += ["Open questions (settled by assumption):"]
    out += [f"  Q{i}. {q['question']}\n      assumed: {q['assumption'] or '(none given)'}"
            for i, q in enumerate(d.open_questions, 1)] or ["  (none)"]
    return "\n".join(out)


def ask_user(ask) -> str | None:
    """Wait for "continue" (None) or an edited assumption (returned). An empty line asks again; end of input is
    "continue"."""
    while True:
        try:
            reply = ask(f"Type '{CONTINUE}' to run the team, or an edited assumption to re-draft once: ").strip()
        except EOFError:
            return None
        if reply.lower() == CONTINUE:
            return None
        if reply:
            return reply


def provenance_of(ep) -> dict:
    """D33: the plan runner's per-step provenance counts and their sum; empty for flat and boss_reviewers."""
    steps = [s for s in (ep.steps if ep else []) if "provenance" in s]
    if not steps:
        return {}
    return {"total": total_provenance([s["provenance"] for s in steps]),
            "steps": {str(s["step"]): s["provenance"] for s in steps}}


def refinement_of(ep, plan_options) -> dict:
    """D50/D51: the refinement settings of a plan run and what they did (latest version of each step)."""
    from dataclasses import asdict
    from amoeba.interp.plan_runner import PlanOptions
    opt = asdict(plan_options or PlanOptions())
    latest = {s["step"]: s for s in (ep.steps if ep else [])}
    refined = [s["refine"] for s in latest.values() if s.get("refine")]
    by: dict[str, int] = {}
    for r in refined:
        by[r["reason"]] = by.get(r["reason"], 0) + 1
    tot = lambda key, when: sum(r[when][key] for r in refined if when in r)
    out = {"self_refine": opt.get("self_refine"), "steps": len(latest), "steps_refined": len(refined),
           "by_reason": by,
           "before": {k: tot(k, "before") for k in ("failed_checks", "untagged", "hallucinated")},
           "after": {k: tot(k, "after") for k in ("failed_checks", "untagged", "hallucinated")}}
    if "collab" in opt:
        collab = [s["collab"] for s in latest.values() if s.get("collab")]
        out.update({"collab": opt["collab"], "collab_steps": len(collab),
                    "collab_agreed": sum(bool(c.get("agreed")) for c in collab),
                    "collab_rounds": sum(c.get("rounds", 0) for c in collab)})
    return out


def blocked_of(ep) -> dict:
    """D36: canonical capability -> how many producer steps (latest version of each; not the answer step) lacked it."""
    latest = {s["step"]: s for s in (ep.steps if ep else []) if not s.get("answer_step")}   # D40: producers only
    counts: dict[str, int] = {}
    for s in latest.values():
        for c in s.get("blocked_canonical", []):
            counts[c] = counts.get(c, 0) + 1
    return dict(sorted(counts.items()))


def cli_plan_options(args: argparse.Namespace):
    """The plan runner's settings from the command line (D39+)."""
    from amoeba.interp.plan_runner import PlanOptions
    return PlanOptions(rerun_stale=args.rerun_stale, max_input_chars=args.max_input_chars,
                       max_summary_input_chars=args.max_summary_input_chars, self_refine=args.self_refine,
                       collab=args.collab)


def cli_token_limits(args: argparse.Namespace) -> dict:
    """D27: --planner-max-tokens / --observer-max-tokens (unset = env or default, see draft.token_limits)."""
    o = args.observer_max_tokens
    return {"planner": args.planner_max_tokens, "agent_observer": o, "plan_observer": o}


def add_client_args(p: argparse.ArgumentParser) -> None:
    """How the model is called — shared by run_task and eval_draft (D46+)."""
    p.add_argument("--profile", default=None,
                   help="with --llm openai: a named profile in amoeba/config/models.yaml (default: its 'default', "
                        "gemma-api); AMOEBA_BASE_URL / AMOEBA_MODEL and --base-url / --model still override (D54)")
    p.add_argument("--llm-cache", default=None, metavar="DIR",
                   help="store every LLM reply (and web tool result) in DIR, keyed by a hash of model, messages, "
                        "max_tokens and temperature (D46)")
    p.add_argument("--llm-cache-mode", choices=["record", "replay", "off"], default="record",
                   help="record: use a stored reply, else call and store; replay: stored replies only, a miss is an "
                        "error (never a live call); off: no cache")
    p.add_argument("--llm-cache-namespace", default="",
                   help="part of every cache key, e.g. the repeat number, so repeats of one prompt stay separate")
    p.add_argument("--max-rate-retries", type=int, default=5,
                   help="retries after HTTP 429/503, with exponential waits (2, 4, 8 … s) or the server's "
                        "Retry-After; a spending-cap 429 is not retried (D48)")
    p.add_argument("--min-seconds-between-calls", type=float, default=0.0,
                   help="wait at least this long between two model calls, for free tiers (D48)")
    p.add_argument("--merge-system", action=argparse.BooleanOptionalAction, default=None,
                   help="put the system message at the top of the user message, for models without a system role "
                        "such as Gemma (D49); default: the profile's setting")
    p.add_argument("--reasoning-effort", choices=["off", "low", "medium", "high", "unset"], default=None,
                   help="sent only when set; 'off' is sent as 'none' (D49); default: the profile's setting; 'unset' "
                        "sends nothing even when the profile sets it")


def endpoint(args: argparse.Namespace, profile) -> tuple[str, str]:
    """D54: (base_url, api key). --base-url > AMOEBA_BASE_URL > the profile; --api-key > AMOEBA_API_KEY > the
    profile's api_key_env variable > OPENAI_API_KEY. The key is never printed or written anywhere."""
    base_url = args.base_url or os.environ.get("AMOEBA_BASE_URL") or profile.base_url
    api_key = (args.api_key or os.environ.get("AMOEBA_API_KEY")
               or (os.environ.get(profile.api_key_env) if profile.api_key_env else None)
               or os.environ.get("OPENAI_API_KEY") or "EMPTY")
    return base_url, api_key


def build_llm(args: argparse.Namespace) -> LLMClient:
    if args.llm == "mock":
        mock = toy_mock_client()
        return CachedLLM(mock, args.llm_cache, args.llm_cache_mode, args.llm_cache_namespace) if args.llm_cache else mock
    # D54: flags win; else the AMOEBA_* env vars; else the profile (amoeba/config/models.yaml)
    profile = get_profile(args.profile)
    base_url, api_key = endpoint(args, profile)
    model = args.model or os.environ.get("AMOEBA_MODEL") or None          # None: the profile's model
    merge = profile.merge_system if args.merge_system is None else args.merge_system
    effort = None if args.reasoning_effort == "unset" else args.reasoning_effort or profile.reasoning_effort

    def make(m: str) -> LLMClient:
        client = OpenAICompatibleClient(base_url=base_url, api_key=api_key, model=m,
                                        max_tokens=profile.max_tokens or 2048, max_rate_retries=args.max_rate_retries,
                                        min_seconds_between_calls=args.min_seconds_between_calls,
                                        merge_system=merge, reasoning_effort=effort)
        return CachedLLM(client, args.llm_cache, args.llm_cache_mode, args.llm_cache_namespace) if args.llm_cache \
            else client
    # a reply limit given on the command line wins over the profile's for that group (D27 flags)
    keep = set(ROLE_GROUPS) - ({"planner"} if getattr(args, "planner_max_tokens", None) else set()) \
        - ({"observers"} if getattr(args, "observer_max_tokens", None) else set())
    return build_router(profile, make, model, keep)


def build_box3_tools(args: argparse.Namespace, tools: ToolRegistry) -> ToolRegistry:
    """A fresh Box 3 registry per run: with --web-tools, web_search/fetch_url (D32), cached when --llm-cache is
    set (D46; replay then needs no Tavily key)."""
    if not args.web_tools:
        return tools
    if args.llm_cache:
        return web_registry(CachedProvider(TavilyProvider, args.llm_cache, args.llm_cache_mode, args.llm_cache_namespace))
    return web_registry()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt", nargs="?", help="a free-text task (cannot be scored)")
    p.add_argument("--toy", action="store_true", help="run generated toy tasks with known answers")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n", type=int, default=20, help="number of toy tasks")
    p.add_argument("--tasks", default=None,
                   help="a .jsonl file of tasks (id, prompt, optional ground_truth or rubric); a task with a rubric "
                        "and no ground_truth is scored by the rubric fraction (D30)")
    p.add_argument("--topology", choices=["flat", "boss_reviewers", "plan"], default="flat",
                   help="plan = the D31 plan runner over depends_on")
    p.add_argument("--llm", choices=["mock", "openai"], default="mock")
    p.add_argument("--base-url", default=None)
    p.add_argument("--model", default=None, help="default: $AMOEBA_MODEL, else the profile's model (D54)")
    p.add_argument("--api-key", default=None)
    p.add_argument("--runs-dir", default="runs")
    p.add_argument("--draft-prompts", choices=["d19", "d24"], default="d19",
                   help="Box 2 prompts: d19 = AutoAgents + D19 edits (default), d24 = ours (spec/BOX2_PROMPT_UPGRADE_D24.md)")
    p.add_argument("--planner-max-tokens", type=int, default=None,
                   help="Planner reply limit (default $AMOEBA_MAX_TOKENS_PLANNER or 8192; D27)")
    p.add_argument("--observer-max-tokens", type=int, default=None,
                   help="both observers' reply limit (default $AMOEBA_MAX_TOKENS_OBSERVER or 8192; D27)")
    p.add_argument("--quality-gate", action="store_true",
                   help="send a draft back (within the round cap) when a hard draft_quality check fails (D28)")
    p.add_argument("--web-tools", action="store_true",
                   help="give Box 3 web_search and fetch_url (Tavily; needs TAVILY_API_KEY). The plan runner hands "
                        "them to roles that asked for web search (D32); Box 2 never sees them")
    p.add_argument("--max-input-chars", type=int, default=6000,
                   help="plan: characters of one input artifact shown to a step (D44)")
    p.add_argument("--max-summary-input-chars", type=int, default=30000,
                   help="plan: characters of all step outputs shown to the summariser (D44)")
    p.add_argument("--drafts-from", default=None, metavar="DIR",
                   help="reuse saved Box 2 drafts instead of drafting: an eval_draft output folder (drafts/<task>.<n>"
                        ".json) or a runs folder (<run_id>/plan.json) (D45)")
    p.add_argument("--draft-pick", type=int, default=0,
                   help="with --drafts-from: use each task's k-th saved draft (0-based; e.g. the repeat number)")
    p.add_argument("--self-refine", choices=["off", "on-issues", "always"], default="on-issues",
                   help="plan: after a step, one refine turn with what plain code found — off: failed checks only; "
                        "on-issues: also untagged figures and unseen [S#]; always: also a self-review when nothing "
                        "was found (D50)")
    p.add_argument("--collab", choices=["concat", "critique"], default="critique",
                   help="plan, multi-role steps: concat = each role writes, outputs joined; critique = the first role "
                        "drafts, the others AGREE or REVISE with numbered issues, it revises (max 2 rounds) (D51)")
    p.add_argument("--interactive", action="store_true",
                   help="after Box 2, print the requirements, assumptions and open questions and wait for 'continue' "
                        "or an edited assumption (appended to the task as 'User clarification: ...', then one "
                        "re-draft round) (D53). Never in eval scripts")
    p.add_argument("--rerun-stale", action="store_true",
                   help="plan: re-run once each step that used a step's output before that step was reworked (D39)")
    add_client_args(p)
    p.add_argument("--max-tokens-per-run", type=int, default=None,
                   help="stop a run cleanly (error='budget') before a call once this many billed tokens were used (D47)")
    p.add_argument("--max-calls-per-run", type=int, default=None,
                   help="stop a run cleanly (error='budget') before its call number N+1 (D47)")
    p.add_argument("--no-log-content", action="store_true",
                   help="leave prompts and replies out of trace.jsonl (they are logged by default)")
    args = p.parse_args(argv)
    if not args.toy and not args.prompt and not args.tasks:
        p.error("give a prompt, --toy or --tasks")
    if args.interactive and args.drafts_from:
        p.error("--interactive reviews a fresh draft; it cannot be combined with --drafts-from")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    llm = build_llm(args)
    tools = default_registry()
    envelope = Envelope.from_registry(tools, model=llm.model)
    if args.tasks:
        tasks = [Task.model_validate_json(l) for l in Path(args.tasks).read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        tasks = ToyTaskSource(args.seed, args.n).tasks() if args.toy else [Task(prompt=args.prompt)]
    saved = load_saved_drafts(args.drafts_from) if args.drafts_from else None
    results = []
    for task in tasks:
        chosen = None
        if saved is not None:
            chosen = pick(saved, task.id, args.draft_pick)
            if chosen is None:
                print(f"[{args.topology}] {task.id}: no saved draft #{args.draft_pick} in {args.drafts_from} — skipped")
                continue
        box3_tools = build_box3_tools(args, tools)   # a fresh source list per run (D32)
        r = run_one(task, args.topology, llm, envelope, box3_tools, args.runs_dir, args.seed,
                    log_content=not args.no_log_content, draft_prompts=args.draft_prompts,
                    max_tokens=cli_token_limits(args), quality_gate=args.quality_gate,
                    plan_options=cli_plan_options(args), saved_draft=chosen,
                    limits=RunLimits(args.max_tokens_per_run, args.max_calls_per_run),
                    ask=input if args.interactive else None)
        results.append(r)
        shown = (r.answer or "").replace("\n", " ")[:60]
        print(f"[{r.topology}] {task.id} score={r.score} tokens={r.total_tokens} calls={r.n_llm_calls} "
              f"rounds={r.draft_rounds} consensus={r.consensus} error={r.error} answer={shown!r}")
        print(f"    {describe(r.usage)}")                                                    # D47
    unmapped = sorted({n for r in results for n in r.unmapped_capabilities})
    if unmapped:   # D29: extend amoeba/capabilities/aliases.yaml with these
        print("unmapped capability names:", ", ".join(unmapped))
    if not results:
        print("== no runs")
        return 1
    scored = [r.score for r in results if r.score is not None]
    n = len(results)
    mean_score = sum(scored) / len(scored) if scored else float("nan")
    print(f"== {args.topology}  n={n}  mean_score={mean_score:.3f}  "
          f"mean_tokens={sum(r.total_tokens for r in results) / n:.1f}  "
          f"mean_llm_calls={sum(r.n_llm_calls for r in results) / n:.2f}  "
          f"(total tokens {sum(r.total_tokens for r in results)}, total calls {sum(r.n_llm_calls for r in results)}, "
          f"errors {sum(r.error is not None for r in results)})  runs in {Path(args.runs_dir).resolve()}")
    costs = [r.usage.get("cost_usd") for r in results]
    print(f"   billed tokens {sum(r.usage.get('tokens', 0) for r in results):,}"
          + (f", est. cost ${sum(costs):.4f}" if all(c is not None for c in costs) else " (no price for this model)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
