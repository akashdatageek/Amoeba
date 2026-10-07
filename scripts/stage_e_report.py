"""D117 Stage E — the report of a pair-runner folder (scripts/stage_e.py): --adapt off vs on, per run and per arm.

Per run: the outcome (done / done with limitation / stuck-stopped / failed), the stuck steps by cause (the off arm,
which does not watch, is read offline by the same watch: amoeba/adapt/stuck.py), the recovered steps by rung (code fix
or the proposer's edit type), the work-arounds apart, the rubric score where the task has one, the billed tokens
(input + output + reasoning), the adaptation's tokens and $, the wall time, the web searches and fetches, and what
broke. Per arm: the sums. Then 3 recovered steps per arm picked at random (seeded), each with its trace lines and its
output before and after, to check the recovery is real and not only the contract passing.

    python -m scripts.stage_e_report eval/stage_e/pilot [--seed 117]
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path

from amoeba.task.models import run_status
from scripts.stuck_report import run_stuck

FAILED = {"agent_error", "infra_error", "no_deliverable", "needs_clarification"}
NOT_DONE = ("partial", "incomplete")      # the answer step's status as the run's error: an answer, not a failure
CODE_RUNGS = {1, 2, "input"}
TRACE_NAMES = {"stuck", "fix_try", "fix_skipped", "proposer_reply", "fix_done", "step_done", "refine",
               "input_truncated", "claimed_file_missing", "adapt_stop"}


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _final_metas(run: Path) -> dict[int, dict]:
    out = {}
    for p in (run / "artifacts").glob("step_*.json"):
        if p.stem[len("step_"):].isdigit() and isinstance(m := _load(p), dict):
            out[m.get("step")] = m
    return out


def _trace(run: Path) -> list[dict]:
    rows = []
    try:
        for line in (run / "trace.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    except OSError:
        pass
    return rows


# box: stage_e
def run_path(row: dict, folder: Path | None = None) -> Path | None:
    """The run folder of a pairs.jsonl row; a relative path (older rows) is found again under the report folder by
    its <arm>/<task>.s<seed>/<run id> tail."""
    if not row.get("run"):
        return None
    p = Path(row["run"])
    if p.exists() or folder is None or row["arm"] not in p.parts:
        return p
    return folder / Path(*p.parts[p.parts.index(row["arm"]):])


# box: stage_e
def run_record(row: dict, folder: Path | None = None) -> dict:
    """One arm's run, measured."""
    run = run_path(row, folder)
    rec = {"task": row["task"], "seed": row["seed"], "arm": row["arm"], "rc": row.get("rc"), "wall_s": row.get("wall_s"),
           "problems": []}
    res = _load(run / "result.json") if run else None
    if res is None:
        rec.update(outcome="failed", problems=[f"no result.json (rc={row.get('rc')})"])
        return rec
    status = res.get("status") or run_status(res.get("error"))
    trace = _trace(run)
    tools = Counter(r.get("gen_ai.tool.name") or r.get("amoeba.tool") for r in trace
                    if r.get("kind") == "span" and r.get("name") == "execute_tool")
    usage = res.get("usage") or {}
    ad = res.get("adaptation") or {}
    fixes = ad.get("fixes") or []
    if row["arm"] == "on":
        events = res.get("stuck") or []
        causes = {}
        for e in events:
            causes.setdefault(e["step"], e["cause"])
        metas = _final_metas(run)
        unresolved = sorted(n for n, m in metas.items() if m.get("status") != "done" and m.get("stuck"))
    else:
        recs = run_stuck(run)
        causes, last = {}, {}
        for r in recs:
            if r["stuck"]:
                causes.setdefault(r["step"], r["cause"])
            last[r["step"]] = r
        unresolved = sorted(n for n, r in last.items() if r["stuck"])
    recovered = Counter(("code: " if f.get("rung") in CODE_RUNGS else "proposer: ") + f["kind"]
                        for f in fixes if f.get("result") == "recovered")
    workarounds = [f for f in fixes if f.get("result") == "finished with limitation"]
    if row.get("rc") not in (0, None):
        rec["problems"].append(f"run_task exit code {row['rc']}")
    err = str(res.get("error") or "")
    answered = bool((res.get("answer") or "").strip()) and err.startswith(NOT_DONE)
    if err and status != "stuck" and not answered:
        rec["problems"].append(f"error: {err[:200]}")
    metas_all = _final_metas(run)
    not_done = Counter(re.split(r"[:;(]", m.get("status_reason") or m.get("status") or "?")[0].strip() or "?"
                       for m in metas_all.values() if m.get("status") != "done")
    if status in FAILED and not answered:
        outcome = "failed"
    elif status == "stuck":
        outcome = "stuck-stopped"
    elif unresolved or workarounds or answered or not_done:
        outcome = "done with limitation"
    else:
        outcome = "done"
    rec.update(run=str(run), status=status, outcome=outcome, stuck_steps=len(causes), not_done=dict(not_done),
               stuck_by_cause=dict(Counter(causes.values())), unresolved=unresolved,
               recovered=dict(recovered), recovered_steps=sorted({f["step"] for f in fixes
                                                                  if f.get("result") == "recovered"}),
               workarounds=len(workarounds), fixes=len(fixes),
               rubric=res.get("score") if res.get("rubric") else None,
               tokens=usage.get("tokens") or res.get("total_tokens"), visible_tokens=res.get("total_tokens"),
               calls=res.get("n_llm_calls"), adapt_tokens=ad.get("tokens", 0) if row["arm"] == "on" else 0,
               adapt_usd=ad.get("cost_usd") if row["arm"] == "on" else None,
               cost_usd=usage.get("cost_usd"), searches=tools.get("web_search", 0), fetches=tools.get("fetch_url", 0),
               latency_min=round((res.get("latency_ms") or 0) / 60000, 1))
    return rec


# box: stage_e
def samples(rows: list[dict], records: list[dict], k: int = 3, seed: int = 117) -> list[dict]:
    """k recovered steps of the on arm picked at random (seeded), each with its trace lines and its output before
    and after the fix."""
    pool = [(r, n) for r in records if r["arm"] == "on" and r.get("run") for n in r.get("recovered_steps", [])]
    out = []
    for r, n in random.Random(seed).sample(pool, min(k, len(pool))):
        run = Path(r["run"])
        lines = [{"name": t["name"], **{k2: v for k2, v in t.items() if k2.startswith("amoeba.") and k2 != "amoeba.box"}}
                 for t in _trace(run) if t.get("kind") == "event" and t.get("name") in TRACE_NAMES
                 and t.get("amoeba.step") == n]
        art = run / "artifacts"
        before = next((art / f"step_{n}.{s}.md" for s in ("try1", "first") if (art / f"step_{n}.{s}.md").exists()), None)
        res = _load(run / "result.json") or {}
        fixes = [f for f in (res.get("adaptation") or {}).get("fixes", []) if f["step"] == n]
        out.append({"task": r["task"], "seed": r["seed"], "step": n, "fixes": fixes, "trace": lines,
                    "before": before.read_text(encoding="utf-8")[:700] if before else "(not kept)",
                    "after": (art / f"step_{n}.md").read_text(encoding="utf-8")[:700]
                    if (art / f"step_{n}.md").exists() else "(replaced by other steps)"})
    return out


def _sum(records: list[dict], arm: str) -> dict:
    rs = [r for r in records if r["arm"] == arm]
    tot = lambda k: sum((r.get(k) or 0) for r in rs)
    return {"runs": len(rs), "outcomes": dict(Counter(r["outcome"] for r in rs)), "stuck_steps": tot("stuck_steps"),
            "stuck_by_cause": dict(sum((Counter(r.get("stuck_by_cause") or {}) for r in rs), Counter())),
            "recovered": dict(sum((Counter(r.get("recovered") or {}) for r in rs), Counter())),
            "workarounds": tot("workarounds"), "tokens": tot("tokens"), "adapt_tokens": tot("adapt_tokens"),
            "wall_min": round(tot("wall_s") / 60, 1), "searches": tot("searches"), "fetches": tot("fetches"),
            "rubric": [r["rubric"] for r in rs if r.get("rubric") is not None]}


# box: stage_e
def report(folder: Path, seed: int = 117) -> tuple[str, dict]:
    rows = [json.loads(l) for f in sorted(folder.rglob("pairs.jsonl"))       # one folder, or one per task
            for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    latest = {}
    for r in rows:                                   # a re-run arm replaces its earlier row
        latest[(r["task"], r["seed"], r["arm"])] = r
    records = [run_record(r, folder) for r in latest.values()]
    arms = {a: _sum(records, a) for a in ("off", "on")}
    picks = samples(rows, records, seed=seed)
    md = ["# D117 Stage E report", "", f"Folder: `{folder}`", "", "## Per run", "",
          "| Task | Seed | Arm | Outcome | Steps not done (why) | Stuck steps (cause) | Recovered (rung) | Work-arounds | "
          "Rubric | Tokens | Adapt tokens | Wall (min) | Searches + fetches | Problems |",
          "|---|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in sorted(records, key=lambda r: (r["task"], r["seed"], r["arm"])):
        md.append(f"| {r['task']} | {r['seed']} | {r['arm']} | {r['outcome']} | {r.get('not_done') or '-'} | "
                  f"{r.get('stuck_steps', 0)} "
                  f"{r.get('stuck_by_cause') or ''} | {r.get('recovered') or '-'} | {r.get('workarounds', 0)} | "
                  f"{r.get('rubric') if r.get('rubric') is not None else '-'} | {r.get('tokens') or 0:,} | "
                  f"{r.get('adapt_tokens') or 0:,} | {round((r.get('wall_s') or 0) / 60, 1)} | "
                  f"{r.get('searches', 0)} + {r.get('fetches', 0)} | {'; '.join(r['problems']) or '-'} |")
    md += ["", "## Per arm", "", "| | off | on |", "|---|---|---|"]
    for k in ("runs", "outcomes", "stuck_steps", "stuck_by_cause", "recovered", "workarounds", "tokens",
              "adapt_tokens", "wall_min", "searches", "fetches", "rubric"):
        md.append(f"| {k} | {arms['off'][k]} | {arms['on'][k]} |")
    md += ["", "## Recovered steps, picked at random (on arm)", "",
           "The off arm makes no fixes, so it has no recovered steps."]
    if not picks:
        md.append("No step was recovered.")
    for s in picks:
        md += ["", f"### {s['task']} seed {s['seed']}, step {s['step']}", "", "Fixes:"]
        md += [f"- {f['kind']} (rung {f['rung']}): {f['result']}" for f in s["fixes"]]
        md += ["", "Trace lines:", "", "```"] + [json.dumps(t, ensure_ascii=False, default=str)[:600] for t in s["trace"]]
        md += ["```", "", "Before:", "", "```", s["before"], "```", "", "After:", "", "```", s["after"], "```"]
    data = {"records": records, "arms": arms, "samples": picks}
    return "\n".join(md) + "\n", data


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("folder")
    p.add_argument("--seed", type=int, default=117, help="the seed of the random pick of recovered steps")
    a = p.parse_args(argv)
    md, data = report(Path(a.folder), a.seed)
    (Path(a.folder) / "REPORT.md").write_text(md, encoding="utf-8")
    (Path(a.folder) / "report.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
