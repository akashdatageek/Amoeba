"""D155 — an edit never drops a check: sub-steps of a split and steps of a re-plan inherit the replaced steps' typed
checks (Box 2's contract) and their requirements; a re-plan may not write checks of its own; a work-around may narrow
done_when but the checks keep reading the original, and the citation checks are never waived. Both proposer modes
(this is the fix's own code path). Offline."""
from types import SimpleNamespace

from amoeba.adapt.stuck import waived_view
from amoeba.config.schema import PlanStep
from amoeba.interp.plan_runner import PlanRunner
from amoeba.interp.runtime import Interpreter
from tests.test_plan_runner import plan_team, step_no
from tests.test_proposer_d117 import BLOCK, ON, REPLAN, edit, good, reply

SEEN = {"name": "output_mentions", "params": {"terms": ["OUT"]}, "covers": ["R1", "R2"]}
CITE = {"name": "cites_every_figure", "params": {}, "covers": ["R3", "R4"]}


def run(task, envelope, trace, tools, script, proposer, setup, tmp_path=None):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script, fix_proposer=list(proposer))
    setup(cfg)
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path, plan_options=ON).run(cfg, task, seed=0)
    return llm, cfg, ep


def by_num(cfg):
    return {s.index + 1: s for s in cfg.plan}


def test_the_last_sub_step_of_a_split_carries_the_checks(task, envelope, trace, tools, tmp_path):
    def script(messages, seed):
        n = step_no(messages)
        if n == "1" and "Price storage only" not in messages[-1]["content"]:
            return reply("Final Output", BLOCK)
        return good(n)
    subs = [{"roles": ["Cost Analyst"], "text": "Price storage only", "do": "list prices", "output": "storage table",
             "done_when": "both priced"},
            {"roles": ["Cost Analyst"], "text": "Price compute", "do": "peak compute", "output": "compute table",
             "done_when": "both priced"}]
    llm, cfg, ep = run(task, envelope, trace, tools, script, [edit("split_step", steps=subs)],
                       lambda c: setattr(c.plan[0], "checks", [SEEN]), tmp_path)
    [f] = ep.adaptation["fixes"]
    assert f["replaced_by"] == [1, 5] and f["checks_carried"] == [{"check": "output_mentions", "from": 1, "to": 5}]
    plan = by_num(cfg)
    assert plan[5].checks == [SEEN] and plan[1].checks == [] and "R1" in plan[5].covers


def test_a_replan_carries_each_checks_to_the_step_that_covers_it(task, envelope, trace, tools):
    def script(messages, seed):
        n = step_no(messages)
        if n == "1" and "list prices in the task" not in messages[-1]["content"]:
            return reply("Final Output", BLOCK)
        return good(n)

    def setup(cfg):
        cfg.plan[0].checks = [SEEN]
        cfg.plan[2].checks = [CITE]                       # step 3 is dropped by the re-plan
    llm, cfg, ep = run(task, envelope, trace, tools, script, [edit("replan_remaining", plan=REPLAN)], setup)
    f = ep.adaptation["fixes"][0]                       # the carried citation check may keep step 4 stuck after it
    assert (f["replaced_by"], f["dropped"]) == ([1, 4], [2, 3])
    assert {(c["check"], c["from"], c["to"]) for c in f["checks_carried"]} == {("output_mentions", 1, 1),
                                                                              ("cites_every_figure", 3, 4)}
    plan = by_num(cfg)
    assert SEEN in plan[1].checks and CITE in plan[4].checks


def test_a_replan_that_writes_checks_is_refused(task, envelope, trace, tools):
    def script(messages, seed):
        return reply("Final Output", BLOCK) if step_no(messages) == "1" else good(step_no(messages))
    own = REPLAN.replace("   done_when: every cell sourced",
                         '   done_when: every cell sourced\n   checks: [{"name": "output_present"}]', 1)
    llm, cfg, ep = run(task, envelope, trace, tools, script, [edit("replan_remaining", plan=own)] * 2,
                       lambda c: None)
    [f] = ep.adaptation["fixes"]
    assert "may not write checks" in f["result"]


def test_a_work_around_narrows_done_when_but_the_checks_read_the_original():
    step = PlanStep(index=0, agent_ids=["a"], text="[A]: x", output="memo", done_when="a table of every cost, sourced")
    fake = SimpleNamespace(done_when_kept={})
    assert PlanRunner.check_view(fake, step, 1) is step
    fake.done_when_kept[1] = step.done_when
    narrowed = step.model_copy(update={"done_when": "costs in USD"})
    assert PlanRunner.check_view(fake, narrowed, 1).done_when == "a table of every cost, sourced"


def test_a_work_around_keeps_the_typed_checks(task, envelope, trace, tools):
    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and "work-around" not in user:
            return reply("Final Output", BLOCK)
        return good(n)
    wa = edit("work_around", capability="currency_api", method="price in USD from the task's list prices",
              done_when="every cell sourced, in USD", limitation="Costs are in USD only.")
    llm, cfg, ep = run(task, envelope, trace, tools, script,
                       [edit("grant_tool", role="Cost Analyst", tool="echo"), wa],
                       lambda c: setattr(c.plan[0], "checks", [SEEN, CITE]))
    assert cfg.plan[0].done_when.endswith("in USD") and cfg.plan[0].checks == [SEEN, CITE]


def test_a_waived_capability_never_waives_a_citation_check():
    meta = {"checks": [{"name": "contract:file_exists pdf", "pass": False},
                       {"name": "contract:figures_dated (pdf sources)", "pass": False}]}
    view, _ = waived_view(meta, [], {"pdf_reader"})
    assert [c["name"] for c in view["checks"]] == ["contract:figures_dated (pdf sources)"]
