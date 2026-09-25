"""D56 — the pool index: every tool and skill Box 3 may stock its toolbox from, cached on disk (0 tokens).

`python -m amoeba pool refresh` reads the sources in amoeba/config/pool.yaml and writes <cache_dir>/index.json plus
one skills/<name>.md per skill body. A run only ever reads this cache (`load_index`); it never fetches the index.

Tools come from the official MCP Registry API (cursor pagination; the latest version of each server name; its
server.json fields remotes, repository and version). Skills come from a GitHub repository, read from a shallow
`git clone` (D58): each <path>/<name>/SKILL.md, YAML frontmatter (name, description) then the body.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

POOL_YAML = Path(__file__).resolve().parents[1] / "config" / "pool.yaml"
REMOTE_TYPES = ("streamable-http", "sse")
CODE_SUFFIXES = (".py", ".sh", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".ps1", ".bat", ".exe")


# box: pool_index
class PoolSourceError(RuntimeError):
    pass


# box: pool_index
def text_sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# box: pool_index
def load_pool_config(path: str | Path = POOL_YAML) -> dict:
    """pool.yaml with its defaults filled in."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    limits = {"max_candidates": 5, "max_per_helper": 3, "max_per_run": 8, "max_skill_chars": 5000,
              "max_calls_per_step": 3, "timeout_s": 20.0, "max_result_chars": 6000, **(data.get("limits") or {})}
    return {"sources": list(data.get("sources") or []), "cache_dir": data.get("cache_dir") or "data/pool",
            "auth_env": dict(data.get("auth_env") or {}), "paid_hosts": list(data.get("paid_hosts") or []),
            "limits": limits}


# box: pool_index
def http_get(url: str, timeout: float = 30.0) -> bytes:
    headers = {"User-Agent": "amoeba-pool-refresh", "Accept": "application/json"}
    if "api.github.com" in url and os.environ.get("GITHUB_TOKEN"):     # optional: a higher GitHub rate limit
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        return r.read()


# ---- tools: the MCP Registry -----------------------------------------------------------------------------------
# box: pool_index
def _official(item: dict) -> dict:
    meta = item.get("_meta") or item.get("server", {}).get("_meta") or {}
    return meta.get("io.modelcontextprotocol.registry/official") or {}


# box: pool_index
def registry_servers(url: str, get: Callable[[str], bytes] = http_get, max_pages: int = 10000) -> list[dict]:
    """Every server.json of the registry, one per server name: the one marked isLatest, else the newest published."""
    by_name: dict[str, tuple[dict, dict]] = {}
    cursor = None
    for _ in range(max_pages):
        q = {"limit": 100, **({"cursor": cursor} if cursor else {})}
        data = json.loads(get(f"{url}?{urllib.parse.urlencode(q)}"))
        for item in data.get("servers") or []:
            server = item.get("server", item)
            name = server.get("name")
            if not name:
                continue
            meta = _official(item)
            if meta.get("status", "active") != "active":
                continue
            old = by_name.get(name)
            if old is None or meta.get("isLatest") or (not old[1].get("isLatest")
                                                      and meta.get("publishedAt", "") >= old[1].get("publishedAt", "")):
                by_name[name] = (server, meta)
        md = data.get("metadata") or {}
        cursor = md.get("nextCursor") or md.get("next_cursor")
        if not cursor:
            break
    return [s for s, _ in by_name.values()]


# box: pool_index
def tool_entry(server: dict, now: str) -> dict:
    """One index entry from a server.json. The first HTTPS remote wins; a server with only packages has none."""
    remotes = [r for r in server.get("remotes") or [] if r.get("type") in REMOTE_TYPES and r.get("url")]
    remote = next((r for r in remotes if r["url"].startswith("https://")), remotes[0] if remotes else {})
    headers = remote.get("headers") or []
    url_vars = re.findall(r"\{(\w+)\}", remote.get("url", ""))
    desc = server.get("description") or ""
    return {"id": server["name"], "name": server["name"], "title": server.get("title") or "", "description": desc,
            "kind": "tool", "source": "registry", "source_repo": (server.get("repository") or {}).get("url") or "",
            "version": server.get("version") or "", "remote_url": remote.get("url") or "",
            "transport": remote.get("type") or ("package" if server.get("packages") else ""),
            "auth_required": any(h.get("isRequired") or h.get("isSecret") for h in headers) or bool(url_vars),
            "auth_headers": [h.get("name") for h in headers if h.get("name")] + url_vars,
            "description_sha256": text_sha256(desc), "refreshed_at": now}


# ---- skills: a GitHub repository ---------------------------------------------------------------------------------
# box: pool_index
def split_skill(text: str) -> tuple[dict, str]:
    """(frontmatter, body) of a SKILL.md; no frontmatter gives ({}, text)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text or "", re.S)
    if not m:
        return {}, text or ""
    try:
        front = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        front = {}
    return (front if isinstance(front, dict) else {}), m.group(2).strip()


# box: pool_index
def git_clone(repo: str, dest: Path, timeout: float = 600.0) -> None:
    """D58: a shallow clone of https://github.com/<repo> into dest (LFS files stay pointers: skills are text)."""
    env = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"}
    subprocess.run(["git", "clone", "--quiet", "--depth", "1", f"https://github.com/{repo}", str(dest)],
                   check=True, capture_output=True, text=True, timeout=timeout, env=env)


# box: pool_index
def repo_skills(repo: str, path: str = "skills", clone: Callable[[str, Path], None] = git_clone,
                work: Path | None = None) -> tuple[dict, list[dict]]:
    """({repo, commit}, [{dir, name, description, body, has_scripts}]) for every <path>/<name>/SKILL.md of a shallow
    clone of the default branch (D58: git, not the GitHub API, which a session's GitHub proxy may refuse). Only the
    repository named in pool.yaml is cloned, and the clone's origin must be exactly that repository."""
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise PoolSourceError(f"not a GitHub owner/name: {repo!r}")
    tmp = Path(tempfile.mkdtemp(prefix="skills-", dir=work))
    try:
        dest = tmp / "repo"
        clone(repo, dest)
        origin = _git(dest, "remote", "get-url", "origin").rstrip("/").removesuffix(".git")
        if origin.lower() != f"https://github.com/{repo}".lower():
            raise PoolSourceError(f"the clone's origin is {origin}, not {repo}")
        commit = _git(dest, "rev-parse", "HEAD")
        root = dest / path.strip("/")
        out = []
        for skill_md in sorted(root.glob("*/SKILL.md")):
            base = skill_md.parent
            files = [f for f in base.rglob("*") if f.is_file()]
            has_scripts = any("scripts" in f.relative_to(base).parts[:-1] or os.access(f, os.X_OK)
                              or f.name.lower().endswith(CODE_SUFFIXES) for f in files)
            front, body = split_skill(skill_md.read_text(encoding="utf-8", errors="replace"))
            out.append({"dir": base.name, "name": str(front.get("name") or base.name),
                        "description": str(front.get("description") or ""), "body": body, "has_scripts": has_scripts})
        return {"repo": repo, "commit": commit}, out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# box: pool_index
def _git(repo_dir: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo_dir), *args], check=True, capture_output=True, text=True).stdout.strip()


# box: pool_index
def skill_entry(repo: str, commit: str, s: dict, now: str) -> dict:
    return {"id": f"{repo}:{s['dir']}", "name": s["name"], "title": "", "description": s["description"],
            "kind": "skill", "source": "repo", "source_repo": f"https://github.com/{repo}", "repo": repo,
            "version": commit, "commit": commit, "has_scripts": s["has_scripts"], "body_length": len(s["body"]),
            "body_file": f"skills/{safe_name(repo)}__{safe_name(s['dir'])}.md",
            "description_sha256": text_sha256(s["description"]), "refreshed_at": now}


# box: pool_index
def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)


# box: pool_index
def refresh(config: dict | None = None, cache_dir: str | Path | None = None, get: Callable[[str], bytes] = http_get,
            only: str | None = None, log: Callable[[str], None] = print,
            clone: Callable[[str, Path], None] = git_clone) -> dict:
    """Build the cache from every source in pool.yaml (no model call). Returns {entries, sources, errors}. A source
    that fails is reported and left out; the other sources are still written."""
    cfg = config or load_pool_config()
    out_dir = Path(cache_dir or cfg["cache_dir"])
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entries, done, errors = [], [], []
    for src in cfg["sources"]:
        if only and src.get("kind") != only:
            continue
        try:
            if src.get("source") == "registry":
                servers = registry_servers(src["url"], get)
                entries += [tool_entry(s, now) for s in servers]
                done.append({**src, "entries": len(servers)})
            elif src.get("source") == "repo":
                meta, skills = repo_skills(src["repo"], src.get("path", "skills"), clone)
                for s in skills:
                    e = skill_entry(meta["repo"], meta["commit"], s, now)
                    (out_dir / e["body_file"]).parent.mkdir(parents=True, exist_ok=True)
                    (out_dir / e["body_file"]).write_text(s["body"], encoding="utf-8")
                    entries.append(e)
                done.append({**src, "commit": meta["commit"], "entries": len(skills)})
            else:
                raise PoolSourceError(f"unknown source type {src.get('source')!r}")
            log(f"pool refresh: {src.get('source')} {src.get('url') or src.get('repo')}: {done[-1]['entries']} entries")
        except Exception as e:                       # one source failing never loses the others
            errors.append({**src, "error": f"{type(e).__name__}: {e}"[:300]})
            log(f"pool refresh: {src.get('source')} {src.get('url') or src.get('repo')} failed: {errors[-1]['error']}")
    out_dir.mkdir(parents=True, exist_ok=True)
    index = {"refreshed_at": now, "sources": done, "errors": errors, "entries": entries}
    tmp = out_dir / "index.json.tmp"
    tmp.write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out_dir / "index.json")
    return index


# box: pool_index
def load_index(cache_dir: str | Path) -> dict | None:
    """The cached index, or None when there is none (the run then logs pool_unavailable and goes on as before)."""
    p = Path(cache_dir) / "index.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# box: pool_index
def skill_body(cache_dir: str | Path, entry: dict) -> str | None:
    p = Path(cache_dir) / entry.get("body_file", "")
    return p.read_text(encoding="utf-8") if entry.get("body_file") and p.is_file() else None
