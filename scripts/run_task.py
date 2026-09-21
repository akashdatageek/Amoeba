"""CLI (spec §10): draft a team for a task, run it, write runs/<run_id>/{team.yaml, plan.json, trace.jsonl, result.json}.

    python -m scripts.run_task "Reverse the string 'adaptive' then uppercase it" --topology flat
    python -m scripts.run_task --toy --seed 0 --n 20 --topology boss_reviewers
    python -m scripts.run_task ... --llm openai --base-url http://localhost:8000/v1 --model qwen2.5
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
            runs_dir: str | Path, seed: int = 0) -> RunResult:
    run_id = str(uuid4())
    run_dir = Path(runs_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace = TraceWriter(run_dir / "trace.jsonl", episode_id=run_id)
    t0 = time.perf_counter()
    draft = None
    answer = error = None
    team_id = ""
    try:
        draft = draft_team(task, llm, envelope, trace, seed)
        cfg = instantiate(draft, topology, task, envelope)
        team_id = cfg.team_id
        dump_yaml(cfg, run_dir / "team.yaml")
        ep = Interpreter(llm, tools, trace).run(cfg, task, seed)
        answer, error = ep.answer, ep.error
    except DraftError as e:
        error = f"draft: {e}"
    finally:
        (run_dir / "plan.json").write_text(
            json.dumps(draft.model_dump() if draft else {}, indent=2, ensure_ascii=False), encoding="utf-8")
        trace.close()
    result = RunResult(
        run_id=run_id, task_id=task.id, team_id=team_id, topology=topology, answer=answer, error=error,
        score=score(answer, task.ground_truth), total_tokens=trace.total_tokens,
        latency_ms=int((time.perf_counter() - t0) * 1000), n_llm_calls=trace.n_llm_calls,
        draft_rounds=draft.rounds_used if draft else 0, consensus=draft.consensus if draft else False)
    (run_dir / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


def build_llm(args: argparse.Namespace) -> LLMClient:
    if args.llm == "mock":
        return toy_mock_client()
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY") or "EMPTY"
    return OpenAICompatibleClient(base_url=args.base_url, api_key=api_key, model=args.model)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt", nargs="?", help="a free-text task (cannot be scored)")
    p.add_argument("--toy", action="store_true", help="run generated toy tasks with known answers")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n", type=int, default=20, help="number of toy tasks")
    p.add_argument("--topology", choices=["flat", "boss_reviewers"], default="flat")
    p.add_argument("--llm", choices=["mock", "openai"], default="mock")
    p.add_argument("--base-url", default=None)
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--api-key", default=None)
    p.add_argument("--runs-dir", default="runs")
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
        r = run_one(task, args.topology, llm, envelope, tools, args.runs_dir, args.seed)
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
