"""D170 — the accept rule compares paired runs (same task, same seed): the mean delta must reach promote.min_delta
(default 0.05), the changed arm must win more than twice as many pairs as it loses, and today's per-task drop and
contract rules still hold. The report lists every pair, the wins, losses and ties and the mean delta. Offline."""
import json
from pathlib import Path

from amoeba.eval.judge import judge_hash
from scripts import promote as P
from tests.test_promote_d166 import replay_file, setup


def paired_runner(scores):
    """scores: {(task, seed): (current, changed)}; each run folder gets result.json with that score."""
    def run(tasks, ids, seeds, out, config_b, passthrough, **kw):
        rows, h = [], judge_hash()["sha256"]
        for t in ids:
            for s in seeds:
                for arm, score in zip(("current", "changed"), scores[(t, s)]):
                    d = Path(out) / arm / f"{t}.s{s}" / "run"
                    (d / "artifacts").mkdir(parents=True, exist_ok=True)
                    sim = {"score": score, "baseline": 0.5, "delta": score - 0.5, "seed": s, "judge_hash": h}
                    (d / "result.json").write_text(json.dumps({"judge_hash": h, "sim_score": sim}))
                    (d / "artifacts" / "step_1.json").write_text(json.dumps({"meta": {"contract": {"A": {}},
                                                                                      "contract_missing": []}}))
                    rows.append({"task": t, "seed": s, "arm": arm, "run": str(d)})
        return rows
    return run


def go(tmp_path, scores):
    lib, lid, cfg, llm = setup(tmp_path)
    return P.promote(lib, lid, replay_file(tmp_path), llm, tmp_path / "promotions", config=cfg, seeds=[0, 1, 2],
                     runner=paired_runner(scores), tools=["calc", "echo"])


def test_three_wins_by_a_hair_and_two_losses_are_rejected(tmp_path):
    scores = {("r1", 0): (0.50, 0.51), ("r1", 1): (0.50, 0.51), ("r1", 2): (0.50, 0.51),     # three hairs
              ("r2", 0): (0.50, 0.495), ("r2", 1): (0.50, 0.495), ("r2", 2): (0.50, 0.50)}   # two losses, a tie
    out = go(tmp_path, scores)
    assert out["decision"] == "rejected", out["why"]
    arms = out["arms"]
    assert (arms["wins"], arms["losses"], arms["ties"]) == (3, 2, 1) and len(arms["pair_rows"]) == 6
    report = Path(out["report"]).read_text()
    assert "| r1 | 0 |" in report and "3 wins, 2 losses, 1 tie" in report


def test_a_clear_win_is_accepted(tmp_path):
    scores = {(t, s): (0.5, 0.7) for t in ("r1", "r2") for s in (0, 1, 2)}
    out = go(tmp_path, scores)
    assert out["decision"] == "accepted", out["why"]
    assert out["arms"]["wins"] == 6 and abs(out["arms"]["mean_delta"] - 0.2) < 1e-9


def test_the_rule_by_itself():
    cfg = {**P.promote_config(), "min_delta": 0.05, "max_task_drop": 0.05}
    base = {"per_task": [{"task": "a", "drop": 0.0}], "contract_current": 1.0, "contract_changed": 1.0}
    assert P.accept({**base, "mean_delta": 0.04, "wins": 9, "losses": 0, "ties": 0}, cfg)[0] is False   # too small
    assert P.accept({**base, "mean_delta": 0.10, "wins": 4, "losses": 2, "ties": 0}, cfg)[0] is False   # 4 = 2 × 2
    assert P.accept({**base, "mean_delta": 0.10, "wins": 5, "losses": 2, "ties": 0}, cfg)[0] is True
    assert P.promote_config()["min_delta"] == 0.05
