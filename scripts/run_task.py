"""CLI (spec §10): draft a team for a task, run it, write runs/<run_id>/{team.yaml, plan.json, trace.jsonl,
capability_requests.json, result.json}.

    python -m scripts.run_task "Reverse the string 'adaptive' then uppercase it" --topology flat
    python -m scripts.run_task --toy --seed 0 --n 20 --topology boss_reviewers
    python -m scripts.run_task ... --llm openai --base-url http://localhost:8000/v1 --model qwen2.5
    AMOEBA_BASE_URL=... AMOEBA_API_KEY=... AMOEBA_MODEL=... python -m scripts.run_task --toy --llm openai
"""
from __future__ import annotations

import argparse
import json
import os
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
from amoeba.task.evaluate import score
from amoeba.task.instantiate import instantiate
from amoeba.task.models import RunResult, Task
from amoeba.task.source import ToyTaskSource
from amoeba.tools.registry import ToolRegistry, default_registry


def run_one(task: Task, topology: str, llm: LLMClient, envelope: Envelope, tools: ToolRegistry,
            runs_dir: str | Path, seed: int = 0, log_content: bool = False, draft_prompts: str = "d19") -> RunResult:
    run_id = str(uuid4())
    run_dir = Path(runs_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace = TraceWriter(run_dir / "trace.jsonl", episode_id=run_id, log_content=log_content)
    t0 = time.perf_counter()
    draft = ep = failed = None
    answer = error = None
    team_id = ""
    try:
        draft = draft_team(task, llm, envelope, trace, seed, prompts=draft_prompts)
        cfg = instantiate(draft, topology, task, envelope)
        team_id = cfg.team_id
        dump_yaml(cfg, run_dir / "team.yaml")
        ep = Interpreter(llm, tools, trace).run(cfg, task, seed)
        answer, error = ep.answer, ep.error
    except DraftError as e:
        error = f"draft: {e}"
        failed = e
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
    result = RunResult(
        run_id=run_id, task_id=task.id, team_id=team_id, topology=topology, answer=answer, error=error,
        score=score(answer, task.ground_truth), total_tokens=trace.total_tokens,
        latency_ms=int((time.perf_counter() - t0) * 1000), n_llm_calls=trace.n_llm_calls,
        draft_rounds=draft.rounds_used if draft else sum(bool(r.plan_observer_raw) for r in (failed.rounds if failed else [])), consensus=draft.consensus if draft else False,
        blocked_steps=ep.blocked_steps if ep else [], requested_capabilities=requested,
        requests_proposed=draft.requests_proposed if draft else 0,
        requests_dropped_by_observers=draft.requests_dropped_by_observers if draft else 0)
    (run_dir / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


def build_llm(args: argparse.Namespace) -> LLMClient:
    if args.llm == "mock":
        return toy_mock_client()
    # flags win; else the AMOEBA_* env vars; else OPENAI_API_KEY / the SDK default endpoint
    base_url = args.base_url or os.environ.get("AMOEBA_BASE_URL") or None
    api_key = args.api_key or os.environ.get("AMOEBA_API_KEY") or os.environ.get("OPENAI_API_KEY") or "EMPTY"
    model = args.model or os.environ.get("AMOEBA_MODEL") or "gpt-4o-mini"
    return OpenAICompatibleClient(base_url=base_url, api_key=api_key, model=model)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt", nargs="?", help="a free-text task (cannot be scored)")
    p.add_argument("--toy", action="store_true", help="run generated toy tasks with known answers")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n", type=int, default=20, help="number of toy tasks")
    p.add_argument("--topology", choices=["flat", "boss_reviewers"], default="flat")
    p.add_argument("--llm", choices=["mock", "openai"], default="mock")
    p.add_argument("--base-url", default=None)
    p.add_argument("--model", default=None, help="default: $AMOEBA_MODEL, else gpt-4o-mini")
    p.add_argument("--api-key", default=None)
    p.add_argument("--runs-dir", default="runs")
    p.add_argument("--draft-prompts", choices=["d19", "d24"], default="d19",
                   help="Box 2 prompts: d19 = AutoAgents + D19 edits (default), d24 = ours (spec/BOX2_PROMPT_UPGRADE_D24.md)")
    p.add_argument("--no-log-content", action="store_true",
                   help="leave prompts and replies out of trace.jsonl (they are logged by default)")
    args = p.parse_args(argv)
    if not args.toy and not args.prompt:
        p.error("give a prompt or --toy")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    llm = build_llm(args)
    tools = default_registry()
    envelope = Envelope.from_registry(tools, model=llm.model)
    tasks = ToyTaskSource(args.seed, args.n).tasks() if args.toy else [Task(prompt=args.prompt)]
    results = []
    for task in tasks:
        r = run_one(task, args.topology, llm, envelope, tools, args.runs_dir, args.seed,
                    log_content=not args.no_log_content, draft_prompts=args.draft_prompts)
        results.append(r)
        shown = (r.answer or "").replace("\n", " ")[:60]
        print(f"[{r.topology}] {task.id} score={r.score} tokens={r.total_tokens} calls={r.n_llm_calls} "
              f"rounds={r.draft_rounds} consensus={r.consensus} error={r.error} answer={shown!r}")
    scored = [r.score for r in results if r.score is not None]
    n = len(results)
    mean_score = sum(scored) / len(scored) if scored else float("nan")
    print(f"== {args.topology}  n={n}  mean_score={mean_score:.3f}  "
          f"mean_tokens={sum(r.total_tokens for r in results) / n:.1f}  "
          f"mean_llm_calls={sum(r.n_llm_calls for r in results) / n:.2f}  "
          f"(total tokens {sum(r.total_tokens for r in results)}, total calls {sum(r.n_llm_calls for r in results)}, "
          f"errors {sum(r.error is not None for r in results)})  runs in {Path(args.runs_dir).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
