"""bench5b — per run: tool calls (name, ok) and plan step statuses, for the observer's scoring. Read-only.

    python eval/bench5b/toolcalls.py [task]
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for line in (ROOT / "eval/bench5b/ledger.jsonl").read_text().splitlines():
    r = json.loads(line)
    if len(sys.argv) > 1 and r["task"] != sys.argv[1] or not r.get("run"):
        continue
    d = ROOT / r["run"]
    if not (d / "trace.jsonl").exists():
        d = ROOT / "eval/bench5b/runs" / r["arch"] / Path(r["run"]).name
    tools, steps, files = Counter(), [], []
    for l in (d / "trace.jsonl").read_text().splitlines():
        e = json.loads(l)
        if e.get("name") == "execute_tool":
            tools[f"{e.get('gen_ai.tool.name')}@{e.get('gen_ai.agent.name')}"] += 1
        elif e.get("name") == "step_done":
            steps.append(f"{e['amoeba.step']}:{e['amoeba.status']}" + (f"({e['amoeba.status_reason'][:70]})"
                                                                       if e.get("amoeba.status_reason") else ""))
        elif e.get("name") in ("local_file", "files_made", "file_made"):
            files.append(str(e.get("amoeba.path") or e.get("amoeba.files")))
    ws = d / "workspace"
    made = sorted(str(p.relative_to(ws)) for p in ws.rglob("*") if p.is_file() and "skills" not in p.parts) \
        if ws.exists() else []
    print(f"{r['task']} {r['arch']} r{r['rep']}: tools={dict(tools)}\n   steps={steps}\n   workspace={made}")
