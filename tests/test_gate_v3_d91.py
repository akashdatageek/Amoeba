"""D91 — Gate v3: rule 2 on per-task means (repeats averaged first) with a one-sided paired permutation test (exact
up to 20 tasks), each hypothesis at its pre-set alpha_i from a fixed quota of 6 per family per stream (no reset on
accept), no prediction rule (its accuracy is recorded), rules 1, 4, 5, 5b, 6 as in v2; per-task noise and spread;
the single pre-registered check stays out of the quota and the recipe store."""
import itertools

import pytest

from amoeba.adapt.experimenter import Pair, ReplayResult
from amoeba.adapt.gate import (alpha_for, decide, noise_floor_tasks, permutation_greater, task_means, task_spread)
from amoeba.adapt.ledger import Ledger
from amoeba.adapt.recipe import apply_edit, load_recipe, seed_recipe
from tests.test_gate_d84 import ENV, Arms, hyp, result
from tests.test_experimenter_d83 import stream


def pairs_result(task_d: dict[str, list[float]], pre=(0.0, 0.0, 0.0), tokens=(1000, 1100)):
    pairs = [Pair(task_id=t, phase="post", k=k, seed=k, score_A=0.5, score_B=0.5 + d, tokens_A=tokens[0],
                  tokens_B=tokens[1], honesty_A=0, honesty_B=0) for t, ds in task_d.items() for k, d in enumerate(ds)]
    pairs += [Pair(task_id=f"p{i}", phase="pre", k=0, seed=0, score_A=1.0, score_B=1.0 + d, tokens_A=tokens[0],
                   tokens_B=tokens[1], honesty_A=0, honesty_B=0) for i, d in enumerate(pre)]
    return ReplayResult(hypothesis_id="h", family="calc", recipe_from=1, recipe_to=2, recipe_A_hash="a",
                        mode="own_draft", pairs=pairs)


def v3(res, h=None, noise=0.0, i=1, alpha=None):
    h = h or hyp()
    a = seed_recipe("calc")
    return decide(a, apply_edit(a, h.edit), h, res, noise, 99, [], ENV, version="v3", hypothesis_index=i, alpha=alpha)


def test_task_means_average_the_repeats_first():
    res = pairs_result({"t1": [0.2, 0.4, 0.0], "t2": [0.0, 0.0, 0.3]})
    assert task_means(res.post()) == {"t1": pytest.approx(0.2), "t2": pytest.approx(0.1)}


def test_the_permutation_test_is_exact_and_matches_brute_force():
    d = [0.3, -0.1, 0.2, 0.0, 0.25, -0.05, 0.1]
    obs = sum(d)
    brute = sum(sum(s * x for s, x in zip(signs, d)) >= obs - 1e-9
                for signs in itertools.product((1, -1), repeat=len(d))) / 2 ** len(d)
    assert permutation_greater(d) == pytest.approx(brute)
    assert permutation_greater([0.1] * 5) == pytest.approx(1 / 32)
    assert permutation_greater([0.1] * 15) == pytest.approx(1 / 2 ** 15)
    assert permutation_greater([]) == 1.0 and permutation_greater([-0.2, -0.1]) == 1.0


def test_above_twenty_tasks_it_samples_with_a_fixed_seed():
    d = [0.05 * ((i % 5) - 1) for i in range(22)]
    p1, p2 = permutation_greater(d, n_random=20_000), permutation_greater(d, n_random=20_000)
    assert p1 == p2 and permutation_greater(d[:12], exact_max=10, n_random=40_000) == \
        pytest.approx(permutation_greater(d[:12]), abs=0.01)


def test_repeats_no_longer_count_as_tasks():
    """5 tasks x 3 identical repeats: v2 saw 15 pairs (p = 2^-15, significant); v3 sees 5 tasks (p = 1/32)."""
    res = pairs_result({f"t{i}": [0.2, 0.2, 0.2] for i in range(5)})
    a = seed_recipe("calc")
    v2 = decide(a, apply_edit(a, hyp().edit), hyp(), res, 0.0, 1, [], ENV, version="v2")
    dec = v3(res)
    assert v2.decision == "accept" and dec.decision == "reject"
    assert dec.p == pytest.approx(1 / 32) and dec.n_tasks == 5 and dec.repeats == 3
    assert dec.reasons[0].startswith("2 not significant: permutation p 0.0312 > alpha 0.0083 (5 tasks)")


def test_a_clean_v3_accept_on_fifteen_tasks():
    res = pairs_result({f"t{i:02d}": [0.2, 0.3, 0.1] for i in range(15)})
    dec = v3(res, noise=0.05)
    assert dec.decision == "accept", dec.reasons
    assert (dec.gate_version, dec.test, dec.hypothesis_index) == ("v3", "permutation", 1)
    assert dec.alpha == pytest.approx(0.05 / 6) and dec.observed_delta == pytest.approx(0.2)
    assert len(dec.task_d) == 15 and dec.retention_delta == 0.0


def test_the_gain_must_beat_the_noise_and_the_floor():
    res = pairs_result({f"t{i:02d}": [0.04] * 3 for i in range(15)})
    assert v3(res).reasons[0].startswith("2 no real gain")
    res = pairs_result({f"t{i:02d}": [0.1] * 3 for i in range(15)})
    assert v3(res, noise=0.12).reasons[0].startswith("2 no real gain")


def test_no_prediction_rule_but_its_accuracy_is_recorded():
    res = pairs_result({f"t{i:02d}": [0.2] * 3 for i in range(15)})
    dec = v3(res, h=hyp(predicted=-0.1))
    assert dec.decision == "accept" and dec.prediction == {"sign_ok": False, "abs_error": pytest.approx(0.3)}
    assert not dec.unexplained_gain


def test_the_quota_is_six_fixed_alphas_and_then_spent():
    assert [alpha_for(i) for i in range(1, 7)] == [pytest.approx(0.05 / 6)] * 6 and alpha_for(7) is None
    res = pairs_result({f"t{i:02d}": [0.2] * 3 for i in range(15)})
    dec = v3(res, i=7)
    assert dec.decision == "reject" and dec.reasons[0].startswith("2 quota spent")
    assert v3(res, i=None, alpha=0.05).decision == "accept"          # the pre-registered check's own alpha


def test_kept_rules_4_5_5b_and_6():
    res = pairs_result({f"t{i:02d}": [0.2] * 3 for i in range(15)}, pre=(-0.3, 0.0, 0.0), tokens=(1000, 3000))
    assert sorted({r.split()[0] for r in v3(res, noise=0.05).reasons}) == ["4", "6"]
    r = result()                                         # the v2 fixture: rules 5 and 5b read per run
    for p in r.post()[:6]:
        p.flags_B, p.error_B = {"hallucinated_citations": 1}, "incomplete"
    reasons = v3(r).reasons
    assert any(x.startswith("5 honesty regression") for x in reasons)
    assert any(x.startswith("5b reliability regression") for x in reasons)


def test_per_task_noise_and_spread():
    cal = pairs_result({"t1": [0.0, 0.5, 0.0], "t2": [0.0, 0.0, 0.0], "t3": [0.25, 0.0, 0.0]})
    assert noise_floor_tasks(cal) == pytest.approx(2 * 0.08333 / 3 ** 0.5, abs=1e-3)
    sp = task_spread(cal)
    assert sp["t2"]["spread"] == 0.0 and sp["t1"]["scores_A2"] == [0.5, 1.0, 0.5] and sp["t1"]["range"] == 0.5


def test_the_ledger_counts_v3_decisions_without_reset(tmp_path):
    led = Ledger(tmp_path / "ledger.jsonl")
    led.append({"event": "decision", "family": "calc", "decision": "reject", "gate_version": "v2"})
    led.append({"event": "decision", "family": "calc", "decision": "accept", "gate_version": "v3"})
    led.append({"event": "decision", "family": "calc", "decision": "reject", "gate_version": "v3"})
    led.append({"event": "decision", "family": "calc", "decision": "reject", "gate_version": "v3", "post_hoc": True})
    led.append({"event": "decision", "family": "calc", "decision": "reject", "gate_version": "v3", "check": True,
                "edit": {"op": "add_planner_rule", "params": {"text": "x"}}})
    led.append({"event": "decision", "family": "other", "decision": "reject", "gate_version": "v3"})
    assert led.hypotheses_used("calc") == 2                  # the accept counts; no reset
    assert all(not r.get("check") for r in led.failed("calc"))   # a person's check never reaches the Architect


def test_the_pre_registered_check_stays_out_of_the_quota_and_the_store(tmp_path):
    from scripts.run_experiment import hand_check
    from amoeba.adapt.gate import Hypothesis
    from tests.test_gate_d84 import RULE
    h = Hypothesis(hypothesis_id="check-assumptions", family="calc", edit=RULE, predicted_delta=0.3)
    row = hand_check(stream(), h, Arms(), tmp_path, repeats=3, check=True)
    led = Ledger(tmp_path / "ledger.jsonl")
    cal = led.rows(event="calibration")[0]
    assert cal["gate_version"] == "v3" and "task_spread" in cal and cal["n_tasks"] >= 1
    assert row["check"] is True and row["gate_version"] == "v3" and row["alpha"] == 0.05
    assert led.rows(event="hypothesis")[0]["check"] is True
    assert led.hypotheses_used("calc") == 0
    assert load_recipe(tmp_path / "recipes", "calc") is None or load_recipe(tmp_path / "recipes", "calc").version == 1
    assert not (tmp_path / "recipes" / "experience.jsonl").exists()


def test_the_loop_report_gives_prediction_accuracy():
    from amoeba.adapt.loop import prediction_accuracy
    rows = [{"event": "decision", "hypothesis_id": "a", "predicted_delta": 0.2, "observed_delta": 0.1},
            {"event": "decision", "hypothesis_id": "b", "predicted_delta": 0.1, "observed_delta": -0.05},
            {"event": "decision", "hypothesis_id": "c", "predicted_delta": 0.1, "observed_delta": 0.3, "check": True},
            {"event": "hypothesis", "hypothesis_id": "d", "predicted_delta": 0.1}]
    pa = prediction_accuracy(rows)
    assert (pa["n"], pa["sign_right"], pa["sign_share"]) == (2, 1, 0.5)
    assert pa["mean_abs_error"] == pytest.approx(0.125)
