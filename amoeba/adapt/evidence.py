"""D95 — evidence logging outside the agents' reach (Phase 2, research review).

One append-only `eval/loop/<stream>/events.jsonl`, written only by the harness (the loop driver and the hand-check
script; never an agent): every alarm with its inputs, every diagnosis, every Architect prompt and FULL reply, every
experiment, Gate decision, revert and human-queue entry, every finished practice run. Each row stores the SHA-256 of
the previous row's line (a hash chain from a genesis of 64 zeros) and the SHA-256 manifest of each run folder or file
it refers to (`MANIFEST.sha256.json` is written next to the files; the hash in the row is what counts).
`scripts/verify_evidence.py` re-checks the whole chain and every manifest and reports the first break.

Shipping off the container (D95): each finished run that passes the key scan, and the new event rows, are queued for
upload to a bucket with object versioning and a retention lock; until an uploader is configured, or while an upload
fails, they stay listed as unshipped in loop_state.json (`Shipper.pending`). Cloud credentials never reach an agent:
`CLOUD_VARS` are removed from every run's environment, and an env file carrying one is refused for runs.
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
                        r"AMOEBA_GCS_\w+|GCS_\w+|AWS_\w+|AZURE_\w+|BOTO_\w+)$")
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
