"""D79 — the Box 2 quality gate (D28) is on by default for --topology plan; off for the baselines and --drafts-from."""
from scripts.run_task import parse_args, quality_gate_on


def test_auto_default_is_on_only_for_the_plan_runner_when_drafting():
    assert quality_gate_on("auto", "plan") is True
    assert quality_gate_on("auto", "flat") is False
    assert quality_gate_on("auto", "boss_reviewers") is False
    assert quality_gate_on("auto", "plan", drafts_from="eval/x") is False      # nothing is drafted


def test_explicit_choice_wins_and_the_bare_flag_still_means_on():
    assert quality_gate_on("on", "flat") is True and quality_gate_on("off", "plan") is False
    assert parse_args(["x", "--quality-gate"]).quality_gate == "on"
    assert parse_args(["x"]).quality_gate == "auto"
    assert parse_args(["x", "--quality-gate", "off"]).quality_gate == "off"


def test_main_passes_the_resolved_gate_to_run_one(monkeypatch, tmp_path):
    import scripts.run_task as rt
    seen = []

    def fake(task, topology, *a, **kw):
        seen.append((topology, kw["quality_gate"]))
        raise SystemExit(0)
    monkeypatch.setattr(rt, "run_one", fake)
    for topo, want in (("plan", True), ("flat", False), ("boss_reviewers", False)):
        try:
            rt.main(["Reverse 'ab'", "--topology", topo, "--runs-dir", str(tmp_path), "--no-pool"])
        except SystemExit:
            pass
        assert seen[-1] == (topo, want)
