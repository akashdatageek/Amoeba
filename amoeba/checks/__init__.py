"""D102 — domain checks: a small plug-in interface. Each module amoeba/checks/<name>.py defines

    check(output: str, evidence: dict) -> tuple[bool, str]

a pure function over one step's output and its evidence (task text, the step's inputs, the run's calc and local-tool
results so far, whether it is the answer step) returning pass/fail and a reason. A niche profile names the checks to
run (profiles/<niche>.yaml `checks:`); the plan runner runs them after each step next to its own step checks, and a
failed one earns the same retry turn as a failed format check.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

CHECKS = sorted(m.name for m in pkgutil.iter_modules([str(Path(__file__).parent)]) if not m.name.startswith("_"))


# box: niche
def run_checks(names, output: str, evidence: dict) -> list[dict]:
    """The named domain checks as step-check rows {name, pass, detail, source: "domain"}."""
    out = []
    for name in names or ():
        ok, reason = importlib.import_module(f"amoeba.checks.{name}").check(output, evidence)
        out.append({"name": f"domain_{name}", "pass": bool(ok), "detail": reason, "source": "domain"})
    return out
