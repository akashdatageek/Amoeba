"""Rebuild the as-built page when, and only when, something it is built from changed (D55).

    python tools/arch_update.py              # rebuild if needed: extract (+ box text) and render
    python tools/arch_update.py --force      # rebuild even if nothing changed (box text still costs 0 tokens then)
    python tools/arch_update.py --background # return at once; the rebuild runs detached (for hooks)

Run by the git post-commit hook (tools/hooks/post-commit; `git config core.hooksPath tools/hooks`) and by the
Claude Code Stop hook (.claude/settings.json). It hashes every input of the page — the package, scripts, tests,
spec, the extract/render tools, the plan page and the newest real run's trace — and compares with
docs/arch/build_stamp.json. Same hash: nothing runs, no model is called. It never fails the caller: problems are
printed and it exits 0 (the extractor itself still refuses to build a page whose anchors point at nothing).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAMP = ROOT / "docs" / "arch" / "build_stamp.json"
LOCK = ROOT / "runs" / ".arch_update.lock"
LOGFILE = ROOT / "runs" / "arch_update.log"
INPUTS = ["amoeba/**/*.py", "amoeba/**/*.txt", "amoeba/**/*.yaml", "scripts/*.py", "tests/**/*.py", "tests/**/*.txt",
          "spec/*.md", "tools/arch_*.py", "docs/arch/plan_phase1.html"]


def stamp() -> str:
    h = hashlib.sha256()
    for pattern in INPUTS:
        for p in sorted(ROOT.glob(pattern)):
            if p.is_file() and "__pycache__" not in p.parts:
                h.update(str(p.relative_to(ROOT)).encode())
                h.update(p.read_bytes())
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        from arch_extract import find_real_run          # the replayed real run is an input too
        rr = find_real_run()
    except Exception:
        rr = None
    if rr:
        h.update(str(rr).encode())
        h.update(str((rr / "trace.jsonl").stat().st_size).encode())
    return h.hexdigest()[:20]


def python() -> str:
    venv = ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def rebuild(force: bool) -> int:
    now = stamp()
    old = json.loads(STAMP.read_text()) if STAMP.exists() else {}
    if old.get("stamp") == now and not force:
        print(f"arch_update: page up to date (inputs {now}); nothing run, 0 model tokens")
        return 0
    t0 = time.time()
    for cmd in ([python(), "tools/arch_extract.py"], [python(), "tools/arch_render.py"]):
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        sys.stdout.write(r.stdout[-3000:])
        if r.returncode:
            sys.stdout.write(r.stderr[-3000:])
            if cmd[1].endswith("arch_extract.py"):
                print(f"arch_update: extract failed (exit {r.returncode}); page not rebuilt")
                return 0
    log = ROOT / "docs" / "arch" / "text_log.jsonl"
    last = json.loads(log.read_text().splitlines()[-1]) if log.exists() else {}
    STAMP.write_text(json.dumps({"stamp": now, "commit": last.get("commit"), "built_at": last.get("ts"),
                                 "seconds": round(time.time() - t0, 1)}, indent=1) + "\n")
    print(f"arch_update: rebuilt in {time.time() - t0:.0f}s; box text model tokens "
          f"{last.get('input_tokens', 0)} in / {last.get('output_tokens', 0)} out ({last.get('llm_calls', 0)} calls)")
    return 0


def main(argv: list[str]) -> int:
    if "--background" in argv:
        LOGFILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOGFILE, "a") as fh:
            subprocess.Popen([python(), __file__] + [a for a in argv if a != "--background"], cwd=ROOT, stdout=fh,
                             stderr=subprocess.STDOUT, start_new_session=True)
        return 0
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)       # one rebuild at a time
    except FileExistsError:
        if time.time() - LOCK.stat().st_mtime < 900:
            print("arch_update: another rebuild is running; skipped")
            return 0
        LOCK.unlink(missing_ok=True)                                 # a stale lock from a killed run
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        return rebuild("--force" in argv)
    except Exception as e:                                           # never fail the hook that called us
        print(f"arch_update: {type(e).__name__}: {e}")
        return 0
    finally:
        os.close(fd)
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
