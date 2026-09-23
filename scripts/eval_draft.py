"""Box 2 only: draft a team for each task, several times, and measure the drafting step. No helper runs.

    python -m scripts.eval_draft --tasks tasks/draft_eval.jsonl --repeats 3 --llm openai
    python -m scripts.eval_draft --tasks tasks/draft_eval.jsonl --repeats 3            # offline stand-in AI

Writes runs/draft_eval/<stamp>/{attempts.jsonl, summary.csv, drafts/, traces/, planner/, replies/}:
- attempts.jsonl: one line per attempt: ok or the DraftError, rounds, consensus, roster, plan steps, capability
  requests, tokens and calls, and the roles the final planner reply holds under the copied AutoAgents regex vs a
  brace-balanced parse (what a D22 fix would recover).
- summary.csv: one row per task plus an ALL row.
- planner/: the final Planner reply of each attempt, so failures can be read.
- replies/: every reply of each attempt (planner, agent_observer, plan_observer, repairs), in order.
- drafts/: the Draft with its per-round record (Draft.rounds), or the error and the rounds of a failed one.
- traces/: one line per call, with the full prompt and reply unless --no-log-content.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from amoeba.interp.trace import TraceWriter
from amoeba.llm.client import ChatResponse, LLMClient, Messages, MockLLMClient
from amoeba.safety.envelope import Envelope
from amoeba.task.draft import DraftError, draft_team
from amoeba.task.models import Task
from amoeba.task.parsers import parse_json_objects, parse_plan, parse_role_blobs, parse_sections
from amoeba.tools.registry import default_registry
from scripts.run_task import build_llm

RETRY_STATUS = (429, 500, 503)


class Recording(LLMClient):
    """Passes calls through, keeps each reply with its kind, and waits out rate limits (429/5xx)."""

    def __init__(self, inner: LLMClient, waits: tuple[int, ...] = (10, 20, 30, 40, 60)):
        self.inner, self.model, self.waits = inner, inner.model, waits
        self.replies: list[tuple[str, str]] = []

    def chat_messages(self, messages: Messages, seed: int = 0) -> ChatResponse:
        for wait in (*self.waits, None):
            try:
                resp = self.inner.chat_messages(messages, seed)
                break
            except Exception as e:
                if wait is None or getattr(e, "status_code", None) not in RETRY_STATUS:
                    raise
                time.sleep(wait)
        self.replies.append((MockLLMClient.classify(messages), resp.content))
        return resp


def role_names(text: str, parser) -> list[str]:
    sec = parse_sections(text)
    blobs = parser(sec.get("Created Roles List", "")) + parser(sec.get("Selected Roles List", ""))
    return list(dict.fromkeys(str(b.get("name", "")).strip() for b in blobs if str(b.get("name", "")).strip()))


def would_pass(text: str, names: list[str], max_agents: int) -> bool:
    """Would the plain-code checks accept this reply if these were the parsed roles? (roster size + a plan step
    naming one of them — the same exact-then-substring rule draft_team uses)."""
    steps = parse_plan(parse_sections(text).get("Execution Plan", ""))
    named = [s for bracket, s in steps
             if [n for n in names if n in bracket] or [n for n in names if n.replace("_", " ") in s.split(":")[0]]]
    return 2 <= len(names) <= max_agents and bool(named)


def attempt(task: Task, rep: int, llm: LLMClient, envelope: Envelope, out: Path, seed: int,
            log_content: bool = True, prompts: str = "d19") -> dict:
    rec = Recording(llm)
    trace = TraceWriter(out / "traces" / f"{task.id}.{rep}.jsonl", episode_id=f"{task.id}.{rep}",
                        log_content=log_content)
    t0 = time.perf_counter()
    row = {"task_id": task.id, "family": task.family, "repeat": rep, "prompts": prompts, "model": llm.model}
    saved: dict = {}
    try:
        d = draft_team(task, rec, envelope, trace, seed, prompts=prompts)
        row.update(ok=True, error="", rounds=d.rounds_used, consensus=d.consensus, roster=len(d.created_roles),
                   plan_steps=len(d.plan), requests_final=len(d.capability_requests),
                   requests_proposed=d.requests_proposed, requests_dropped=d.requests_dropped_by_observers,
                   request_names=sorted({q.name for q in d.capability_requests}))
        q = d.quality["checks"]
        row.update(quality_passed=d.quality["passed"], quality_failed=d.quality["failed"],
                   failed_checks=d.quality["failed_checks"], requirements=len(d.requirements),
                   requirements_covered=q["requirements_covered"]["ok"],
                   roles_defined_pct=round(100 * q["roles_fully_defined"]["defined"] / max(1, len(d.created_roles))),
                   verification_step=q["verification_step"]["ok"], summariser_ok=q["summariser"]["ok"],
                   last_verdicts=[d.rounds[-1].agent_verdict, d.rounds[-1].plan_verdict] if d.rounds else [])
        saved = d.model_dump(mode="json")
    except DraftError as e:
        saved = {"error": f"draft: {e}", "rounds": [r.model_dump(mode="json") for r in e.rounds]}
        row.update(ok=False, error=f"draft: {e}", rounds=sum(k == "plan_observer" for k, _ in rec.replies), consensus=False,
                   roster=0, plan_steps=0, requests_final=0, requests_proposed=0, requests_dropped=0, request_names=[])
    except Exception as e:   # an API failure is recorded, not hidden, and does not stop the other attempts
        saved = {"error": f"exception: {type(e).__name__}: {e}"}
        row.update(ok=False, error=f"exception: {type(e).__name__}: {str(e)[:160]}", rounds=0, consensus=False,
                   roster=0, plan_steps=0, requests_final=0, requests_proposed=0, requests_dropped=0, request_names=[])
    finally:
        trace.close()
    (out / "drafts").mkdir(parents=True, exist_ok=True)   # the Draft (or the rounds of a failed one), as plan.json
    (out / "drafts" / f"{task.id}.{rep}.json").write_text(json.dumps(saved, indent=1, ensure_ascii=False),
                                                         encoding="utf-8")
    (out / "replies").mkdir(parents=True, exist_ok=True)   # every reply of the attempt, in order, to read the rounds
    (out / "replies" / f"{task.id}.{rep}.json").write_text(
        json.dumps([{"kind": k, "text": t} for k, t in rec.replies], ensure_ascii=False, indent=1), encoding="utf-8")
    planner = [text for kind, text in rec.replies if kind == "planner"]
    final = planner[-1] if planner else ""
    if final:
        (out / "planner").mkdir(parents=True, exist_ok=True)
        (out / "planner" / f"{task.id}.{rep}.txt").write_text(final, encoding="utf-8")
    row["derived_correct"] = derived_correct(task, final)
    regex = role_names(final, parse_role_blobs)
    balanced = role_names(final, parse_json_objects)
    row.update(tokens=trace.total_tokens, calls=trace.n_llm_calls, latency_ms=int((time.perf_counter() - t0) * 1000),
               repair_calls=max(0, len(planner) - row["rounds"]) if row["ok"] else None,
               roles_regex=regex, roles_balanced=balanced,
               lost_to_regex=sorted(set(balanced) - set(regex)),
               ok_with_balanced_parse=bool(final) and would_pass(final, balanced, envelope.max_agents))
    return row


def derived_correct(task: Task, reply: str) -> bool | None:
    """Task-specific arithmetic check (D24 §5): every expected derived number appears in the final Planner reply, in
    any of its listed spellings (spaces and case ignored). None when the task lists none."""
    wanted = task.expected.get("derived", [])
    if not wanted or not reply:
        return None if not wanted else False
    flat = "".join(reply.lower().split())
    return all(any("".join(alt.lower().split()) in flat for alt in alts) for alts in wanted)


def summarise(rows: list[dict]) -> list[dict]:
    def agg(label: str, family: str, rs: list[dict]) -> dict:
        n = len(rs)
        ok = [r for r in rs if r["ok"]]
        mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else ""
        rate = lambda xs: (lambda v: round(sum(v) / len(v), 2) if v else "")([1.0 if x else 0.0 for x in xs if x is not None])
        errors: dict[str, int] = {}
        for r in rs:
            if not r["ok"]:
                key = r["error"].split(" outside")[0].split(":")[1].strip() if r["error"].startswith("draft:") \
                    else r["error"].split(":")[0]
                errors[key] = errors.get(key, 0) + 1
        return {"task_id": label, "family": family, "prompts": ",".join(sorted({r.get("prompts", "") for r in rs})),
                "model": ",".join(sorted({r.get("model", "") for r in rs})), "attempts": n, "ok": len(ok), "ok_rate": round(len(ok) / n, 2),
                "ok_with_balanced_parse": sum(r["ok_with_balanced_parse"] for r in rs),
                "attempts_losing_roles_to_regex": sum(bool(r["lost_to_regex"]) for r in rs),
                "mean_rounds_ok": mean([r["rounds"] for r in ok]),
                "consensus_rate_ok": mean([1.0 if r["consensus"] else 0.0 for r in ok]),
                "mean_roster_ok": mean([r["roster"] for r in ok]), "mean_plan_steps_ok": mean([r["plan_steps"] for r in ok]),
                "requests_proposed": sum(r["requests_proposed"] for r in rs),
                "requests_final": sum(r["requests_final"] for r in rs),
                "requests_dropped": sum(r["requests_dropped"] for r in rs),
                "request_names": " ".join(sorted({x for r in rs for x in r["request_names"]})),
                "mean_tokens": mean([r["tokens"] for r in rs]), "mean_calls": mean([r["calls"] for r in rs]),
                # D24 draft_quality (accepted drafts; a d19 draft has no requirement ids, so those are blank)
                "requirements_covered_rate": rate([r.get("requirements_covered") for r in ok]),
                "mean_roles_defined_pct": mean([r["roles_defined_pct"] for r in ok if "roles_defined_pct" in r]),
                "verification_step_rate": rate([r.get("verification_step") for r in ok]),
                "summariser_ok_rate": rate([r.get("summariser_ok") for r in ok]),
                "derived_correct_rate": rate([r.get("derived_correct") for r in rs]),
                "mean_requests_final": mean([r["requests_final"] for r in rs]),
                "truncated_calls": sum(r.get("truncated", 0) for r in rs),
                "errors": "; ".join(f"{k} x{v}" for k, v in sorted(errors.items()))}

    order = list(dict.fromkeys(r["task_id"] for r in rows))
    out = [agg(t, rows[[r["task_id"] for r in rows].index(t)]["family"], [r for r in rows if r["task_id"] == t])
           for t in order]
    return out + [agg("ALL", "", rows)]


def load_tasks(path: str | Path) -> list[Task]:
    return [Task(**json.loads(line)) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tasks", default="tasks/draft_eval.jsonl")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--llm", choices=["mock", "openai"], default="mock")
    p.add_argument("--base-url", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--api-key", default=None)
    p.add_argument("--out", default=None, help="default: runs/draft_eval/<UTC stamp>")
    p.add_argument("--no-log-content", action="store_true", help="leave prompts and replies out of the traces")
    p.add_argument("--draft-prompts", choices=["d19", "d24"], default="d19", help="Box 2 prompts (D24)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    llm = build_llm(args)
    tools = default_registry()
    envelope = Envelope.from_registry(tools, model=llm.model)
    out = Path(args.out or f"runs/draft_eval/{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(out / "attempts.jsonl", "w", encoding="utf-8") as fh:
        for task in load_tasks(args.tasks):
            for rep in range(args.repeats):
                row = attempt(task, rep, llm, envelope, out, args.seed, log_content=not args.no_log_content,
                              prompts=args.draft_prompts)
                rows.append(row)
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                print(f"{task.id} #{rep} ok={row['ok']} rounds={row['rounds']} consensus={row['consensus']} "
                      f"roster={row['roster']} requests={row['request_names']} tokens={row['tokens']} "
                      f"error={row['error'][:70]!r} lost_to_regex={row['lost_to_regex']}", flush=True)
    summary = summarise(rows)
    with open(out / "summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    a = summary[-1]
    print(f"== {len(rows)} attempts  ok {a['ok']}/{a['attempts']}  ok with a brace-balanced role parse "
          f"{a['ok_with_balanced_parse']}/{a['attempts']}  mean rounds {a['mean_rounds_ok']}  "
          f"consensus {a['consensus_rate_ok']}  mean tokens {a['mean_tokens']}  -> {out / 'summary.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
