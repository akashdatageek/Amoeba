"""Observer round 2b — network dry run (no LLM): what the D60 pool step would show the picker for round 1's requests.

    python eval/round2b/dryrun.py [--probe]      # writes eval/round2b/dryrun.json; --probe tries one HTTPS request per host

As eval/round2/dryrun.py, but in D60's order: up to vet_depth keyword matches are vetted first and only the best
max_candidates that pass are listed (what the picker will see); a request with none is `all_refused` (no AI call).
The hosts of the shown tools are what a round-2b run may need to reach.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval" / "round2"))
from dryrun import INSTALLED, probe                   # noqa: E402
from amoeba.pool.index import load_index            # noqa: E402
from amoeba.pool.match import rank                   # noqa: E402
from amoeba.pool.stock import PoolSetup, vet         # noqa: E402
from amoeba.task.models import Draft                 # noqa: E402


def main(argv: list[str]) -> int:
    setup = PoolSetup(env={})
    index = load_index(setup.dir)
    if index is None:
        print("no pool cache; run python -m amoeba pool refresh")
        return 1
    entries, lim = index["entries"], setup.limits
    top, depth = int(lim["max_candidates"]), int(lim.get("vet_depth", 50))
    rows, hosts = [], {}
    for run in sorted((ROOT / "eval/round1/runs").iterdir()):
        draft = Draft.model_validate(json.loads((run / "plan.json").read_text(encoding="utf-8")))
        roles = {r.name: r for r in draft.created_roles}
        seen = set()
        for q in draft.capability_requests:
            key = (q.kind, (q.canonical or q.name).lower(), q.for_role)
            if key in seen:
                continue
            seen.add(key)
            row = {"task": run.name.split("__")[0], "request": q.name, "kind": q.kind, "for_role": q.for_role}
            if q.canonical in INSTALLED or q.name in INSTALLED:
                rows.append({**row, "skipped": "registered_tool", "shown": [], "refused": {}})
                continue
            if not (q.for_role in roles or any(q.name in r.missing_tools for r in roles.values())):
                rows.append({**row, "skipped": "no_helper", "shown": [], "refused": {}})
                continue
            shown, refused = [], {}
            for score, e in rank(q, entries, depth):
                reason = vet(e, setup)[0]
                if reason is None:
                    host = urlparse(e.get("remote_url", "")).hostname if e["kind"] == "tool" else None
                    shown.append({"id": e["id"], "kind": e["kind"], "score": score, "host": host})
                    if host:
                        hosts.setdefault(host, []).append(f"{row['task']}:{q.name}:{e['id']}")
                    if len(shown) == top:
                        break
                else:
                    refused[reason] = refused.get(reason, 0) + 1
            rows.append({**row, "shown": shown, "refused": refused,
                         **({"skipped": "all_refused"} if not shown else {})})
    out = {"refreshed_at": index.get("refreshed_at"), "entries": len(entries), "vet_depth": depth, "requests": rows,
           "hosts": {h: sorted(set(v)) for h, v in sorted(hosts.items())}}
    if "--probe" in argv:
        out["probes"] = [probe(h) for h in sorted(hosts)]
    (Path(__file__).parent / "dryrun.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for r in rows:
        print(f"{r['task']:14} {r['request']:24} {r.get('skipped') or str(len(r['shown'])) + ' shown'}  refused {r['refused']}")
        for c in r["shown"]:
            print(f"    {c['score']:2} {c['kind']:5} {c['id']}  {c['host'] or ''}")
    for p in out.get("probes", []):
        print(("BLOCKED " if p["blocked"] else "ok      ") + f"{p['host']:50} {p['http_code']} {p['error'][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
