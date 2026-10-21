"""D150 — fixes don't waste their tries: a fix kind that failed on a step is never tried again on it, and after one
failed code fix on a step the next try is the fix proposer (rung D). Offline."""
from tests.test_fixes_d117 import reply, run, step_no

NO_EDIT = "I cannot see a fix."


def stall(messages, seed):
    n = step_no(messages)
    return reply("calc", "1 + 1") if n == "1" else reply("Final Output", f"OUT-{n} done")


def test_after_a_failed_more_turns_fix_the_proposer_comes_next(task, envelope, trace, tools, tmp_path):
    from amoeba.interp.plan_runner import PlanOptions          # D154: counts the single proposer's calls
    llm, cfg, ep = run(task, envelope, trace, tools, stall, tmp_path, proposer=(NO_EDIT,),
                       opts=PlanOptions(adapt="on", failed_step="run", proposer="single"))
    kinds = [(f["kind"], f["rung"]) for f in ep.adaptation["fixes"] if f["step"] == 1]
    assert kinds[0] == ("set_run_option:max_turns", 1)
    assert kinds[1][1] == "D", kinds                          # the proposer, not a second max_turns fix
    assert llm.calls_of("fix_proposer")


def test_a_failed_kind_is_never_tried_again_on_the_step(task, envelope, trace, tools, tmp_path):
    llm, cfg, ep = run(task, envelope, trace, tools, stall, tmp_path, proposer=(NO_EDIT,))
    tried = [f["kind"] for f in ep.adaptation["fixes"] if f["step"] == 1 and f["result"].startswith("failed")]
    assert len(tried) == len(set(tried)), tried
