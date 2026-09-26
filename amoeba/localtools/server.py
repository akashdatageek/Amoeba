"""D59 — one `claude mcp serve` process per run, over stdio, with the official MCP Python SDK.

The server is started once (listing its tools) and kept open for the whole run: the SDK's stdio transport lives on
an event loop in a background thread, and each tool call is sent to that loop and waited for with a time limit.
`close()` ends the session and the process. Nothing here decides what may be called: that is `toolbox.py`.
"""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path


# box: localtools
class LocalServerError(RuntimeError):
    pass


# box: localtools
class StdioServer:
    """A long-lived MCP client session to a stdio server (`command`, started in `cwd` with exactly `env`)."""

    def __init__(self, command: list[str], cwd: str | Path, env: dict[str, str], errlog: str | Path | None = None,
                 start_timeout_s: float = 60.0):
        self.command, self.cwd, self.env = list(command), str(cwd), dict(env)
        self.errlog_path = errlog
        self.start_timeout_s = start_timeout_s
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.session = None
        self.info: dict = {}
        self._stop: asyncio.Event | None = None
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._held = None

    def start(self) -> list[dict]:
        """Start the process, initialise, list the tools: [{name, description, input_schema}]."""
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, name="amoeba-localtools", daemon=True)
        self.thread.start()
        self._held = asyncio.run_coroutine_threadsafe(self._hold(), self.loop)
        if not self._ready.wait(self.start_timeout_s):
            self.close()
            raise LocalServerError(f"{' '.join(self.command)} did not start within {self.start_timeout_s:.0f}s")
        if self._error is not None:
            err = self._error
            self.close()
            raise LocalServerError(f"{' '.join(self.command)} failed to start: {type(err).__name__}: {err}"[:300])
        return self._run(self._listing(), self.start_timeout_s)

    async def _hold(self) -> None:
        """Enter the transport and the session, signal ready, and stay inside them until close()."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        self._stop = asyncio.Event()
        errlog = open(self.errlog_path, "a", encoding="utf-8") if self.errlog_path else None
        try:
            params = StdioServerParameters(command=self.command[0], args=self.command[1:], env=self.env, cwd=self.cwd)
            kw = {"errlog": errlog} if errlog else {}
            async with stdio_client(params, **kw) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    server = getattr(init, "server_info", None) or getattr(init, "serverInfo", None)
                    self.info = {"name": getattr(server, "name", ""), "version": getattr(server, "version", "")}
                    self.session = session
                    self._ready.set()
                    await self._stop.wait()
        except BaseException as e:            # a failed start is reported by start(); a failed close is ignored
            if not self._ready.is_set():
                self._error = e
                self._ready.set()
        finally:
            self.session = None
            if errlog:
                errlog.close()

    async def _listing(self) -> list[dict]:
        out, cursor = [], None
        for _ in range(20):
            page = await (self.session.list_tools(cursor=cursor) if cursor else self.session.list_tools())
            out += [{"name": t.name, "description": t.description or "",
                     "input_schema": getattr(t, "input_schema", None) or getattr(t, "inputSchema", None) or {}}
                    for t in page.tools]
            cursor = getattr(page, "next_cursor", None) or getattr(page, "nextCursor", None)
            if not cursor:
                break
        return out

    def _run(self, coro, timeout_s: float):
        if self.loop is None or self.session is None:
            coro.close()
            raise LocalServerError("the local tool server is not running")
        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        try:
            return fut.result(timeout_s)
        except TimeoutError:
            fut.cancel()
            raise

    def call(self, tool: str, arguments: dict, timeout_s: float) -> tuple[str, bool]:
        """(text, is_error). Raises TimeoutError when no answer came within timeout_s."""
        async def go():
            r = await self.session.call_tool(tool, arguments)
            parts = [b.text if getattr(b, "type", "") == "text" else f"[{getattr(b, 'type', 'other')} content omitted]"
                     for b in (r.content or [])]
            structured = getattr(r, "structured_content", None) or getattr(r, "structuredContent", None)
            if not any(p.strip() for p in parts) and structured is not None:
                parts = [json.dumps(structured, ensure_ascii=False)]
            return "\n".join(parts), bool(getattr(r, "is_error", None) or getattr(r, "isError", None))
        return self._run(go(), timeout_s)

    def close(self) -> None:
        if self.loop is None:
            return
        if self._stop is not None:
            self.loop.call_soon_threadsafe(self._stop.set)
        try:                                   # the session and the transport close, the process ends
            self._held.result(15)
        except Exception:
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread is not None:
            self.thread.join(10)
        self.loop = None
