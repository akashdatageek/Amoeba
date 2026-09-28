"""D66 — provenance fixes. A number equal to a calc or local-tool result of the same step is derived, whatever its
tag, and plain code removes an [unverified] next to it (bench5 loan: the calc-computed payment was tagged
[unverified]). A number given in the task that carries only a web source tag is 'given' and flagged (bench5 diesel:
'Fuel Efficiency: 6.5 mpg [S1]')."""
from amoeba.interp.plan_runner import PlanOptions, refine_findings
from amoeba.interp.provenance import check_provenance, computed_values, strip_unverified
from amoeba.interp.runtime import Interpreter
from tests.test_plan_runner import BODY, plan_team, step_no

CALC = "250000 * ((0.07/12) * (1 + 0.07/12)**60) / ((1 + 0.07/12)**60 - 1)"
LOAN_TASK = "What is the monthly payment on a $250,000 equipment loan at 7% APR over 5 years? Show the formula."
DIESEL_TASK = "Compute fuel cost at 6.5 mpg for Chicago–Indianapolis 185 miles."


def test_a_calc_result_tagged_unverified_is_derived_and_the_tag_is_removed():
    values = computed_values(["4950.299635087366"])
    text = "## Result\nMonthly payment: $4,950.30 [unverified]\nRate: 7% [unverified]"
    out, n = strip_unverified(text, values)
    assert n == 1 and "Monthly payment: $4,950.30\n" in out and "7% [unverified]" in out
    p = check_provenance(text, set(), LOAN_TASK, "", ["4950.299635087366"], ["4950.299635087366"])
    statuses = {f["as"]: f["status"] for f in p["figures"]}
    assert statuses["$4,950.30"] == "derived" and statuses["7%"] == "unverified"


def test_a_web_result_does_not_count_as_computed():
    p = check_provenance("Price: $6.29 [unverified]", set(), "", "", ["[S1] price 6.29"], [])
    assert p["figures"][0]["status"] == "unverified"


def test_a_task_number_with_only_a_web_tag_is_given_and_flagged():
    text = "Fuel Efficiency: 6.5 mpg [S1]\nPrice: $6.29/gal [S1]\nGallons: 185 / 6.5 = 28.46"
    p = check_provenance(text, {"S1"}, DIESEL_TASK, "", ["[S1] U.S. diesel $6.29 as of Sep 14"], [], {"S1"})
    statuses = {f["as"]: f["status"] for f in p["figures"]}
    assert statuses["6.5"] == "given" and statuses["$6.29"] == "cited" and p["given_with_web_tag"] == ["6.5"]
    _, prov_items = refine_findings([], p)
    assert "given in the task, not found in a web source: 6.5" in prov_items[0]


def test_in_a_run_the_loan_payment_loses_its_unverified_tag(task, envelope, trace, tools):
    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and "(calc):" not in user:
            return f"## Thought\nok\n\n## CurrentStep\nc\n\n## Action\ncalc\n\n## ActionInput\n{CALC}"
        extra = "\nMonthly payment: $4,950.30 [unverified]" if n == "1" else ""
        return f"## Thought\nok\n\n## CurrentStep\nc\n\n## Action\nFinal Output\n\n## ActionInput\nOUT-{n}\n{BODY}{extra}"
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script)
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions()).run(cfg, task, seed=0)
    one = next(s for s in ep.steps if s["step"] == 1)
    assert one["unverified_tags_removed"] == 1
    assert one["provenance"]["unverified"] == 0
    two = [c for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "2"][0]["messages"][-1]["content"]
    assert "Monthly payment: $4,950.30\n" in two or two.rstrip().endswith("Monthly payment: $4,950.30")
