"""Observer rounds 2b and 3 — round 2's facts per run (eval/round2/observe.py), written to this round's folder, plus
(round 3) what the local toolbox did: calls, refusals, files created, skills attached.

    python eval/round2b/observe.py <out dir> runs/<run_id> [...]     # writes <out dir>/facts/<task_id>.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "round2"))
sys.path.insert(0, str(HERE.parent / "round1"))
from observe import lines, observe as observe_r1   # noqa: E402  (round 1's)
import importlib.util                               # noqa: E402

_spec = importlib.util.spec_from_file_location("observe_r2", HERE.parent / "round2" / "observe.py")
observe_r2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(observe_r2)


def local_facts(run: Path) -> dict:
    trace = lines(run / "trace.jsonl")
    result = json.loads((run / "result.json").read_text(encoding="utf-8")) if (run / "result.json").exists() else {}
    ev = lambda n: [{k: v for k, v in t.items() if k.startswith(("amoeba.", "gen_ai.tool", "error"))}
                    for t in trace if t["name"] == n]
    steps = []
    for p in sorted((run / "artifacts").glob("step_*.json")):
        if p.stem.count("_") == 1:
            m = json.loads(p.read_text(encoding="utf-8"))
            if "claimed_files" in m:
                steps.append({"step": m["step"], "status": m["status"], "claimed": m["claimed_files"],
                              "missing": m["claimed_files_missing"]})
    return {"files_created": result.get("files_created"), "local_tool_calls": result.get("local_tool_calls"),
            "local_refusals": result.get("local_refusals"), "skills_attached": result.get("skills_attached"),
            "server": (result.get("pool") or {}).get("local"),
            "calls": ev("local_call"), "refused": ev("local_refused"), "tools_refused_once": ev("local_tool_refused"),
            "unavailable": ev("local_unavailable"), "claims": steps}


def main(argv: list[str]) -> int:
    out = Path(argv[0]) / "facts"
    out.mkdir(parents=True, exist_ok=True)
    for arg in argv[1:]:
        run = Path(arg)
        facts = observe_r1(run)
        facts["pool"] = observe_r2.pool_facts(run)
        facts["local"] = local_facts(run)
        (out / f"{facts['task_id']}.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False, default=str),
                                                      encoding="utf-8")
        p, c, l = facts["pool"], facts["cost"], facts["local"]
        s = p["pool_summary"] or {}
        print(f"{facts['task_id']}: error={facts['error']} tokens={c['usage'].get('tokens')} calls={c['llm_calls']} "
              f"steps={[x['status'] for x in facts['box3']['steps']]} filled={s.get('filled')} "
              f"reasons={s.get('reasons')} attached={[a['as'] for a in s.get('attached', [])]} "
              f"pool_calls={len(p['pool_calls'])} local_calls={l['local_tool_calls']} refusals={l['local_refusals']} "
              f"files={[f['path'] for f in l['files_created'] or []]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
