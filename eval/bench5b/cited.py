"""bench5b — for each run of a task: every URL in the final answer, and whether it appears in a tool result the team
really got (web_search / fetch_url results, which come back in the next model call's input) before the answer. Also
prints the lines of those results that mention a given phrase. Read-only.

    python eval/bench5b/cited.py bench5-ceo [phrase ...]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URL = re.compile(r"https?://[^\s)\]>\"'`,]+")


def main() -> None:
    task, phrases = sys.argv[1], sys.argv[2:]
    for line in (ROOT / "eval/bench5b/ledger.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["task"] != task or not r.get("run"):
            continue
        d = ROOT / r["run"]
        if not d.exists():
            d = ROOT / "eval/bench5b/runs" / r["arch"] / Path(r["run"]).name
        answer = json.loads((d / "result.json").read_text()).get("answer") or ""
        seen = ""
        for l in (d / "trace.jsonl").read_text().splitlines():
            e = json.loads(l)
            if e.get("name") == "chat":
                for m in e.get("gen_ai.input.messages") or []:
                    c = m.get("content") if isinstance(m, dict) else str(m)
                    if isinstance(c, str) and ("Observation" in c or "Result" in c or "http" in c):
                        seen += "\n" + c
        print(f"== {r['arch']} r{r['rep']}")
        for u in dict.fromkeys(u.rstrip(".") for u in URL.findall(answer)):
            print(f"   cited {u}: {'IN a tool result' if u in seen else ('host seen' if u.split('/')[2] in seen else 'NOT seen')}")
        for p in phrases:
            hits = [s.strip()[:220] for s in re.split(r"\n", seen) if p.lower() in s.lower()]
            for h in list(dict.fromkeys(hits))[:3]:
                print(f"   [{p}] {h}")


if __name__ == "__main__":
    main()
