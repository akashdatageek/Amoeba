"""D59 — the local toolbox: Claude Code's Bash, Read, Write, Edit (and Glob, Grep when the server offers them) as
`local:<Name>` tools of the run, plus local skills, for Box 3's "Stock the toolbox" step.

LLM proposes, plain code disposes. Local items join the pool's candidates (ranked above internet ones), the same
one AI pick chooses, and plain code vets, attaches and gates every call:
  - only the allowed tools; every other tool the server lists is refused once, by name, at the start;
  - every path inside runs/<id>/workspace/, every Bash command from there and through the gate (gate.py);
  - 60 s per call, 8,000 characters of output, 20 calls per step and 60 per run;
  - a trace line for every call and every refusal; the files the calls created, with their step, in result.json.
The server runs with a minimal environment: PATH (this Python first, so python3 has openpyxl, python-docx,
python-pptx, matplotlib and pypdf), a private HOME, and no keys or proxy settings.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from amoeba.config.schema import AgentSpec
from amoeba.interp.shorten import shorten
from amoeba.tools.web import note_seen
from amoeba.localtools.gate import (in_workspace, inside, protected_command, protected_path, readonly_root,
                                    require_sandbox, screen_command)
from amoeba.localtools.sandbox import SANDBOX_WORKSPACE, OpenShellBox, sandbox_config
from amoeba.localtools.office import office_check
from amoeba.localtools.server import StdioServer
from amoeba.localtools.skills import card_text, copy_skill, list_skills, sandbox_skill_path
from amoeba.pool.match import document_format, rank
from amoeba.pool.mcp import SourceBook, data_block

INPUTS = "sources"            # D107: the workspace folder of read-only input files (fetched pages and data tables)

CONFIG_FILE = Path(__file__).resolve().parents[1] / "config" / "localtools.yaml"

# what each tool is for (for the match and the picker) and how a helper writes its ActionInput
TOOL_TEXT = {
    "Bash": ("run Python code or a shell command in this run's sandboxed workspace (code runner: python3 with "
             "openpyxl, python-docx, python-pptx, matplotlib, pypdf); make charts, spreadsheets, documents; no network",
             "ActionInput: the shell command as plain text (or {\"command\": \"...\"}). It runs from the workspace "
             "folder; python3 has openpyxl, python-docx, python-pptx, matplotlib and pypdf; there is no network. "
             "Save every file you make inside the workspace (e.g. chart.png) and name it in your output."),
    "Read": ("read a file in the workspace: text, code, a PDF's pages",
             "ActionInput: a file path inside the workspace (relative paths start there), or "
             "{\"file_path\": \"...\", \"offset\": N, \"limit\": N}."),
    "Write": ("write (save) a file in the workspace: text, markdown, csv, code",
              "ActionInput: {\"file_path\": \"name.ext\", \"content\": \"...\"} (a path inside the workspace)."),
    "Edit": ("edit a file in the workspace by replacing exact text",
             "ActionInput: {\"file_path\": \"...\", \"old_string\": \"...\", \"new_string\": \"...\"}."),
    "Glob": ("find files in the workspace by name pattern", "ActionInput: a pattern such as **/*.csv."),
    "Grep": ("search the contents of files in the workspace", "ActionInput: {\"pattern\": \"...\", \"path\": \".\"}."),
}
PATH_ARG = {"Read": "file_path", "Write": "file_path", "Edit": "file_path", "Glob": "path", "Grep": "path"}
READ_TOOLS = {"Read", "Glob", "Grep"}
PLAIN_ARG = {"Bash": "command", "Read": "file_path", "Glob": "pattern", "Grep": "pattern"}


# box: localtools
def load_local_config(path: Path = CONFIG_FILE) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# box: localtools
@dataclass
class LocalSetup:
    """What a run needs for --local-tools on: localtools.yaml, the command, the pool cache (for kept skill clones)."""

    config: dict = field(default_factory=load_local_config)
    command: list[str] | None = None                  # default: config["command"] (claude mcp serve)
    pool_dir: str | Path = "data/pool"
    env: Any = field(default_factory=lambda: os.environ)
    mode: str | None = None                           # D96a: "sandbox" | "inprocess" (--local-tools-mode); None: config

    @property
    def limits(self) -> dict:
        return self.config["limits"]

    @property
    def isolation(self) -> str:
        """D96: "openshell" = the server and its commands run in a fresh OpenShell sandbox per run; "process" = the
        D59 server process on this host (AMOEBA_SANDBOX=1 required)."""
        if self.mode == "inprocess":                  # D96a: only when asked for explicitly
            return "process"
        if self.mode == "sandbox":
            return "openshell"
        return sandbox_config(self.config)["isolation"]

    def with_limits(self, sandbox: dict | None) -> "LocalSetup":
        """D102: a copy with a niche profile's sandbox limits (timeout_s per command; cpu, memory, run_timeout_s per
        sandbox) over localtools.yaml's."""
        if not sandbox:
            return self
        cfg = {**self.config, "limits": dict(self.config["limits"]), "sandbox": dict(self.config.get("sandbox") or {})}
        if sandbox.get("timeout_s") is not None:
            cfg["limits"]["timeout_s"] = sandbox["timeout_s"]
        for k in ("cpu", "memory", "run_timeout_s"):
            if sandbox.get(k) is not None:
                cfg["sandbox"][k] = sandbox[k]
        return LocalSetup(config=cfg, command=self.command, pool_dir=self.pool_dir, env=self.env, mode=self.mode)

    def without(self, names) -> "LocalSetup":
        """D80 --disable-tools: a copy whose allowed tools leave out `local:<Name>` for each name given."""
        drop = {n.removeprefix("local:") for n in names or () if n.startswith("local:")}
        cfg = {**self.config, "allowed_tools": [t for t in self.config["allowed_tools"] if t not in drop]}
        return LocalSetup(config=cfg, command=self.command, pool_dir=self.pool_dir, env=self.env, mode=self.mode)


# box: localtools
def unfence(text: str) -> str:
    """D61 (P17): the content of a surrounding markdown code fence (```bash ... ```), else the text stripped."""
    text = (text or "").strip()
    m = re.fullmatch(r"```(?:[\w+.-]*[ \t]*\n)?(.*?)\n?```", text, re.S)   # a language tag only before a newline
    return m.group(1).strip() if m else text


# box: localtools
def alias_words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


# box: localtools
class LocalToolbox:
    """One run's local toolbox. start() lists the server's tools; call() gates and runs one; finish() copies the
    workspace into the run folder, closes the server and returns what goes into result.json."""

    def __init__(self, setup: LocalSetup, run_dir: str | Path, trace):
        if setup.isolation != "openshell":            # D96: the OpenShell sandbox is the boundary there
            require_sandbox(setup.env)
        self.setup, self.trace = setup, trace
        self.box = None                               # D96: the run's OpenShell sandbox (isolation openshell)
        self.lim = setup.limits
        self.run_dir = Path(run_dir)
        self.workspace = self.run_dir / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.home = self.run_dir / "localtools_home"
        self.server = None
        self.exposed: list[str] = []                  # allowed and offered by the server
        self.listing: list[dict] = []
        self.step: int | None = None
        self.calls = 0
        self.step_calls = 0
        self.refusals: dict[str, int] = {}
        self.files: dict[str, dict] = {}             # workspace-relative path -> {path, size, step}
        self._seen = self._snapshot()
        self.skills: list[dict] = []                 # listed local skills
        self.skills_attached: list[dict] = []
        self.inputs: list[dict] = []                 # D107: read-only input files in sources/ (fetched pages, tables)
        self.error: str | None = None
        self.book = None                             # D61 (G7): the run's [S#] list, set by stock_toolbox
        self.office: dict | None = None              # D71: office_check(), run when the xlsx skill is attached

    # ---- the server -------------------------------------------------------------------------------------------
    def server_env(self) -> dict[str, str]:
        """Exactly what the local-tool server (and every agent command it runs) gets: no keys, no proxy, no cloud
        credentials (D95)."""
        return {"PATH": os.pathsep.join([str(Path(sys.executable).parent), os.environ.get("PATH", "")]),
                "HOME": str(self.home.resolve()), "LANG": "C.UTF-8", "MPLBACKEND": "Agg",
                "PYTHONDONTWRITEBYTECODE": "1", "AMOEBA_SANDBOX": "1"}

    def start(self) -> None:
        cmd = self.setup.command or list(self.setup.config["command"])
        self.home.mkdir(parents=True, exist_ok=True)
        env = self.server_env()
        try:
            if self.setup.isolation == "openshell":   # D96: a fresh sandbox; the server runs inside it
                scfg = sandbox_config(self.setup.config)
                self.box = OpenShellBox(scfg, str(self.run_dir.resolve()), record=lambda e, d: self.trace.event(
                    e, {"amoeba.box": "localtools", **d}))
                self.box.create()
                cmd = [sys.executable, "-m", "amoeba.localtools.sandbox", "bridge", self.box.name,
                       "--endpoint", scfg["endpoint"], "--", *cmd]
                env = {"PATH": env["PATH"], "LANG": "C.UTF-8"}   # the relay needs nothing else
            self.server = StdioServer(cmd, self.workspace.resolve(), env,
                                      errlog=self.run_dir / "localtools.stderr.log")
            self.listing = self.server.start()
        except Exception as e:                        # no CLI, no start: the run goes on without local tools
            self.error = f"{type(e).__name__}: {e}"[:300]
            self.server = None
            self.trace.event("local_unavailable", {"amoeba.box": "localtools", "error.type": self.error,
                                                   "amoeba.local.command": " ".join(cmd)})
            return
        allowed = list(self.setup.config["allowed_tools"])
        names = [t["name"] for t in self.listing]
        self.exposed = [n for n in allowed if n in names]
        for n in names:                               # refused once each, at the start
            if n not in allowed:
                self._refuse_tool(n, "not_allowed")
        for n in allowed:
            if n not in names:
                self.trace.event("local_tool_missing", {"amoeba.box": "localtools", "gen_ai.tool.name": n,
                                                        "amoeba.reason": "not_offered_by_server"})
        self.skills = list_skills(self.setup.config, Path(self.setup.pool_dir))
        self.trace.event("local_tools", {"amoeba.box": "localtools", "amoeba.local.server": self.server.info,
                                         "amoeba.local.exposed": [f"local:{n}" for n in self.exposed],
                                         "amoeba.local.refused": [n for n in names if n not in allowed],
                                         "amoeba.local.skills": [s["id"] for s in self.skills],
                                         "amoeba.local.workspace": str(self.workspace)})

    def _refuse_tool(self, name: str, reason: str) -> None:
        self.trace.event("local_tool_refused", {"amoeba.box": "localtools", "gen_ai.tool.name": name,
                                                "amoeba.reason": reason})

    # ---- matching: local items first (D59) ----------------------------------------------------------------------
    def entries(self) -> list[dict]:
        tools = [{"id": f"local:{n}", "name": f"local:{n}", "title": f"{n} (local, sandboxed)",
                  "description": TOOL_TEXT.get(n, ("", ""))[0], "kind": "tool", "source": "local"}
                 for n in self.exposed]
        return tools + (self.skills if self.exposed else [])

    def alias_hits(self, q) -> list[dict]:
        """Local entries named by an alias whose words all appear in the request's name or standard name."""
        have = alias_words(q.name) | alias_words(q.canonical)
        by_id = {e["id"]: e for e in self.entries()}
        out = []
        for target, phrases in (self.setup.config.get("aliases") or {}).items():
            if not any(alias_words(p) <= have for p in phrases):
                continue
            if target.startswith("skill:"):
                out += [e for e in self.entries() if e["kind"] == "skill" and e["name"] == target[6:]]
            elif target in by_id:
                out.append(by_id[target])
        return out

    def candidates(self, q, top: int) -> list[tuple[int, dict]]:
        """(score, entry) for local items: alias hits first (score 100), then keyword matches."""
        if self.server is None:
            return []
        out, seen = [], set()
        for e in self.alias_hits(q):
            if e["id"] not in seen:
                out.append((100, e))
                seen.add(e["id"])
        for s, e in rank(q, self.entries(), top):
            if e["id"] not in seen:
                out.append((s, e))
                seen.add(e["id"])
        return out[:top]

    def format_skill(self, q) -> dict | None:
        """D69: the vetted local skill for the document format a request names (xlsx, docx, pptx, pdf), or None."""
        fmt = document_format(q)
        if fmt is None or self.server is None:
            return None
        return next((e for e in self.entries() if e["kind"] == "skill" and e["name"] == fmt and self.vet(e) is None),
                    None)

    def vet(self, entry: dict) -> str | None:
        if self.server is None:
            return "local_unavailable"
        if entry["kind"] == "tool":
            return None if entry["name"].removeprefix("local:") in self.exposed else "not_exposed"
        return None if (Path(entry["path"]) / "SKILL.md").is_file() else "body_missing"

    # ---- attaching -------------------------------------------------------------------------------------------
    def register(self, reg, name: str) -> None:
        if name not in reg:
            reg.register(name, f"local tool {name} (claude mcp serve, sandboxed, D59)",
                         lambda text, _n=name.removeprefix("local:"): self.call(_n, text))

    def attach_tool(self, a: AgentSpec, name: str, reg, request: str = "") -> None:
        self.register(reg, name)
        if name not in a.tools:
            a.tools.append(name)
        if not any(p.get("name") == name for p in a.pool):
            a.pool.append({"kind": "tool", "id": name, "name": name, "source": "local", "request": request,
                           "text": TOOL_TEXT[name.removeprefix("local:")][1]})

    def attach_skill(self, a: AgentSpec, entry: dict, reg, request: str = "") -> bool:
        body = card_text(entry, int(self.lim["max_skill_chars"]))
        if body is None:
            return False
        boxed = self.setup.isolation == "openshell"
        if boxed:                                     # D96: skills are baked into the image, read-only
            dest = sandbox_skill_path(entry)          # D103: the root is a label; its folder is root_path
            if dest is None:
                self.trace.event("skill_refused", {"amoeba.box": "localtools", "amoeba.skill": entry["id"],
                                                   "amoeba.reason": "not in the sandbox image"})
                return False
        else:
            dest = copy_skill(entry, self.workspace)
            self._seen = self._snapshot()             # the copied skill is input, not a file the team made
        note = ""
        if entry["name"] == "xlsx":                   # D71: can formulas be recalculated here? checked once per run
            if self.office is None:
                self.office = office_check()
                self.trace.event("office_check", {"amoeba.box": "localtools", "amoeba.ok": self.office["ok"],
                                                  "amoeba.detail": self.office["detail"]})
            if not self.office["ok"]:
                note = ("\nNote from plain code: LibreOffice cannot recalculate formulas in this sandbox "
                        f"({self.office['detail']}), so scripts/recalc.py will fail; write the formulas and say what "
                        "they compute.")
        a.pool.append({"kind": "skill", "id": entry["id"], "name": entry["name"], "source": "local", "request": request,
                       "text": f"Skill: {entry['name']} (local, from {entry['root']})\n"
                               f"{data_block('skill ' + entry['name'], body)}\n"
                               + (f"Full skill files are in {dest}/ (read-only); read them with local:Read if needed."
                                  if boxed else
                                  f"Full skill files are in skills/{entry['name']}/; read them with local:Read if needed.")
                               + note})
        for n in ("Read", "Bash", "Write", "Edit"):  # a skill is used by reading and running its files
            if n in self.exposed:
                self.attach_tool(a, f"local:{n}", reg)
        rec = next((s for s in self.skills_attached if s["id"] == entry["id"]), None)
        if rec is None:
            rec = {"id": entry["id"], "name": entry["name"], "root": entry["root"],
                   "path": f"sandbox:{dest}" if boxed else str(dest.relative_to(self.run_dir)), "helpers": []}
            self.skills_attached.append(rec)
        rec["helpers"].append(a.name)
        return True

    # ---- calls -----------------------------------------------------------------------------------------------
    def begin_step(self, step: int, trace=None) -> None:
        self.step, self.step_calls = step, 0
        if trace is not None:
            self.trace = trace
        if isinstance(self.book, SourceBook):        # WebTools is stepped by its own runner call
            self.book.begin_step(step, trace)

    @staticmethod
    def what(tool: str, args) -> str:
        """The command or path a call is about, for its trace line (a file's content is never logged)."""
        if not isinstance(args, dict):
            return str(args or "")[:300]
        key = "command" if tool == "Bash" else PATH_ARG.get(tool, "")
        return str(args.get(key) or args.get("pattern") or "")[:300]

    def refuse(self, tool: str, reason: str, detail: str = "", what: str = "") -> str:
        self.refusals[reason] = self.refusals.get(reason, 0) + 1
        self.trace.event("local_refused", {"amoeba.box": "localtools", "amoeba.step": self.step,
                                           "gen_ai.tool.name": f"local:{tool}", "amoeba.input": what[:300],
                                           "amoeba.decision": "refused", "amoeba.reason": reason,
                                           "amoeba.detail": detail[:200]})
        return f"refused: local:{tool} — {reason}" + (f" ({detail[:200]})" if detail else "") + \
               ". Nothing was run; stay inside the workspace, with no network."

    def arguments(self, tool: str, text: str) -> dict:
        text = unfence(text)                          # D61 (P17): a ```bash ... ``` block is its content
        if text.startswith("{"):
            try:
                obj = json.loads(text)
            except ValueError:
                obj = None
            if isinstance(obj, dict):
                return obj
        if tool in PLAIN_ARG:
            return {PLAIN_ARG[tool]: text}
        raise ValueError(f"write a JSON object: {TOOL_TEXT[tool][1]}")

    def call(self, tool: str, text: str) -> str:
        if self.server is None:
            return f"error: local:{tool} is not available in this run"
        try:
            args = self.arguments(tool, text) if tool in TOOL_TEXT else {}
            bad = None
        except ValueError as e:
            args, bad = {}, str(e)
        what = self.what(tool, args) or (text or "")[:120]
        if self.calls >= int(self.lim["max_calls_per_run"]):
            return self.refuse(tool, "run_cap", f"{self.lim['max_calls_per_run']} calls per run", what)
        if self.step_calls >= int(self.lim["max_calls_per_step"]):
            return self.refuse(tool, "step_cap", f"{self.lim['max_calls_per_step']} calls per step", what)
        if tool not in self.exposed:
            return self.refuse(tool, "not_allowed", "", what)
        if bad is not None:
            return self.refuse(tool, "bad_input", bad, what)
        timeout_s = float(self.lim["timeout_s"])
        boxed = self.box is not None
        if boxed and self.box.expired():               # D96: the run's time limit
            return self.refuse(tool, "run_time_cap", f"{self.box.cfg['run_timeout_s']} s per run", what)
        ws = str(self.workspace.resolve())
        if tool == "Bash":
            command = str(args.get("command", ""))
            screened = command.replace(SANDBOX_WORKSPACE, ws) if boxed else command
            why = protected_command(command) or screen_command(
                screened, self.workspace, sandbox_config(self.setup.config) if boxed else None)   # D103
            if why:
                return self.refuse(tool, *why, what=what)
            run_in = Path(SANDBOX_WORKSPACE) if boxed else self.workspace
            args = {"command": in_workspace(command, run_in) if boxed else in_workspace(command, self.workspace),
                    "timeout": int(timeout_s * 1000)}
        if tool in PATH_ARG:
            key = PATH_ARG[tool]
            if key in args or key == "file_path":
                raw = str(args.get(key, ""))
                if boxed and raw.startswith(SANDBOX_WORKSPACE):
                    raw = ws + raw[len(SANDBOX_WORKSPACE):]
                if boxed and tool in READ_TOOLS and readonly_root(raw, sandbox_config(self.setup.config)):
                    pass                              # D96: a baked-in skill file, read-only in the sandbox
                else:
                    p = inside(raw, self.workspace)
                    if p is None:
                        return self.refuse(tool, "outside_workspace", "", what)
                    if tool not in READ_TOOLS and protected_path(p, self.workspace):
                        return self.refuse(tool, "protected_config", "MCP configs, skills and hooks are read-only",
                                           what)
                    raw = str(p)
                args[key] = (SANDBOX_WORKSPACE + raw[len(ws):]) if boxed and raw.startswith(ws) else raw
            else:
                args[key] = SANDBOX_WORKSPACE if boxed else ws
        self.calls += 1
        self.step_calls += 1
        t0 = time.perf_counter()
        try:
            out, is_error = self.server.call(tool, args, timeout_s + 5)
            timed_out = False
        except TimeoutError:
            out, is_error, timed_out = f"timed out after {timeout_s:.0f} s", True, True
        except Exception as e:                        # a broken call is an error line, never a crash
            out, is_error, timed_out = f"{type(e).__name__}: {e}"[:300], True, False
        if boxed:                                     # D96: the files the team made, copied out of the sandbox
            try:
                self.box.pull(self.workspace)
            except Exception as e:
                self.trace.event("sandbox_pull_failed", {"amoeba.box": "localtools", "amoeba.error": str(e)[:200]})
        new = self._scan()
        cap = int(self.lim["max_output_chars"])
        cut = shorten(out, cap)                       # D64: head, result lines and the last lines of output kept
        self.trace.event("local_call", {"amoeba.box": "localtools", "amoeba.step": self.step,
                                        "gen_ai.tool.name": f"local:{tool}", "amoeba.input": what,
                                        "amoeba.decision": "allowed", "amoeba.chars": len(out),
                                        "amoeba.chars_passed": len(cut), "amoeba.is_error": is_error,
                                        "amoeba.timeout": timed_out, "amoeba.files": new,
                                        "amoeba.ms": int((time.perf_counter() - t0) * 1000)})
        more = f"\n[shortened from {len(out)} characters: head, result lines and tail kept]" if len(out) > cap else ""
        src = ""
        if self.book is not None and not is_error:    # D61 (G7): a local result is a source the helper can cite
            key = hashlib.sha256(f"{self.calls}:{tool}:{what}".encode()).hexdigest()[:10]
            s = self.book._source(f"local://{tool}/{key}", f"local:{tool} · {what[:80]}", "local", what[:300])
            note_seen(s, cut)                                                   # D74
            src = f" [{s['id']}] (cite a fact from this result by its [{s['id']}])"
            self.trace.event("local_source", {"amoeba.box": "localtools", "amoeba.step": self.step,
                                              "gen_ai.tool.name": f"local:{tool}", "amoeba.source_id": s["id"]})
        return f"[local:{tool}{' error' if is_error else ''}]{src}\n{cut}{more}"

    # ---- files -----------------------------------------------------------------------------------------------
    def _snapshot(self) -> dict[str, tuple[int, int]]:
        out = {}
        if self.workspace.is_dir():
            for f in self.workspace.rglob("*"):
                rel = f.relative_to(self.workspace)
                if f.is_file() and not f.is_symlink() and rel.parts[0] not in ("skills", INPUTS):   # D107: inputs
                    st = f.stat()
                    out[str(rel)] = (st.st_size, st.st_mtime_ns)
        return out

    def _scan(self) -> list[str]:
        """Files new or changed since the last look, credited to the current step."""
        now = self._snapshot()
        changed = [p for p, v in now.items() if self._seen.get(p) != v]
        for p in changed:
            self.files[p] = {"path": p, "size": now[p][0], "step": self.step}
        self._seen = now
        return changed

    # box: localtools
    def add_input(self, name: str, content: bytes) -> str:
        """D107: a read-only input file in <workspace>/sources/ — on the host and, in sandbox mode, in the sandbox's
        workspace (no network there: this is how fetched data reaches the analysts). Never counted as made."""
        safe = re.sub(r"[^\w.-]+", "_", name).strip("._")[:120] or "source"
        rel = f"{INPUTS}/{safe}"
        p = self.workspace / INPUTS / safe
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            p.chmod(0o644)
        p.write_bytes(content)
        p.chmod(0o444)
        if self.box is not None:
            q = shlex.quote(f"{SANDBOX_WORKSPACE}/{rel}")
            try:
                r = self.box.exec(["bash", "-c", f"mkdir -p {SANDBOX_WORKSPACE}/{INPUTS} && rm -f {q} && cat > {q} "
                                                 f"&& chmod 0444 {q}"], stdin=content, timeout_s=60)
                if getattr(r, "exit_code", 0) != 0:
                    raise RuntimeError(f"exit {r.exit_code}")
            except Exception as e:                    # the host copy stays; the step is told what is missing
                self.trace.event("input_upload_failed", {"amoeba.box": "localtools", "amoeba.file": rel,
                                                         "amoeba.error": str(e)[:200]})
        return rel

    # box: localtools
    def save_source(self, rec: dict, web=None) -> str | None:
        """D107: one fetched page (text) or data file (its table as CSV) into sources/, and sources/index.json with
        each file's source id, url, title, kind, rows and time (its provenance). The web source records its file."""
        sid = rec.get("source", "S0")
        if rec.get("kind") == "data":
            import csv
            import io
            buf = io.StringIO()
            csv.writer(buf).writerows((rec.get("table") or {}).get("rows") or [])
            stem = re.sub(r"\.(csv|tsv|xlsx|xlsm|json)$", "", rec.get("url", "").rstrip("/").rsplit("/", 1)[-1].split("?")[0])
            rel = self.add_input(f"{sid}_{stem or 'data'}.csv", buf.getvalue().encode("utf-8"))
            rows = (rec.get("table") or {}).get("n_rows")
        else:
            slug = re.sub(r"[^\w]+", "_", rec.get("title") or "page").strip("_")[:40] or "page"
            head = f"Source: {sid}\nURL: {rec.get('url', '')}\nTitle: {rec.get('title', '')}\n\n"
            rel = self.add_input(f"{sid}_{slug}.txt", (head + (rec.get("text") or "")).encode("utf-8"))
            rows = None
        src = next((s for s in (web.sources if web is not None else []) if s["id"] == sid), None)
        entry = {"source": sid, "file": rel, "kind": rec.get("kind"), "url": rec.get("url"), "rows": rows,
                 "title": (src or {}).get("title") or rec.get("title"), "fetched_at": (src or {}).get("fetched_at"),
                 "step": rec.get("step")}
        self.inputs = [x for x in self.inputs if x["file"] != rel] + [entry]
        self.add_input("index.json", json.dumps(self.inputs, indent=1, ensure_ascii=False).encode("utf-8"))
        if src is not None:
            src["workspace_file"] = rel
            if rec.get("kind") == "page":             # what the analysts can read from the file counts as in S#
                note_seen(src, (rec.get("text") or "")[:20000])
        self.trace.event("workspace_source", {"amoeba.box": "localtools", "amoeba.source_id": sid, "amoeba.file": rel,
                                              "amoeba.kind": rec.get("kind"), "amoeba.rows": rows})
        return rel

    def has_file(self, name: str) -> bool:
        """A file the team says it made: the path in the workspace, or a file of that name anywhere in it."""
        p = inside(name, self.workspace)
        if p is not None and p.is_file():
            return True
        base = Path(name).name
        if any(Path(f).name == base for f in self._snapshot()):
            return True
        skills = self.workspace / "skills"                # a skill's own script the step ran (recalc.py) is no lie
        return skills.is_dir() and any(f.is_file() for f in skills.rglob(base))

    def finish(self) -> dict:
        """Copy the workspace to runs/<id>/artifacts/files/ (skills/ left out), close the server, and report."""
        if self.box is not None:                      # D96: last copy, the sandbox's own decisions, then delete it
            try:
                self.box.pull(self.workspace)
            except Exception:
                pass
        self._scan()
        if self.server is not None:
            self.server.close()
        if self.box is not None:
            self.trace.event("sandbox_log", {"amoeba.box": "localtools", "amoeba.sandbox": self.box.name,
                                             "amoeba.decisions": self.box.logs()})
            self.box.delete()
        dest = self.run_dir / "artifacts" / "files"
        for rel in self._snapshot():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.workspace / rel, dest / rel)
        shutil.rmtree(self.home, ignore_errors=True)
        now = self._snapshot()
        files = [{**v, "size": now.get(p, (v["size"],))[0]} for p, v in sorted(self.files.items()) if p in now]
        return {"files_created": files, "local_tool_calls": self.calls, "local_refusals": dict(self.refusals),
                "skills_attached": self.skills_attached}
