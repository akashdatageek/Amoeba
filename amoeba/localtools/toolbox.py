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

import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from amoeba.config.schema import AgentSpec
from amoeba.localtools.gate import in_workspace, inside, require_sandbox, screen_command
from amoeba.localtools.server import StdioServer
from amoeba.localtools.skills import card_text, copy_skill, list_skills
from amoeba.pool.match import rank
from amoeba.pool.mcp import data_block

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

    @property
    def limits(self) -> dict:
        return self.config["limits"]


# box: localtools
def alias_words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


# box: localtools
class LocalToolbox:
    """One run's local toolbox. start() lists the server's tools; call() gates and runs one; finish() copies the
    workspace into the run folder, closes the server and returns what goes into result.json."""

    def __init__(self, setup: LocalSetup, run_dir: str | Path, trace):
        require_sandbox(setup.env)
        self.setup, self.trace = setup, trace
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
        self.error: str | None = None

    # ---- the server -------------------------------------------------------------------------------------------
    def start(self) -> None:
        cmd = self.setup.command or list(self.setup.config["command"])
        self.home.mkdir(parents=True, exist_ok=True)
        env = {"PATH": os.pathsep.join([str(Path(sys.executable).parent), os.environ.get("PATH", "")]),
               "HOME": str(self.home.resolve()), "LANG": "C.UTF-8", "MPLBACKEND": "Agg",
               "PYTHONDONTWRITEBYTECODE": "1", "AMOEBA_SANDBOX": "1"}
        self.server = StdioServer(cmd, self.workspace.resolve(), env, errlog=self.run_dir / "localtools.stderr.log")
        try:
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

    def attach_tool(self, a: AgentSpec, name: str, reg) -> None:
        self.register(reg, name)
        if name not in a.tools:
            a.tools.append(name)
        if not any(p.get("name") == name for p in a.pool):
            a.pool.append({"kind": "tool", "id": name, "name": name, "source": "local",
                           "text": TOOL_TEXT[name.removeprefix("local:")][1]})

    def attach_skill(self, a: AgentSpec, entry: dict, reg) -> bool:
        body = card_text(entry, int(self.lim["max_skill_chars"]))
        if body is None:
            return False
        dest = copy_skill(entry, self.workspace)
        self._seen = self._snapshot()                 # the copied skill is input, not a file the team made
        a.pool.append({"kind": "skill", "id": entry["id"], "name": entry["name"], "source": "local",
                       "text": f"Skill: {entry['name']} (local, from {entry['root']})\n"
                               f"{data_block('skill ' + entry['name'], body)}\n"
                               f"Full skill files are in skills/{entry['name']}/; read them with local:Read if needed."})
        for n in ("Read", "Bash", "Write", "Edit"):  # a skill is used by reading and running its files
            if n in self.exposed:
                self.attach_tool(a, f"local:{n}", reg)
        rec = next((s for s in self.skills_attached if s["id"] == entry["id"]), None)
        if rec is None:
            rec = {"id": entry["id"], "name": entry["name"], "root": entry["root"],
                   "path": str(dest.relative_to(self.run_dir)), "helpers": []}
            self.skills_attached.append(rec)
        rec["helpers"].append(a.name)
        return True

    # ---- calls -----------------------------------------------------------------------------------------------
    def begin_step(self, step: int, trace=None) -> None:
        self.step, self.step_calls = step, 0
        if trace is not None:
            self.trace = trace

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
        text = (text or "").strip()
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
        if tool == "Bash":
            why = screen_command(str(args.get("command", "")), self.workspace)
            if why:
                return self.refuse(tool, *why, what=what)
            args = {"command": in_workspace(args["command"], self.workspace), "timeout": int(timeout_s * 1000)}
        if tool in PATH_ARG:
            key = PATH_ARG[tool]
            if key in args or key == "file_path":
                p = inside(str(args.get(key, "")), self.workspace)
                if p is None:
                    return self.refuse(tool, "outside_workspace", "", what)
                args[key] = str(p)
            else:
                args[key] = str(self.workspace.resolve())
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
        new = self._scan()
        cap = int(self.lim["max_output_chars"])
        cut = out[:cap]
        self.trace.event("local_call", {"amoeba.box": "localtools", "amoeba.step": self.step,
                                        "gen_ai.tool.name": f"local:{tool}", "amoeba.input": what,
                                        "amoeba.decision": "allowed", "amoeba.chars": len(out),
                                        "amoeba.chars_passed": len(cut), "amoeba.is_error": is_error,
                                        "amoeba.timeout": timed_out, "amoeba.files": new,
                                        "amoeba.ms": int((time.perf_counter() - t0) * 1000)})
        more = f"\n[… first {cap} of {len(out)} characters]" if len(out) > cap else ""
        return f"[local:{tool}{' error' if is_error else ''}]\n{cut}{more}"

    # ---- files -----------------------------------------------------------------------------------------------
    def _snapshot(self) -> dict[str, tuple[int, int]]:
        out = {}
        if self.workspace.is_dir():
            for f in self.workspace.rglob("*"):
                rel = f.relative_to(self.workspace)
                if f.is_file() and not f.is_symlink() and rel.parts[0] != "skills":
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

    def has_file(self, name: str) -> bool:
        """A file the team says it made: the path in the workspace, or a file of that name anywhere in it."""
        p = inside(name, self.workspace)
        if p is not None and p.is_file():
            return True
        base = Path(name).name
        return any(Path(f).name == base for f in self._snapshot())

    def finish(self) -> dict:
        """Copy the workspace to runs/<id>/artifacts/files/ (skills/ left out), close the server, and report."""
        self._scan()
        if self.server is not None:
            self.server.close()
        dest = self.run_dir / "artifacts" / "files"
        for rel in self._snapshot():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.workspace / rel, dest / rel)
        shutil.rmtree(self.home, ignore_errors=True)
        now = self._snapshot()
        files = [{**v, "size": now.get(p, (v["size"],))[0]} for p, v in sorted(self.files.items()) if p in now]
        return {"files_created": files, "local_tool_calls": self.calls, "local_refusals": dict(self.refusals),
                "skills_attached": self.skills_attached}
