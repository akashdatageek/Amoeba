"""D156 — preflight: is everything a task category needs here, before any real run?

    python -m scripts.preflight [--profile gemma-api] [--mode sandbox|inprocess] [--skip-model-check]

One table, a row per check: ok / missing / warn / n/a, what was seen, how to fix it, and the task categories that
need it. Exit 1 when anything a category needs is missing. The checks:
- GEMINI_API_KEY and TAVILY_API_KEY set, and one tiny live call each (the keys are never printed);
- `scripts.model_check <profile> --protocol v2`: reading, planner, step turn and Final_Output must pass;
- the model's rate limits (RPM, RPD from models.yaml), and any quota reply seen (D160's parse_quota);
- Tavily's remaining credits, when its /usage endpoint reports them;
- sandbox mode: Docker running, the OpenShell gateway healthy, amoeba-sandbox:local built; the pool cache with skills;
- through the run's own local toolbox (inside the sandbox, or on this host in in-process mode): one call each of
  Bash, Read, Write, Edit, Glob, Grep; the Python libraries (LIBS), soffice and office_check();
- the skills xlsx, docx, pptx, pdf listed and attachable.
Every outside call goes through `World`, so tests replace it (tests/test_preflight_d156.py)."""
from __future__ import annotations

import argparse
import inspect
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from amoeba.llm.quota import parse_quota

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ("research", "exact", "files", "software", "chain", "decision", "missing", "drone")
LOCAL = ("exact", "files", "software", "chain", "drone")         # the categories that run code or write files
# import name -> the categories that need it (D158: the same list is in the sandbox Dockerfile and docs/design)
LIBS = {"numpy": ("exact", "drone"), "pandas": ("exact", "files"), "matplotlib": ("files",), "PIL": ("drone",),
        "openpyxl": ("files",), "docx": ("files",), "pptx": ("files",), "pypdf": ("files",), "scipy": ("exact",),
        "pytest": ("software",)}
PIP = {"PIL": "pillow", "docx": "python-docx", "pptx": "python-pptx"}
SKILLS = ("xlsx", "docx", "pptx", "pdf")
REQUIRED_PROBES = ("reading", "planner", "step (native tools)", "Final_Output")
ENV_FIX = "add it in the environment settings (never on the command line or in a file)"


# box: tools
@dataclass
class Row:
    check: str
    status: str                                      # ok | missing | warn | n/a
    detail: str = ""
    fix: str = ""
    needed_by: tuple = ()


# box: tools
class World:
    """The outside world of the checks. Each method makes one live call; tests override them."""

    def __init__(self, mode: str = "sandbox", profile: str = "gemma-api", skip_model_check: bool = False,
                 pool_dir: str = "data/pool"):
        self.mode, self.profile, self.skip_model_check, self.pool_dir = mode, profile, skip_model_check, pool_dir
        self.env = os.environ
        self._box = None

    def _prof(self):
        from amoeba.llm.profiles import get_profile
        return get_profile(self.profile)

    def chat(self, prompt: str) -> str:
        from amoeba.llm.anthropic_client import make_client
        p = self._prof()
        c = make_client(p.provider, base_url=p.base_url, api_key=self.env.get(p.api_key_env or "", ""),
                        model=p.model, max_tokens=64, merge_system=p.merge_system, max_rate_retries=0)
        return c.chat("You answer in one word.", prompt).content

    def tavily_search(self, query: str) -> list:
        from amoeba.tools.web import TavilyProvider
        return TavilyProvider(self.env.get("TAVILY_API_KEY")).search(query, 1)

    def tavily_usage(self) -> dict | None:
        import urllib.request
        from amoeba.tools.web import TAVILY_URL
        req = urllib.request.Request(f"{TAVILY_URL}/usage",
                                     headers={"Authorization": f"Bearer {self.env.get('TAVILY_API_KEY', '')}"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:                             # not every plan or version has /usage
            return None

    def model_check(self) -> dict:
        with tempfile.TemporaryDirectory(prefix="amoeba-preflight-mc-") as tmp:
            subprocess.run([sys.executable, "-m", "scripts.model_check", self.profile, "--protocol", "v2",
                            "--out-dir", tmp], cwd=ROOT, capture_output=True, text=True, timeout=1800)
            files = list(Path(tmp).glob("*.json"))
            return json.loads(files[0].read_text()) if files else {"probes": []}

    def sh(self, cmd: list[str]) -> tuple[int, str]:
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return p.returncode, (p.stdout + p.stderr).strip()
        except (OSError, subprocess.TimeoutExpired) as e:
            return 127, str(e)

    def gateway_health(self) -> str:
        from openshell.sandbox import SandboxClient
        from amoeba.localtools.sandbox import sandbox_config
        from amoeba.localtools.toolbox import load_local_config
        return str(SandboxClient(sandbox_config(load_local_config())["endpoint"], timeout=20).health()).strip()

    def pool_skills(self) -> list[dict]:
        from amoeba.localtools.skills import list_skills
        from amoeba.localtools.toolbox import load_local_config
        return list_skills(load_local_config(), Path(self.pool_dir))

    def rate(self) -> dict:
        from amoeba.llm.router import load_registry
        reg, _ = load_registry()
        model = self._prof().model
        return next((dict(e.rate or {}) for e in reg.values() if e.model == model), {})

    def toolbox(self):
        """The run's own local toolbox, started as a run would start it (sandbox: a fresh OpenShell sandbox)."""
        if self._box is None:
            self._box = LiveBox(self)
        return self._box

    def close(self) -> None:
        if self._box is not None:
            self._box.close()


# box: tools
class LiveBox:
    def __init__(self, world: World):
        from amoeba.interp.trace import TraceWriter
        from amoeba.localtools.toolbox import LocalSetup, LocalToolbox
        self.tmp = tempfile.TemporaryDirectory(prefix="amoeba-preflight-")
        self.box = LocalToolbox(LocalSetup(pool_dir=world.pool_dir, mode=world.mode, env=world.env), self.tmp.name,
                                TraceWriter(None, episode_id="preflight"))
        self.box.start()
        if self.box.server is None:
            log = Path(self.tmp.name) / "localtools.stderr.log"
            tail = log.read_text(errors="replace").strip().splitlines()[-1:] if log.exists() else []
            raise RuntimeError(" | ".join([*tail, self.box.error or "the local-tool server did not start"]))

    def call(self, tool: str, text: str) -> str:
        self.box.begin_step(1)
        return self.box.call(tool, text)

    def attach(self, name: str) -> bool:
        from amoeba.config.schema import AgentSpec, PromptRef
        from amoeba.tools.registry import ToolRegistry
        entry = next((s for s in self.box.skills if s["name"] == name), None)
        a = AgentSpec(agent_id="p", name="Preflight", role="worker", model="m", prompt=PromptRef(system="s", user="u"))
        return entry is not None and self.box.attach_skill(a, entry, ToolRegistry())

    def close(self) -> None:
        try:
            self.box.finish()
        finally:
            self.tmp.cleanup()


# box: tools
def _row(check, ok, detail, fix, needed, warn=False) -> Row:
    return Row(check, "ok" if ok else ("warn" if warn else "missing"), detail, "" if ok else fix, tuple(needed))


# box: tools
def check_keys(w: World) -> list[Row]:
    need = {"GEMINI_API_KEY": CATEGORIES, "TAVILY_API_KEY": ("research", "decision")}
    return [_row(k, bool(w.env.get(k)), "set" if w.env.get(k) else "not set", f"{k}: {ENV_FIX}", n)
            for k, n in need.items()]


# box: tools
def check_model(w: World) -> list[Row]:
    rows, quota = [], None
    try:
        reply = w.chat("Reply with the word ok.")
        rows.append(_row("gemma call", "ok" in (reply or "").lower(), f"replied ...{' '.join(reply.split())[-24:]!r}",
                         "check the profile's base_url and model in amoeba/llm/profiles.py", CATEGORIES))
    except Exception as e:
        quota = parse_quota(str(e))
        rows.append(Row("gemma call", "missing", " ".join(str(e).split())[:120],
                        "the daily quota is spent: run tomorrow, or use a paid key" if quota and quota["kind"] == "daily"
                        else "check the key and the network (the agent proxy)", CATEGORIES))
    r = w.rate()
    limits = f"RPM {r.get('rpm') or '?'}, RPD {r.get('rpd') or '?'} (models.yaml)"
    if quota is None:
        rows.append(Row("gemma rate limits", "ok", f"{limits}; no quota reply seen (the API does not report what is left)"))
    elif quota["kind"] == "daily":
        rows.append(Row("gemma rate limits", "missing", f"{limits}; daily quota reached (limit {quota['limit']})",
                        "wait for the daily reset; a stopped run resumes with --resume <run_id> (D160)", CATEGORIES))
    else:
        rows.append(Row("gemma rate limits", "warn", f"{limits}; per-minute quota reached (limit {quota['limit']}, "
                        f"retry in {quota['retry_s']} s)", "wait a minute; runs wait and retry on their own (D48)"))
    if w.skip_model_check:
        rows.append(Row("model_check v2", "warn", "skipped (--skip-model-check)", "run without --skip-model-check"))
        return rows
    res = w.model_check()
    got = {p["probe"]: p["status"] for p in res.get("probes", [])}
    bad = [f"{p}: {got.get(p, 'not run')}" for p in REQUIRED_PROBES if got.get(p) != "ok"]
    rows.append(_row("model_check v2", not bad, "; ".join(bad) or " / ".join(REQUIRED_PROBES) + " ok",
                     f"python -m scripts.model_check {w.profile} --protocol v2 (see its table)", CATEGORIES))
    return rows


# box: tools
def check_tavily(w: World) -> list[Row]:
    if not w.env.get("TAVILY_API_KEY"):
        return [Row("tavily call", "missing", "no key", f"TAVILY_API_KEY: {ENV_FIX}", ("research", "decision"))]
    hits = w.tavily_search("OpenAI-compatible API rate limits")
    rows = [_row("tavily call", bool(hits), f"{len(hits)} result(s)", "check the key and the network",
                 ("research", "decision"))]
    acc = ((w.tavily_usage() or {}).get("account") or {})
    used, limit = acc.get("plan_usage"), acc.get("plan_limit")
    if limit is None:
        rows.append(Row("tavily credits", "warn", "not reported by the API", "see app.tavily.com"))
    else:
        left = float(limit) - float(used or 0)
        rows.append(_row("tavily credits", left > 0, f"{left:g} of {limit} left this month",
                         "top up the Tavily plan or wait for the monthly reset", ("research", "decision")))
    return rows


# box: tools
def check_host(w: World) -> list[Row]:
    if w.mode != "sandbox":
        rows = [Row(n, "n/a", "in-process mode") for n in ("docker", "openshell gateway", "image amoeba-sandbox:local")]
        rows.append(_row("AMOEBA_SANDBOX=1", w.env.get("AMOEBA_SANDBOX") == "1", "in-process mode runs commands here",
                         "set AMOEBA_SANDBOX=1, only inside a disposable machine", LOCAL))
    else:
        code, out = w.sh(["docker", "info", "--format", "{{.ServerVersion}}"])
        rows = [_row("docker", code == 0, out.splitlines()[0][:80] if out else f"exit {code}",
                     "start the Docker daemon (dockerd)", LOCAL)]
        try:
            h = w.gateway_health()
            rows.append(_row("openshell gateway", "healthy" in h.lower() or "serving" in h.lower() or h == "",
                             " ".join(h.split())[:80] or "healthy", "docker compose -p amoeba-sandbox -f "
                             "amoeba/config/sandbox/docker-compose.yml up -d", LOCAL))
        except Exception as e:
            rows.append(Row("openshell gateway", "missing", f"{type(e).__name__}: {e}"[:120],
                            "docker compose -p amoeba-sandbox -f amoeba/config/sandbox/docker-compose.yml up -d",
                            LOCAL))
        code, _ = w.sh(["docker", "image", "inspect", "amoeba-sandbox:local"])
        rows.append(_row("image amoeba-sandbox:local", code == 0, "built" if code == 0 else "not built",
                         "bash amoeba/config/sandbox/build.sh", LOCAL))
    skills = w.pool_skills()
    rows.append(_row("pool skills", bool(skills), f"{len(skills)} skill(s) in {w.pool_dir}",
                     "python -m amoeba pool refresh", ("files",)))
    return rows


OFFICE_RUN = "python3 preflight_office.py"


# box: tools
def office_source() -> str:
    """office.py's own check, made runnable alone (it needs only openpyxl and soffice), printing JSON."""
    from amoeba.localtools import office
    return inspect.getsource(office) + "\nimport json\nprint(json.dumps(office_check()))\n"


# box: tools
def check_local(w: World) -> list[Row]:
    fix_lib = (lambda m: f"add {PIP.get(m, m)} to amoeba/config/sandbox/Dockerfile and run build.sh") \
        if w.mode == "sandbox" else (lambda m: f"pip install {PIP.get(m, m)}")
    try:
        box = w.toolbox()
    except Exception as e:
        why = f"{type(e).__name__}: {e}"[:120]
        why = f"{type(e).__name__}: {e}"[-160:]
        fix = ("the gateway and the sandbox supervisor images must match: docker pull "
               "ghcr.io/nvidia/openshell/gateway:latest, then docker compose ... up -d again"
               if "error phase" in why else
               "pip install -e . (the sandbox bridge runs python -m amoeba...)" if "No module named 'amoeba'" in why else
               "generate the gateway's certs once (docs/RUNNING_ON_A_VM.md), then restart it"
               if "launch-scoped" in why else "see the docker / gateway rows above")
        return [Row("local toolbox", "missing", why, fix, LOCAL)]
    calls = {"Write": '{"file_path": "preflight.txt", "content": "hello"}', "Read": "preflight.txt",
             "Edit": '{"file_path": "preflight.txt", "old_string": "hello", "new_string": "hello again"}',
             "Glob": "*.txt", "Grep": '{"pattern": "hello", "path": "."}', "Bash": "echo hello"}
    rows = []
    for tool in ("Write", "Read", "Edit", "Glob", "Grep", "Bash"):
        out = box.call(tool, calls[tool])
        ok = out.startswith(f"[local:{tool}]") and "refused" not in out[:200]
        rows.append(_row(f"local:{tool}", ok, " ".join(_stdout(out).split())[:60],
                         "see localtools.stderr.log; the server is `claude mcp serve`", LOCAL))
    rows.sort(key=lambda r: ["Bash", "Read", "Write", "Edit", "Glob", "Grep"].index(r.check.split(":")[1]))
    probe = ("import importlib, json\nout = {}\nfor m in %r:\n    try:\n        importlib.import_module(m); out[m] = True\n"
             "    except Exception:\n        out[m] = False\nprint(json.dumps(out))\n" % list(LIBS))
    got = _json_tail(box.call("Bash", f"python3 - <<'PY'\n{probe}PY"))
    for m, need in LIBS.items():
        rows.append(_row(f"import {m}", bool(got.get(m)), "imports" if got.get(m) else "not importable", fix_lib(m),
                         need))
    out = box.call("Bash", "command -v soffice || command -v libreoffice")
    has = out.startswith("[local:Bash]") and "office" in _stdout(out)
    rows.append(_row("soffice", has, _stdout(out).strip()[:60] or "not found",
                     "add libreoffice-calc and libreoffice-writer (Dockerfile, or scripts/setup_office.sh)", ("files",)))
    box.call("Write", json.dumps({"file_path": "preflight_office.py", "content": office_source()}))
    res = _json_tail(box.call("Bash", OFFICE_RUN + "  # office_check"))
    rows.append(_row("office_check", bool(res.get("ok")), str(res.get("detail") or "no result")[:80],
                     "LibreOffice Calc must recalculate =A1*A2 to 6 (see amoeba/localtools/office.py)", ("files",)))
    listed = {s["name"] for s in w.pool_skills()}
    for s in SKILLS:
        if s not in listed:
            rows.append(Row(f"skill {s}", "missing", "not listed", "python -m amoeba pool refresh", ("files",)))
        else:
            ok = box.attach(s)
            rows.append(_row(f"skill {s}", ok, "listed, attaches" if ok else "listed, does not attach",
                             "rebuild the image (skills are baked into /opt/skills)", ("files",)))
    return rows


# box: tools
def _stdout(out: str) -> str:
    """The text a local call printed: the server answers Bash with {"stdout": ..., "stderr": ...} after a header."""
    body = (out or "").split("\n", 1)[-1] if (out or "").startswith("[local:") else (out or "")
    try:
        d = json.loads(body)
    except ValueError:
        return body
    return f"{d.get('stdout', '')}\n{d.get('stderr', '')}".strip() if isinstance(d, dict) and "stdout" in d \
        else body


# box: tools
def _json_tail(out: str) -> dict:
    for line in reversed(_stdout(out).splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                return {}
    return {}


CHECKS = (check_keys, check_model, check_tavily, check_host, check_local)


# box: tools
def run_checks(w: World, checks=CHECKS) -> list[Row]:
    """Every check; one that crashes becomes a missing row with the error, never a crash."""
    rows = []
    for c in checks:
        try:
            rows += c(w)
        except Exception as e:
            rows.append(Row(c.__name__.removeprefix("check_"), "missing", f"{type(e).__name__}: {e}"[:120],
                            "see the error", CATEGORIES))
    return rows


# box: tools
def exit_code(rows: list[Row]) -> int:
    return 1 if any(r.status == "missing" and r.needed_by for r in rows) else 0


# box: tools
def table(rows: list[Row]) -> str:
    head = ("check", "status", "what was seen", "how to fix", "needed by")
    data = [(r.check, r.status, r.detail, r.fix, ", ".join(r.needed_by) if r.status == "missing" else "")
            for r in rows]
    width = [min(48, max(len(str(x[i])) for x in [head, *data])) for i in range(5)]
    line = lambda x: " | ".join(str(v)[:width[i]].ljust(width[i]) for i, v in enumerate(x)).rstrip()
    return "\n".join([line(head), "-+-".join("-" * n for n in width), *map(line, data)])


# box: tools
def main(argv: list[str] | None = None, world: World | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--profile", default="gemma-api")
    p.add_argument("--mode", choices=["sandbox", "inprocess"], default="sandbox", help="the local-tools mode")
    p.add_argument("--skip-model-check", action="store_true", help="skip the ~5 minute model_check")
    p.add_argument("--pool-dir", default="data/pool")
    args = p.parse_args(argv)
    w = world or World(args.mode, args.profile, args.skip_model_check, args.pool_dir)
    try:
        rows = run_checks(w)
    finally:
        if world is None:
            w.close()
    print(f"== preflight: profile {args.profile}, local tools {args.mode}")
    print(table(rows))
    missing = sorted({c for r in rows if r.status == "missing" for c in r.needed_by})
    print(f"== {'MISSING for: ' + ', '.join(missing) if missing else 'everything the categories need is here'}")
    return exit_code(rows)


if __name__ == "__main__":
    sys.exit(main())
