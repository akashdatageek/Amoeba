"""Part 2 Step 2 finding: under --routing routed (the plan runner's default, and the only mode with
--max-usd-per-run), profile claude-sonnet+gemma-verify ran every verify step on Sonnet: the router allowed only the
profile's own registry entry, so Gemma was filtered out ("not in the niche profile's models") and D146's verifier was
never attached. The profile's verifier must reach the router as an allowed model and the verifier / plan-observer
preference, for every run of the command."""
from scripts.run_task import build_router_llm, parse_args
from amoeba.llm.router import CallSpec


def router(monkeypatch, tmp_path, gemini=True):
    monkeypatch.setenv("AMOEBA_RATE_DIR", str(tmp_path / "rate"))
    monkeypatch.setenv("CLAUDE_API_KEY", "k")
    if gemini:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
    else:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    args = parse_args(["x", "--topology", "plan", "--llm", "openai", "--profile", "claude-sonnet+gemma-verify",
                       "--max-usd-per-run", "6"])
    return build_router_llm(args, "routed")


def test_verify_steps_and_the_plan_observer_route_to_the_verifier(monkeypatch, tmp_path):
    r = router(monkeypatch, tmp_path)
    r.begin_run(role_prefs=None)                          # run_one's call: the preference must survive it
    assert r.route(CallSpec(role="verifier"))[0] == "gemma-4-31b"
    assert r.route(CallSpec(role="plan_observer"))[0] == "gemma-4-31b"
    for role in ("worker", "planner", "summariser", "fix_proposer"):
        assert r.route(CallSpec(role=role))[0] == "claude-sonnet-5-5", role
    assert r.usd_cap == 6.0


def test_without_the_verifier_key_the_team_model_verifies(monkeypatch, tmp_path):
    r = router(monkeypatch, tmp_path, gemini=False)
    r.begin_run(role_prefs=None)
    assert r.route(CallSpec(role="verifier"))[0] == "claude-sonnet-5-5"
