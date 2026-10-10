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
from amoeba.llm.client import LLMClient, OpenAICompatibleClient, api_error, describe_api_error
from amoeba.llm.toy_mock import toy_mock_client
from amoeba.safety.envelope import Envelope
from amoeba.task.draft import DraftError, draft_team, toolbox_text
from amoeba.task.interpret import (NeedsClarification, apply_clarify, ask_all, ask_one, classify_family,
                                   enforce_opening, open_questions, opening_line, read_task, with_note)
from amoeba.config.niche import add_done_clauses, environment_text, load_profile
from amoeba.memory.context import load_context, standards_slots
from amoeba.interp.trace import TracedLLM
from amoeba.task.evaluate import rubric_score, score
from amoeba.task.instantiate import instantiate
from amoeba.task.deliverables import no_deliverable_of
from amoeba.task.models import RunResult, Task, run_status
from amoeba.task.source import ToyTaskSource
from amoeba.tools.registry import ToolRegistry, default_registry
from amoeba.interp.provenance import total as total_provenance
from amoeba.task.saved_drafts import load_saved_drafts, pick
from amoeba.llm.cache import CachedLLM, CachedProvider, CacheMiss
from amoeba.llm.limits import RunLimitReached, RunLimits, describe, estimate
from amoeba.llm.profiles import ROLE_GROUPS, build_router, get_profile
from amoeba.tools.web import TavilyProvider, web_registry
from amoeba.pool.stock import PoolSetup, SharedPicks, stock_toolbox
from amoeba.localtools.gate import SandboxRequired, require_sandbox
from amoeba.localtools.toolbox import LocalSetup, LocalToolbox
from amoeba.adapt.faults import check_flag


LOCAL_FIELDS = {"files_created", "local_tool_calls", "local_refusals", "skills_attached"}
PHASE2_FIELDS = {"disabled_tools", "routing", "deliverables", "requirement_status", "stuck", "adaptation", "faults"}           # left out of result.json when None (Phase 1 records unchanged)


# box: ov_leave, capreq, runresult
def run_one(task: Task, topology: str, llm: LLMClient, envelope: Envelope, tools: ToolRegistry,
            runs_dir: str | Path, seed: int = 0, log_content: bool = False, draft_prompts: str = "d19",
            max_tokens: dict | None = None, quality_gate: bool = False, plan_options=None,
            saved_draft=None, limits: RunLimits | None = None, ask=None, pool: PoolSetup | None = None,
            local: LocalSetup | None = None, equal_tools: bool = False, picks_file: str | None = None,
            picks_only: bool = False, timezone: str | None = None, interpret: bool = False,
            context=None, disabled_tools=(),
            cli_explicit: frozenset = frozenset(), max_turns: int | None = None,
            default_max_turns: int | None = None, family_classify: bool = False,
            niche=None, deliverable_check: bool = False,
            workspace_sources: bool = False, ask_assumed: str = "off", clarify: dict | None = None) -> RunResult:
    """One run: Box 2 drafts a team (or `saved_draft`, a SavedDraft, is reused — D45), Box 3 runs it, Box 1 scores.
    ask: D53 --interactive — a function like input(); the user checks the draft before Box 3 and may clarify once.
    pool: D56 — Box 3 first stocks the toolbox from the cached pool (None: that step is off).
    local: D59 — --local-tools on: Claude Code's tools and skills (claude mcp serve) in runs/<id>/workspace/.
    picks_file: D70 — one pool pick per task and request, shared by every run of the task; picks_only: stop after
    the toolbox step (a pre-pass that makes the picks before the architectures run).
    interpret: D77 — read the task before planning (task interpretation step); context: the read-only user context
    (--context, amoeba.memory.context.load_context) it reads.
    disabled_tools: D80 --disable-tools — already taken out of `tools`, `pool` and `local` by the caller
    (disable_tools); recorded, and left out of the toolbox Box 2 is shown.
    family_classify: D101 — a free-text task (family "freeform") gets a family from Box 1 (keyword rules, else one
    routed family_classifier call); it is recorded only (D117 removed the recipes it used to select).
    niche: D102 --niche — a NicheProfile (amoeba.config.niche); a neutral one (general) changes nothing. Otherwise
    (plan runner only): its Environment section in Box 1 and Box 2, its tool allowlist enforced in Box 3 (refusals
    logged), its done clauses on the answer step and its domain checks after each step.
    ask_assumed: D116 — "on": every reading the interpretation step would assume (a tie included) is asked about
    before planning, through `ask` or, without it, the terminal; when nobody can be asked the run stops with
    error needs_clarification and writes clarification.json. clarify: D116 --clarify answers {entity: reading}."""
    prof = niche if niche is not None and not niche.is_neutral() else None          # D102: general = None
    if prof is not None and topology != "plan":
        raise ValueError("niche profiles are for Amoeba's plan runner only; the baselines stay as they are (D102)")
    run_id = str(uuid4())
    run_dir = Path(runs_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace = TraceWriter(run_dir / "trace.jsonl", episode_id=run_id, log_content=log_content,
                        stamp={"amoeba.profile": getattr(llm, "profile", None)})   # D54: on every line
    trace.limits = limits          # D47: checked before every LLM call when set
    if hasattr(llm, "begin_run"):  # D97: the router's account for this run (data class)
        llm.begin_run(data_class="sensitive" if "sensitive" in (task.tags or []) else "normal", role_prefs=None)
    t0 = time.perf_counter()
    family_rec = None
    if family_classify and topology == "plan" and task.family == "freeform":      # D101: Box 1 names the family
        family_rec = classify_family(task.prompt, TracedLLM(llm, trace), seed=seed)
        trace.event("task_family", {"amoeba.box": "interpret", "amoeba.family": family_rec["family"],
                                    "amoeba.family_how": family_rec["how"]})
        if family_rec["family"] != "new":
            task = task.model_copy(update={"family": family_rec["family"]})
    if disabled_tools:
        trace.event("tools_disabled", {"amoeba.box": "stream", "amoeba.tools": list(disabled_tools)})
    lessons: dict[str, str] = {}                                                # Box 2's {lessons} slot
    if saved_draft is None and topology == "plan" and (context or {}).get("standards"):   # D99: approved standards
        lessons = dict(lessons)
        for who, text in standards_slots(context).items():
            lessons[who] = lessons.get(who, "") + text
        trace.event("user_standards", {"amoeba.box": "memory", "amoeba.standards": list(context["standards"])})
    env_text = ""
    if prof is not None:                          # D102: one Environment section; Box 3 enforces the tool allowlist
        env_text = environment_text(prof, tools.names())
        tools.niche = prof
        if saved_draft is None:
            lessons = dict(lessons)
            for who in ("planner", "agent_observer", "plan_observer"):
                lessons[who] = lessons.get(who, "") + env_text
        if prof.checks:
            from dataclasses import replace
            from amoeba.interp.plan_runner import PlanOptions
            plan_options = replace(plan_options or PlanOptions(), domain_checks=tuple(prof.checks))
        trace.event("niche", {"amoeba.box": "niche", "amoeba.niche": prof.name, "amoeba.tools": prof.allowed_tools,
                              "amoeba.models": prof.allowed_models, "amoeba.checks": prof.checks,
                              "amoeba.done_when": prof.done_when})
    if deliverable_check and topology == "plan":   # D105 + D110: the final-answer requirement check runs in Box 3
        from dataclasses import replace as _replace
        from amoeba.interp.plan_runner import PlanOptions
        plan_options = _replace(plan_options or PlanOptions(), final_check="on")
    max_turns = max_turns or default_max_turns          # --max-turns, else a harness default (--option-defaults)
    draft = ep = failed = clarification = None
    answer = error = None
    team_id = ""
    requests: list = []
    pool_summary: dict = {"status": "off"} if pool is None else {}
    box = LocalToolbox(local, run_dir, trace) if local is not None else None   # D59: refuses without AMOEBA_SANDBOX=1
    local_out: dict = {}
    interp = None
    cfg = None
    stated: dict = {}
    try:
        if saved_draft is not None:   # D45: reuse a saved Box 2 draft; no drafting call is made
            draft = saved_draft.draft
            interp = draft.interpretation or None                                  # D77: read when it was drafted
            trace.event("draft_reused", {"amoeba.draft_source": saved_draft.source, "amoeba.task_id": task.id})
        else:
            toolbox = toolbox_text(envelope, web="web_search" in tools, local=local is not None, pool=pool is not None,
                                   disabled=disabled_tools)
            if interpret:             # D77: what the task is about is settled before the Planner drafts
                interp = read_task(task.prompt, TracedLLM(llm, trace), context, seed, environment=env_text)
                if interp["ambiguous"] and clarify:              # D116: answers given with --clarify
                    interp = apply_clarify(interp, clarify)
                    if interp.get("clarified"):
                        trace.event("interpretation_clarified", {"amoeba.answers": interp["clarified"]})
                if interp["ambiguous"] and ask_assumed == "on":  # D116: never assume a reading; ask first
                    asker = ask if ask is not None else (input if can_ask() else None)
                    if asker is None:
                        qs = open_questions(interp)
                        (run_dir / "clarification.json").write_text(json.dumps(
                            {"task_id": task.id, "questions": qs, "how": "answer with --clarify 'ENTITY=READING' "
                             "(the words or the option number), one per entity"}, indent=2, ensure_ascii=False),
                            encoding="utf-8")
                        trace.event("clarification_needed", {"amoeba.box": "interpret", "amoeba.questions": qs})
                        raise NeedsClarification(qs)
                    interp = ask_all(interp, asker)
                    trace.event("interpretation_questions", {"amoeba.box": "interpret",
                                                             "amoeba.questions": interp.get("questions", [])})
                elif interp["ambiguous"] and ask is not None:
                    interp = ask_one(interp, ask)
                    trace.event("interpretation_question", {"amoeba.question": interp["question"]})
            task = task.model_copy(update={"prompt": with_note(task.prompt, interp)})
            draft = draft_team(task, llm, envelope, trace, seed, prompts=draft_prompts, max_tokens=max_tokens,
                               quality_gate=quality_gate, toolbox=toolbox, interpretation=interp,   # D68, D77
                               lessons=lessons)                                                       # D82
            if ask is not None:       # D53: the user reads the draft's intake before Box 3 runs
                print(intake_text(draft))
                clarification = ask_user(ask)
                trace.event("intake_review", {"amoeba.clarification": clarification, "amoeba.redraft": bool(clarification)})
                if clarification:     # appended to the task; one re-draft round revising the draft just shown
                    (run_dir / "plan.first.json").write_text(draft.model_dump_json(indent=2), encoding="utf-8")
                    task = task.model_copy(update={"prompt": f"{task.prompt}\n\nUser clarification: {clarification}"})
                    draft = draft_team(task, llm, envelope, trace, seed, prompts=draft_prompts, max_tokens=max_tokens,
                                       quality_gate=quality_gate, max_rounds=1, history=draft.raw_draft,
                                       toolbox=toolbox, interpretation=interp, lessons=lessons)
        task = task.model_copy(update={"prompt": with_note(task.prompt, interp)})    # D77: Box 3 reads it too
        if prof is not None and prof.done_when:           # D102: what "done" means here, on the answer step(s)
            draft, done_steps = add_done_clauses(draft, prof)
            trace.event("niche_done_when", {"amoeba.box": "niche", "amoeba.steps": done_steps})
        cfg = instantiate(draft, topology, task, envelope)
        if max_turns is not None:                         # --max-turns (or a harness default)
            for a in cfg.agents.values():
                a.limits.max_turns = max_turns
        team_id = cfg.team_id
        requests = [q.model_copy(deep=True) for q in draft.capability_requests]
        picks = SharedPicks(picks_file, task.id) if picks_file else None           # D70
        if pool is not None or box is not None:   # D56: Box 3 starts by stocking the toolbox, before the runner
            tools, pool_summary = stock_toolbox(requests, cfg, tools, llm, trace, pool, seed, local=box, picks=picks)
        # D61: what became of each request, for the step contract (an unfilled one is a capability the helper lacks)
        cfg.meta["capability_requests"] = [{"name": q.name, "for_role": q.for_role, "canonical": q.canonical,
                                            "status": q.status, "reason": q.reason} for q in requests]
        dump_yaml(cfg, run_dir / "team.yaml")
        restock = (lambda reqs, c, reg, **kw: stock_toolbox(reqs, c, reg, llm, trace, pool, seed, local=box,
                                                           restock=True, picks=None if kw else picks, **kw)) \
            if (pool is not None or box is not None) else None                   # D63: requests a re-plan makes
        if picks_only:                                                             # D70: the picks pre-pass
            answer, error = None, "picks_only"
        else:
            web = getattr(tools, "web", None)
            if workspace_sources and box is not None and web is not None and topology == "plan":   # D107
                web.on_data = lambda rec, _b=box, _w=web: _b.save_source(rec, _w)
            ep = Interpreter(llm, tools, trace, run_dir=run_dir, plan_options=plan_options, equal_tools=equal_tools,
                             stock=restock, max_agents=envelope.max_agents, timezone=timezone).run(cfg, task, seed)
            answer, error = ep.answer, ep.error
            answer, stated = enforce_opening(answer, interp)     # D77: an assumed subject is stated, by plain code
            if stated:
                trace.event("assumption_stated", {"amoeba.line": opening_line(interp), **{
                    f"amoeba.{k}": v for k, v in stated.items()}})
    except DraftError as e:
        error = f"draft: {e}"
        failed = e
    except RunLimitReached as e:      # D47: a limit reached while drafting; what exists is saved below
        error = e.code
    except NeedsClarification as e:   # D116: a reading would have been assumed and nobody could be asked
        error = f"needs_clarification: {e}"
    except CacheMiss as e:            # D46: replay mode never falls back to a live call
        error = f"cache_miss: {e}"
        trace.event("cache_miss", {"error.type": str(e)[:300]})
    except Exception as e:            # D57: the model service failed after its retries (drafting or the pool pick)
        if not api_error(e):
            raise
        error = f"api: {describe_api_error(e)}"
        trace.event("api_error", {"error.type": error[:300]})
    finally:
        # a failed draft is kept too: the error and every round up to it
        saved = draft.model_dump(mode="json") if draft else \
            {"error": error, "rounds": [r.model_dump(mode="json") for r in (failed.rounds if failed else [])]}
        (run_dir / "plan.json").write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
        if box is not None:           # D59: the server is closed and the workspace copied, whatever happened
            local_out = box.finish()
            trace.event("local_summary", {"amoeba.box": "localtools", **{f"amoeba.local.{k}": v for k, v in local_out.items()}})
        trace.close()
    # D19/D21: every tool or skill the team asked for (always written); D56: with what the toolbox step did about it
    if draft and not requests:
        requests = [q.model_copy(deep=True) for q in draft.capability_requests]
    during = [q.model_copy(update={"status": "unfilled", "reason": "raised_during_run"}) if pool is not None else q
              for q in (ep.requested_capabilities if ep else [])]
    requested = requests + during
    (run_dir / "capability_requests.json").write_text(
        json.dumps([q.model_dump() for q in requested], indent=2, ensure_ascii=False), encoding="utf-8")
    deliverables = requirement_status = None
    fc = getattr(ep, "final_check", None) if ep else None
    if deliverable_check and topology == "plan" and fc:            # D105 + D110: the final-answer requirement check
        deliverables = fc
        requirement_status = {r: x["status"] for r, x in fc["requirements"].items()}
        if error is None or error in ("partial", "incomplete"):
            error = no_deliverable_of(fc) or error
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
        clarification=clarification, profile=getattr(llm, "profile", None), models=models_of(llm, trace),
        replan=ep.replan if ep else {},
        interpretation=interpretation_of(interp, stated),
        pool=pool_summary, disabled_tools=list(disabled_tools) or None, family=family_rec,
        routing=llm.summary() if hasattr(llm, "summary") and hasattr(llm, "registry") else None,
        status=run_status(error), deliverables=deliverables, requirement_status=requirement_status,
        stuck=ep.stuck if ep and topology == "plan" and getattr(plan_options, "adapt", "off") == "on" else None,
        adaptation=ep.adaptation if ep and topology == "plan" and getattr(plan_options, "adapt", "off") == "on"
        else None,
        faults=(ep.faults or None) if ep and topology == "plan" else None,              # D119
        **local_out)
    # D59: the local-tools fields exist only when --local-tools is on; off, result.json is as before
    exclude = (set() if box else LOCAL_FIELDS) | {f for f in PHASE2_FIELDS if getattr(result, f) is None}
    (run_dir / "result.json").write_text(result.model_dump_json(indent=2, exclude=exclude or None), encoding="utf-8")
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


# box: interpret
def can_ask() -> bool:
    """D116: whether a person can answer at the terminal (stdin is one)."""
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


# box: interpret
def parse_clarify(items: list[str] | None) -> dict[str, str]:
    """D116: --clarify 'ENTITY=READING' (repeatable) as {entity: reading}."""
    out = {}
    for it in items or []:
        if "=" not in it:
            raise ValueError(f"--clarify expects ENTITY=READING, got {it!r}")
        k, v = it.split("=", 1)
        out[k.strip().strip('"')] = v.strip()
    return out


# box: planner
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


def interpretation_of(interp: dict | None, stated: dict) -> dict:
    """D77: the working interpretation for result.json: each entity's reading, how it was settled, the alternatives,
    the question asked (if any) and what plain code added to the answer. D116: every question asked, the --clarify
    answers used, and the questions still open (pending: what a needs_clarification run asks the user)."""
    if not interp:
        return {}
    return {"working": [{k: w[k] for k in ("entity", "reading", "settled", "confidence", "alternatives")}
                        for w in interp.get("working", [])],
            "ambiguous": interp.get("ambiguous", []), "question": interp.get("question"),
            "context": interp.get("context", {}), "opening_line": opening_line(interp), "added_by_code": stated,
            **({"questions": interp["questions"]} if interp.get("questions") else {}),            # D116
            **({"clarified": interp["clarified"]} if interp.get("clarified") else {}),
            **({"pending": open_questions(interp)} if interp.get("ambiguous") else {})}


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
    tot = lambda key, when: sum(r[when].get(key, 0) for r in refined if when in r)
    out = {"self_refine": opt.get("self_refine"), "steps": len(latest), "steps_refined": len(refined),
           "by_reason": by,
           "before": {k: tot(k, "before") for k in ("failed_checks", "untagged", "hallucinated")},
           "after": {k: tot(k, "after") for k in ("failed_checks", "untagged", "hallucinated")}}
    if "collab" in opt:
        collab = [s["collab"] for s in latest.values() if s.get("collab")]
        out.update({"collab": opt["collab"], "collab_steps": len(collab),
                    "collab_agreed": sum(bool(c.get("agreed")) for c in collab),
                    "collab_rounds": sum(c.get("rounds", 0) for c in collab)})
    if opt.get("contract") == "on":           # D61: what the step contract found (latest version of each step)
        steps = list(latest.values())
        out["contract"] = {"steps_lacking_undeclared": sum(bool(s.get("contract_missing")) for s in steps),
                           "steps_with_unused": sum(bool(s.get("unused")) for s in steps),
                           "not_needed_lines": sum(len(s.get("not_needed", [])) for s in steps),
                           "tool_calls": sum(len(s.get("tool_calls", [])) for s in steps),
                           "tool_calls_ok": sum(c["ok"] for s in steps for c in s.get("tool_calls", [])),
                           "refine_findings_before": tot("contract", "before"),
                           "refine_findings_after": tot("contract", "after")}
    return out


def blocked_of(ep) -> dict:
    """D36: canonical capability -> how many producer steps (latest version of each; not the answer step) lacked it."""
    latest = {s["step"]: s for s in (ep.steps if ep else []) if not s.get("answer_step")}   # D40: producers only
    counts: dict[str, int] = {}
    for s in latest.values():
        for c in s.get("blocked_canonical", []):
            counts[c] = counts.get(c, 0) + 1
    return dict(sorted(counts.items()))


# box: checks
def quality_gate_on(choice: str | bool, topology: str, drafts_from: str | None = None) -> bool:
    """D79: the Box 2 quality gate (D28) is on by default for Amoeba's plan runner, off for the baselines (flat,
    boss_reviewers keep their papers' drafting) and when a saved draft is reused (nothing is drafted)."""
    if isinstance(choice, bool):
        return choice
    if choice == "auto":
        return topology == "plan" and not drafts_from
    return choice == "on"


# box: tools
def disable_tools(names, tools: ToolRegistry, pool: PoolSetup | None = None, local: LocalSetup | None = None):
    """D80 --disable-tools a,b: one run without these tools — out of the registry (and so the envelope Box 2 is
    shown), out of the pool (by id or name) and, for local:<Name>, out of the local tools' allow list."""
    names = [n.strip() for n in names or () if n.strip()]
    if not names:
        return tools, pool, local
    if pool is not None:
        pool = PoolSetup(config=pool.config, cache_dir=pool.cache_dir, connector=pool.connector, env=pool.env,
                         disabled=frozenset(names))
    return tools.without(names), pool, (local.without(names) if local is not None else None)


OPTION_FLAGS = {"replan": "--replan", "self_refine": "--self-refine", "collab": "--collab",
                "check_retry_turns": "--check-retry-turns", "max_turns": "--max-turns",
                "max_input_chars": "--max-input-chars", "max_summary_input_chars": "--max-summary-input-chars"}   # D114
INT_OPTIONS = ("check_retry_turns", "max_turns", "max_input_chars", "max_summary_input_chars")


def explicit_flags(argv: list[str]) -> frozenset:
    """The option flags given on the command line (they win over --option-defaults)."""
    return frozenset(a.split("=", 1)[0] for a in argv if a.startswith("--"))


def cli_plan_options(args: argparse.Namespace):
    """The plan runner's settings from the command line (D39+)."""
    from amoeba.interp.plan_runner import PlanOptions
    extra = {"check_retry_turns": args.check_retry_turns} if getattr(args, "check_retry_turns", None) else {}
    return PlanOptions(rerun_stale=args.rerun_stale, max_input_chars=args.max_input_chars,
                       max_summary_input_chars=args.max_summary_input_chars, self_refine=args.self_refine,
                       collab=args.collab, contract=args.step_contract, replan=args.replan,
                       verify_first=getattr(args, "verify_first", "off"), disputes=getattr(args, "disputes", "off"),
                       replan_method=getattr(args, "replan_method", "off"), dated=getattr(args, "dated_figures", "off"),
                       cite_arithmetic=getattr(args, "cite_arithmetic", "off"),
                       final_check=getattr(args, "deliverable_check", "off"),
                       xlsx_formulas=getattr(args, "xlsx_formulas", "off"), adapt=getattr(args, "adapt", "off"),
                       faults=tuple(getattr(args, "inject_fault", ()) or ()), **extra)


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


# box: router
def routing_mode(args: argparse.Namespace) -> str:
    """D97: --routing; by default routed for Amoeba's plan runner, fixed for the baselines (and Paper 1's benchmark)."""
    return getattr(args, "routing", None) or ("routed" if getattr(args, "topology", "flat") == "plan" else "fixed")


# box: router
def build_router_llm(args: argparse.Namespace, mode: str, registry=None, policy=None):
    """D97: the per-call model router over the registry (amoeba/config/models.yaml)."""
    from amoeba.llm.router import ModelRouter, load_registry
    if registry is None:
        registry, policy = load_registry()
    effort = None if args.reasoning_effort == "unset" else args.reasoning_effort

    def make(e):
        key = args.api_key or os.environ.get(e.api_key_env or "", "")
        client = OpenAICompatibleClient(base_url=e.base_url, api_key=key, model=e.model, max_tokens=2048,
                                        max_rate_retries=args.max_rate_retries, min_seconds_between_calls=0.0,
                                        merge_system=e.merge_system if args.merge_system is None else args.merge_system,
                                        reasoning_effort=effort or e.reasoning_effort)
        return CachedLLM(client, args.llm_cache, args.llm_cache_mode, args.llm_cache_namespace) if args.llm_cache \
            else client
    allowed_arg = getattr(args, "allowed_models", None)
    allowed = [m.strip() for m in allowed_arg.split(",") if m.strip()] if allowed_arg else None
    fixed = None
    if args.model:                                    # --model names a registry entry or an API model id
        fixed = next((n for n, e in registry.items() if args.model in (n, e.model)), None)
    niche = getattr(args, "niche_profile", None)       # D102: the niche profile's models and verifier setting
    usd_cap = getattr(args, "max_usd_per_run", None)
    if niche is not None:
        if niche.models.get("verifier_independence"):
            policy = {**policy, "verifier_independence": niche.models["verifier_independence"]}
        if usd_cap is None:
            usd_cap = niche.safety.max_usd_per_run
    router = ModelRouter(registry, policy, make, mode=mode, allowed=allowed, usd_cap=usd_cap, fixed_model=fixed,
                         profile_allowed=niche.allowed_models if niche is not None else getattr(args, "profile_models",
                                                                                                None))
    router.profile = f"router:{mode}"
    return router


# box: client
def build_llm(args: argparse.Namespace) -> LLMClient:
    if args.llm == "mock":
        mock = toy_mock_client()
        return CachedLLM(mock, args.llm_cache, args.llm_cache_mode, args.llm_cache_namespace) if args.llm_cache else mock
    mode = routing_mode(args)
    if mode == "routed":                              # D97: every call through the per-call router
        return build_router_llm(args, mode)
    # fixed (the baselines' default) and role: the D54 profile path, unchanged; fixed drops per-role models
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
    if mode == "fixed":
        from dataclasses import replace
        profile = replace(profile, roles={g: {k: v for k, v in r.items() if k != "model"}
                                          for g, r in profile.roles.items()})
    return build_router(profile, make, model, keep)


def build_box3_tools(args: argparse.Namespace, tools: ToolRegistry) -> ToolRegistry:
    """A fresh Box 3 registry per run: with --web-tools, web_search/fetch_url (D32), cached when --llm-cache is
    set (D46; replay then needs no Tavily key)."""
    if not args.web_tools:
        return tools
    research = getattr(args, "research", "off") == "on" and args.topology == "plan"      # D106: plan runner only
    if args.llm_cache:
        return web_registry(CachedProvider(TavilyProvider, args.llm_cache, args.llm_cache_mode, args.llm_cache_namespace),
                            research=research)
    return web_registry(research=research)


# box: free_text
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
    p.add_argument("--quality-gate", nargs="?", choices=["on", "off", "auto"], const="on", default="auto",
                   help="send a draft back (within the round cap) when a hard draft_quality check fails (D28). "
                        "auto (default, D79): on for --topology plan, off for the baselines and with --drafts-from "
                        "(no drafting); a bare --quality-gate means on")
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
    p.add_argument("--step-contract", choices=["on", "off"], default="on",
                   help="plan: plain code checks each step against its contract — every capability a helper lacked "
                        "and every tool or skill attached to it is used, marked BLOCKED or marked NOT NEEDED, else "
                        "the step is partial and the answer's Limitations say so; verifiers see each step's sources "
                        "and tool calls; the answer is checked for files and cited figures it left out (D61)")
    p.add_argument("--verify-first", choices=["on", "off"], default="on",
                   help="plan: a verify step first works out its own result from the checked steps' inputs and its "
                        "tools, without their outputs, in a fresh context; then it sees the outputs and compares. "
                        "Both are recorded in step_N.json (D90)")
    p.add_argument("--research", choices=["on", "off"], default="on",
                   help="plan, with --web-tools: plain code splits a packed web_search (several quoted queries, places "
                        "or years) into one search each, reads the top 3 results of each (official domains first) and "
                        "parses the data files (.csv/.xlsx/.json) a read page links; the helpers are told to search "
                        "one entity, year or series at a time (D106). The baselines never get it")
    p.add_argument("--workspace-sources", choices=["on", "off"], default="on",
                   help="plan, with --web-tools and --local-tools on: every page and data file the web tools read is "
                        "saved read-only in the run's workspace under sources/ (tables as CSV, pages as text; "
                        "sources/index.json gives each one's [S#], url and time), so analysts in the sandbox can compute "
                        "from them (D107). The baselines never get it")
    p.add_argument("--deliverable-check", choices=["on", "off"], default="on",
                   help="plan: a run whose answer has no content, or that never made a file the plan promised (with "
                        "--local-tools on), ends with error 'no_deliverable: …' and status no_deliverable; "
                        "result.json records `deliverables` (D105). The baselines are never checked")
    p.add_argument("--xlsx-formulas", choices=["on", "off"], default="on",
                   help="plan, with --local-tools on: after a step that made an .xlsx file, plain code checks that "
                        "totals and derived cells are formulas, not typed numbers; a typed one fails the check with the "
                        "cell names and earns the retry turn (D113)")
    p.add_argument("--cite-arithmetic", choices=["on", "off"], default="on",
                   help="plan: the citation check (D74) leaves out a number the line shows as a calculation's result "
                        "(after = or ≈), a power's base and exponent, and the years of a range; the operands are "
                        "still checked (D104)")
    p.add_argument("--dated-figures", choices=["on", "off"], default="on",
                   help="plan: every web-sourced figure of the final answer must carry its source's date (on its line "
                        "or in the source's entry); undated ones earn the answer step a refine turn, and those still "
                        "undated are listed in Limitations by plain code (D110)")
    p.add_argument("--replan-method", choices=["on", "off"], default="on",
                   help="plan, with --replan on: a step a re-plan adds or rewrites for a failed step must change the "
                        "method (a different tool, source type, or one search per entity/year/series, stated in the "
                        "step); a re-plan that repeats it is rejected and logged; the observer is shown how each "
                        "failed step worked (D108)")
    p.add_argument("--disputes", choices=["on", "off"], default="on",
                   help="plan, with --verify-first on: plain code compares the verifier's own result with the checked "
                        "outputs' figures by label (5%% tolerance); a disagreement earns the producers one rework turn "
                        "with both values shown, and one still there makes the step partial and goes into the "
                        "answer's Limitations; a PASS never overrides it (D109)")
    p.add_argument("--adapt", choices=["on", "off"], default="on",
                   help="plan: in-task adaptation (D117). After each step attempt plain code marks the step STUCK on "
                        "a stuck signal (a missing input, the same error twice, checks failing after the retry, max "
                        "turns, an unfilled capability, no file change), diagnoses one cause, then tries code fixes "
                        "cheapest first (pass or re-run the upstream input, more turns, retry turns, a larger input, "
                        "attach the missing tool from the pool shortlist), then one fix-proposer edit, within the "
                        "limits of adapt.yaml `adapt`; when none recovers the step the task stops with adapt_report.md")
    p.add_argument("--inject-fault", action="append", default=[], metavar="CAUSE:STEP[:N]",
                   help=argparse.SUPPRESS)   # D119: test-only, refused unless AMOEBA_TEST_FAULTS=1
    p.add_argument("--replan", choices=["on", "off"], default="off",
                   help="plan: the Action Observer (D63) — after a wave in which a step lacked a capability, a verify "
                        "step still failed, a step reported a missing input or the team got a tool the plan never "
                        "named, one planner call may revise the steps that have not run; plain code validates the "
                        "decision (max 2 re-plans and 3 added steps per run) and saves plan.v<k>.json")
    p.add_argument("--equal-tools", choices=["on", "off"], default="off",
                   help="flat and boss_reviewers get the plan runner's tool access: the D32 web grant, and (boss_reviewers) "
                        "tool calls for the solver and critics, the solver holding every tool the team was given (D62). "
                        "Their logic is otherwise unchanged; they never get the step contract")
    p.add_argument("--interactive", action="store_true",
                   help="after Box 2, print the requirements, assumptions and open questions and wait for 'continue' "
                        "or an edited assumption (appended to the task as 'User clarification: ...', then one "
                        "re-draft round) (D53). Never in eval scripts")
    p.add_argument("--pool", action=argparse.BooleanOptionalAction, default=True,
                   help="Box 3 first fills capability requests from the cached tool/skill pool (MCP Registry servers, "
                        "anthropics/skills): keyword match, one AI pick per request, plain-code vetting (D56). Build "
                        "the cache with `python -m amoeba pool refresh`; without it the run logs pool_unavailable "
                        "and goes on as before")
    p.add_argument("--pool-dir", default=None, metavar="DIR",
                   help="the pool cache (default: cache_dir in amoeba/config/pool.yaml, data/pool)")
    p.add_argument("--local-tools", choices=["on", "off"], default="off",
                   help="Box 3 may also borrow Claude Code's tools (Bash, Read, Write, Edit, Glob, Grep) and skills "
                        "through `claude mcp serve`, in a fresh OpenShell sandbox per run (D96; isolation process: the D59 server "
                        "on this host, which needs AMOEBA_SANDBOX=1)")
    p.add_argument("--routing", choices=["fixed", "role", "routed"], default=None,
                   help="D97: fixed = one model for every call (default for the baselines); role = the profile's "
                        "static per-role models (D54); routed = the per-call router (default for --topology plan)")
    p.add_argument("--allowed-models", default=None,
                   help="D97: comma-separated registry names the router may use (default: the whole registry)")
    p.add_argument("--max-usd-per-run", type=float, default=None,
                   help="D97: the router drops a model whose estimated cost would pass this run budget")
    p.add_argument("--local-tools-mode", choices=["sandbox", "inprocess"], default="sandbox",
                   help="D96a: sandbox (default) = a fresh OpenShell sandbox per run; inprocess = the D59 server on "
                        "this host, only when asked for and only with AMOEBA_SANDBOX=1")
    p.add_argument("--picks-file", default=None, metavar="FILE",
                   help="D70: one pool pick per task and request, shared by every run that names the same file (the "
                        "three architectures of a benchmark); a recorded pick is reused when it passed vetting again")
    p.add_argument("--interpret", choices=["on", "off"], default="on",
                   help="D77: read the task before planning — list the readings of its key names and terms; a clear "
                        "winner is used, otherwise --interactive asks one question and a non-interactive run states "
                        "its assumption in the answer")
    p.add_argument("--ask-assumed", choices=["on", "off"], default="on",
                   help="D116: on (default) = every reading the interpretation step would only assume (no reading "
                        "leads the next by 0.3, a tie included) is asked about before planning; with no terminal "
                        "the run stops with error needs_clarification and writes clarification.json. off = the "
                        "D77 behaviour (the answer states the assumption); the experiment harness passes off")
    p.add_argument("--clarify", action="append", default=None, metavar="ENTITY=READING",
                   help="D116: answer an interpretation question ahead of time (the words or the option number); "
                        "repeat for each entity")
    p.add_argument("--context", default=None, metavar="YAML",
                   help="D77: read-only user context (location, organisation, role) for the interpretation step")
    p.add_argument("--timezone", default=None, metavar="IANA",
                   help="D75: the run's time zone for today's date and weekday in every step prompt, e.g. "
                        "America/Chicago (default: the machine's local zone)")
    p.add_argument("--niche", default="general",
                   help="D102: the environment's profile, profiles/<name>.yaml (allowed tools and models, sandbox limits, "
                        "domain rules, done clauses, domain checks, safety limits); general = today's behaviour. Plan "
                        "runner only")
    p.add_argument("--family-classify", choices=["auto", "on", "off"], default="auto",
                   help="D101: give a free-text task (family freeform) a task family in Box 1 (keyword rules, else one "
                        "routed call); recorded in result.json; auto = on for the plan runner, off for the baselines")
    p.add_argument("--check-retry-turns", type=int, default=None,
                   help="plan: turns a failed-check retry gets (D42; default 2)")
    p.add_argument("--max-turns", type=int, default=None,
                   help="turns per step for every helper (default 5)")
    p.add_argument("--option-defaults", default="", metavar="K=V,...",
                   help="harness defaults for replan, self_refine, collab, check_retry_turns, max_turns and the input "
                        "sizes, e.g. replan=on; a flag given on the command line wins")
    p.add_argument("--disable-tools", default="", metavar="A,B",
                   help="D80: take these tools out of the registry, the pool and the local tools for this run (e.g. "
                        "calc,local:Bash); used by remove_tool shifts")
    p.add_argument("--picks-only", action="store_true",
                   help="D70: stop after the toolbox step (make the picks for --picks-file before the runs)")
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
    args.explicit = explicit_flags(argv if argv is not None else sys.argv[1:])
    args.inject_fault = check_flag(args.inject_fault, args.topology)      # D119: SystemExit unless allowed
    for kv in filter(None, args.option_defaults.split(",")):            # harness defaults; an explicit flag wins
        k, _, v = kv.partition("=")
        k = k.strip().replace("-", "_")
        if k not in OPTION_FLAGS:
            p.error(f"--option-defaults: {k!r} is not one of {sorted(OPTION_FLAGS)}")
        if OPTION_FLAGS[k] not in args.explicit:
            setattr(args, k, int(v) if k in INT_OPTIONS else v.strip())
    try:                                                                  # D102
        args.niche_profile = load_profile(args.niche)
    except ValueError as e:
        p.error(str(e))
    if not args.niche_profile.is_neutral() and args.topology != "plan":
        p.error("--niche is for --topology plan only; the baselines stay as they are (D102)")
    if args.local_tools == "on" and LocalSetup(mode=args.local_tools_mode).isolation != "openshell":   # D96a
        try:
            require_sandbox()
        except SandboxRequired as e:
            p.error(str(e))
    return args


# box: niche
def niche_tools(niche, tools: ToolRegistry, local: LocalSetup | None):
    """D102: the registry without the tools the profile does not allow (with the profile attached, so Box 3 refuses
    anything else a plan names), and the local tools cut to the profile's list, with its sandbox limits."""
    from amoeba.config.niche import tool_allowed
    descs = tools.descriptions()
    out = tools.without([n for n in tools.names() if not tool_allowed(n, niche, descs.get(n, ""))[0]])
    out.niche = niche
    if local is not None:
        local = local.without([f"local:{t}" for t in local.config["allowed_tools"]
                               if not tool_allowed(f"local:{t}", niche)[0]]).with_limits(niche.sandbox)
    return out, local


# box: interpret
def family_classify_on(flag: str, topology: str) -> bool:
    """D101: on for Amoeba's plan runner by default; the baselines keep their behaviour unless asked."""
    return flag == "on" or (flag == "auto" and topology == "plan")


# box: free_text
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    llm = build_llm(args)
    disabled = [n.strip() for n in args.disable_tools.split(",") if n.strip()]          # D80
    tools, _, _ = disable_tools(disabled, default_registry())
    envelope = Envelope.from_registry(tools, model=llm.model)
    if args.tasks:
        tasks = [Task.model_validate_json(l) for l in Path(args.tasks).read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        tasks = ToyTaskSource(args.seed, args.n).tasks() if args.toy else [Task(prompt=args.prompt)]
    saved = load_saved_drafts(args.drafts_from) if args.drafts_from else None
    pool = PoolSetup(cache_dir=args.pool_dir) if args.pool else None   # D56
    local = LocalSetup(pool_dir=pool.dir if pool else PoolSetup(cache_dir=args.pool_dir).dir,
                       mode=args.local_tools_mode) if args.local_tools == "on" else None   # D59, D96a
    _, pool, local = disable_tools(disabled, tools, pool, local)        # D80
    niche = args.niche_profile                                           # D102
    if not niche.is_neutral():
        tools, local = niche_tools(niche, tools, local)
        envelope = Envelope.from_registry(tools, model=llm.model)        # Box 2 is shown the allowed tools only
    results = []
    for task in tasks:
        chosen = None
        if saved is not None:
            chosen = pick(saved, task.id, args.draft_pick)
            if chosen is None:
                print(f"[{args.topology}] {task.id}: no saved draft #{args.draft_pick} in {args.drafts_from} — skipped")
                continue
        box3_tools = build_box3_tools(args, tools)   # a fresh source list per run (D32)
        if disabled:                                 # D80
            box3_tools = box3_tools.without(disabled)
        if not niche.is_neutral():                   # D102: Box 3's own copy, the refusal guard rides on it
            box3_tools, _ = niche_tools(niche, box3_tools, None)
        r = run_one(task, args.topology, llm, envelope, box3_tools, args.runs_dir, args.seed,
                    log_content=not args.no_log_content, draft_prompts=args.draft_prompts,
                    max_tokens=cli_token_limits(args),
                    quality_gate=quality_gate_on(args.quality_gate, args.topology, args.drafts_from),
                    plan_options=cli_plan_options(args), saved_draft=chosen,
                    limits=RunLimits(args.max_tokens_per_run or niche.safety.max_tokens_per_run,
                                     args.max_calls_per_run or niche.safety.max_calls_per_run),
                    ask=input if args.interactive else None, pool=pool, local=local,
                    equal_tools=args.equal_tools == "on", picks_file=args.picks_file, picks_only=args.picks_only,
                    timezone=args.timezone, interpret=args.interpret == "on", context=load_context(args.context),
                    disabled_tools=disabled, cli_explicit=args.explicit,
                    max_turns=args.max_turns if "--max-turns" in args.explicit else None,
                    default_max_turns=None if "--max-turns" in args.explicit else args.max_turns,
                    family_classify=family_classify_on(args.family_classify, args.topology),     # D101
                    niche=niche,
                    deliverable_check=args.deliverable_check == "on" and args.topology == "plan",   # D105
                    workspace_sources=args.workspace_sources == "on" and args.topology == "plan",   # D107
                    ask_assumed=args.ask_assumed, clarify=parse_clarify(args.clarify))                  # D116
        results.append(r)
        shown = (r.answer or "").replace("\n", " ")[:60]
        print(f"[{r.topology}] {task.id} score={r.score} tokens={r.total_tokens} calls={r.n_llm_calls} "
              f"rounds={r.draft_rounds} consensus={r.consensus} status={r.status} error={r.error} answer={shown!r}")
        print(f"    {describe(r.usage)}")                                                    # D47
        if r.status == "needs_clarification":                                              # D116
            q = (r.interpretation or {}).get("pending") or []
            for x in q:
                print(f'    ? What did you mean by "{x["entity"]}": ' + " | ".join(
                    f"{i}. {o}" for i, o in enumerate(x["options"][:-1], 1)))
            print("    answer and run again with --clarify 'ENTITY=READING' (see clarification.json in the run folder)")
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
