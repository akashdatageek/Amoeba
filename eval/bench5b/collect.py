"""Five-task benchmark rerun (bench5b, copied from eval/bench5/collect.py) — copy every run in the ledger into eval/bench5b/runs/<arch>/<run id>/ (the committed
evidence) and key-scan everything that will be committed; build the replay archive of the benchmark's cache entries.

    python eval/bench5b/collect.py

Copies result.json, trace.jsonl, team.yaml, plan and artifacts, the stderr log and the workspace files the team made
(the attached skill folders, workspace/skills/, are left out: they are third-party copies, not the team's work).
The key scan looks for API-key shapes (AIza…, tvly-…, sk-…) and for the exact values in the private env files; it
prints only counts, never a value, and exits 1 on any hit. The replay archive (eval/bench5b/replay_cache.tar.gz)
holds every LLM and web cache entry in a "bench5b-" namespace; unpack it into runs/cache/ and run
with --llm-cache-mode replay to replay the night without a network.
"""
import io
import json
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "eval/bench5b/runs"
SP = Path(os.environ.get("AMOEBA_SCRATCH", "/tmp/claude-0/-home-user-Amoeba/6ad97438-2398-5c56-be15-1b8885aa050c/scratchpad"))
SHAPES = re.compile(rb"AIza[0-9A-Za-z_\-]{30,}|tvly-[0-9A-Za-z_\-]{16,}|sk-[0-9A-Za-z]{20,}")


def secrets() -> list[bytes]:
    vals = []
    for f in ("gemma.env", "tavily.env", "amoeba.env"):
        p = SP / f
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip().removeprefix("export ").strip()
                if "=" in line and not line.startswith("#"):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if len(v) >= 12 and ("KEY" in line.split("=", 1)[0] or "TOKEN" in line.split("=", 1)[0]):
                        vals.append(v.encode())
    return vals


def copy_runs() -> int:
    n = 0
    for line in (ROOT / "eval/bench5b/ledger.jsonl").read_text().splitlines():
        rec = json.loads(line)
        if not rec.get("run"):
            continue
        src = ROOT / rec["run"]
        dst = OUT / rec["arch"] / src.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=lambda d, names: [x for x in names if x in ("localtools_home",)
                                                           or (Path(d).name == "workspace" and x == "skills")])
        n += 1
    return n


def scan(paths: list[Path]) -> int:
    vals, hits = secrets(), 0
    for base in paths:
        for f in (base.rglob("*") if base.is_dir() else [base]):
            if f.is_file():
                b = f.read_bytes()
                if SHAPES.search(b) or any(v in b for v in vals):
                    hits += 1
                    print(f"KEY-LIKE CONTENT in {f.relative_to(ROOT)}")
    print(f"key scan: {len(vals)} private values and 3 key shapes checked; {hits} file(s) hit")
    return hits


def archive() -> Path:
    """LLM entries carry their namespace; web entries do not, so a web entry belongs to the benchmark when its key
    recomputes under one of the bench5b-<arch>-r<k>, bench5b-draft or bench5b-picks namespaces."""
    from amoeba.llm.cache import cache_key
    out = ROOT / "eval/bench5b/replay_cache.tar.gz"
    n = 0
    with tarfile.open(out, "w:gz") as tar:
        for f in sorted((ROOT / "runs/cache/llm").glob("*/*.json")):
            if re.search(r'"namespace":\s*"bench5b-', f.read_text(encoding="utf-8", errors="replace")[:4000]):
                tar.add(f, arcname=str(f.relative_to(ROOT / "runs/cache")))
                n += 1
        for f in sorted((ROOT / "runs/cache/web").glob("*/*.json")):
            r = json.loads(f.read_text(encoding="utf-8"))
            parts = {k: v for k, v in r.items() if k not in ("key", "provider", "result")}
            names = [f"bench5b-{a}-r{k}" for a in ("autoagents", "agentverse", "amoeba") for k in (1, 2, 3)]
            if any(cache_key({**parts, "provider": r.get("provider"), "namespace": ns}) == r.get("key")
                   for ns in (*names, "bench5b-draft", "bench5b-picks")):
                tar.add(f, arcname=str(f.relative_to(ROOT / "runs/cache")))
                n += 1
    print(f"replay archive: {n} cache entries → {out.relative_to(ROOT)} ({out.stat().st_size:,} bytes)")
    return out


def main() -> int:
    print(f"copied {copy_runs()} run folders to {OUT.relative_to(ROOT)}")
    arc = archive()
    hits = scan([OUT, ROOT / "eval/bench5b/drafts", ROOT / "eval/bench5b/ledger.jsonl", ROOT / "docs/eval/bench5b"])
    with tarfile.open(arc) as tar:                       # the archive too, member by member
        vals = secrets()
        for m in tar.getmembers():
            b = tar.extractfile(m).read() if m.isfile() else b""
            if SHAPES.search(b) or any(v in b for v in vals):
                hits += 1
                print(f"KEY-LIKE CONTENT in replay archive member {m.name}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
