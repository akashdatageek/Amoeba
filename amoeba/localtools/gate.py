"""D59 — the plain-code gate in front of every local tool call. It never asks a model.

- The whole feature needs AMOEBA_SANDBOX=1: the operator says this machine is a disposable sandbox.
- File paths (Read, Write, Edit, and Glob/Grep's search path) must resolve inside the run's workspace, symlinks
  followed: otherwise "outside_workspace".
- A Bash command runs from the workspace. Network commands are refused ("network_command"); destructive commands
  and ways out of the workspace are refused ("unsafe_command").

The Bash rules are a screen, not a jail: they catch the plain cases a helper writes. What contains a determined
command is the sandbox the operator vouched for (AMOEBA_SANDBOX=1), the minimal environment the server runs with
(no keys, no proxy settings), and the per-call limits in toolbox.py.
"""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path


# box: localtools
class SandboxRequired(RuntimeError):
    pass


# box: localtools
def require_sandbox(env=None) -> None:
    """--local-tools on runs only where AMOEBA_SANDBOX=1 is set."""
    if (env if env is not None else os.environ).get("AMOEBA_SANDBOX") != "1":
        raise SandboxRequired("--local-tools on needs AMOEBA_SANDBOX=1 (run inside a disposable sandbox): "
                              "local tools run shell commands and write files")


# box: localtools
def inside(path: str, workspace: Path) -> Path | None:
    """The absolute path when `path` (relative paths count from the workspace) resolves inside the workspace."""
    if not isinstance(path, str) or not path.strip() or "\x00" in path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = workspace / p
    real, ws = p.resolve(), workspace.resolve()
    return real if real == ws or ws in real.parents else None


NETWORK = re.compile(
    r"(?<![\w.-])(curl|wget|ssh|scp|sftp|rsync|nc|ncat|netcat|telnet|ftp|socat)(?![\w.-])"
    r"|\bgit\s+(clone|push|fetch|pull|remote\s+add|submodule)\b"
    r"|\b(pip3?|uv\s+pip|python3?\s+-m\s+pip)\s+install\b"
    r"|\b(npm|pnpm)\s+(install|i|add|ci)\b|\byarn\s+add\b|\b(apt|apt-get|brew|conda)\s+install\b"
    r"|\b(import|from)\s+(socket|requests|urllib|urllib3|http\.client|httpx|aiohttp|ftplib|smtplib|paramiko)\b"
    r"|\burlopen\s*\(|/dev/tcp/", re.I)

UNSAFE = re.compile(
    r"\bsudo\b|(?<![\w-])su\s+-?\w*\s*$|\bchroot\b|\bmount\b|\bdocker\b|\bnsenter\b"
    r"|\brm\s+(-\w+\s+)*(/|~|\*|\.\.?)(\s|/|$)"
    r"|\bmkfs\b|\bdd\s+if=|:\(\)\s*\{|\b(shutdown|reboot|halt|poweroff)\b|\bkill(all)?\b|\bpkill\b"
    r"|\bchmod\s+(-\w+\s+)*[0-7]*\s*/|\bchown\b|\bcrontab\b|\bsystemctl\b"
    r"|(^|[\s;&|(])cd\s+(/|~|-(\s|$)|\$)|\.\./|(^|[\s'\"=(])\.\.(\s|$|['\"])|~/|\$HOME\b|\$\{HOME\}"
    r"|\bln\s+(-\w+\s+)*-?s\b|\beval\b|\bexec\s+\d*[<>]", re.I)

ABS_PATH = re.compile(r"(?:^|(?<=[\s'\"=(<>:,]))(/[A-Za-z0-9_.][^\s'\";|&)<>,]*)")
ALLOWED_ABS = ("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/stdin")


# box: localtools
def screen_command(command: str, workspace: Path) -> tuple[str, str] | None:
    """(reason, what matched) for a Bash command that must not run, or None."""
    if not isinstance(command, str) or not command.strip():
        return "unsafe_command", "empty command"
    m = NETWORK.search(command)
    if m:
        return "network_command", m.group(0).strip()
    m = UNSAFE.search(command)
    if m:
        return "unsafe_command", m.group(0).strip()
    ws = str(workspace.resolve())
    for p in ABS_PATH.findall(command):
        if p in ALLOWED_ABS or p == ws or p.startswith(ws + "/"):
            continue
        if inside(p, workspace) is None:
            return "unsafe_command", f"path outside the workspace: {p[:80]}"
    return None


# box: localtools
def in_workspace(command: str, workspace: Path) -> str:
    """The command as it is sent: always started from the workspace (the server's shell keeps its last cwd)."""
    return f"cd {shlex.quote(str(workspace.resolve()))} && {command}"
