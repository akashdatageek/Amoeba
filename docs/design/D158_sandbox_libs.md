# D158 — the sandbox holds what the checks need

Status: **built** (branch claude/gemma-preflight, Oct 21). D156's first live preflight found the gaps this fixes.

## Why
The eight test categories need code to import scipy (exact answers), pytest (software), Pillow (drone images), and
LibreOffice to recalculate a spreadsheet and convert documents (files). D156's preflight found the image had no
scipy, no pytest and no LibreOffice. In-process mode had its own gaps: pandas, scipy and LibreOffice Writer were
missing on the host. Two separate lists drift apart, so there should be one list.

The same preflight found that `local:Glob` and `local:Grep` were never offered. Claude Code's `mcp serve` no longer
lists Glob or Grep, so a helper asking for them was refused as not_allowed, even though localtools.yaml allows them.

## What
1. **One library list**, `amoeba/config/sandbox/libs.txt`: numpy, pandas, scipy, matplotlib, pillow, openpyxl,
   python-docx, python-pptx, pypdf, pytest. Each line says which category needs it.
   - The Dockerfile copies it in and runs `pip install -r` on it.
   - In-process mode installs the same file: `pip install -r amoeba/config/sandbox/libs.txt`, which
     `scripts/setup_office.sh` now also runs.
   - The preflight's `LIBS` (D156) is the import side of the same list; a test checks the two agree.
2. **LibreOffice Calc and Writer** in the image (`apt-get install --no-install-recommends`), and in
   `scripts/setup_office.sh` for in-process mode. Calc recalculates formulas (D71); Writer converts docx to pdf.
3. **Glob and Grep through Bash.** When the server offers Bash but not Glob or Grep, the toolbox still exposes them
   (`LocalToolbox.served_by_bash`). It serves each call as one Bash call that plain code writes:
   - Glob: Python's `glob(pattern, recursive=True)`;
   - Grep: `grep -rInI`;
   - in both, every argument is shell-quoted, so the pattern is data and never runs as a command.
   - All the gates still apply first: the path must be in the workspace (or a read-only skill root), and the per-step
     and per-run caps count these calls too.
   - The trace records the call under the tool's own name (`local:Glob`, `local:Grep`).
4. **Build robustness.**
   - The base images can come from a Docker Hub mirror: `BASE_REGISTRY=mirror.gcr.io/library build.sh`. Docker Hub
     returned 429 here.
   - apt uses the build CA secret when one is given, as npm and pip already did.

## As built (Oct 21)
- `amoeba/config/sandbox/libs.txt` (new), `Dockerfile`, `build.sh`, `scripts/setup_office.sh`.
- `amoeba/localtools/toolbox.py`: `BY_BASH`, `GLOB_PY`, `LocalToolbox.served_by_bash` and `LocalToolbox.served()`.
- The image was rebuilt. The preflight imports, soffice, office_check and all six local tools pass in **both** modes
  (tables in the PR).

**Existing tests that changed: two, in `tests/test_localtools.py`.** They asserted that the exposed tools were only
Bash, Read, Write and Edit, with the fake server lacking Glob and Grep. They now expect all six, with Glob and Grep
served through Bash.

## Tests
`tests/test_sandbox_libs_d158.py`:
- every library preflight imports is in libs.txt, and the Dockerfile and setup_office.sh install it plus Calc and
  Writer;
- the list sits in the build context;
- Glob and Grep are served through the fake server's Bash, and both find the right files and lines;
- the gates still hold: a path outside the workspace is refused, and shell text in a pattern never runs.
