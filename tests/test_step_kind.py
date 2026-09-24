"""D37 — explicit verification steps: `kind: work|verify` wins; keywords are only a logged fallback."""
from amoeba.interp.runtime import Interpreter
from amoeba.task.parsers import parse_plan_d24
from tests.test_plan_runner import DIAMOND, finish, plan_team

TARIFF = DIAMOND.replace("3. [Schema Engineer, Cost Analyst]: Cross-check numbers\n",
                         "3. [Schema Engineer, Cost Analyst]: Review current tariff schedules\n   kind: work\n")


def test_parser_reads_kind():
    [(_, _, work), (_, _, verify), (_, _, unset)] = parse_plan_d24(
        "1. [A]: Gather\n   kind: work\n2. [B]: Check A\n   kind: Verify\n   depends_on: 1\n3. [C]: Write\n")
    assert (work["kind"], verify["kind"], unset["kind"]) == ("work", "verify", "")


def test_a_review_step_declared_work_is_not_a_verifier(task, envelope, trace, tools):
    llm, cfg = plan_team(task, envelope, trace, text=TARIFF, plan_worker=finish)
    assert cfg.plan[2].kind == "work" and cfg.plan[2].text.endswith("Review current tariff schedules")
    ep = Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    three = next(s for s in ep.steps if s["step"] == 3)
    assert three["verification"] is False and "verdict" not in three
    assert trace.events("verification_inferred") == []
    assert all("You are VERIFYING" not in c["messages"][-1]["content"] for c in llm.calls_of("plan_worker"))


def test_a_declared_verify_step_is_a_verifier_whatever_its_title(task, envelope, trace, tools):
    text = DIAMOND.replace("2. [Schema Engineer]: Prototype and test\n", "2. [Schema Engineer]: Price storage\n"
                                                                          "   kind: verify\n")
    llm, cfg = plan_team(task, envelope, trace, text=text, plan_worker=finish)
    ep = Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    by = {s["step"]: s for s in ep.steps}
    assert by[2]["verification"] is True and by[2]["verdict"] == "PASS"
    assert by[3]["verification"] is False              # "Cross-check" with kinds declared elsewhere: no keyword guess


def test_without_kinds_the_keyword_rule_is_used_and_logged(task, envelope, trace, tools):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=finish)       # DIAMOND declares no kind
    ep = Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    assert next(s for s in ep.steps if s["step"] == 3)["verification"] is True
    [ev] = trace.events("verification_inferred")
    assert ev["amoeba.step"] == 3 and "Cross-check" in ev["amoeba.text"]
