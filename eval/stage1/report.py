"""Part 2: one table of Stage 1 runs (Step 4 and Step 5) from their run folders, plus the judge-access audit.

    python eval/stage1/report.py <runs-root> [<runs-root> ...]   # each holds <label>/<run uuid>/ folders

Per run: the score from its scorers (sim_score.json), requirements met, stuck steps, each Box 4 round (both edits, the
control, the pick, the verdicts), whether the answer is an honest stop, cost, time and calls. The audit lists every
mention of the frozen judge folders (tasks/*_keys, tasks/*_hidden) in what the team saw or ran; any hit voids the run.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from amoeba.llm.limits import estimate  # noqa: E402

JUDGE = re.compile(r"stage1_keys|stage1_hidden|_keys/|_hidden/|_hidden_tests")
HONEST = re.compile(r"could not (reach|get|access|obtain|find)|cannot (reach|access|get)|no access|not able to|"
                    r"unable to|BLOCKED", re.I)


def chat_spans(trace: Path) -> list[dict]:
    return [s for s in map(json.loads, trace.open(encoding="utf-8")) if s.get("kind") == "span" and s.get("name") == "chat"]


def audit(run: Path) -> list[str]:
    """Judge-folder mentions in the team's prompts, replies and tool calls (the trace) and in its workspace files."""
    hits = []
    for line in (run / "trace.jsonl").open(encoding="utf-8"):
        if JUDGE.search(line):
            e = json.loads(line)
            if e.get("name") == "judge_hash":
                continue
            hits.append(f"trace {e.get('name')}: {JUDGE.search(line).group(0)}")
    ws = run / "workspace"
    for f in ws.rglob("*") if ws.is_dir() else []:
        if f.is_file() and f.stat().st_size < 2_000_000 and "skills" not in f.relative_to(ws).parts[:1]:
            try:
                if JUDGE.search(f.read_text(encoding="utf-8", errors="ignore")):
                    hits.append(f"workspace {f.relative_to(ws)}")
            except OSError:
                pass
    return hits


def rounds(run: Path) -> list[dict]:
    p = run / "rounds.jsonl"
    out = []
    for r in map(json.loads, p.open(encoding="utf-8")) if p.exists() else []:
        if r.get("kind") != "round":
            continue
        edits = [f"{e['scope']}:{e['op']}" for e in r.get("edits") or []]
        probes = [f"{p['scope']}:{p['op']}={p['status']}(-{len(p.get('cleared') or [])}/+{len(p.get('new') or [])})"
                  for p in r.get("probes") or []]
        ctl = r.get("control")
        out.append({"step": r["step"], "cause": r["cause"], "edits": edits, "probes": probes,
                    "control": (ctl or {}).get("status") if ctl else f"none ({r.get('control_skipped') or ''})",
                    "pick": r.get("pick"), "pick_reason": r.get("pick_reason"),
                    "verdicts": r.get("verdicts") or r.get("outcome")})
    return out


def one(label: str, run: Path) -> dict:
    res = json.loads((run / "result.json").read_text(encoding="utf-8"))
    sim = json.loads((run / "sim_score.json").read_text(encoding="utf-8")) if (run / "sim_score.json").exists() \
        else (res.get("sim_score") or {})
    use = estimate(chat_spans(run / "trace.jsonl"), "claude-sonnet-5-5")
    req = res.get("requirement_status") or {}
    ad = res.get("adaptation") or {}
    stuck = sorted({k.get("step") for k in ad.get("fixes") or []} | {s.get("step") for s in ad.get("stuck_steps") or []
                                                                     if isinstance(s, dict)})
    ans = res.get("answer") or ""
    return {"label": label, "task": res.get("task_id"), "run": run.name, "score": sim.get("score"),
            "parts": {p["name"]: p.get("score") for p in sim.get("parts") or []}, "score_error": sim.get("error"),
            "req_met": sum(v == "met" for v in req.values()), "req_total": len(req), "status": res.get("status"),
            "error": (res.get("error") or "")[:120], "stuck_steps": [s for s in stuck if s is not None],
            "fixes": len(ad.get("fixes") or []), "rounds": rounds(run), "honest_stop": bool(HONEST.search(ans)),
            "lessons_learned": ad.get("lessons_learned"), "usd": use["cost_usd"], "calls": use["calls"],
            "tokens": use["tokens"], "minutes": round((res.get("latency_ms") or 0) / 60000, 1),
            "verifier": [v.get("independence") for v in res.get("verifier_independence") or []],
            "faults": res.get("faults"), "audit": audit(run)}


def main(roots: list[str]) -> None:
    rows = []
    for root in map(Path, roots):
        for lab in sorted(p for p in root.iterdir() if p.is_dir()):
            for run in sorted(q for q in lab.iterdir() if (q / "result.json").exists()):
                rows.append(one(lab.name, run))
    print("| run | task | score (parts) | req met | status | stuck steps / fixes | Box 4 rounds | honest stop | "
          "cost | min | calls | audit |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        parts = ", ".join(f"{k} {v}" for k, v in r["parts"].items())
        rnd = "; ".join(f"s{x['step']} {x['cause']}: {' / '.join(x['probes'])}; control {x['control']}; pick "
                        f"{x['pick'] or 'none'}" for x in r["rounds"]) or "-"
        print(f"| {r['label']} | {r['task']} | {r['score']} ({parts}) | {r['req_met']}/{r['req_total']} | "
              f"{r['status']} | {r['stuck_steps']} / {r['fixes']} | {rnd} | {'yes' if r['honest_stop'] else 'no'} | "
              f"${r['usd']:.2f} | {r['minutes']} | {r['calls']} | {'VOID: ' + str(r['audit'][:3]) if r['audit'] else 'clean'} |")
    total = sum(r["usd"] or 0 for r in rows)
    print(f"\ntotal ${total:.2f} over {len(rows)} run(s)")
    Path("stage1_rows.json").write_text(json.dumps(rows, indent=1, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
