"""D157 — input files given with a task. run_task copies each one into the run's workspace under inputs/,
read-only (like the fetched sources/ of D107), before any model call; Box 1 and Box 2 are shown the list with sizes,
and so is every helper on its role card. A file that is not there stops the run before anything is spent."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

FOLDER = "inputs"


# box: interpret
def copy_inputs(paths: list[str], workspace: str | Path) -> list[dict]:
    """[{path: "inputs/<name>", size}] in the order given; the copies are read-only. Two files with one name keep
    both (the second gets a numbered name)."""
    missing = [p for p in paths if not Path(p).is_file()]
    if missing:
        raise FileNotFoundError(f"input file(s) not found: {', '.join(missing)}")
    dest = Path(workspace) / FOLDER
    dest.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in paths:
        src = Path(p)
        name = re.sub(r"[^\w.-]+", "_", src.name).strip("._")[:120] or "input"
        stem, suffix, k = Path(name).stem, Path(name).suffix, 2
        while (dest / name).exists():
            name, k = f"{stem}_{k}{suffix}", k + 1
        shutil.copyfile(src, dest / name)
        (dest / name).chmod(0o444)
        rows.append({"path": f"{FOLDER}/{name}", "size": (dest / name).stat().st_size})
    return rows


# box: interpret
def inputs_text(rows: list[dict]) -> str:
    """The block Box 1, Box 2 and every helper see; "" with no files (prompts unchanged)."""
    if not rows:
        return ""
    lines = "\n".join(f"- {r['path']} ({r['size']} bytes)" for r in rows)
    return ("\n\nInput files given with the task (read-only, in the workspace; read them with local:Read or code, "
            f"never write to them):\n{lines}\nA step that needs one of these files names it.")
