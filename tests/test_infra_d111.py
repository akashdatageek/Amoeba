"""D111 — an infrastructure failure is status infra_error, never a score (offline, mock LLM): a run that ended in an
API, connection, proxy, cache or runner error is retried (at most adapt.yaml infra.retries), left out of the pairs,
the Monitor and the Gate's reliability rule (which counts agent errors only), and logged; the LLM client and the
harness read the proxy fresh on a dropped connection, so a proxy that moved cannot silently break a running process."""
import json

from amoeba.adapt.experimenter import InProcessRunner, RunRecord, SubprocessRunner, _scored_pairs, experiment, infra_cfg
from amoeba.adapt.gate import honesty_shares
from amoeba.adapt.monitor import LoopState, PracticeRecord, monitor
from amoeba.adapt.recipe import seed_recipe
from amoeba.llm.client import OpenAICompatibleClient
from amoeba.config.proxy import fresh_proxy, refresh_proxy
from amoeba.safety.envelope import Envelope
from amoeba.task.models import Task, infra_error, run_status
from amoeba.tools.registry import default_registry
from scripts.run_task import run_one
from tests.conftest import mock
from tests.test_plan_runner import APPROVE, DIAMOND, finish
from tests.test_loop_d89 import NUM
from tests.test_retention_d100 import plain_stream


class APIConnectionError(Exception):          # matched by class name, like the SDK's (amoeba.llm.client.dropped)
    pass


def test_status_classes():
    assert run_status(None) == "ok"
    for e in ("api: APIConnectionError: Connection error.", "api: APITimeoutError: timed out",
              "api: RateLimitError 429: quota", "api: InternalServerError 503: busy", "cache_miss: x",
              "runner: rc=-9"):
        assert run_status(e) == "infra_error" and infra_error(e), e
    for e in ("api: BadRequestError 400: too long", "budget", "draft: no plan", "max_calls"):
        assert run_status(e) == "agent_error", e
    assert infra_cfg() == {"retries": 2, "exclude": True}


def lost(messages, seed):
    raise APIConnectionError("Connection error.")


def test_result_json_records_the_status(tmp_path):
    reg = default_registry()
    broken = mock(planner=lost)
    r = run_one(Task(id="t", prompt="Compute 2 + 2."), "plan", broken, Envelope.from_registry(reg), reg, tmp_path,
                draft_prompts="d24")
    res = json.loads((tmp_path / r.run_id / "result.json").read_text())
    assert res["error"].startswith("api: APIConnectionError") and res["status"] == "infra_error"
    ok = run_one(Task(id="t", prompt="Compute 2 + 2."), "plan",
                 mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=finish),
                 Envelope.from_registry(reg), reg, tmp_path, draft_prompts="d24")
    assert json.loads((tmp_path / ok.run_id / "result.json").read_text())["status"] == "ok"


class Flaky(InProcessRunner):
    def __init__(self, fails):
        super().__init__(lambda job: None)
        self.fails, self.calls = fails, {}

    def run(self, jobs):
        out = []
        for job in jobs:
            n = self.calls.setdefault((job.arm, job.task.id, job.k), [0])
            self.llm_for = self._llm(n)
            out += super().run([job])
        return out

    def _llm(self, n):
        def make(job):
            n[0] += 1
            if n[0] <= self.fails:
                return mock(planner=lost)
            return mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=finish)
        return make


def test_an_infra_error_is_retried_and_then_scored(tmp_path):
    s = plain_stream(3)
    runner = Flaky(fails=2)                                   # two lost connections, then fine: within the 2 retries
    res = experiment(seed_recipe("calc"), __import__("tests.test_retention_d100", fromlist=["RULE"]).RULE, "h1", s,
                     runner, tmp_path, repeats=1, slices=("post",))
    assert res.excluded == [] and len(res.pairs) == 2
    assert all(n[0] == 3 for n in runner.calls.values())      # 1 + 2 retries each
    assert all(p.error_A is None and p.error_B is None for p in res.pairs)


def test_still_infra_after_the_retries_is_left_out_and_logged(tmp_path):
    s = plain_stream(3)
    runner = Flaky(fails=99)
    from tests.test_retention_d100 import RULE
    res = experiment(seed_recipe("calc"), RULE, "h1", s, runner, tmp_path, repeats=1, slices=("post",))
    assert res.pairs == [] and len(res.excluded) == 2
    assert res.excluded[0]["status"] == "infra_error" and res.excluded[0]["arms"]["A"].startswith("api:")
    assert all(n[0] == 3 for n in runner.calls.values())
    saved = json.loads((tmp_path / "experiments" / "h1" / "experiment.json").read_text())
    assert len(saved["excluded"]) == 2


def rec(arm, error=None, run_dir="x", score=1.0):
    return RunRecord(arm=arm, task_id="t", k=0, seed=0, run_dir=run_dir, score=score, error=error)


def test_pairs_leave_out_infra_and_the_reliability_rule_counts_agent_errors_only():
    from amoeba.adapt.stream import StreamTask
    t = StreamTask(id="t", prompt="p", family="calc", split="heldout", phase="post", rubric=NUM)
    pairs, ex = _scored_pairs([t], 1, {("t", 0): rec("A")}, {("t", 0): rec("B", "api: APIConnectionError: x", score=0)})
    assert pairs == [] and ex[0]["arms"] == {"B": "api: APIConnectionError: x"}
    pairs, _ = _scored_pairs([t], 1, {("t", 0): rec("A")}, {("t", 0): rec("B", "budget", score=0)})
    assert len(pairs) == 1                                                    # an agent error is the team's: scored
    p = pairs[0]
    infra = p.model_copy(update={"error_B": "api: InternalServerError 503: busy"})
    assert honesty_shares([p])[3] == 1.0 and honesty_shares([infra])[3] == 0.0


def test_the_monitor_never_sees_an_infra_run():
    ok = [PracticeRecord(order=i, task_id=f"p{i}", family="calc", score=1.0) for i in range(1, 8)]
    bad = [PracticeRecord(order=i, task_id=f"p{i}", family="calc", score=None, status="infra_error")
           for i in range(8, 11)]
    assert monitor(ok + bad, LoopState(family="calc")) is None                # three lost runs raise no score alarm
    assert monitor(ok + [r.model_copy(update={"status": None}) for r in bad], LoopState(family="calc")) is not None


def test_the_proxy_is_read_fresh(tmp_path, monkeypatch):
    f = tmp_path / "README.md"
    f.write_text("Outbound HTTPS goes through a local proxy at http://127.0.0.1:43843\n(set via HTTPS_PROXY)\n")
    env = {"AMOEBA_PROXY_FILE": str(f), "HTTPS_PROXY": "http://127.0.0.1:40713",
           "https_proxy": "http://127.0.0.1:40713", "YARN_HTTPS_PROXY": "http://127.0.0.1:40713", "OTHER": "1"}
    assert fresh_proxy(env) == "http://127.0.0.1:43843"
    assert refresh_proxy(env) == "http://127.0.0.1:43843"
    assert env["HTTPS_PROXY"] == env["https_proxy"] == env["YARN_HTTPS_PROXY"] == "http://127.0.0.1:43843"
    assert refresh_proxy(env) is None and env["OTHER"] == "1"                 # unchanged: nothing to do
    f.write_text("export HTTPS_PROXY=http://10.0.0.5:3128\n")
    assert fresh_proxy(env) == "http://10.0.0.5:3128"
    assert fresh_proxy({"HTTPS_PROXY": "x"}) is None                          # unset: nothing changes


def test_the_client_reconnects_through_the_new_proxy(tmp_path, monkeypatch):
    f = tmp_path / "proxy"
    f.write_text("HTTPS_PROXY=http://127.0.0.1:2222\n")
    monkeypatch.setenv("AMOEBA_PROXY_FILE", str(f))
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1111")

    class Resp:
        usage = None
        model = "m"
        choices = [type("C", (), {"message": type("M", (), {"content": "hi"})(), "finish_reason": "stop"})()]

    class Dead:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    raise APIConnectionError("Connection error.")

    class Alive:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    return Resp()

    c = OpenAICompatibleClient(base_url="http://127.0.0.1:9/v1", api_key="k", model="m", sleep=lambda s: None)
    c._client, c._connect = Dead(), Alive
    out = c.chat_messages([{"role": "user", "content": "x"}])
    assert out.content == "hi" and out.retries[0]["proxy_refreshed"] is True
    import os
    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:2222"


def test_the_harness_hands_each_run_the_fresh_proxy(tmp_path, monkeypatch):
    f = tmp_path / "proxy"
    f.write_text("HTTPS_PROXY=http://127.0.0.1:2222\n")
    seen = []

    def fake_run(cmd, cwd, env, stdout, stderr):
        seen.append(env["HTTPS_PROXY"])
        return type("R", (), {"returncode": 1})()
    monkeypatch.setattr("amoeba.adapt.experimenter.subprocess.run", fake_run)
    from amoeba.adapt.experimenter import Job
    from amoeba.adapt.stream import StreamTask
    r = SubprocessRunner([], env={"AMOEBA_PROXY_FILE": str(f), "HTTPS_PROXY": "http://127.0.0.1:1111"},
                         scratch=tmp_path / "s", log=lambda m: None)
    job = Job(arm="A", task=StreamTask(id="t", prompt="p", family="calc", split="heldout", phase="post", rubric=NUM), k=0, seed=0,
              store=tmp_path / "st", out=tmp_path / "out", namespace="n")
    got = r._one(job)
    assert got.crashed() and got.error == "runner: rc=1" and len(seen) == 3   # no result: retried twice, then infra
    assert set(seen) == {"http://127.0.0.1:2222"}
