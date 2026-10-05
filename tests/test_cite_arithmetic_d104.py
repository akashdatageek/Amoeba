"""D104 — the citation check (D74) skips in-line arithmetic: a calculation's result shown on the line, a power's base
and exponent, and the years of a range are not claims of their own; the operands and every other figure are still
checked; off, nothing changes. (Probe (hard) H1: these flags alone set correct steps to partial.)"""
from amoeba.interp.citecheck import derived_tokens, mislabelled_citations
from amoeba.interp.plan_runner import PlanOptions
from scripts.run_task import cli_plan_options, parse_args

SRC = {"S3": "Fuel cost 350 dollars; tolls 1,428.00", "S5": "data for 2017 only, 4 options"}
TEXT = """Total: 350 + 1,428.00 = 1,778.00 [S3]
Combinations: 4¹⁰ = 1,048,576 [S5]
Also 4^10 ≈ 1.05 million [S5]
Years 2016 … 2019 and 2016–2019 [S5]
Wrong figure 999 [S3]
Operand not in the source: 351 + 1,428.00 = 1,779.00 [S3]"""


def claims_of(found):
    return [x["claim"] for x in found]


def test_arithmetic_results_powers_and_year_ranges_are_skipped():
    assert claims_of(mislabelled_citations(TEXT, SRC, arithmetic=True)) == ["999", "351"]
    before = claims_of(mislabelled_citations(TEXT, SRC))
    assert {"1,778.00", "1,048,576", "2016", "2019", "999", "351"} <= set(before)       # off: as before


def test_derived_tokens():
    assert derived_tokens("a = 1,778.00 and b ≈ ~$12.5") == {"1778.00", "12.5"}
    assert derived_tokens("4¹⁰ and 2^(8)") == {"4", "2", "8"}
    assert derived_tokens("from 2016 to 2019") == {"2016", "2019"}
    assert derived_tokens("price 350 per unit") == set()


def test_the_flag():
    assert parse_args(["x"]).cite_arithmetic == "on"
    assert cli_plan_options(parse_args(["x"])).cite_arithmetic == "on" and PlanOptions().cite_arithmetic == "off"
