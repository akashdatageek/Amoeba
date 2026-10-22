"""D169 — a planner_rule change is tested with real planning: both config arms plan fresh (no --drafts-from) on
promote.planner_seeds seeds (default 5), so the changed arm's Planner sees the rule and the current arm's does not.
tool_guidance and reorder_allowed_edits keep the shared draft. The report says which mode was used and why. Offline:
the real pair runner with run_task --llm mock."""
import json
from pathlib import Path

from scripts import promote as P
from tests.test_promote_d166 import fake_runner, replay_file, setup

RULE = {"kind": "planner_rule", "text": "Name the unit of every figure in the plan."}


def planner_prompts(run: Path) -> list[str]:
    out = []
    for line in (Path(run) / "trace.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        attrs = row.get("attributes") or row.get("attrs") or row
        if '"planner"' in line and "gen_ai.input.messages" in line:
            out.append(json.dumps(attrs.get("gen_ai.input.messages", line)))
    return out


def test_a_planner_rule_is_tested_with_fresh_plans_in_both_arms(tmp_path):
    lib, lid, cfg, llm = setup(tmp_path, proposal=RULE)
    out = P.promote(lib, lid, replay_file(tmp_path), llm, tmp_path / "promotions", config=cfg, seeds=[0],
                    passthrough=["--topology", "plan", "--llm", "mock", "--draft-prompts", "d24"],
                    tools=["calc", "echo"])
    rows = [json.loads(x) for x in next((tmp_path / "promotions" / "arms").iterdir()).joinpath(
        "pairs.jsonl").read_text().splitlines()]
    by_arm = {r["arm"]: r for r in rows if r["task"] == "r1"}
    changed, current = planner_prompts(by_arm["changed"]["run"]), planner_prompts(by_arm["current"]["run"])
    assert changed and current                                    # both arms planned (no shared draft)
    assert any(RULE["text"] in x for x in changed) and not any(RULE["text"] in x for x in current)
    rec = json.loads(Path(out["report"]).with_suffix(".json").read_text())
    assert rec["test_mode"]["mode"] == "fresh plans" and "planner" in rec["test_mode"]["why"]
    assert "fresh plans" in Path(out["report"]).read_text()


def test_planner_seeds_default_and_the_shared_draft_for_other_kinds(tmp_path):
    seen = {}
    runner = fake_runner({"r1": 0.9, "r2": 0.9})

    def spy(tasks, ids, seeds, out, config_b, passthrough, **kw):
        seen.setdefault("calls", []).append((list(seeds), kw))
        return runner(tasks, ids, seeds, out, config_b, passthrough)
    lib, lid, cfg, llm = setup(tmp_path / "a", proposal=RULE)
    P.promote(lib, lid, replay_file(tmp_path), llm, tmp_path / "pa", config=cfg, runner=spy, tools=["calc"],
              passthrough=["--draft-prompts", "d24"])
    assert seen["calls"][-1] == ([0, 1, 2, 3, 4], {"fresh_plans": True})          # promote.planner_seeds: 5
    lib, lid, cfg, llm = setup(tmp_path / "c", proposal=RULE)                     # d19 prompts have no slot
    out = P.promote(lib, lid, replay_file(tmp_path), llm, tmp_path / "pc", config=cfg, runner=spy, tools=["calc"])
    assert out["decision"] == "refused" and "d24" in out["why"] and len(seen["calls"]) == 1
    lib, lid, cfg, llm = setup(tmp_path / "b")                                     # a tool_guidance change
    out = P.promote(lib, lid, replay_file(tmp_path), llm, tmp_path / "pb", config=cfg, runner=spy,
                    tools=["calc"])
    assert seen["calls"][-1] == ([0, 1, 2], {})                                    # shared draft, promote.seeds
    assert json.loads(Path(out["report"]).with_suffix(".json").read_text())["test_mode"]["mode"] == "shared draft"


def test_stage_e_fresh_plans_leaves_out_drafts_from(tmp_path):
    from scripts.stage_e import arm_command
    cmd = arm_command("changed", Path("t.jsonl"), 1, tmp_path, tmp_path / "p.json", tmp_path / "first", [],
                      fresh_plans=True)
    assert "--drafts-from" not in cmd
