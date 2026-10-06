"""D111 — an infrastructure failure is status infra_error, never the team's (offline, mock LLM): a run that ended in an
API, connection, proxy, cache or runner error is recorded as infra_error; the LLM client reads the proxy fresh on a
dropped connection, so a proxy that moved cannot silently break a running process. (D117 removed the experiment and
loop parts: retries in the Experimenter, the Monitor and the Gate's reliability rule.)"""
import json

from amoeba.llm.client import OpenAICompatibleClient
from amoeba.config.proxy import fresh_proxy, refresh_proxy
from amoeba.safety.envelope import Envelope
from amoeba.task.models import Task, infra_error, run_status
from amoeba.tools.registry import default_registry
from scripts.run_task import run_one
from tests.conftest import mock
from tests.test_plan_runner import APPROVE, DIAMOND, finish


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
