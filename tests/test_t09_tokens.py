"""T9 — token accounting is recorded, summed, and never enforced."""
import json
import re

from amoeba.llm.toy_mock import toy_mock_client
from amoeba.task.source import ToyTaskSource
from scripts.run_task import run_one
from tests.conftest import ROOT


def test_chat_spans_carry_usage_and_result_sums_them(tmp_path, envelope, tools):
    llm = toy_mock_client()
    for topology in ("flat", "boss_reviewers"):
        task = ToyTaskSource(seed=1, n=1).tasks()[0]
        r = run_one(task, topology, llm, envelope, tools, tmp_path)
        lines = [json.loads(l) for l in (tmp_path / r.run_id / "trace.jsonl").read_text().splitlines()]
        chats = [l for l in lines if l["name"] == "chat"]
        assert chats and all("gen_ai.usage.input_tokens" in c and "gen_ai.usage.output_tokens" in c for c in chats)
        assert all("gen_ai.request.model" in c and "latency_ms" in c for c in chats)
        assert r.total_tokens == sum(c["gen_ai.usage.input_tokens"] + c["gen_ai.usage.output_tokens"] for c in chats)
        assert r.n_llm_calls == len(chats)
        assert {l["name"] for l in lines} >= {"invoke_workflow", "invoke_agent", "chat"}


def test_nothing_in_the_code_path_reads_a_budget():
    # D47: the one exception is the opt-in module behind --max-tokens-per-run / --max-calls-per-run; it is checked
    # below that it does nothing unless a limit is set
    offenders = []
    for path in (ROOT / "amoeba").rglob("*.py"):
        if path.relative_to(ROOT).as_posix() == "amoeba/llm/limits.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if re.search(r"budget", code, re.I):
                offenders.append(f"{path.relative_to(ROOT)}:{n}")
    assert offenders == []


def test_openai_client_drops_seed_when_the_endpoint_rejects_it():
    # Gemini's OpenAI-compatible endpoint answers 400 'Unknown name "seed"'; retry once without it, then never send it
    from amoeba.llm.client import OpenAICompatibleClient

    class BadRequest(Exception):
        status_code = 400

    sent = []

    class Completions:
        def create(self, **kw):
            sent.append(kw)
            if "seed" in kw:
                raise BadRequest('Error code: 400 - Unknown name "seed": Cannot find field.')
            msg = type("M", (), {"content": "ok"})
            return type("R", (), {"choices": [type("C", (), {"message": msg})], "model": "m",
                                  "usage": type("U", (), {"prompt_tokens": 3, "completion_tokens": 1})})

    c = OpenAICompatibleClient(base_url="http://x", api_key="k", model="m")
    c._client = type("O", (), {"chat": type("Ch", (), {"completions": Completions()})})
    r1 = c.chat("s", "u", seed=0)
    r2 = c.chat("s", "u", seed=0)
    assert (r1.content, r1.input_tokens, r1.output_tokens) == ("ok", 3, 1) and r2.content == "ok"
    assert ["seed" in k for k in sent] == [True, False, False] and c.sends_seed is False


def test_without_limits_a_run_is_never_stopped_on_tokens(tmp_path, envelope, tools):
    task = ToyTaskSource(seed=1, n=1).tasks()[0]
    r = run_one(task, "flat", toy_mock_client(), envelope, tools, tmp_path)      # no limits passed
    lines = [json.loads(l) for l in (tmp_path / r.run_id / "trace.jsonl").read_text().splitlines()]
    assert r.error is None and not [l for l in lines if l["name"] == "budget_stop"]
