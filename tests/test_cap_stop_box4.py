"""Part 2 Step 2 finding: the run's USD cap (D97 router, --max-usd-per-run) reached inside a Box 4 proposer call
raised NoModelAvailable out of the whole run (a traceback, no result). The cap must end the step's adaptation like any
other limit and let the run finish with what it has. Offline (MockLLMClient)."""
import pytest

from amoeba.interp.plan_runner import PlanOptions, PlanRunner
from amoeba.llm.router import NoModelAvailable
from tests.test_scoped_proposers_d154 import RULE_NO, RULE_OK, run, stall_until


def over_cap(*a, **k):
    raise NoModelAvailable("no model for planner: claude-sonnet-5-5: over the run USD cap ($1.0000)")


@pytest.mark.parametrize("proposer", ["scoped", "single"])
def test_the_usd_cap_in_a_proposer_call_ends_adaptation_not_the_run(task, envelope, trace, tools, monkeypatch,
                                                                     proposer):
    monkeypatch.setattr(PlanRunner, "_proposer_call", over_cap)
    opts = PlanOptions(adapt="on", failed_step="run", proposer=proposer)
    llm, cfg, ep = run(task, envelope, trace, tools, stall_until("FINISH NOW"), [RULE_OK], [RULE_NO], opts=opts)
    assert ep.answer                                          # the run finished and assembled an answer
    stopped = ep.adaptation.get("stopped") or {}
    assert "no model" in str(stopped.get("why", "")) and "USD cap" in str(stopped.get("why", ""))
    assert [e for e in trace.events("adapt_no_model")]
