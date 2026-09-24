"""D47 — opt-in per-run limits (error "budget", everything so far saved) and the token / cost estimate."""
import json

from amoeba.llm.cache import CachedLLM
from amoeba.llm.limits import RunLimits, describe, estimate
from amoeba.llm.toy_mock import toy_mock_client
from amoeba.task.models import Task
from amoeba.task.source import ToyTaskSource
from scripts.run_task import main, run_one
from tests.conftest import fx, mock
from tests.test_plan_runner import APPROVE, DIAMOND, finish


def test_a_call_limit_stops_the_run_cleanly(tmp_path, envelope, tools):
    task = ToyTaskSource(0, 1).tasks()[0]
    r = run_one(task, "flat", toy_mock_client(), envelope, tools, tmp_path, limits=RunLimits(max_calls=4))
    assert r.error == "budget" and r.n_llm_calls == 4 and r.answer is None
    d = tmp_path / r.run_id
    [stop] = [json.loads(l) for l in (d / "trace.jsonl").read_text().splitlines() if '"budget_stop"' in l]
    assert (stop["amoeba.used.calls"], stop["amoeba.limit.max_calls"]) == (4, 4)
    assert json.loads((d / "plan.json").read_text())["created_roles"]        # the draft made so far is kept
    assert json.loads((d / "result.json").read_text())["error"] == "budget"


def test_a_token_limit_in_box3_keeps_the_steps_that_ran(tmp_path, envelope, tools):
    llm = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=finish)
    r = run_one(Task(prompt="Compute 17 * 23 + 5."), "plan", llm, envelope, tools, tmp_path, draft_prompts="d24",
                limits=RunLimits(max_tokens=6500))   # drafting ~4.6k, steps ~0.8k each
    assert r.error == "budget"
    arts = sorted(p.name for p in (tmp_path / r.run_id / "artifacts").glob("step_*.json"))
    assert arts and "step_4.json" not in arts                                # stopped before the last step
    assert r.usage["tokens"] >= 6500 and r.usage["calls"] == r.n_llm_calls


def test_cached_calls_are_free_and_do_not_count(tmp_path, envelope, tools):
    task = ToyTaskSource(0, 1).tasks()[0]
    run_one(task, "flat", CachedLLM(toy_mock_client(), tmp_path / "c", "record"), envelope, tools, tmp_path / "a")
    r = run_one(task, "flat", CachedLLM(toy_mock_client(), tmp_path / "c", "record"), envelope, tools, tmp_path / "b",
                limits=RunLimits(max_calls=1))
    assert r.error is None and r.usage["calls"] == 0 and r.usage["cached_calls"] == r.n_llm_calls


def test_cost_estimate_uses_the_price_file_and_says_when_it_cannot():
    spans = [{"gen_ai.usage.input_tokens": 1_000_000, "gen_ai.usage.output_tokens": 200_000,
              "amoeba.usage.reasoning_tokens": 300_000},
             {"gen_ai.usage.input_tokens": 50, "gen_ai.usage.output_tokens": 5, "amoeba.cache_hit": True}]
    u = estimate(spans, "m", prices={"m": {"input": 0.10, "output": 0.40}})
    assert (u["input"], u["output"], u["reasoning"], u["cached_calls"], u["cost_usd"]) == (1_000_000, 200_000, 300_000, 1, 0.3)
    assert "est. cost $0.3000" in describe(u) and "1 cached call(s) free" in describe(u)
    none = estimate(spans, "unknown-model", prices={})
    assert none["cost_usd"] is None and "no price for unknown-model" in describe(none)


def test_cli_prints_tokens_and_cost_and_honours_the_limits(tmp_path, capsys):
    main(["--toy", "--n", "1", "--runs-dir", str(tmp_path), "--max-calls-per-run", "3"])
    out = capsys.readouterr().out
    assert "error=budget" in out and "tokens:" in out and "no price for toy-mock" in out
