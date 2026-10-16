"""D149 — diagnosis fixes: BLOCKED lines in any markdown (**, *, `, a leading "- ") name their capability; a held tool
refused 2+ times in one step for the same reason makes the cause tool_error, whatever else is missing (replayed on run
71d2f910 step 1, attempt 3). Offline."""
import json
from pathlib import Path

import pytest

from amoeba.adapt.stuck import diagnose, refusal_counts, step_signals
from amoeba.interp.plan_runner import blocked_marks

RUN = Path("eval/manual/audit_fixes/live/71d2f910-ecbd-4854-a4eb-7c557ee61ed0/artifacts")


@pytest.mark.parametrize("line", ["**BLOCKED:** Census API key — x", "*BLOCKED:* Census API key — x",
                                  "`BLOCKED:` Census API key — x", "- *BLOCKED*: Census API key — x",
                                  "- `BLOCKED`: Census API key — x"])
def test_blocked_in_any_markdown(line):
    assert blocked_marks(line) == ["Census API key"], line


def test_repeated_refusal_of_a_held_tool_is_tool_error():
    tries = [json.loads((RUN / f"step_1.try{i}.json").read_text()) for i in (1, 2, 3)]
    counts = refusal_counts(tries)                          # attempts 1–3 of step 1
    assert counts == {("local:Bash", "unsafe_command"): 2}
    meta = {**tries[2], "refusals": counts}
    d = diagnose(step_signals(meta, plan={}))
    assert d["cause"] == "tool_error"
    assert any("refused 2 times" in e for e in d["evidence"])


def test_one_refusal_does_not_decide_the_cause():
    tries = [json.loads((RUN / f"step_1.try{i}.json").read_text()) for i in (1, 2)]
    meta = {**tries[1], "refusals": refusal_counts(tries)}
    assert diagnose(step_signals(meta, plan={}))["cause"] == "missing_data"


def test_the_runner_counts_refusals_across_a_steps_attempts(task, envelope, trace, tools):
    from amoeba.interp.plan_runner import PlanOptions
    from tests.test_ladder_d145 import runner
    pr, _ = runner(task, envelope, trace, tools)
    one = [{"tool": "local:Bash", "result": "refused: local:Bash — unsafe_command ('..'). Nothing was run."}]
    assert pr.count_refusals(1, one) == [{"tool": "local:Bash", "reason": "unsafe_command", "n": 1}]
    assert pr.count_refusals(1, one) == [{"tool": "local:Bash", "reason": "unsafe_command", "n": 2}]
    assert pr.count_refusals(2, []) == []
