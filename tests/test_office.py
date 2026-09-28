"""D71 — the office suite: LibreOffice headless computes formula values in the sandbox (after
scripts/setup_office.sh). The live tests are skipped where LibreOffice Calc is not installed (for example CI)."""
import shutil
from pathlib import Path

import openpyxl
import pytest

from amoeba.localtools import office
from amoeba.localtools.office import office_check, recalc

FIXTURE = Path(__file__).parent / "fixtures" / "bench5_shipment.xlsx"
CHECK = office_check()
live = pytest.mark.skipif(not CHECK["ok"], reason=f"LibreOffice Calc not usable here: {CHECK['detail']}")


@live
def test_a_two_cell_workbook_gets_its_value():
    assert CHECK == {"ok": True, "detail": "=A1*A2 gave 6"}


@live
def test_the_bench5_shipment_file_computes_its_totals(tmp_path):
    f = tmp_path / "shipment_data.xlsx"
    shutil.copy(FIXTURE, f)
    assert openpyxl.load_workbook(f, data_only=True).active["B6"].value is None      # openpyxl never computes
    assert recalc(f)["ok"]
    row = [c.value for c in openpyxl.load_workbook(f, data_only=True).active[6]]
    assert row[0] == "Total" and row[1] == 43 and row[3] == 79800 and round(row[2], 2) == 1855.81


def test_without_libreoffice_the_check_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(office, "soffice", lambda: None)
    assert office_check() == {"ok": False, "detail": "LibreOffice (soffice) is not installed"}
    assert recalc(tmp_path / "x.xlsx")["ok"] is False
