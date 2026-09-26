"""Observer round 2 — network dry run (no LLM): what the pool step would offer for round 1's capability requests.

    python eval/round2/dryrun.py [--probe]      # writes eval/round2/dryrun.json; --probe tries one HTTPS request per host

For every capability request in round 1's saved drafts (round 2 reuses them with --drafts-from), the same code the
run uses ranks the cached pool (top 5, tools and skills alike, D58) and vets every candidate — the picker may choose
any of the five. Requests the step would not send to the picker (an installed tool, no helper) are listed as such.
The remote hosts of the tools that pass vetting are what a round-2 run may need to reach.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from amoeba.pool.index import load_index            # noqa: E402
from amoeba.pool.match import rank                   # noqa: E402
from amoeba.pool.stock import PoolSetup, vet         # noqa: E402
from amoeba.task.models import Draft                 # noqa: E402

INSTALLED = {"echo", "calc", "web_search", "fetch_url"}     # the round's registry (--web-tools on)


def probe(host: str) -> dict:
    """One HTTPS request through the environment's proxy; the gateway's refusal shows as a failed CONNECT."""
    r = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-m", "15", "-w", "%{http_code}", f"https://{host}/"],
                       capture_output=True, text=True)
    blocked = "CONNECT tunnel failed" in r.stderr or "403" in r.stderr
    return {"host": host, "http_code": r.stdout.strip(), "error": r.stderr.strip()[:160], "blocked": blocked}


def main(argv: list[str]) -> int:
    setup = PoolSetup(env={})
    index = load_index(setup.dir)
    if index is None:
        print("no pool cache; run python -m amoeba pool refresh")
        return 1
    entries = index["entries"]
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
                rows.append({**row, "skipped": "registered_tool", "candidates": []})
                continue
            if not (q.for_role in roles or any(q.name in r.missing_tools for r in roles.values())):
                rows.append({**row, "skipped": "no_helper", "candidates": []})
                continue
            cands = []
            for score, e in rank(q, entries, int(setup.limits["max_candidates"])):
                reason = vet(e, setup)[0]
                host = urlparse(e.get("remote_url", "")).hostname if e["kind"] == "tool" else None
                cands.append({"id": e["id"], "kind": e["kind"], "score": score, "vet": reason or "pass", "host": host,
                              "auth_headers": e.get("auth_headers") or []})
                if reason is None and host:
                    hosts.setdefault(host, []).append(f"{row['task']}:{q.name}:{e['id']}")
            rows.append({**row, "candidates": cands})
    out = {"refreshed_at": index.get("refreshed_at"), "entries": len(entries), "requests": rows,
           "hosts": {h: sorted(set(v)) for h, v in sorted(hosts.items())}}
    if "--probe" in argv:
        out["probes"] = [probe(h) for h in sorted(hosts)]
    (Path(__file__).parent / "dryrun.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for r in rows:
        tag = r.get("skipped") or f"{sum(c['vet'] == 'pass' for c in r['candidates'])}/{len(r['candidates'])} pass"
        print(f"{r['task']:14} {r['request']:24} {r['kind']:5} {tag}")
        for c in r["candidates"]:
            print(f"    {c['score']:2} {c['kind']:5} {c['vet']:20} {c['id']}  {c['host'] or ''}")
    for p in out.get("probes", []):
        print(("BLOCKED " if p["blocked"] else "ok      ") + f"{p['host']:45} {p['http_code']} {p['error'][:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
