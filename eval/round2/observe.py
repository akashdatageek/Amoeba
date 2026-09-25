"""Observer round 2 — round 1's facts for each run, plus what the pool step did and what came of it.

    python eval/round2/observe.py runs/<run_id> [...]        # writes eval/round2/facts/<task_id>.json

Read-only, like round 1's observer (whose extraction it reuses). Added per run:
- every capability request's outcome (status, reason, pool id, candidates) and the pool trace events;
- for every call of a pool tool: its host, what the helper sent (the ActionInput of the reply that chose it), the
  source id the result got, the result's first characters, and whether the final answer cites that source id.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "round1"))
from observe import lines, observe as observe_r1   # noqa: E402

SECTION = re.compile(r"^##\s*ActionInput\s*$(.*?)(?=^##\s|\Z)", re.M | re.S)


def action_input(chat: dict) -> str:
    out = "\n".join(m.get("content", "") for m in chat.get("gen_ai.output.messages") or [])
    m = SECTION.search(out)
    return m.group(1).strip() if m else ""


def pool_facts(run: Path) -> dict:
    trace = lines(run / "trace.jsonl")
    result = json.loads((run / "result.json").read_text(encoding="utf-8")) if (run / "result.json").exists() else {}
    answer = result.get("answer") or ""
    index = {}
    idx_path = Path("data/pool/index.json")
    if idx_path.exists():
        index = {e["id"]: e for e in json.loads(idx_path.read_text(encoding="utf-8"))["entries"]}
    ev = lambda n: [t for t in trace if t["name"] == n]
    by_name = {}
    for a in result.get("pool", {}).get("attached", []):
        by_name[a["as"]] = a
    calls = []
    for i, t in enumerate(trace):
        if t["name"] == "execute_tool" and str(t.get("gen_ai.tool.name", "")).startswith("pool:"):
            name = t["gen_ai.tool.name"]
            agent = t.get("gen_ai.agent.name")
            # the reply that chose the tool: the last chat of that agent written before this span closed
            chat = next((c for c in reversed(trace[:i]) if c["name"] == "chat" and c.get("gen_ai.agent.name") == agent),
                        {})
            call_ev = next((c for c in trace[i + 1:] if c["name"] == "pool_call" and c.get("gen_ai.tool.name") == name),
                           None)
            err = next((c for c in trace[i + 1:i + 4] if c["name"] in ("tool_error", "tool_limit")
                        and c.get("gen_ai.tool.name") == name), None)
            pid = (by_name.get(name) or {}).get("id")
            sid = call_ev.get("amoeba.source_id") if call_ev else None
            # what came back: the first prompt after the call that shows this source id or the tool's error line
            shown = ""
            for c in trace[i + 1:]:
                if c["name"] == "chat" and c.get("gen_ai.agent.name") == agent:
                    msg = "\n".join(m.get("content", "") for m in c.get("gen_ai.input.messages") or [])
                    k = msg.find(f"[{sid}] {name}") if sid else msg.find(f"error: {name}")
                    if k >= 0:
                        shown = msg[k:k + 600]
                    break
            calls.append({"tool": name, "pool_id": pid,
                          "host": urlparse((index.get(pid) or {}).get("remote_url", "")).hostname,
                          "agent": agent, "step": t.get("amoeba.step") or (call_ev or {}).get("amoeba.step"),
                          "sent": action_input(chat)[:500],
                          "mcp_tool": (call_ev or {}).get("amoeba.pool.tool"),
                          "source_id": sid, "result_chars": (call_ev or {}).get("amoeba.chars"),
                          "is_error": (call_ev or {}).get("amoeba.is_error"),
                          "error": (err or {}).get("error.type") or ((err or {}).get("name") if err else None),
                          "result_start": shown,
                          "cited_in_answer": bool(sid) and f"[{sid}]" in answer or bool(sid and re.search(
                              rf"\[[^\]]*\b{sid}\b[^\]]*\]", answer))})
    return {
        "pool_summary": result.get("pool"),
        "pool_events": {n: [{k: v for k, v in e.items() if k.startswith(("amoeba.", "gen_ai.agent", "error"))}
                            for e in ev(n)]
                        for n in ("pool_unavailable", "pool_match", "pool_vet", "pool_pinned", "pool_connect_failed",
                                  "pool_summary")},
        "pool_calls": calls,
        "unknown_tool_pool": [(u.get("gen_ai.agent.name"), u.get("gen_ai.tool.name")) for u in ev("unknown_tool")],
        "skills_on_cards": [a for a in result.get("pool", {}).get("attached", []) if a.get("kind") == "skill"],
    }


def main(argv: list[str]) -> int:
    out = HERE / "facts"
    out.mkdir(exist_ok=True)
    for arg in argv:
        run = Path(arg)
        facts = observe_r1(run)
        facts["pool"] = pool_facts(run)
        (out / f"{facts['task_id']}.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False, default=str),
                                                      encoding="utf-8")
        p, c = facts["pool"], facts["cost"]
        s = p["pool_summary"] or {}
        print(f"{facts['task_id']}: error={facts['error']} tokens={c['total_tokens']} calls={c['llm_calls']} "
              f"steps={[x['status'] for x in facts['box3']['steps']]} pool filled={s.get('filled')} "
              f"unfilled={s.get('unfilled')} reasons={s.get('reasons')} pool_calls={len(p['pool_calls'])} "
              f"cited={sum(x['cited_in_answer'] for x in p['pool_calls'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
