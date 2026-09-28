"""Professor benchmark — Box 2 in plain words, per task (for the walkthrough report).

    python eval/professor/box2.py prof-loan

Prints each drafting round: the Planner's requirements, roles (one line each), steps with depends_on and capability
requests; each Observer's verdict and suggestions (their SUGGESTIONS section, or the reply's tail); and what changed
between rounds. Read-only on eval/professor/drafts/.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def section(raw: str, name: str) -> str:
    m = re.search(rf"##\s*{name}\s*\n(.*?)(?=\n##\s|\Z)", raw or "", re.S | re.I)
    return m.group(1).strip() if m else ""


def main(task: str) -> None:
    d = json.loads((ROOT / "eval/professor/drafts/drafts" / f"{task}.0.json").read_text())
    print(f"# {task}: rounds_used={d['rounds_used']} consensus={d['consensus']}")
    for r in d["rounds"]:
        print(f"\n## Round {r['index']}")
        req = section(r["planner_raw"], "Requirements")
        print("Requirements:", req[:800] if req else "(see final)")
        for role in r.get("roles") or []:
            print(f"  role: {role.get('name')} — {role.get('goal') or role.get('description')} · tools={role.get('tools')}")
        for i, s in enumerate(r.get("plan") or [], 1):
            print(f"  step {i}: {s.get('text')} · kind={s.get('kind')} · depends_on={s.get('depends_on')} · output={s.get('output')}")
        for q in r.get("capability_requests") or []:
            print(f"  request: {q.get('name')} ({q.get('kind')}) for {q.get('for_role')}: {q.get('what_it_does')}")
        for who in ("agent_observer", "plan_observer"):
            raw = r.get(f"{who}_raw") or ""
            verdict = r.get("agent_verdict" if who == "agent_observer" else "plan_verdict")
            sugg = section(raw, "Suggestions") or section(raw, "Issues") or raw.split("</thought>")[-1][-900:]
            print(f"  {who}: verdict={verdict} n_suggestions={r.get(('agent' if who == 'agent_observer' else 'plan') + '_suggestions_n')}")
            print("    " + re.sub(r"\s+", " ", sugg)[:1200])
    print("\n## Final")
    print("Requirements:", d.get("requirements"))
    for role in d["created_roles"]:
        print(f"  role: {role['name']}{' (summariser)' if role.get('is_summariser') else ''} — {role.get('goal') or role.get('description')} · tools={role.get('tools')} missing={role.get('missing_tools')}")
    for s in d["plan"]:
        print(f"  step {s['index'] + 1}: {s['text']} · depends_on={s.get('depends_on')} · kind={s.get('kind')}")
    for q in d["capability_requests"]:
        print(f"  request: {q['name']} ({q['kind']}) for {q['for_role']} → canonical {q.get('canonical')} mapped={q.get('mapped')}")
    print("requests proposed/dropped:", d.get("requests_proposed"), d.get("requests_dropped_by_observers"))


if __name__ == "__main__":
    main(sys.argv[1])
