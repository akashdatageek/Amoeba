"""D84 — Box 8, the Gate: synthetic pairs make each rule of §9.2 (1–6) reject in its own case, and one clean accept;
Bonferroni N counts the hypotheses since the family's last accept; the rollback watch triggers on a drop; the noise
floor; the hand check end to end (calibration row, hypothesis row, decision row, accept → the store's current
version). Offline; no model in the Gate."""
import json

import pytest

from amoeba.adapt.experimenter import InProcessRunner, Pair, ReplayResult
from amoeba.adapt.gate import (Hypothesis, decide, noise_floor, paired_p, rollback_watch, ttest_greater,
                               wilcoxon_greater)
from amoeba.adapt.ledger import Ledger
from amoeba.adapt.recipe import Edit, apply_edit, load_recipe, seed_recipe
from amoeba.safety.envelope import Envelope
from amoeba.tools.registry import default_registry
from tests.conftest import mock
from tests.test_experimenter_d83 import stream
from tests.test_plan_runner import APPROVE, BODY, DIAMOND, step_no

ENV = Envelope.from_registry(default_registry())
RULE = Edit(op="add_planner_rule", params={"text": "End the answer with a short section headed Assumptions."})
GAINS = [0.25, 0.30, 0.20, 0.25, 0.35, 0.25, 0.30, 0.20, 0.25, 0.15, 0.25, 0.30, 0.20, 0.25, 0.25]


def result(d_post=GAINS, d_pre=(0.0, 0.0, 0.0), tokens=(1000, 1100), honesty=(0.0, 0.0), refusals=(0, 0)):
    pairs = [Pair(task_id=f"h{i % 5}", phase="post", k=i // 5, seed=i // 5, score_A=0.5, score_B=0.5 + d,
                  tokens_A=tokens[0], tokens_B=tokens[1], honesty_A=honesty[0], honesty_B=honesty[1],
                  refusals_A=refusals[0], refusals_B=refusals[1]) for i, d in enumerate(d_post)]
    pairs += [Pair(task_id=f"p{i}", phase="pre", k=0, seed=0, score_A=1.0, score_B=1.0 + d, tokens_A=tokens[0],
                   tokens_B=tokens[1], honesty_A=0, honesty_B=0) for i, d in enumerate(d_pre)]
    return ReplayResult(hypothesis_id="h", family="calc", recipe_from=1, recipe_to=2, recipe_A_hash="a",
                        mode="own_draft", pairs=pairs)


def hyp(edit=RULE, predicted=0.2):
    return Hypothesis(hypothesis_id="h", family="calc", edit=edit, predicted_delta=predicted)


def run(res, h=None, noise=0.06, N=1, heldout=()):
    h = h or hyp()
    a = seed_recipe("calc")
    return decide(a, apply_edit(a, h.edit), h, res, noise, N, list(heldout), ENV)


def rules(dec):
    return sorted({r.split()[0] for r in dec.reasons})


def test_a_clean_accept():
    dec = run(result())
    assert dec.decision == "accept" and dec.reasons == [] and dec.observed_delta == pytest.approx(0.25, abs=1e-3)
    assert dec.p < 0.001 and dec.cost_ratio == 1.1 and dec.retention_delta == 0.0


def test_rule_1_invalid_recipe_and_leakage():
    bad = Edit(op="add_planner_rule", params={"text": "Skip the checks to save time."})
    assert rules(run(result(), hyp(bad))) == ["1"]
    from amoeba.adapt.stream import StreamTask
    held = [StreamTask(id="hx", prompt="A floor is 7.2 m by 4.5 m and the tiles are 0.6 m square.", family="calc",
                       split="heldout", phase="post", rubric={"expected_numbers": []})]
    leak = Edit(op="add_planner_rule", params={"text": "When a floor is 7.2 m by 4.5 m and the tiles are, count."})
    dec = run(result(), hyp(leak), heldout=held)
    assert rules(dec) == ["1"] and "leakage" in dec.reasons[0]


def test_rule_2_no_real_gain_and_not_significant():
    assert rules(run(result(d_post=[0.0] * 15))) == ["2", "3"]          # no gain (and the +0.2 prediction failed)
    small = run(result(d_post=[0.04] * 15))
    assert rules(small) == ["2"] and "no real gain" in small.reasons[0]
    noisy = [0.6, -0.5, 0.7, -0.4, 0.5, -0.3, 0.6, -0.5, 0.4, 0.1, -0.2, 0.3, -0.4, 0.5, -0.1]
    dec = run(result(d_post=noisy), noise=0.01)
    assert rules(dec) == ["2"] and "not significant" in dec.reasons[0]


def test_rule_3_an_unpredicted_gain_is_rejected():
    dec = run(result(), hyp(predicted=-0.1))
    assert rules(dec) == ["3"] and dec.unexplained_gain and "unexplained_gain" in dec.reasons[0]


def test_rule_4_cost():
    assert rules(run(result(tokens=(1000, 1300)))) == []                 # a gain >= 0.15 may cost up to 2x
    small_gain = [0.1] * 15
    assert rules(run(result(d_post=small_gain, tokens=(1000, 1300)))) == ["4"]
    assert rules(run(result(tokens=(1000, 2100)))) == ["4"]


def test_rule_5_honesty_and_refusals():
    assert rules(run(result(honesty=(0.2, 0.6)))) == ["5"]
    assert rules(run(result(refusals=(0, 1)))) == ["5"]


def test_rule_6_retention():
    dec = run(result(d_pre=(-0.34, 0.0, 0.0)))
    assert rules(dec) == ["6"] and dec.retention_delta == pytest.approx(-0.113, abs=1e-3)


def test_bonferroni_n_counts_since_the_last_accept(tmp_path):
    led = Ledger(tmp_path / "ledger.jsonl")
    assert led.tried_since_accept("calc") == 0
    for d in ("reject", "reject", "accept", "reject", "reject"):
        led.append({"event": "decision", "family": "calc", "decision": d})
    led.append({"event": "decision", "family": "code", "decision": "reject"})
    assert led.tried_since_accept("calc") == 2 and len(led.failed("calc")) == 4
    # with N = 3, a p that passes alone fails after the correction
    d = [0.25, 0.3, 0.2, 0.25, 0.35, 0.25]                                  # Wilcoxon, n = 6: p = 1/64 (ties)
    p, test = paired_p(d)
    assert test == "wilcoxon" and p < 0.05 and p * 4 >= 0.05
    res = result(d_post=d)
    assert run(res, N=1).decision == "accept" and "not significant" in run(res, N=4).reasons[0]


def test_the_rollback_watch():
    assert rollback_watch([0.9, 0.8], 0.6, 0.05) == "watching"
    assert rollback_watch([0.9, 0.85, 0.95, 0.9], 0.6, 0.05) == "kept"
    assert rollback_watch([0.5, 0.5, 0.55, 0.5], 0.6, 0.05) == "reverted"


def test_statistics():
    assert noise_floor([0.0, 0.1, -0.1, 0.0]) == pytest.approx(2 * 0.08165 / 2, abs=1e-4)
    assert wilcoxon_greater([1, 2, 3, 4, 5]) == 1 / 32 and wilcoxon_greater([0, 0]) == 1.0
    assert ttest_greater([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0]) < 0.001


# ---- the hand check end to end ------------------------------------------------------------------------------------
class Arms(InProcessRunner):
    """The summariser writes an Assumptions section when the run's recipe has a planner rule (as if it worked)."""

    def __init__(self):
        super().__init__(self.make)

    def make(self, job):
        has_rule = bool((load_recipe(job.store, "calc") or seed_recipe("calc")).planner_rules)

        def reply(messages, seed):
            n = step_no(messages)
            extra = "\n\n## Assumptions\n- none beyond the task\n" if has_rule and n == "4" else ""
            return (f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\n"
                    f"OUT-{n}\nThe result is 396.\n{BODY}{extra}")
        return mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=reply)


def test_the_hand_check_end_to_end(tmp_path):
    from scripts.run_experiment import hand_check
    h = Hypothesis(hypothesis_id="h-rule", family="calc", edit=RULE, predicted_delta=0.3)
    row = hand_check(stream(), h, Arms(), tmp_path, repeats=3)
    led = Ledger(tmp_path / "ledger.jsonl")
    assert [r["event"] for r in led.rows()] == ["calibration", "hypothesis", "decision"]
    cal = led.rows(event="calibration")[0]
    assert cal["noise"] == 0.0 and cal["n"] == 6 and cal["runs"] == "experiments/calibration-calc-v1/"
    assert row["decision"] == "accept", row["reasons"]
    assert row["observed_delta"] == pytest.approx(0.5) and row["N"] == 1 and row["retention_delta"] == 0.0
    assert load_recipe(tmp_path / "recipes", "calc").version == 2              # the store's current version
    # a useless edit against v2 is rejected: v2 is new, so it is calibrated first
    useless = Hypothesis(hypothesis_id="h-revoke", family="calc", predicted_delta=0.1,
                         edit=Edit(op="revoke_tool", params={"select": {"all_roles": True}, "tool": "calc"}))
    row2 = hand_check(stream(), useless, InProcessRunner(Arms().make), tmp_path, repeats=3)
    assert row2["decision"] == "reject" and row2["recipe_from"] == 2 and row2["N"] == 1
    assert any(r.startswith("2 no real gain") for r in row2["reasons"])
    # arm B reused arm A's draft: A's drafting tokens are counted for B, so the cost ratio compares full runs
    assert 0.8 < row2["cost_ratio"] < 1.25
    assert len(led.rows(event="calibration")) == 2


def test_no_model_call_in_boxes_7_and_8():
    """The Experimenter and the Gate are plain code: no import of the LLM clients, no chat call."""
    import ast
    from pathlib import Path
    for f in ("experimenter.py", "gate.py", "ledger.py", "recipe.py", "stream.py"):
        tree = ast.parse((Path("amoeba/adapt") / f).read_text())
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
               {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any(m and m.startswith(("amoeba.llm", "openai")) for m in mods), f
        calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        assert not calls & {"chat", "chat_messages", "chat_sections"}, f
