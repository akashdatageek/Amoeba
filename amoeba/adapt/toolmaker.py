"""D125 — the tool writer and the tool library (user decision, Oct 12).

When a stuck step lacks a tool and the pool had nothing to attach, Box 4 may have a model write one. LLM proposes,
plain code disposes:

  feasible     plain code first: the missing capability must name a file type or job that a library the sandbox
               already has can do offline (adapt.yaml `tool_writer.libraries`, e.g. docx → python-docx), and the run
               must have a code runner (the local toolbox's sandboxed Bash, --local-tools on). Anything else (an API,
               a login, live data) is not written; the next rung (the fix proposer) takes over.
  write        the tool writer (a model call, agent name "tool_writer") replies with a name, a one-line description,
               its input and a ```python block that defines run(args) -> str and self_test().
  check        plain code parses the code (ast): imports only the allowed library and a short stdlib list, no
               eval/exec/compile/__import__, no subprocess, sockets or os calls, at most `max_code_chars`.
  self-test    plain code appends its own command-line harness, puts the file in the run's workspace (made_tools/,
               never counted as a file the team made) and runs its self-test there (`cd made_tools && python3 <name>.py
               --self-test`) through
               the local toolbox: the same gate, sandbox, limits and trace as the helpers' own code. The tool is
               given to the step only when the self-test prints SELF-TEST OK.
  use          the step's helpers get `made:<name>`; a call runs the tool in the sandbox with the helper's input.

The library (`tool_writer.library`, default data/tool_library/, git-ignored like the pool): a tool whose self-test
passed and that the step then used without an error, in a step that is no longer stuck, is saved there with a
manifest (capability, file type, libraries, sha256, task, run, step) as "unreviewed". Nothing unreviewed is ever
offered again. `python -m scripts.tool_library list|show|approve|reject` is the user's review; an approved tool is
tried before any new tool is written (by capability name, then file type), only if its sha256 still matches, and its
self-test runs again in the sandbox before the step gets it. This is the one thing that carries over between tasks
(a deliberate, user-approved exception to D117).
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from amoeba.adapt.config import adapt_config

TOOLS_DIR = "made_tools"            # the workspace folder of written tools (left out of the files a step made)
PREFIX = "made:"
OK_LINE = "SELF-TEST OK"
NAME = re.compile(r"^[a-z][a-z0-9_]{2,40}$")
DEFAULTS = {
    "enabled": True,
    "max_code_chars": 8000,
    "attempts": 2,
    "library": "data/tool_library",
    "libraries": {"docx": ["docx"], "xlsx": ["openpyxl"], "pptx": ["pptx"], "pdf": ["pypdf", "matplotlib"],
                  "png": ["matplotlib"], "svg": ["matplotlib"], "csv": [], "json": []},
    "aliases": {"word": "docx", "document": "docx", "excel": "xlsx", "spreadsheet": "xlsx", "workbook": "xlsx",
                "powerpoint": "pptx", "slides": "pptx", "deck": "pptx", "chart": "png", "plot": "png",
                "graph": "png"},
    "stdlib": ["json", "csv", "re", "math", "statistics", "datetime", "decimal", "fractions", "collections",
               "itertools", "functools", "textwrap", "string", "io", "pathlib", "typing", "dataclasses", "base64",
               "html", "unicodedata", "sys"],
}
BANNED_CALLS = {"eval", "exec", "compile", "__import__", "globals", "locals", "vars", "breakpoint", "input"}
BANNED_ATTRS = {"system", "popen", "spawn", "fork", "execv", "execve", "remove", "rmtree", "unlink", "rmdir",
                "chmod", "chown", "kill", "connect", "urlopen"}
HARNESS = '''

# ---- added by plain code (D125): the command-line harness; not written by the model ----
if __name__ == "__main__":
    import json as _json, sys as _sys
    if _sys.argv[1:2] == ["--self-test"]:
        self_test()
        print("SELF-TEST OK")
    else:
        _raw = _sys.argv[2] if _sys.argv[1:2] == ["--args-hex"] and len(_sys.argv) > 2 else ""
        _args = _json.loads(bytes.fromhex(_raw).decode("utf-8")) if _raw else {}
        print(run(_args))
'''


# box: toolmaker
def tw_config(config: dict | None = None) -> dict:
    """adapt.yaml `tool_writer`, with defaults for what is not set."""
    return {**DEFAULTS, **((config or adapt_config()).get("tool_writer") or {})}


# box: toolmaker
def runner_ready(local) -> bool:
    """A code runner for written tools: the local toolbox is up and offers Bash (its sandboxed workspace)."""
    return local is not None and getattr(local, "server", None) is not None and "Bash" in getattr(local, "exposed", [])


# box: toolmaker
def file_kind(capability: str, cfg: dict) -> str | None:
    """The file type or job a capability names, by its words: docx_generator → docx, excel_writer → xlsx."""
    words = re.findall(r"[a-z0-9]+", (capability or "").lower().replace("_", " "))
    kinds = cfg["libraries"]
    return next((w for w in words if w in kinds), None) or \
        next((cfg["aliases"][w] for w in words if w in cfg["aliases"] and cfg["aliases"][w] in kinds), None)


# box: toolmaker
def feasible(items: list[str], local, cfg: dict | None = None) -> dict:
    """Plain code's feasibility check for writing a tool: {ok, capability, kind, libraries, why}."""
    cfg = cfg or tw_config()
    if not cfg.get("enabled", True):
        return {"ok": False, "why": "tool writer: off in adapt.yaml"}
    if not runner_ready(local):
        return {"ok": False, "why": "tool writer: no code runner (local tools are off)"}
    for cap in items or []:
        kind = file_kind(cap, cfg)
        if kind is not None:
            return {"ok": True, "capability": cap, "kind": kind, "libraries": list(cfg["libraries"][kind])}
    return {"ok": False, "why": f"tool writer: no offline library for {', '.join(items or []) or 'the capability'}"}


# box: toolmaker
def parse_tool(text: str) -> dict:
    """The tool writer's reply: the last JSON object holding "name" (name, description, input) and the last
    ```python block (the code). ValueError naming what is missing."""
    s, dec, objs, i = text or "", json.JSONDecoder(), [], (text or "").find("{")
    while i != -1:
        try:
            obj, end = dec.raw_decode(s, i)
        except ValueError:
            i = s.find("{", i + 1)
            continue
        if isinstance(obj, dict):
            objs.append(obj)
        i = s.find("{", end)
    head = next((o for o in reversed(objs) if "name" in o), None)
    blocks = re.findall(r"```python[ \t]*\n(.*?)```", s, re.S)
    missing = [x for x, ok in (("a JSON object with name, description, input", head), ("a ```python block", blocks))
               if not ok]
    if missing:
        raise ValueError("the reply has no " + " and no ".join(missing))
    return {"name": str(head.get("name", "")).strip(), "description": str(head.get("description", "")).strip()[:300],
            "input": str(head.get("input", "")).strip()[:300], "code": blocks[-1].rstrip() + "\n"}


# box: toolmaker
def check_code(tool: dict, libraries: list[str], cfg: dict | None = None) -> list[str]:
    """Plain code's checks on a written tool, before anything runs: the problems (empty: it may run)."""
    cfg = cfg or tw_config()
    out, src = [], tool.get("code") or ""
    if not NAME.match(tool.get("name") or ""):
        out.append("name must be 3-41 characters: lower-case letters, digits, underscores, starting with a letter")
    if len(src) > int(cfg["max_code_chars"]):
        out.append(f"the code is {len(src)} characters; at most {cfg['max_code_chars']}")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return out + [f"the code does not parse: {e.msg} (line {e.lineno})"]
    allowed = set(libraries) | set(cfg["stdlib"])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [(node.module or "").split(".")[0]] if node.level == 0 else ["(relative import)"]
        else:
            mods = []
        out += [f"import {m} is not allowed (allowed: {', '.join(sorted(allowed))})" for m in mods if m not in allowed]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
            out.append(f"{node.func.id}() is not allowed")
        if isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRS:
            out.append(f".{node.attr} is not allowed")
    defs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    out += [f"the code must define {f}" for f in ("run(args)", "self_test()") if f.split("(")[0] not in defs]
    if "__main__" in src:
        out.append("leave out the if __name__ == \"__main__\" block; plain code adds its own")
    return list(dict.fromkeys(out))


# box: toolmaker
def tool_text(tool: dict) -> str:
    """The file plain code runs: a header line, the model's code and plain code's harness."""
    return (f"# made by the Amoeba tool writer (D125): {tool['name']} — {tool.get('description', '')[:200]}\n"
            + tool["code"] + HARNESS)


# box: toolmaker
def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# box: toolmaker
def install(local, tool: dict, text: str | None = None) -> str:
    """Put the tool's file in the run's workspace (and its sandbox); returns its workspace path."""
    rel = f"{TOOLS_DIR}/{tool['name']}.py"
    local.put_file(rel, (text or tool_text(tool)).encode("utf-8"))
    return rel


# box: toolmaker
def self_test(local, rel: str) -> tuple[bool, str]:
    """Run the tool's self-test through the local toolbox (gate, sandbox, limits, trace). (passed, output)."""
    folder, file = rel.rsplit("/", 1)                 # in made_tools/: its example files are not files the team made
    out = local.call("Bash", json.dumps({"command": f"cd {folder} && python3 {file} --self-test"}))
    ok = OK_LINE in out and not out.startswith(("[local:Bash error]", "refused", "error"))
    return ok, out


# box: toolmaker
def call_tool(local, rel: str, text: str) -> str:
    """A helper's call of a made tool: its ActionInput as JSON args (plain text becomes {"text": ...})."""
    raw = (text or "").strip()
    try:
        args = json.loads(raw) if raw.startswith("{") else {"text": raw}
    except ValueError:
        args = {"text": raw}
    if not isinstance(args, dict):
        args = {"text": raw}
    hexed = json.dumps(args, ensure_ascii=False).encode("utf-8").hex()   # hex: no '/' or word the gate refuses
    return local.call("Bash", json.dumps({"command": f"python3 {rel} --args-hex {hexed}"}))


# box: toolmaker
def library_root(cfg: dict | None = None) -> Path:
    root = Path((cfg or tw_config())["library"])
    return root if root.is_absolute() else Path(__file__).resolve().parents[2] / root


# box: toolmaker
class ToolLibrary:
    """data/tool_library/<name>/{tool.py, manifest.json}. Tools are saved "unreviewed"; only "approved" ones (the
    user's decision, scripts/tool_library.py) are ever offered, and only while tool.py still matches its sha256."""

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root is not None else library_root()

    def manifests(self) -> list[dict]:
        if not self.root.is_dir():
            return []
        out = []
        for m in sorted(self.root.glob("*/manifest.json")):
            try:
                out.append(json.loads(m.read_text(encoding="utf-8")))
            except ValueError:
                continue
        return out

    def get(self, name: str) -> dict | None:
        p = self.root / name / "manifest.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None

    def text(self, name: str) -> str:
        return (self.root / name / "tool.py").read_text(encoding="utf-8")

    def intact(self, m: dict) -> bool:
        p = self.root / m["name"] / "tool.py"
        return p.is_file() and sha(p.read_text(encoding="utf-8")) == m.get("sha256")

    def find(self, capability: str, kind: str | None) -> dict | None:
        """An approved, unchanged tool for this capability (same name first, then the same file type)."""
        ok = [m for m in self.manifests() if m.get("status") == "approved" and self.intact(m)]
        cap = (capability or "").lower()
        return next((m for m in ok if m.get("capability", "").lower() == cap), None) or \
            next((m for m in ok if kind and m.get("kind") == kind), None)

    def save(self, tool: dict, text: str, meta: dict) -> dict:
        """Save a tool that worked, as unreviewed. An existing name gets a numbered folder; nothing is overwritten."""
        name, k = tool["name"], 2
        while (self.root / name).exists():
            name, k = f"{tool['name']}_{k}", k + 1
        d = self.root / name
        d.mkdir(parents=True)
        (d / "tool.py").write_text(text, encoding="utf-8")
        m = {"name": name, "tool_name": tool["name"], "description": tool.get("description", ""),
             "input": tool.get("input", ""), "sha256": sha(text), "status": "unreviewed",
             "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **meta}
        (d / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return m

    def set_status(self, name: str, status: str) -> dict:
        m = self.get(name)
        if m is None:
            raise KeyError(f"no tool {name!r} in {self.root}")
        m["status"] = status
        m[f"{status}_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if status == "approved":
            m["sha256"] = sha(self.text(name))            # what the user reviewed is what may run
        (self.root / name / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n",
                                                        encoding="utf-8")
        return m
