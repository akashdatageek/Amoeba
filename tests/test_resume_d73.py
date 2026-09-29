"""D73 — crash resilience: HTTP 500/502/504 are retried like 429/503 (same waits, same cap), and a crashed run is
resumable: rerun with the same cache namespace, it replays every finished call from the cache and pays only for the
rest. Offline, with the mock LLM and a fake web provider."""
import re

import pytest

import amoeba.tools.web as web_module
from amoeba.interp.trace import TracedLLM, TraceWriter
from amoeba.llm.cache import CachedLLM, CachedProvider
from amoeba.llm.client import LLMClient
from amoeba.task.models import Task
from amoeba.tools.web import web_registry
from scripts.run_task import run_one
from tests.conftest import fx, mock
from tests.test_rate_limits import ApiError, client
from tests.test_web_tools import FakeProvider

APPROVE = fx("observer_d24_approve")


@pytest.mark.parametrize("status", [500, 502, 504])
def test_server_errors_are_retried_with_the_same_waits_and_cap(status):
    c, slept, sent = client([ApiError(status), ApiError(status), "ok"])
    trace = TraceWriter(None)
    r = TracedLLM(c, trace).chat("s", "u")
    assert r.content == "ok" and slept == [2.0, 4.0] and len(sent) == 3
    assert [e["http.status_code"] for e in trace.events("rate_limited")] == [status, status]
    c2, slept2, _ = client([ApiError(status)] * 6)                        # the cap is the same: 5 retries
    with pytest.raises(ApiError):
        c2.chat("s", "u")
    assert slept2 == [2.0, 4.0, 8.0, 16.0, 32.0]


def worker(messages, seed):
    """Step 1 searches, then fetches S1, then answers; the other steps answer at once."""
    user = messages[-1]["content"]
    n = re.search(r"# Your step \(step (\d+)\)", user).group(1)
    if n == "1" and "[S1]" not in user:
        return "## Thought\ns\n\n## CurrentStep\ns\n\n## Action\nweb_search\n\n## ActionInput\nRDS price\n"
    if n == "1" and ", fetched " not in user:
        return "## Thought\ns\n\n## CurrentStep\ns\n\n## Action\nfetch_url\n\n## ActionInput\nS1\n"
    return f"## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\nStep {n}: storage is " \
           f"$0.115 per GB-month [S1]\n"


class Flaky(LLMClient):
    """Passes calls to the mock; call number `fail_at` (and every retry of it) answers HTTP 500 — a lasting outage."""

    def __init__(self, inner, fail_at=None):
        self.inner, self.model, self.fail_at, self.n = inner, inner.model, fail_at, 0
        self.temperature = getattr(inner, "temperature", None)

    def chat_messages(self, messages, seed=0, max_tokens=None):
        self.n += 1
        if self.fail_at is not None and self.n >= self.fail_at:
            raise ApiError(500, "Internal error encountered.")
        return self.inner.chat_messages(messages, seed, max_tokens=max_tokens)


def team():
    return mock(planner=[fx("draft_d24_full")], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=worker)


def run(tmp_path, cache, inner, env, fail_at=None, runs="runs"):
    llm = CachedLLM(Flaky(inner, fail_at), cache, "record", namespace="ns")
    web = web_registry(CachedProvider(FakeProvider, cache, "record", namespace="ns"))
    return run_one(Task(prompt="Estimate the monthly cost for 50 tenants at 200 GB each.", id="t"), "plan", llm,
                   env, web, tmp_path / runs, draft_prompts="d24")


def test_a_crashed_run_resumes_from_the_cache_and_never_pays_for_finished_work(tmp_path, monkeypatch, envelope):
    clean = team()                                         # the same run without an outage: how many calls it needs
    monkeypatch.setattr(web_module, "now_iso", lambda: "2026-09-28T20:56:53+00:00")
    ok = run(tmp_path, tmp_path / "clean_cache", clean, envelope)
    total = len(clean.calls)
    assert not str(ok.error or '').startswith('api') and total >= 8

    first = team()
    crashed = run(tmp_path, tmp_path / "cache", first, envelope, fail_at=7)          # a lasting HTTP 500 on the 7th call
    assert crashed.error.startswith("api: ApiError 500") and len(first.calls) == 6

    monkeypatch.setattr(web_module, "now_iso", lambda: "2026-09-28T21:03:11+00:00")   # the rerun is minutes later
    second = team()
    resumed = run(tmp_path, tmp_path / "cache", second, envelope, runs="runs2")
    assert (resumed.error, resumed.answer) == (ok.error, ok.answer)   # the same run, finished
    assert len(second.calls) == total - 6                  # the six finished calls replayed; only the rest was paid


def test_a_cached_page_keeps_the_time_it_was_really_fetched(tmp_path, monkeypatch):
    monkeypatch.setattr(web_module, "now_iso", lambda: "T1")
    rec = CachedProvider(FakeProvider, tmp_path, "record")
    assert rec.fetch("https://ex.com/1")["fetched_at"] == "T1"
    assert all(r["fetched_at"] == "T1" for r in rec.search("q", 3))
    monkeypatch.setattr(web_module, "now_iso", lambda: "T2")
    web = web_registry(CachedProvider(FakeProvider, tmp_path, "record")).web
    web.begin_step(1)
    assert ", fetched T1" in web.fetch_url("https://ex.com/1")            # the replayed page shows its real time
