"""D71 — the office suite in the sandbox: LibreOffice headless, so spreadsheet formulas get computed values.

The xlsx skill's scripts/recalc.py (and any helper) recalculates a workbook through `soffice --headless`. That needs
LibreOffice Calc, not only libreoffice-core (with core alone every file fails with "source file could not be
loaded"): `scripts/setup_office.sh` installs it. Each run gives soffice a fresh profile folder and HOME so a stale or
shared profile cannot block it. `office_check()` proves it works on a two-cell workbook; the local toolbox runs it
once at start and logs the outcome (trace `office_check`).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


# box: localtools
def recalc(path: str | Path, timeout_s: int = 90) -> dict:
    """Open `path` in LibreOffice headless and save it again as .xlsx, so every formula cell holds its value.
    Returns {ok, detail}; the file is replaced only on success."""
    exe = soffice()
    if exe is None:
        return {"ok": False, "detail": "LibreOffice (soffice) is not installed"}
    path = Path(path).resolve()
    with tempfile.TemporaryDirectory(prefix="amoeba-office-") as tmp:
        home, out = Path(tmp) / "home", Path(tmp) / "out"
        home.mkdir()
        env = {**os.environ, "HOME": str(home)}
        cmd = [exe, "--headless", "--norestore", "--nologo", f"-env:UserInstallation=file://{Path(tmp) / 'profile'}",
               "--convert-to", "xlsx", "--outdir", str(out), str(path)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, env=env)
        except subprocess.TimeoutExpired:
            return {"ok": False, "detail": f"soffice timed out after {timeout_s} s"}
        made = out / (path.stem + ".xlsx")
        if p.returncode != 0 or not made.exists():
            return {"ok": False, "detail": (p.stderr or p.stdout or "no output").strip().splitlines()[-1][:200]}
        shutil.move(str(made), str(path))
    return {"ok": True, "detail": "recalculated"}


# box: localtools
def office_check() -> dict:
    """A two-cell workbook (2 and 3, and =A1*A2) must come back from LibreOffice with the value 6."""
    import openpyxl
    with tempfile.TemporaryDirectory(prefix="amoeba-office-check-") as tmp:
        f = Path(tmp) / "check.xlsx"
        wb = openpyxl.Workbook()
        wb.active["A1"], wb.active["A2"], wb.active["A3"] = 2, 3, "=A1*A2"
        wb.save(f)
        r = recalc(f, timeout_s=60)
        if not r["ok"]:
            return r
        value = openpyxl.load_workbook(f, data_only=True).active["A3"].value
        return {"ok": value == 6, "detail": f"=A1*A2 gave {value!r}"}
