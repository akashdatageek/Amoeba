"""Short view of one task's runs across rounds 3b and 4 (for scoring): python eval/round4/brief.py <task> [answer chars]"""
import json, sys
from pathlib import Path
F = json.loads((Path(__file__).parent / "facts.json").read_text())
task, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1500
for f in sorted((x for x in F if x["task"] == task), key=lambda x: (x["round"], x["repeat"])):
    print(f"\n######## {f['round']} rep{f['repeat']} {f['run']}  err={f['error']} calls={f['calls']} tok={f['usage']['tokens']}")
    print("requests:", [(q['name'], q['for_role'], q['status'], q['reason'], q['pool_id']) for q in f["requests"]])
    print("local:", [(s, t, (i or '')[:70].replace('\n', ' '), e) for s, t, i, e in f["local_calls"]], "refused:", f["local_refused"])
    print("pool:", f["pool_calls"], "web:", f["web_calls"], "files:", [x['path'] for x in f["files_created"] or []])
    p = f["provenance"]["total"]; sc = f["summary_check"] or {}
    print(f"prov cited={p['cited']} unver={p['unverified']} untagged={p['untagged']} halluc={p['hallucinated_citations']} | lim={sc.get('limitations_section')} added={sc.get('limitations_added_by_code')} unused_added={sc.get('unused_added_by_code')} files_listed={sc.get('files_listed_by_code')} left_out={sc.get('cited_figures_left_out')}")
    for s in f["steps"]:
        print(f"  step {s['step']} {s['roles']} {s['status']} ({s['status_reason']}) nn={s['not_needed']} miss={s['contract_missing']} unused={s['unused']} refine={s['refine_reason']} v={s['verdict']} chg={s['changed_by_contract']} tools={[(a,t,o) for a,t,o,_ in s['tool_calls']]}")
    for x in f["not_needed_lines"]:
        print("  NN:", x["step"], x["agent"], x["line"][:200])
    print("  rework:", [r.get('amoeba.step') for r in f['rework']], "skipped:", [(r.get('amoeba.step'), r.get('amoeba.lacked')) for r in f['rework_skipped']], "contract cost:", f['contract_refine_cost'])
    ans = Path(f["run"]).joinpath("result.json")
    a = json.loads(ans.read_text())["answer"] or ""
    print("  ANSWER:", a[:n].replace("\n", "\n    "))
