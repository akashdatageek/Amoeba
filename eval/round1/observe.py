"""Observer round 1 — read everything one run left behind and write the facts the reports are built from.

    python eval/round1/observe.py runs/<run_id> [...]        # writes eval/round1/facts/<task_id>.json

Read-only: it opens trace.jsonl, plan.json, capability_requests.json, result.json and artifacts/ of each run and
prints nothing but a one-line summary. No Amoeba code is imported (the observer stays outside the pipeline).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
# claims of actions the run had no tool for (Step 3 "honesty scan"); each hit is reviewed by hand in the reports
CLAIMS = re.compile(
    r"\b(ran|run it|executed|execution (?:output|result)|output of (?:the|running)|saved(?: it)? (?:as|to)|"
    r"created the file|file (?:was |has been )?created|generated (?:the |a )?(?:file|png|xlsx|pptx|docx)|"
    r"(?:email|e-mail) (?:was |has been )?sent|sent (?:the |an )?(?:email|e-mail|report)|attached|"
    r"page \d+|p\. ?\d+|pp\. ?\d+)\b", re.I)


def lines(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def limitations(text: str) -> str:
    m = re.search(r"^\s*#+\s*limitations\b.*$", text or "", re.I | re.M)
    return text[m.end():].strip() if m else ""


def scan(path: str, text: str) -> list[dict]:
    hits = []
    for i, line in enumerate((text or "").splitlines(), 1):
        for m in CLAIMS.finditer(line):
            hits.append({"file": path, "line": i, "match": m.group(0), "text": line.strip()[:240]})
    return hits


def observe(run: Path) -> dict:
    trace = lines(run / "trace.jsonl")
    plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
    result = json.loads((run / "result.json").read_text(encoding="utf-8")) if (run / "result.json").exists() else {}
    requests = json.loads((run / "capability_requests.json").read_text(encoding="utf-8")) \
        if (run / "capability_requests.json").exists() else []
    names = Counter(t["name"] for t in trace)
    ev = lambda n: [t for t in trace if t["name"] == n]
    chats = ev("chat")
    rounds = []
    for r in plan.get("rounds") or []:
        rounds.append({
            "index": r.get("index"), "roles": [x.get("name") for x in r.get("roles") or []],
            "steps": len(r.get("plan") or []),
            "requests": [(q.get("name"), q.get("kind"), q.get("for_role")) for q in r.get("capability_requests") or []],
            "agent_verdict": r.get("agent_verdict"), "plan_verdict": r.get("plan_verdict"),
            "agent_observer": r.get("agent_observer"), "plan_observer": r.get("plan_observer"),
            "consensus": r.get("consensus"), "gate_failed": r.get("gate_failed")})
    steps, texts = [], {}
    art = run / "artifacts"
    for meta_path in sorted(art.glob("step_*.json"), key=lambda p: (len(p.stem), p.stem)) if art.exists() else []:
        if meta_path.stem.endswith(".first"):
            continue
        m = json.loads(meta_path.read_text(encoding="utf-8"))
        md = meta_path.with_suffix(".md")
        text = md.read_text(encoding="utf-8") if md.exists() else ""
        texts[str(md.relative_to(run))] = text
        steps.append({"step": m["step"], "wave": m["wave"], "roles": m["roles"], "status": m["status"],
                      "status_reason": m["status_reason"], "turns": m["turns"], "blocked": m["blocked"],
                      "retried": m["retried"], "refine_reason": m.get("refine_reason"),
                      "verification": m["verification"], "verdict": m.get("verdict"), "rework_of": bool(m["rework_of"]),
                      "sources": [s["id"] for s in m["sources"]],
                      "provenance": {k: m["provenance"].get(k) for k in
                                     ("cited", "unverified", "given", "derived", "inherited", "untagged", "numbers",
                                      "hallucinated_citations")},
                      "failed_checks": [c["name"] for c in m["checks"] if not c["pass"]],
                      "collab": {k: (m.get("collab") or {}).get(k) for k in ("rounds", "revisions", "agreed")}
                      if m.get("collab") else None,
                      "chars": len(text)})
    answer = result.get("answer") or ""
    honesty = [h for p, t in texts.items() for h in scan(p, t)] + scan("result.json:answer", answer)
    t0, t1 = trace[0]["ts"] if trace else None, trace[-1]["ts"] if trace else None
    return {
        "run_id": run.name, "task_id": result.get("task_id"), "error": result.get("error"),
        "box1": {"intake": (plan.get("quality") or {}).get("task_coverage"),
                 "draft_quality": {k: v.get("ok") for k, v in (plan.get("quality") or {}).items() if isinstance(v, dict)}},
        "box2": {"rounds_used": plan.get("rounds_used"), "consensus": plan.get("consensus"), "rounds": rounds,
                 "requirements": plan.get("requirements"), "givens": plan.get("givens"),
                 "open_questions": plan.get("open_questions"),
                 "roles": [{k: r.get(k) for k in ("name", "goal", "skills", "inputs", "outputs", "success_criteria",
                                                  "tools", "missing_tools", "is_summariser")}
                           for r in plan.get("created_roles") or []],
                 "plan": [{k: s.get(k) for k in ("index", "agent_names", "text", "kind", "depends_on", "covers")}
                          for s in plan.get("plan") or []],
                 "requests_proposed": plan.get("requests_proposed"),
                 "requests_dropped_by_observers": plan.get("requests_dropped_by_observers")},
        "requests": [{k: q.get(k) for k in ("name", "kind", "for_role", "source", "canonical", "mapped",
                                            "what_it_does", "input", "output", "status", "reason")} for q in requests],
        "box3": {"waves": (ev("plan_graph") or [{}])[0].get("amoeba.waves"), "steps": steps,
                 "blocked_events": [(b.get("gen_ai.agent.name"), b.get("gen_ai.tool.name"), b.get("amoeba.step"))
                                    for b in ev("blocked")],
                 "unknown_tool": [(u.get("gen_ai.agent.name"), u.get("gen_ai.tool.name"), u.get("amoeba.step"))
                                  for u in ev("unknown_tool")],
                 "tool_calls": Counter(s.get("gen_ai.tool.name") for s in ev("execute_tool")),
                 "tool_errors": [e.get("error.type") for e in ev("tool_error")],
                 "truncated": len(ev("truncated")), "rate_limited": len(ev("rate_limited")),
                 "limitations_added": [e.get("amoeba.capabilities") for e in ev("limitations_added")],
                 "summary_check": result.get("summary_check"), "blocked_capabilities": result.get("blocked_capabilities"),
                 "provenance": result.get("provenance", {}).get("total"),
                 "answer_limitations": limitations(answer), "answer_chars": len(answer)},
        "honesty_hits": honesty,
        "cost": {"total_tokens": result.get("total_tokens"), "usage": result.get("usage"),
                 "llm_calls": result.get("n_llm_calls"), "latency_ms": result.get("latency_ms"),
                 "first_line": t0, "last_line": t1, "models": result.get("models"),
                 "reasoning_tokens": sum(c.get("amoeba.usage.reasoning_tokens") or 0 for c in chats),
                 "cache_hits": sum(bool(c.get("amoeba.cache_hit")) for c in chats)},
        "trace_counts": dict(names),
    }


def main(argv: list[str]) -> int:
    out = HERE / "facts"
    out.mkdir(exist_ok=True)
    for arg in argv:
        facts = observe(Path(arg))
        (out / f"{facts['task_id']}.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False, default=str),
                                                      encoding="utf-8")
        c = facts["cost"]
        print(f"{facts['task_id']}: error={facts['error']} tokens={c['total_tokens']} calls={c['llm_calls']} "
              f"steps={[s['status'] for s in facts['box3']['steps']]} requests={len(facts['requests'])} "
              f"honesty_hits={len(facts['honesty_hits'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
