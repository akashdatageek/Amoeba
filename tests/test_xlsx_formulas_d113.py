"""D113 — spreadsheet checks (offline): after a step that made a workbook, totals and derived cells must be formulas;
a typed total, a typed sum of the cells left of / above it, or a typed product of two cells to its left fails the
check with the cell names (the step's retry turn); numbers the task states are inputs; formulas pass; off, and
without local tools, nothing is checked."""
from openpyxl import Workbook

from amoeba.checks import CHECKS, run_checks
from amoeba.checks.xlsx_formulas import typed_derived_cells
from amoeba.interp.plan_runner import PlanOptions
from scripts.run_task import cli_plan_options, parse_args


def book(path, typed: bool):
    wb = Workbook()
    ws = wb.active
    ws.title = "Plan"
    ws.append(["Truck", "Weight", "Miles", "Rate", "Cost"])
    ws.append(["A", 9500, 120, 2.5, "=C2*D2" if not typed else 300])
    ws.append(["B", 7200, 80, 2.5, "=C3*D3" if not typed else 200])
    ws.append(["Total", "=SUM(B2:B3)" if not typed else 16700, "=SUM(C2:C3)" if not typed else 200, None,
               "=SUM(E2:E3)" if not typed else 500])
    ws.append(["Fixed fee", 4, 6, 10, None])                          # 4 + 6 = 10: a sum to the left, typed
    wb.save(path)
    return path


def test_typed_totals_and_derived_cells_are_found(tmp_path):
    got = {x["cell"]: x["why"] for x in typed_derived_cells(book(tmp_path / "t.xlsx", typed=True))}
    assert got["Plan!E2"] == "the product of two cells to its left" and got["Plan!E3"] == got["Plan!E2"]
    assert got["Plan!B4"] == "a total typed in" and got["Plan!C4"] == "a total typed in"
    assert got["Plan!E4"] == "a total typed in" and got["Plan!D5"] == "the sum of the 2 cells to its left"
    assert "Plan!B2" not in got and "Plan!C2" not in got                      # inputs


def test_formulas_pass_and_task_numbers_are_inputs(tmp_path):
    assert [x["cell"] for x in typed_derived_cells(book(tmp_path / "f.xlsx", typed=False))] == ["Plan!D5"]
    assert typed_derived_cells(book(tmp_path / "g.xlsx", typed=False), task="a fee of 10 per load") == []


def test_the_check_row_and_the_flag(tmp_path):
    assert "xlsx_formulas" in CHECKS
    [row] = run_checks(["xlsx_formulas"], "", {"xlsx_files": [str(book(tmp_path / "t.xlsx", typed=True))]})
    assert row["name"] == "domain_xlsx_formulas" and row["pass"] is False
    assert "Plan!E4 = 500 (a total typed in)" in row["detail"] and "=SUM(" in row["detail"]
    [ok] = run_checks(["xlsx_formulas"], "", {"xlsx_files": [], "task": ""})
    assert ok["pass"] is True
    assert parse_args(["x"]).xlsx_formulas == "on" and cli_plan_options(parse_args(["x"])).xlsx_formulas == "on"
    assert PlanOptions().xlsx_formulas == "off"
