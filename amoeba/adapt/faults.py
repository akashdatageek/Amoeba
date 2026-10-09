"""D119 — fault injection (test-only): one known fault at one point of the plan runner, so the stuck watch's
diagnosis and the fixes can be checked against a ground truth.

    --inject-fault <cause>:<step>[:<n>]     (repeatable, hidden from --help; <step> is a number or "auto")

run_task refuses the flag unless AMOEBA_TEST_FAULTS=1 is set in the environment; nothing else sets it. With no flag
nothing here runs and every run is as before. Each fault fires the same way with --adapt off and on, so a pair of
runs differs only in whether something tries to fix it.

  tool_error       the step's first n tool calls (default 3) return "error: <tool> failed: injected fault"
                   instead of running; later calls run normally
  capability       one tool the step's helpers hold is taken from them and listed as missing while the step runs; the
                   run's registry keeps it, so a grant (D117 rung 2) gives it back and ends the fault
  missing_input    the step sees its first input (an upstream step's output) cut to n characters (default 200) until
                   a fix passes that input in full (add_dependency or rerun_upstream)
  missing_input_b  the upstream output itself is saved cut to n characters (default 200) the first time that step runs;
                   a re-run of the upstream step saves it whole
  max_turns        the step gets n turns (default 2) and no forced last turn until a fix sets its turns
  checks           plain code adds one check to the step: a markdown table with a Source column; the helpers are
                   not told until the check fails (the retry turn shows it)

"auto" picks the step by code from the plan: the first step that is neither the summary nor a verification step
and that holds a tool (tool_error, capability), has an input (missing_input, missing_input_b), or any (max_turns,
checks). Every arming, firing and clearing is a trace event; result.json records `faults`.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

ENV = "AMOEBA_TEST_FAULTS"
DEFAULT_N = {"tool_error": 3, "capability": 0, "missing_input": 200, "missing_input_b": 200, "max_turns": 2,
             "checks": 0}
CAUSES = tuple(DEFAULT_N)
# what a correct watch and the cheapest right fix would be, for the report's confusion and recovery tables
EXPECTED = {"tool_error": ("tool_error", "set_run_option:max_turns"), "capability": ("capability", "grant_tool"),
            "missing_input": ("missing_input", "add_dependency"),
            "missing_input_b": ("missing_input", "rerun_upstream"),
            "max_turns": ("max_turns", "set_run_option:max_turns"),
            "checks": ("checks", "set_run_option:check_retry_turns")}
INJECTED_ERROR = "error: {tool} failed: injected fault"
NOT_TOOLS = {"Final Output", "print"}
CHECK_NAME = "table_sources"
CHECK_DETAIL = "there is no markdown table with a Source column for the figures (| ... | Source | with a |---| row)"


# box: faults
@dataclass
class Fault:
    cause: str
    step: int | None                     # None: "auto", resolved when the run starts
    n: int
    target: dict = field(default_factory=dict)    # the tool or upstream step it acts on
    fired: int = 0
    cleared: str = ""

    def record(self) -> dict:
        return {"cause": self.cause, "step": self.step, "n": self.n, **self.target, "fired": self.fired,
                "cleared": self.cleared or None, "expected": dict(zip(("diagnosis", "first_fix"),
                                                                      EXPECTED[self.cause]))}


# box: faults
def parse_fault(spec: str) -> Fault:
    """`<cause>:<step>[:<n>]` → Fault; ValueError on anything else."""
    parts = (spec or "").strip().split(":")
    if len(parts) not in (2, 3) or parts[0] not in DEFAULT_N:
        raise ValueError(f"--inject-fault {spec!r}: expected <cause>:<step>[:<n>] with cause one of "
                         f"{', '.join(CAUSES)}")
    if parts[1] != "auto" and not parts[1].isdigit():
        raise ValueError(f"--inject-fault {spec!r}: the step is a number or 'auto'")
    if len(parts) == 3 and not parts[2].isdigit():
        raise ValueError(f"--inject-fault {spec!r}: n is a whole number")
    return Fault(parts[0], None if parts[1] == "auto" else int(parts[1]),
                 int(parts[2]) if len(parts) == 3 else DEFAULT_N[parts[0]])


# box: faults
def allowed(env: dict | None = None) -> bool:
    return (os.environ if env is None else env).get(ENV) == "1"


# box: faults
def check_flag(specs: list[str] | None, topology: str, env: dict | None = None) -> tuple[str, ...]:
    """The validated specs of --inject-fault; SystemExit unless AMOEBA_TEST_FAULTS=1 and the topology is plan."""
    specs = [s for s in specs or [] if s]
    if not specs:
        return ()
    if not allowed(env):
        raise SystemExit(f"--inject-fault is test-only: set {ENV}=1 in the environment to use it")
    if topology != "plan":
        raise SystemExit("--inject-fault needs --topology plan")
    try:
        return tuple(f"{f.cause}:{f.step if f.step is not None else 'auto'}:{f.n}" for f in map(parse_fault, specs))
    except ValueError as e:
        raise SystemExit(str(e))


# box: faults
def pick_step(cause: str, steps: list[dict]) -> int | None:
    """The step "auto" names. `steps`: {"n", "deps", "tools", "summary", "verify"} in plan order."""
    work = [s for s in steps if not s["summary"] and not s["verify"]]
    if cause in ("tool_error", "capability"):
        work = [s for s in work if s["tools"]]
    elif cause in ("missing_input", "missing_input_b"):
        work = [s for s in work if s["deps"]]
    return work[0]["n"] if work else None


# box: faults
def has_source_table(text: str) -> bool:
    rows = [l for l in (text or "").splitlines() if re.match(r"^\s*\|.*\|\s*$", l)]
    return any(re.search(r"\|\s*sources?\s*\|", r, re.I) for r in rows) and \
        bool(re.search(r"^\s*\|?\s*:?-{3,}", text or "", re.M))


# box: faults
class Faults:
    """The run's armed faults and the hooks the plan runner calls (each a no-op without a fault for that step)."""

    def __init__(self, specs: tuple | list = (), trace=None):
        self.faults = [parse_fault(s) for s in specs or ()]
        self.trace = trace
        self.hidden: dict[str, list[str]] = {}       # agent id -> tools taken from it (capability, while running)
        self.saved: set[int] = set()                 # upstream steps already saved once (missing_input_b)

    def __bool__(self) -> bool:
        return bool(self.faults)

    def _event(self, name: str, f: Fault, **extra) -> None:
        if self.trace is not None:
            self.trace.event(name, {"amoeba.box": "faults", "amoeba.fault": f.cause, "amoeba.step": f.step,
                                    **{f"amoeba.{k}": v for k, v in extra.items()}})

    def arm(self, steps: list[dict]) -> None:
        """Resolve "auto" and each fault's target; a fault with no step it can act on stays unarmed (logged)."""
        by_n = {s["n"]: s for s in steps}
        for f in self.faults:
            if f.step is None:
                f.step = pick_step(f.cause, steps)
            s = by_n.get(f.step)
            if s is None:
                f.cleared = "not armed: no step it can act on"
                self._event("fault_unarmed", f, why=f.cleared)
                continue
            if f.cause == "capability":
                if not s["tools"]:
                    f.cleared = f"not armed: step {f.step} holds no tool"
                    self._event("fault_unarmed", f, why=f.cleared)
                    continue
                f.target = {"tool": s["tools"][0]}
            elif f.cause in ("missing_input", "missing_input_b"):
                if not s["deps"]:
                    f.cleared = f"not armed: step {f.step} has no input"
                    self._event("fault_unarmed", f, why=f.cleared)
                    continue
                f.target = {"upstream": s["deps"][0]}
            self._event("fault_armed", f, n=f.n, **f.target)

    def get(self, cause: str, n: int | None) -> Fault | None:
        return next((f for f in self.faults if f.cause == cause and f.step == n and n is not None
                     and not f.cleared), None)

    def summary(self) -> list[dict]:
        return [f.record() for f in self.faults]

    # ---- the hooks --------------------------------------------------------------------------------------------
    def tool_result(self, n: int, tool: str) -> str | None:
        """tool_error: the injected error for one of the step's first n tool calls, else None (run the tool)."""
        f = self.get("tool_error", n)
        if f is None or tool in NOT_TOOLS or f.fired >= f.n:
            return None
        f.fired += 1
        f.target.setdefault("tools", [])
        if tool not in f.target["tools"]:
            f.target["tools"].append(tool)
        self._event("fault_fired", f, tool=tool, call=f.fired)
        return INJECTED_ERROR.format(tool=tool)

    def hide(self, n: int, agents: list) -> None:
        """capability: take the tool from the step's helpers and list it as missing, for this step only."""
        f = self.get("capability", n)
        if f is None:
            return
        t = f.target["tool"]
        for a in agents:
            if t in a.tools and a.agent_id not in self.hidden:
                a.tools.remove(t)
                if t not in a.missing_tools:
                    a.missing_tools.append(t)
                self.hidden[a.agent_id] = [t]
                f.fired += 1
                self._event("fault_fired", f, tool=t, agent=a.name)

    def restore(self, agents: list) -> None:
        """After the step: the helpers get the hidden tool back for their other steps."""
        for a in agents:
            for t in self.hidden.pop(a.agent_id, []):
                if t not in a.tools:
                    a.tools.append(t)
                a.missing_tools = [x for x in a.missing_tools if x != t]

    def granted(self, n: int, got: list[str]) -> None:
        """A grant for step n that gave the hidden tool back ends the capability fault."""
        f = self.get("capability", n)
        if f is not None and f.target["tool"] in got:
            f.cleared = "granted back"
            self._event("fault_cleared", f, how=f.cleared)

    def input_body(self, n: int | None, d: int, body: str, full: bool) -> str:
        """missing_input: the first input cut to n characters until a fix passes it in full."""
        f = self.get("missing_input", n)
        if f is None or f.target.get("upstream") != d:
            return body
        if full:
            f.cleared = "passed in full"
            self._event("fault_cleared", f, how=f.cleared)
            return body
        f.fired += 1
        self._event("fault_fired", f, upstream=d, chars=min(len(body), f.n), of=len(body))
        return body[:f.n]

    def saved_text(self, u: int, text: str) -> str:
        """missing_input_b: the upstream output saved cut the first time that step runs."""
        f = next((x for x in self.faults if x.cause == "missing_input_b" and not x.cleared
                  and x.target.get("upstream") == u), None)
        if f is None:
            return text
        if u in self.saved:
            f.cleared = "upstream re-run"
            self._event("fault_cleared", f, how=f.cleared)
            return text
        self.saved.add(u)
        f.fired += 1
        self._event("fault_fired", f, upstream=u, chars=min(len(text), f.n), of=len(text))
        return text[:f.n]

    def turns(self, n: int, turns: int, fixed: bool) -> tuple[int, bool]:
        """max_turns: (the step's turns, whether its last turn forces a Final Output)."""
        f = self.get("max_turns", n)
        if f is None:
            return turns, True
        if fixed:
            f.cleared = "turns set by a fix"
            self._event("fault_cleared", f, how=f.cleared)
            return turns, True
        f.fired += 1
        self._event("fault_fired", f, turns=f.n)
        return f.n, False

    def extra_checks(self, n: int, text: str) -> list[dict]:
        """checks: one more check plain code runs on the step's output."""
        f = self.get("checks", n)
        if f is None:
            return []
        ok = has_source_table(text)
        if not ok:
            f.fired += 1
            self._event("fault_fired", f, check=CHECK_NAME)
        return [{"name": CHECK_NAME, "pass": ok, "detail": CHECK_DETAIL, "source": "markers"}]
