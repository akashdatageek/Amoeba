"""Tool registry with `echo` and `calc`. Dispatch by name (AutoAgents routes every drafted tool to SerpAPI — D7)."""
from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from typing import Callable


class ToolError(RuntimeError):
    pass


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable[[str], str]


# box: tools
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, description: str, fn: Callable[[str], str]) -> None:
        self._tools[name] = Tool(name, description, fn)

    def names(self) -> list[str]:
        return list(self._tools)

    def descriptions(self) -> dict[str, str]:
        return {t.name: t.description for t in self._tools.values()}

    def copy(self) -> "ToolRegistry":
        """A run's own registry: the same tools (and web tools) plus whatever this run adds (D56 pool tools)."""
        new = ToolRegistry()
        new._tools = dict(self._tools)
        if hasattr(self, "web"):
            new.web = self.web
        return new

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def execute(self, name: str, action_input: str, agent=None) -> str:
        """The single tool call site (Phase 4's PreToolUse hook lands here)."""
        if name not in self._tools:
            raise ToolError(f"unknown tool {name!r}")
        return self._tools[name].fn(action_input)


def echo(text: str) -> str:
    return text


_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UN = {ast.USub: operator.neg, ast.UAdd: operator.pos}


# box: tools
def calc(expr: str) -> str:
    """Arithmetic on numbers only (+ - * / // % ** and parentheses); anything else is an error string."""
    src = expr.strip().strip("`").strip()

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 1000:
                raise ToolError("exponent too large")
            return _BIN[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UN:
            return _UN[type(n.op)](ev(n.operand))
        raise ToolError(f"unsupported expression: {ast.dump(n)[:40]}")

    try:
        value = ev(ast.parse(src, mode="eval"))
    except SyntaxError as e:
        return f"error: {e.msg}"
    except (ToolError, ZeroDivisionError, OverflowError, ValueError) as e:
        return f"error: {e}"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


# box: tools
def default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register("echo", "returns its input unchanged", echo)
    reg.register("calc", "evaluates an arithmetic expression such as 12 * (3 + 4)", calc)
    return reg
