"""D46 — the response cache: record, replay (a miss is an error, never a live call), off; web results too."""
import json

import pytest

from amoeba.llm.cache import CachedLLM, CachedProvider, CacheMiss
from amoeba.llm.client import MockLLMClient
from amoeba.llm.toy_mock import toy_mock_client
from amoeba.task.source import ToyTaskSource
from amoeba.tools.web import web_registry
from scripts.run_task import main, run_one
from tests.test_web_tools import FakeProvider

MSG = [{"role": "system", "content": "s"}, {"role": "user", "content": "hello"}]


def counting():
    llm = MockLLMClient(responder=lambda m, s: f"reply {len(llm.calls)}", model="m")
    return llm


def test_record_then_replay_gives_the_same_reply_without_a_call(tmp_path):
    live = counting()
    rec = CachedLLM(live, tmp_path, "record")
    first = rec.chat_messages(MSG, max_tokens=100)
    again = rec.chat_messages(MSG, max_tokens=100)            # record mode reuses a stored reply
    assert (first.content, again.content, again.cached, len(live.calls)) == ("reply 0", "reply 0", True, 1)
    other = counting()
    rep = CachedLLM(other, tmp_path, "replay")
    assert rep.chat_messages(MSG, seed=7, max_tokens=100).content == "reply 0" and other.calls == []   # seed not keyed
    with pytest.raises(CacheMiss):
        rep.chat_messages(MSG, max_tokens=200)                  # a different max_tokens is a different key
    assert other.calls == []                                     # never a live call
    [f] = list((tmp_path / "llm").rglob("*.json"))
    saved = json.loads(f.read_text())
    assert saved["messages"] == MSG and saved["response"]["content"] == "reply 0" and saved["max_tokens"] == 100


def test_namespace_and_off_mode(tmp_path):
    live = counting()
    CachedLLM(live, tmp_path, "record", namespace="rep0").chat_messages(MSG)
    CachedLLM(live, tmp_path, "record", namespace="rep1").chat_messages(MSG)   # a repeat is not collapsed
    CachedLLM(live, tmp_path, "off").chat_messages(MSG)
    CachedLLM(live, tmp_path, "off").chat_messages(MSG)
    assert len(live.calls) == 4 and len(list((tmp_path / "llm").rglob("*.json"))) == 2


def test_web_results_replay_without_the_provider(tmp_path):
    made = []
    rec = CachedProvider(lambda: made.append(1) or FakeProvider(), tmp_path, "record")
    assert rec.search("RDS price", 3)[0]["url"] == "https://ex.com/1" and rec.fetch("https://ex.com/1")["title"] == "Page"
    boom = CachedProvider(lambda: (_ for _ in ()).throw(AssertionError("no live provider in replay")), tmp_path, "replay")
    assert boom.search("RDS price", 3)[0]["url"] == "https://ex.com/1" and boom.fetch("https://ex.com/1")["title"] == "Page"
    with pytest.raises(CacheMiss):
        boom.search("something new", 3)
    assert made == [1]
    web = web_registry(boom)
    with pytest.raises(CacheMiss):                               # not turned into a tool error string
        web.execute("web_search", "something new")


def test_a_replay_miss_stops_the_run_cleanly(tmp_path, envelope, tools):
    task = ToyTaskSource(0, 1).tasks()[0]
    r = run_one(task, "flat", CachedLLM(toy_mock_client(), tmp_path / "cache", "replay"), envelope, tools,
                tmp_path / "runs")
    assert r.error.startswith("cache_miss: no cached reply") and r.answer is None
    assert (tmp_path / "runs" / r.run_id / "result.json").exists()


def test_cli_record_then_replay_is_identical_and_traced(tmp_path, capsys):
    args = ["--toy", "--n", "2", "--llm-cache", str(tmp_path / "c")]
    main(args + ["--runs-dir", str(tmp_path / "a")])
    main(args + ["--llm-cache-mode", "replay", "--runs-dir", str(tmp_path / "b")])
    answers = lambda d: sorted(json.loads(p.read_text())["answer"] for p in (tmp_path / d).glob("*/result.json"))
    assert answers("a") == answers("b") and all(answers("b"))
    spans = [json.loads(l) for p in (tmp_path / "b").glob("*/trace.jsonl") for l in p.read_text().splitlines()]
    chats = [s for s in spans if s["name"] == "chat"]
    assert chats and all(s.get("amoeba.cache_hit") for s in chats)
