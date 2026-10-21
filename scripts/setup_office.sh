#!/usr/bin/env bash
# D71: LibreOffice Calc (D158: and Writer) for the sandbox, so spreadsheet formulas can be recalculated headless (the xlsx skill's
# scripts/recalc.py, amoeba/localtools/office.py). libreoffice-core alone cannot load any file.
# Run once per machine or container, before runs with --local-tools on:  sudo scripts/setup_office.sh
set -euo pipefail
apt-get update -qq
apt-get install -y --no-install-recommends libreoffice-calc libreoffice-writer
# D158: in-process mode imports the same libraries as the sandbox image
python3 -m pip install -r "$(dirname "$0")/../amoeba/config/sandbox/libs.txt"   # amoeba/config/sandbox/libs.txt
python3 - <<'PY'
from amoeba.localtools.office import office_check
print("office_check:", office_check())
PY
