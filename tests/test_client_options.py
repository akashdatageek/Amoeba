"""D49 — --merge-system and --reasoning-effort, tested on a mocked SDK client (no network)."""
import pytest

from amoeba.llm.cache import CachedLLM
from amoeba.llm.client import OpenAICompatibleClient, merge_system
from scripts.run_task import parse_args
from tests.test_rate_limits import client

SYS = [{"role": "system", "content": "You are X."}, {"role": "user", "content": "Do Y."}]


def test_merge_system_moves_the_system_text_into_the_first_user_message():
    assert merge_system(SYS) == [{"role": "user", "content": "You are X.\n\nDo Y."}]
    hist = [{"role": "system", "content": "S"}, {"role": "assistant", "content": "[a]: hi"}, {"role": "user", "content": "U"}]
    assert merge_system(hist) == [{"role": "assistant", "content": "[a]: hi"}, {"role": "user", "content": "S\n\nU"}]
    assert merge_system([{"role": "system", "content": "S"}]) == [{"role": "user", "content": "S"}]
    assert merge_system([{"role": "user", "content": "U"}]) == [{"role": "user", "content": "U"}]


def test_the_client_sends_merged_messages_and_reasoning_effort_only_when_set():
    plain, _, sent = client(["ok"])
    plain.chat("You are X.", "Do Y.")
    assert sent[0]["messages"][0]["role"] == "system" and "reasoning_effort" not in sent[0]
    gemma, _, sent2 = client(["ok"], merge_system=True, reasoning_effort="off")
    gemma.chat("You are X.", "Do Y.")
    assert sent2[0]["messages"] == [{"role": "user", "content": "You are X.\n\nDo Y."}]
    assert sent2[0]["reasoning_effort"] == "none"
    high, _, sent3 = client(["ok"], reasoning_effort="high")
    high.chat("s", "u")
    assert sent3[0]["reasoning_effort"] == "high"
    with pytest.raises(ValueError):
        OpenAICompatibleClient(base_url="http://x", api_key="k", model="m", reasoning_effort="max")


def test_the_options_are_part_of_the_cache_key(tmp_path):
    a, _, _ = client(["ok"])
    b, _, _ = client(["ok"], merge_system=True)
    assert CachedLLM(a, tmp_path).key(SYS, 100) != CachedLLM(b, tmp_path).key(SYS, 100)


def test_cli_flags():
    args = parse_args(["--toy", "--merge-system", "--reasoning-effort", "low"])
    assert args.merge_system is True and args.reasoning_effort == "low"
    assert parse_args(["--toy"]).reasoning_effort is None
