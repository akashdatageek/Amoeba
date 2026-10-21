"""D160 — Gemma quota handling: a per-minute quota is waited out and retried (the wait the reply asks for); a daily
quota is never retried — the run stops cleanly with status quota_exhausted, saves what it needs, and
`run_task --resume <run_id>` continues another day without paying again for finished calls. Offline: a mock client
that answers daily-quota errors."""
import json
from datetime import date

import pytest

import scripts.run_task as rt
from amoeba.llm.cache import CachedLLM
from amoeba.llm.client import LLMClient, quota_exhausted
from amoeba.task.models import Task, run_status
from tests.conftest import fx, mock
from tests.test_preflight_d156 import PER_DAY, PER_MINUTE
from tests.test_rate_limits import ApiError, client

APPROVE = fx("observer_d24_approve")
TASK = "Estimate the monthly cost for 50 tenants at 200 GB each."


def test_a_per_minute_quota_waits_as_long_as_the_reply_asks_then_retries():
    c, slept, sent = client([ApiError(429, PER_MINUTE), "ok"])
    assert c.chat("s", "u").content == "ok" and slept == [39.0] and len(sent) == 2


def test_a_daily_quota_is_not_retried():
    c, slept, sent = client([ApiError(429, PER_DAY), "ok"])
    with pytest.raises(ApiError) as e:
        c.chat("s", "u")
    assert slept == [] and len(sent) == 1 and quota_exhausted(e.value)
    assert e.value.amoeba_quota["kind"] == "daily"
    assert not quota_exhausted(ApiError(429, PER_MINUTE)) and not quota_exhausted(ApiError(500))


def test_the_status():
    assert run_status("quota_exhausted: stopped with step(s) 3 not run") == "quota_exhausted"
    assert run_status("quota_exhausted") == "quota_exhausted"


def worker(messages, seed):
    return "## Thought\nok\n\n## CurrentStep\nw\n\n## Action\nFinal Output\n\n## ActionInput\nStorage is $0.115 per GB\n"


def team():
    return mock(planner=[fx("draft_d24_full")], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=worker)


def cli_team():
    """The CLI's defaults call more kinds (a verifier's own answer, critics); any other kind answers like a worker."""
    m = team()
    m._responder = worker
    return m


class DailyQuota(LLMClient):
    """Passes calls to the mock until call `fail_at`; from then on every call answers the daily-quota 429."""

    def __init__(self, inner, fail_at=None):
        self.inner, self.model, self.fail_at, self.n = inner, inner.model, fail_at, 0
        self.temperature = getattr(inner, "temperature", None)

    def chat_messages(self, messages, seed=0, max_tokens=None, **kw):
        self.n += 1
        if self.fail_at is not None and self.n >= self.fail_at:
            e = ApiError(429, PER_DAY)
            from amoeba.llm.quota import parse_quota
            e.amoeba_quota = parse_quota(PER_DAY)                 # as the client marks it, without retrying
            raise e
        return self.inner.chat_messages(messages, seed, max_tokens=max_tokens)


def test_a_daily_quota_mid_plan_stops_the_run_cleanly(tmp_path, envelope, tools):
    r = rt.run_one(Task(prompt=TASK, id="t"), "plan", CachedLLM(DailyQuota(team(), fail_at=7), tmp_path / "c", "record"),
                   envelope, tools, tmp_path / "runs", draft_prompts="d24")
    assert r.status == "quota_exhausted" and r.error.startswith("quota_exhausted")
    res = json.loads((tmp_path / "runs" / r.run_id / "result.json").read_text())
    assert res["status"] == "quota_exhausted"


def test_a_daily_quota_while_planning_stops_cleanly_too(tmp_path, envelope, tools):
    r = rt.run_one(Task(prompt=TASK, id="t"), "plan", DailyQuota(team(), fail_at=1), envelope, tools,
                   tmp_path / "runs", draft_prompts="d24")
    assert r.status == "quota_exhausted"


def test_resume_next_day_pays_only_for_what_was_not_finished(tmp_path, monkeypatch, capsys):
    runs, clients = tmp_path / "runs", []

    def build(args, fail_at=None):
        inner = cli_team()
        clients.append(inner)
        return CachedLLM(DailyQuota(inner, fail_at), args.llm_cache, args.llm_cache_mode, args.llm_cache_namespace)

    clean = cli_team()                                        # how many calls the whole run needs
    monkeypatch.setattr(rt, "build_llm", lambda a: CachedLLM(clean, str(tmp_path / "clean"), "record", "x"))
    monkeypatch.setattr(rt, "run_date", lambda tz=None: date(2026, 10, 21))
    rt.main([TASK, "--topology", "plan", "--draft-prompts", "d24", "--interpret", "off", "--family-classify", "off", "--no-pool", "--adapt", "off", "--runs-dir", str(tmp_path / "clean_runs")])
    total = len(clean.calls)
    clean_res = next(json.loads(f.read_text()) for f in (tmp_path / "clean_runs").glob("*/result.json"))

    monkeypatch.setattr(rt, "build_llm", lambda a: build(a, fail_at=7))
    assert rt.main([TASK, "--topology", "plan", "--draft-prompts", "d24", "--interpret", "off", "--family-classify", "off", "--no-pool", "--adapt", "off", "--runs-dir", str(runs),
                    "--llm-cache", str(tmp_path / "cache")]) == 0
    out = capsys.readouterr().out
    run_id = next(p.name for p in runs.iterdir() if (p / "resume.json").exists())
    saved = json.loads((runs / run_id / "resume.json").read_text())
    assert saved["run_date"] == "2026-10-21" and saved["task"]["prompt"] == TASK and "--resume" in out
    assert len(clients[0].calls) == 6

    monkeypatch.setattr(rt, "run_date", lambda tz=None: date(2026, 10, 22))   # the next day
    monkeypatch.setattr(rt, "build_llm", lambda a: build(a))
    assert rt.main(["--resume", run_id, "--runs-dir", str(runs)]) == 0
    assert len(clients[1].calls) == total - 6                 # the six finished calls replayed; only the rest paid
    new = [json.loads((p / "result.json").read_text()) for p in runs.iterdir()
           if p.name != run_id and (p / "result.json").exists()]
    assert len(new) == 1 and new[0]["status"] == clean_res["status"] and new[0]["resumed_from"] == run_id
    assert new[0]["answer"] == clean_res["answer"]                # the same run, finished


def test_a_live_run_gets_a_cache_so_it_can_resume(tmp_path):
    a = rt.parse_args(["x", "--llm", "openai", "--runs-dir", str(tmp_path)])
    rt.default_cache(a)
    assert a.llm_cache == str(tmp_path / "llm_cache") and a.llm_cache_namespace.startswith("run-")
    m = rt.parse_args(["x", "--runs-dir", str(tmp_path)])            # the mock: unchanged
    rt.default_cache(m)
    assert m.llm_cache is None
    off = rt.parse_args(["x", "--llm", "openai", "--llm-cache-mode", "off"])
    rt.default_cache(off)
    assert off.llm_cache is None
