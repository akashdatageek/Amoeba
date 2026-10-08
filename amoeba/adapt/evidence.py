"""D95 — evidence logging outside the agents' reach (Phase 2, research review).

An append-only `events.jsonl`, written only by the harness, never by an agent. Since D117 each run keeps its own
(`<run>/events.jsonl`): every stuck event, every fix tried, every rung skipped and every stop of in-task adaptation.
(The removed learning loop wrote one per stream, `eval/loop/<stream>/events.jsonl`; those logs stay verifiable.)
Each row stores the SHA-256 of
the previous row's line (a hash chain from a genesis of 64 zeros) and the SHA-256 manifest of each run folder or file
it refers to (`MANIFEST.sha256.json` is written next to the files; the hash in the row is what counts).
`scripts/verify_evidence.py` re-checks the whole chain and every manifest and reports the first break.

Shipping off the container (D95; used by the removed loop, kept for later use): each finished run that passes the key
scan, and the new event rows, go to the
repository's orphan `evidence` branch (`GitShipper`): copied into a worktree of that branch in the same layout as
eval/loop/<stream>/, committed at most every 10 minutes as a normal fast-forward commit whose message carries the
hash-chain head (the SHA-256 of the last event row), and pushed. A failed push is retried; whatever is not pushed yet
stays listed as unshipped in loop_state.json. Shipping runs in the harness process only. Agents never get git or
cloud credentials: `CLOUD_VARS` (cloud, GIT_*, GH_*, GITHUB_*, SSH agent) are removed from every run's environment,
an env file carrying one is refused for runs, and the local-tool server keeps its minimal environment. The bucket
uploader (`Shipper` with `gcs_uploader`) is kept but disabled (adapt.yaml evidence.gcs.enabled: false).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

GENESIS = "0" * 64
MANIFEST_NAME = "MANIFEST.sha256.json"
# names of environment variables that carry cloud credentials or the bucket: never in an agent's environment
CLOUD_VARS = re.compile(r"^(GOOGLE_APPLICATION_CREDENTIALS|GOOGLE_CLOUD_PROJECT|GCLOUD_PROJECT|CLOUDSDK_\w+|"
                        r"AMOEBA_GCS_\w+|GCS_\w+|AWS_\w+|AZURE_\w+|BOTO_\w+|"
                        r"GIT_\w+|GH_\w+|GITHUB_\w+|SSH_AUTH_SOCK|SSH_AGENT_PID)$")   # D95: no cloud or git credentials
KEY_SHAPES = re.compile(rb"AIza[0-9A-Za-z_\-]{30,}|tvly-[0-9A-Za-z_\-]{16,}|sk-[0-9A-Za-z]{20,}|ghp_[0-9A-Za-z]{30,}"
                        rb"|-----BEGIN [A-Z ]*PRIVATE KEY-----|\"private_key\"\s*:")
SECRET_NAMES = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", re.I)


# box: evidence
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# box: evidence
def _file_sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# box: evidence
def manifest_entries(target: Path) -> list[list]:
    """[relative path, sha256, size] of every file of a folder (or of one file), sorted; the manifest file left out."""
    target = Path(target)
    if target.is_file():
        return [[target.name, _file_sha(target), target.stat().st_size]]
    out = []
    for p in sorted(target.rglob("*")):
        if p.is_file() and not p.is_symlink() and p.name != MANIFEST_NAME:
            out.append([p.relative_to(target).as_posix(), _file_sha(p), p.stat().st_size])
    return out


# box: evidence
def manifest(target: Path, root: Path, write: bool = True) -> dict:
    """{"path": target relative to root, "files": n, "sha256": hash of the canonical entry list}; with write, the
    entries go to <folder>/MANIFEST.sha256.json as well."""
    target, root = Path(target), Path(root)
    entries = manifest_entries(target)
    digest = sha256_text(json.dumps(entries, separators=(",", ":"), ensure_ascii=False))
    if write and target.is_dir():
        (target / MANIFEST_NAME).write_text(json.dumps({"sha256": digest, "files": entries}, indent=1), encoding="utf-8")
    try:
        rel = target.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = str(target)
    return {"path": rel, "files": len(entries), "sha256": digest}


import threading as _threading

_APPEND_LOCK = _threading.RLock()              # the runner's worker threads append too (one harness process)


# box: evidence
def tool_decisions(run_dir: Path) -> list[dict]:
    """D96: every allow / deny decision of a run's local tools — gate.py's (local_call allowed, local_refused,
    local_tool_refused, skill_refused) and the sandbox's (created, its own log lines, deleted) — from its trace."""
    keep = {"local_call", "local_refused", "local_tool_refused", "skill_refused", "sandbox_created", "sandbox_log",
            "sandbox_deleted", "sandbox_delete_failed", "local_unavailable"}
    out = []
    for f in sorted(Path(run_dir).glob("trace*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("name") in keep:
                out.append({k: v for k, v in r.items() if k not in ("episode_id", "kind")})
    return out


# box: evidence
def route_decisions(run_dir: Path) -> list[dict]:
    """D97: the router's decisions of a run (its `route` trace events), as plain dicts."""
    out = []
    for f in sorted(Path(run_dir).glob("trace*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("name") == "route":
                out.append({k.removeprefix("amoeba.route."): v for k, v in r.items() if k.startswith("amoeba.route.")})
    return out


# box: evidence
class EvidenceLog:
    """<root>/events.jsonl: append-only, hash-chained. A row with a `key` already in the log is not written twice
    (a resumed loop logs nothing again)."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.path = self.root / "events.jsonl"

    def lines(self) -> list[str]:
        return self.path.read_text(encoding="utf-8").splitlines() if self.path.exists() else []

    def rows(self) -> list[dict]:
        return [json.loads(l) for l in self.lines() if l.strip()]

    def has(self, key: str) -> bool:
        return any(r.get("key") == key for r in self.rows())

    def append(self, event: str, data: dict, refers_to: list | tuple = (), key: str | None = None) -> dict | None:
        with _APPEND_LOCK:
            return self._append(event, data, refers_to, key)

    def _append(self, event: str, data: dict, refers_to, key) -> dict | None:
        if key is not None and self.has(key):
            return None
        lines = self.lines()
        row = {"seq": len(lines), "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event,
               "key": key, "data": data, "manifests": [manifest(Path(p), self.root) for p in refers_to if Path(p).exists()],
               "prev_sha": sha256_text(lines[-1]) if lines else GENESIS}
        line = json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return row


# box: evidence
def verify(root: str | Path) -> dict:
    """The whole chain and every manifest of <root>/events.jsonl: {"ok", "rows", "manifests", "first_break"}; the
    first break names the line (1-based), what broke and how."""
    root = Path(root)
    path = root / "events.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    prev, checked = GENESIS, 0
    for i, line in enumerate(lines):
        brk = lambda kind, detail: {"ok": False, "rows": len(lines), "manifests": checked,
                                    "first_break": {"line": i + 1, "kind": kind, "detail": detail}}
        try:
            row = json.loads(line)
        except ValueError as e:
            return brk("parse", str(e)[:200])
        if row.get("seq") != i:
            return brk("seq", f"seq {row.get('seq')} at position {i}")
        if row.get("prev_sha") != prev:
            return brk("chain", f"prev_sha {str(row.get('prev_sha'))[:16]}… does not match the previous row "
                                f"{prev[:16]}… (a row was changed, removed or inserted before this one)")
        for m in row.get("manifests") or []:
            target = root / m["path"]
            if not target.exists():
                return brk("manifest", f"{m['path']} is missing")
            now = manifest(target, root, write=False)
            if now["sha256"] != m["sha256"]:
                return brk("manifest", f"{m['path']} changed: {now['files']} files now, {m['files']} logged")
            checked += 1
        prev = sha256_text(line)
    return {"ok": True, "rows": len(lines), "manifests": checked, "first_break": None}


# box: evidence
def experiment_refs(root: Path, exp: Path) -> list[Path]:
    """D95: what an experiment event refers to: its experiment.json and pairs.jsonl and every run folder of its
    pairs (both arms)."""
    refs = [exp / "experiment.json", exp / "pairs.jsonl"]
    pairs = exp / "pairs.jsonl"
    for line in (pairs.read_text(encoding="utf-8").splitlines() if pairs.exists() else []):
        p = json.loads(line)
        for k in ("run_A", "run_B"):
            if p.get(k):
                d = Path(p[k]) if Path(p[k]).is_absolute() else root / p[k]
                if d not in refs:
                    refs.append(d)
    return refs


# ---- the key scan and the ship queue ----------------------------------------------------------------------------------
# box: evidence
def secret_values(env: dict) -> list[str]:
    """The values of secret-looking variables (names with KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL), 12+ characters."""
    return sorted({v for k, v in (env or {}).items() if SECRET_NAMES.search(k) and isinstance(v, str) and len(v) >= 12})


# box: evidence
def key_scan(target: Path, secrets: list[str] = ()) -> list[str]:
    """Files under target that hold a key shape (AIza…, tvly-…, sk-…, ghp_…, a private key) or a secret's value."""
    target = Path(target)
    vals = [s.encode() for s in secrets if s]
    files = [target] if target.is_file() else [p for p in sorted(target.rglob("*")) if p.is_file()]
    hits = []
    for p in files:
        try:
            b = p.read_bytes()
        except OSError:
            continue
        if KEY_SHAPES.search(b) or any(v in b for v in vals):
            hits.append(str(p))
    return hits


# box: evidence
def run_env(env: dict) -> dict:
    """A run's environment without any cloud credential or bucket variable (agents never see them)."""
    return {k: v for k, v in env.items() if not CLOUD_VARS.match(k)}


# box: evidence
def refuse_cloud_vars(name: str, pairs: dict) -> None:
    bad = sorted(k for k in pairs if CLOUD_VARS.match(k))
    if bad:
        raise ValueError(f"{name} sets {', '.join(bad)}: cloud credentials never go into a run's environment (D95); "
                         f"give the bucket's env file to the shipper only")


# box: evidence
class Shipper:
    """The off-container copy (D95). `upload(local_path, object_name)` sends one file (None: no bucket configured yet).
    A run is shipped only after it passes the key scan; a failed upload is retried up to `retries` times, then the
    item stays in `pending` (persisted by the caller in loop_state.json) and is retried on the next call."""

    def __init__(self, root: Path, upload: Callable[[Path, str], None] | None = None, secrets: list[str] = (),
                 prefix: str = "", retries: int = 3, pending: list[dict] | None = None):
        self.root, self.upload, self.secrets, self.prefix = Path(root), upload, list(secrets), prefix
        self.retries = retries
        self.pending: list[dict] = list(pending or [])
        self.blocked: list[dict] = []

    def queue_run(self, run_dir: Path) -> None:
        hits = key_scan(run_dir, self.secrets)
        rel = Path(run_dir).resolve().relative_to(self.root.resolve()).as_posix()
        if hits:                     # never shipped (nor committed) until cleaned; reported in loop_state.json
            self.blocked.append({"kind": "run", "path": rel, "key_scan_hits": [Path(h).name for h in hits][:10]})
            return
        self.pending.append({"kind": "run", "path": rel})

    def queue_events(self) -> None:
        self.pending.append({"kind": "events", "path": "events.jsonl", "rows": len(EvidenceLog(self.root).lines())})

    def flush(self) -> list[dict]:
        """Try every pending item; returns what is still unshipped (with the last error)."""
        if self.upload is None:
            for p in self.pending:
                p["error"] = "no bucket configured"
            return self.pending
        left = []
        for item in self.pending:
            target = self.root / item["path"]
            files = [target] if target.is_file() else [f for f in sorted(target.rglob("*")) if f.is_file()]
            err = None
            for f in files:
                name = self.prefix + f.relative_to(self.root).as_posix()
                if item["kind"] == "events":     # each upload of the log is its own object version (versioning on)
                    name = f"{self.prefix}events/events.{item['rows']:06d}.jsonl"
                for _ in range(self.retries):
                    try:
                        self.upload(f, name)
                        err = None
                        break
                    except Exception as e:     # any upload failure is retried, then left pending
                        err = f"{type(e).__name__}: {str(e)[:200]}"
                if err:
                    break
            if err:
                left.append({**item, "error": err})
        self.pending = left
        return left


# box: evidence
def gcs_uploader(bucket: str, credentials_file: str | None = None) -> Callable[[Path, str], None]:
    """The bucket copy (kept, disabled: adapt.yaml evidence.gcs.enabled is false; the evidence goes to the git branch).
    Uploads with if_generation_match=0, so an object is never overwritten (object-create-only rights suffice)."""
    from amoeba.adapt.config import adapt_config
    if not (adapt_config().get("evidence", {}).get("gcs", {}) or {}).get("enabled"):
        raise RuntimeError("the GCS uploader is disabled (adapt.yaml evidence.gcs.enabled: false)")
    from google.cloud import storage            # optional dependency, only when enabled
    client = storage.Client.from_service_account_json(credentials_file) if credentials_file else storage.Client()
    b = client.bucket(bucket)

    def upload(path: Path, name: str) -> None:
        b.blob(name).upload_from_filename(str(path), if_generation_match=0)
    return upload


# ---- the evidence branch (D95) -----------------------------------------------------------------------------------------
# box: evidence
def chain_head(events_file: Path) -> tuple[int, str]:
    """(rows, SHA-256 of the last row) of an events.jsonl; (0, GENESIS) when it is empty or missing."""
    lines = [l for l in (events_file.read_text(encoding="utf-8").splitlines() if events_file.exists() else [])]
    return len(lines), (sha256_text(lines[-1]) if lines else GENESIS)


# box: evidence
class GitShipper:
    """Ships to the `evidence` branch through a worktree of it (`worktree`, created from origin/<branch> if missing).
    `queue_run(run_dir)` key-scans a finished run and queues it; `flush(force)` commits at most every `batch_seconds`
    (always when forced): the queued runs, events.jsonl and every path the new event rows name, under `stream_rel`
    (eval/loop/<stream>), one commit whose message carries the chain head, then a fast-forward push, retried. Thread
    safe (the runner's workers call queue_run). `git` runs in this (harness) process only."""

    def __init__(self, root: Path, stream: str, worktree: Path, repo: Path, branch: str = "evidence",
                 secrets: list[str] = (), batch_seconds: float = 600, retries: int = 3,
                 pending: list[dict] | None = None, state: dict | None = None, run=None, clock=None, push: bool = True):
        import subprocess
        import threading
        import time
        self.root, self.stream, self.worktree, self.repo = Path(root), stream, Path(worktree), Path(repo)
        self.branch, self.secrets, self.batch, self.retries, self.push_on = branch, list(secrets), batch_seconds, retries, push
        self.pending: list[dict] = list(pending or [])
        self.blocked: list[dict] = []
        self.state = dict(state or {"last_ship": 0.0, "rows_shipped": 0})
        self._run = run or (lambda args, cwd: subprocess.run(args, cwd=cwd, capture_output=True, text=True))
        self._clock = clock or time.time
        self._lock = threading.RLock()
        try:
            self.stream_rel = self.root.resolve().relative_to(self.repo.resolve()).as_posix()
        except ValueError:
            self.stream_rel = f"eval/loop/{stream}"

    # -- git
    def git(self, *args, in_repo: bool = False) -> tuple[int, str]:
        p = self._run(["git", *args], self.repo if in_repo else self.worktree)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def ensure_worktree(self) -> None:
        if (self.worktree / ".git").exists():
            return
        self.git("fetch", "origin", self.branch, in_repo=True)
        rc, out = self.git("worktree", "add", str(self.worktree), self.branch, in_repo=True)
        if rc != 0:
            raise RuntimeError(f"cannot make the {self.branch} worktree: {out[-300:]}")

    # -- queue
    def queue_run(self, run_dir: Path) -> None:
        with self._lock:
            hits = key_scan(run_dir, self.secrets)
            rel = Path(run_dir).resolve().relative_to(self.root.resolve()).as_posix()
            if hits:
                self.blocked.append({"kind": "run", "path": rel, "key_scan_hits": [Path(h).name for h in hits][:10]})
                return
            if not any(p["path"] == rel for p in self.pending):
                self.pending.append({"kind": "run", "path": rel})

    def queue_events(self) -> None:
        with self._lock:
            if not any(p["kind"] == "events" for p in self.pending):
                self.pending.append({"kind": "events", "path": "events.jsonl"})

    # -- ship
    def _copy(self, rel: str) -> list[str]:
        """Copy one path into the worktree (key-scanned first); returns key-scan hits (then nothing is copied)."""
        import shutil
        src, dst = self.root / rel, self.worktree / self.stream_rel / rel
        if not src.exists():
            return []
        hits = key_scan(src, self.secrets)
        if hits:
            return hits
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return []

    def flush(self, force: bool = False) -> list[dict]:
        """Ship what is queued if the batch interval has passed (or force); returns what is still unshipped."""
        with self._lock:
            if not self.pending:
                return []
            if not force and self._clock() - float(self.state.get("last_ship") or 0) < self.batch:
                return [{**p, "error": "waiting for the next batch"} for p in self.pending]
            try:
                self.ensure_worktree()
            except RuntimeError as e:
                return [{**p, "error": str(e)[:300]} for p in self.pending]
            ev = EvidenceLog(self.root)
            rows = ev.rows()
            new = rows[int(self.state.get("rows_shipped") or 0):]
            paths = [p["path"] for p in self.pending if p["kind"] == "run"]
            for r in new:
                paths += [m["path"] for m in r.get("manifests") or []]
            shipped_runs = 0
            for rel in dict.fromkeys(paths):
                hits = self._copy(rel)
                if hits:
                    self.blocked.append({"kind": "path", "path": rel, "key_scan_hits": [Path(h).name for h in hits][:10]})
                else:
                    shipped_runs += any(p["path"] == rel for p in self.pending if p["kind"] == "run")
            hits = self._copy("events.jsonl")
            if hits:                    # the log itself never holds a key; if it does, stop and say so
                return [{**p, "error": "events.jsonl failed the key scan"} for p in self.pending]
            n, head = chain_head(self.root / "events.jsonl")
            self.git("add", "-A", self.stream_rel)
            rc, out = self.git("diff", "--cached", "--quiet")
            if rc != 0:
                s = Path(self.stream_rel).name          # the folder name under eval/loop/ (verify_branch reads it)
                msg = (f"evidence: {s} · rows {int(self.state.get('rows_shipped') or 0)}–{n} · {shipped_runs} "
                       f"run folder(s)\n\nChain-Head: {s} {head}\nChain-Rows: {s} {n}\n")
                rc, out = self.git("-c", "user.name=amoeba-harness", "-c", "user.email=harness@amoeba.invalid",
                                   "commit", "-q", "-m", msg)
                if rc != 0:
                    return [{**p, "error": f"commit failed: {out[-200:]}"} for p in self.pending]
            err = None
            if self.push_on:
                for _ in range(self.retries):
                    rc, out = self.git("push", "origin", f"HEAD:refs/heads/{self.branch}")
                    if rc == 0:
                        err = None
                        break
                    err = f"push failed: {out.strip()[-300:]}"
                    self.git("fetch", "origin", self.branch)          # the next try is still a fast-forward
            if err:
                return [{**p, "error": err} for p in self.pending]
            self.pending = []
            self.state.update(last_ship=self._clock(), rows_shipped=n, head=head)
            return []


# box: evidence
def make_shipper(root: Path, stream: str, secrets: list[str] = (), pending: list[dict] | None = None,
                 state: dict | None = None, repo: Path | None = None):
    """The configured shipper (adapt.yaml evidence): GitShipper to the evidence branch, or a queue that ships nothing."""
    from amoeba.adapt.config import adapt_config
    c = adapt_config().get("evidence", {}) or {}
    clean = [{k: v for k, v in p.items() if k != "error"} for p in pending or []]
    repo = Path(repo or Path(__file__).resolve().parents[2])
    if c.get("target") == "github":
        return GitShipper(root, stream, (repo / c.get("worktree", "../amoeba-evidence")).resolve(), repo,
                          branch=c.get("branch", "evidence"), secrets=secrets,
                          batch_seconds=float(c.get("batch_seconds", 600)), retries=int(c.get("retries", 3)),
                          pending=clean, state=state)
    return Shipper(root, None, secrets, pending=clean)


# box: evidence
def verify_branch(repo: Path, branch: str = "evidence", stream: str | None = None, fetch: bool = True) -> dict:
    """D95: check the evidence branch against GitHub's history. For every commit (oldest first): each `Chain-Head:
    <stream> <sha>` in its message equals the SHA-256 of the last row of that stream's events.jsonl in the commit,
    `Chain-Rows` its row count, and the file only grew (the earlier commit's file is a prefix of it). Then the branch
    head's copy is checked like the local one (whole chain and every manifest). First break reported."""
    import subprocess
    import tarfile
    import tempfile
    repo = Path(repo)
    g = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True)
    if fetch:
        g("fetch", "origin", branch)
    ref = f"origin/{branch}" if g("rev-parse", "--verify", f"origin/{branch}").returncode == 0 else branch
    commits = g("rev-list", "--reverse", ref).stdout.split()
    if not commits:
        return {"ok": False, "commits": 0, "first_break": {"kind": "branch", "detail": f"{ref} not found"}}
    last: dict[str, str] = {}
    heads = 0
    for c in commits:
        msg = g("log", "-1", "--format=%B", c).stdout
        rows = dict(re.findall(r"^Chain-Rows:\s+(\S+)\s+(\d+)\s*$", msg, re.M))
        for s, head in re.findall(r"^Chain-Head:\s+(\S+)\s+([0-9a-f]{64})\s*$", msg, re.M):
            if stream and s != stream:
                continue
            brk = lambda kind, detail: {"ok": False, "commits": len(commits), "heads": heads,
                                        "first_break": {"commit": c[:12], "stream": s, "kind": kind, "detail": detail}}
            p = g("show", f"{c}:eval/loop/{s}/events.jsonl")
            if p.returncode != 0:
                return brk("missing", "events.jsonl is not in the commit")
            text = p.stdout
            lines = text.splitlines()
            if (sha256_text(lines[-1]) if lines else GENESIS) != head:
                return brk("head", "the message's chain head is not the SHA-256 of the commit's last event row")
            if s in rows and int(rows[s]) != len(lines):
                return brk("rows", f"message says {rows[s]} rows, the file has {len(lines)}")
            if s in last and not text.startswith(last[s]):
                return brk("rewritten", "events.jsonl changed rows an earlier evidence commit already held")
            last[s] = text
            heads += 1
    with tempfile.TemporaryDirectory() as tmp:
        arch = Path(tmp) / "head.tar"
        with open(arch, "wb") as fh:
            subprocess.run(["git", "archive", "--format=tar", ref], cwd=repo, stdout=fh, check=True)
        with tarfile.open(arch) as tf:
            tf.extractall(Path(tmp) / "tree", filter="data")
        streams = [stream] if stream else sorted(p.parent.name for p in (Path(tmp) / "tree" / "eval" / "loop").glob(
            "*/events.jsonl"))
        for s in streams:
            res = verify(Path(tmp) / "tree" / "eval" / "loop" / s)
            if not res["ok"]:
                return {"ok": False, "commits": len(commits), "heads": heads,
                        "first_break": {"stream": s, "where": f"{ref} head copy", **res["first_break"]}}
    return {"ok": True, "commits": len(commits), "heads": heads, "streams": streams, "first_break": None}


# box: evidence
def run_finished(ev: EvidenceLog, root: Path, run_dir: Path, shipper=None) -> None:
    """D95/D96: when a run finishes: its local-tool decisions (gate.py and the sandbox) go into events.jsonl, and the
    run is key-scanned and queued for the evidence branch."""
    run_dir = Path(run_dir)
    routes = [d for f in sorted(run_dir.glob("*/")) for d in route_decisions(f)] + route_decisions(run_dir)
    if routes:                                    # D97: every routing decision of the run
        try:
            rel_r = run_dir.resolve().relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            rel_r = str(run_dir)
        ev.append("routing", {"run": rel_r, "decisions": routes,
                              "verifier_same_family": sum(1 for d in routes if d.get("verifier_same_family")),
                              "no_model": sum(1 for d in routes if d.get("cause") == "no_model")},
                  key=f"routing:{rel_r}")
    found = [d for f in sorted(run_dir.glob("*/")) for d in tool_decisions(f)] + tool_decisions(run_dir)
    if found:
        try:
            rel = run_dir.resolve().relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            rel = str(run_dir)
        ev.append("tool_decisions", {"run": rel, "decisions": found,
                                     "refused": sum(d.get("name") == "local_refused" for d in found)},
                  key=f"tool_decisions:{rel}")
    if shipper is not None:
        shipper.queue_run(run_dir)
