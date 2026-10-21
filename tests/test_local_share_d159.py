"""D159 — local-tool calls scale with the plan: the fixed 60 calls per run becomes a run allowance of
calls_per_step x planned steps, and each step gets a share of what is left (step_share x left / steps not yet run),
like D151's token share. Offline: the fake `claude mcp serve`."""
from amoeba.interp.trace import TraceWriter
from amoeba.localtools.toolbox import LocalToolbox, load_local_config
from tests.test_localtools import lsetup, skills  # noqa: F401  (skills is a fixture)


def test_the_config_has_a_share_not_a_fixed_run_cap():
    lim = load_local_config()["limits"]
    assert lim.get("max_calls_per_run") is None                      # no fixed cap by default any more
    assert lim["calls_per_step"] == 12 and lim["step_share"] == 1.5 and lim["max_calls_per_step"] == 20


def box(skills, tmp_path, **limits):
    b = LocalToolbox(lsetup(skills, **limits), tmp_path / "run", TraceWriter(None))
    b.start()
    return b


def test_an_eleven_step_plan_is_not_stopped_while_each_step_stays_within_its_share(skills, tmp_path):
    b = box(skills, tmp_path)
    try:
        for n in range(1, 12):
            b.begin_step(n, plan_steps=11, not_run=12 - n)
            for _ in range(10):                                      # 110 calls in all: the old cap stopped at 60
                assert b.call("Bash", "true").startswith("[local:Bash]"), n
        assert b.calls == 110 and b.refusals == {}
        assert b.allowance() == 132                                   # 12 calls x 11 steps
        out = b.finish()
        assert out["local_step_shares"]["1"]["share"] == 18          # 1.5 x 132 / 11
    finally:
        pass


def test_a_step_over_its_share_is_refused_and_told_why(skills, tmp_path):
    b = box(skills, tmp_path, max_calls_per_step=50)
    b.begin_step(1, plan_steps=4, not_run=4)                          # share 1.5 x 48 / 4 = 18
    for _ in range(18):
        b.call("Bash", "true")
    out = b.call("Bash", "true")
    assert out.startswith("refused: local:Bash — step_share")
    assert "18 = 1.5 x 48 calls left / 4 steps not yet run" in out
    b.begin_step(2, plan_steps=4, not_run=3)                          # the next step has its own share again
    assert b.call("Bash", "true").startswith("[local:Bash]")
    assert b.step_shares[2]["share"] == 15                            # 1.5 x (48 - 18) / 3
    b.finish()


def test_the_per_step_ceiling_still_holds(skills, tmp_path):
    b = box(skills, tmp_path, max_calls_per_step=2)
    b.begin_step(5, plan_steps=5, not_run=1)                          # share 1.5 x 60 / 1 = 90, ceiling 2
    b.call("Bash", "true")
    b.call("Bash", "true")
    assert b.call("Bash", "true").startswith("refused: local:Bash — step_cap")
    b.finish()


def test_without_a_plan_the_allowance_is_the_old_sixty(skills, tmp_path):
    b = box(skills, tmp_path)
    b.begin_step(1)                                                   # flat / boss_reviewers / preflight
    assert b.allowance() == 60 and b.step_shares == {}
    b.finish()


def test_the_plan_runner_tells_the_toolbox_the_plan_size():
    import inspect
    from amoeba.interp import plan_runner
    src = inspect.getsource(plan_runner.PlanRunner)
    assert "plan_steps=" in src and "not_run=" in src
