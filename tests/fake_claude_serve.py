"""A stand-in for `claude mcp serve` in tests (D59): an MCP server over stdio with the same tool names and argument
names as Claude Code's Bash, Read, Write and Edit, plus tools Amoeba must refuse (WebFetch, Agent). No Glob or Grep,
like Claude Code 2.1.283's server. Offline; the Bash tool runs the command for real in the server's working directory.

    python tests/fake_claude_serve.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

server = MCPServer("fake-claude-serve")


@server.tool(name="Bash", description="Executes a given bash command and returns its output.")
def bash(command: str, timeout: float = 120000, description: str = "") -> str:
    try:
        r = subprocess.run(["bash", "-c", command], capture_output=True, text=True, timeout=timeout / 1000)
    except subprocess.TimeoutExpired:
        raise ToolError(f"Command timed out after {int(timeout / 1000)}s")
    return json.dumps({"stdout": r.stdout.rstrip("\n"), "stderr": r.stderr.rstrip("\n"), "interrupted": False})


@server.tool(name="Read", description="Reads a file from the local filesystem.")
def read(file_path: str, offset: int = 0, limit: int = 2000) -> str:
    text = Path(file_path).read_text(encoding="utf-8")
    return json.dumps({"type": "text", "file": {"filePath": file_path, "content": text}})


@server.tool(name="Write", description="Writes a file to the local filesystem.")
def write(file_path: str, content: str) -> str:
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).write_text(content, encoding="utf-8")
    return json.dumps({"type": "create", "filePath": file_path})


@server.tool(name="Edit", description="Performs exact string replacements in files.")
def edit(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    p = Path(file_path)
    text = p.read_text(encoding="utf-8")
    if old_string not in text:
        raise ToolError("String to replace not found in file.")
    p.write_text(text.replace(old_string, new_string, -1 if replace_all else 1), encoding="utf-8")
    return json.dumps({"filePath": file_path})


@server.tool(name="WebFetch", description="Fetches a URL.")
def web_fetch(url: str, prompt: str = "") -> str:
    return "should never be called"


@server.tool(name="Agent", description="Launches a sub-agent.")
def agent(prompt: str) -> str:
    return "should never be called"


if __name__ == "__main__":
    server.run()
