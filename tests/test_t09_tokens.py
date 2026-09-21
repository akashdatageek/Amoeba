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
    offenders = []
    for path in (ROOT / "amoeba").rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if re.search(r"budget", code, re.I):
                offenders.append(f"{path.relative_to(ROOT)}:{n}")
    assert offenders == []
