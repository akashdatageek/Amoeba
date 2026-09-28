"""Professor benchmark — a readable timeline of one run (for the observer writing the walkthrough report).

    python eval/professor/walk.py runs/professor/<arch>/<run_id> [--full]

Read-only. Prints: the result (answer, error, cost), what the toolbox did per request, then every model call in order
(who, which box, the action and its input, or the text it wrote), every tool call with its input and a short result,
local calls and files, pool and web calls, and — for the plan runner — each step's status, contract check, verdict and
rework.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path


def msgs(v):
    if isinstance(v, list):
        return v
    for f in (ast.literal_eval, json.loads):
        try:
            return f(v)
        except Exception:
            pass
    return []


def short(s, n=300):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n] + " …"


def main(run: Path, full: bool = False) -> None:
    res = json.loads((run / "result.json").read_text())
    tr = [json.loads(l) for l in (run / "trace.jsonl").read_text().splitlines() if l.strip()]
    u = res["usage"]
    print(f"# {res['task_id']} · {res['topology']} · {run.name}\nerror={res['error']} calls={res['n_llm_calls']} "
          f"in={u['input']} out={u['output']} reasoning={u['reasoning']} billed={u['tokens']} "
          f"latency={res['latency_ms']/1000:.0f}s")
    print("requests:", [(q["name"], q["for_role"], q.get("status"), q.get("reason"), q.get("pool_id"))
                        for q in res.get("requested_capabilities", [])])
    print("attached:", [(a["as"], a["helpers"]) for a in (res.get("pool") or {}).get("attached", [])])
    print("files_created:", res.get("files_created"), "local calls:", res.get("local_tool_calls"),
          "refusals:", res.get("local_refusals"))
    print()
    n = 0
    for t in tr:
        nm = t["name"]
        if nm == "chat":
            n += 1
            out = msgs(t.get("gen_ai.output.messages", "[]"))
            text = "\n".join(m.get("content", "") for m in out if isinstance(m, dict))
            user = msgs(t.get("gen_ai.input.messages", "[]"))
            ulast = next((m["content"] for m in reversed(user) if m.get("role") == "user"), "") if user else ""
            step = re.search(r"# Your step \(step (\d+)\)", ulast)
            act = re.search(r"##\s*Action\s*\n+(.+?)\n", text + "\n")
            inp = text.split("## ActionInput", 1)[1] if "## ActionInput" in text else ""
            boss_act = re.match(r"\s*(?:#+\s*)?Action\s*:\s*(.+?)\s*\n\s*(?:#+\s*)?ActionInput\s*:\s*(.*)", text, re.S)
            who = t.get("gen_ai.agent.name") or t.get("amoeba.box")
            head = f"[{n}] {t.get('amoeba.box')} · {who}" + (f" · step {step.group(1)}" if step else "") + \
                   f" · in {t.get('gen_ai.usage.input_tokens')} out {t.get('gen_ai.usage.output_tokens')}"
            if act:
                print(f"{head} → ACTION {act.group(1).strip()}: {short(inp, 1500 if full else 400)}")
            elif boss_act:
                print(f"{head} → ACTION {boss_act.group(1).strip()}: {short(boss_act.group(2), 400)}")
            else:
                print(f"{head} → TEXT: {short(text, 3000 if full else 500)}")
        elif nm == "execute_tool":
            print(f"    tool {t.get('gen_ai.tool.name')} ({t.get('gen_ai.agent.name')}) error={t.get('error.type')}")
        elif nm in ("local_call", "local_refused"):
            print(f"    {nm} step {t.get('amoeba.step')}: {t.get('gen_ai.tool.name')} {short(t.get('amoeba.input'), 200)} "
                  f"error={t.get('amoeba.is_error')} files={t.get('amoeba.files')} reason={t.get('amoeba.reason')}")
        elif nm in ("pool_call", "web_search", "fetch_url", "tool_error", "local_source"):
            print(f"    {nm}: " + short({k: v for k, v in t.items() if k.startswith(("amoeba.", "gen_ai.tool", "error"))
                                        and k not in ("amoeba.profile", "amoeba.box")}, 400))
        elif nm in ("step_done", "contract_check", "rework", "rework_skipped", "reverify", "refine", "limitations_added",
                    "blocked", "unknown_tool", "capability_mapped", "summary_check", "rate_limited", "step_contract",
                    "collab_round", "pool_vet", "claimed_file_missing", "check_retry"):
            print(f"  · {nm}: " + short({k: v for k, v in t.items() if k.startswith(("amoeba.", "gen_ai.tool", "http"))
                                         and k not in ("amoeba.profile", "amoeba.box")}, 500))
    print("\n## ANSWER\n" + (res.get("answer") or "(none)"))


if __name__ == "__main__":
    main(Path(sys.argv[1]), "--full" in sys.argv)
