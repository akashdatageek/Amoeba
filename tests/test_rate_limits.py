"""D48 — HTTP 429/503 are retried with exponential waits or the server's Retry-After (max 5), traced; a spending-cap
429 is not retried; --min-seconds-between-calls spaces calls out. No network: the SDK client is faked."""
import pytest

from amoeba.interp.trace import TracedLLM, TraceWriter
from amoeba.llm.client import OpenAICompatibleClient


class ApiError(Exception):
    def __init__(self, status, msg="", retry_after=None):
        super().__init__(msg or f"Error code: {status}")
        self.status_code = status
        self.response = type("Resp", (), {"headers": {"retry-after": retry_after} if retry_after else {}})()


def client(script, **kw):
    """An OpenAICompatibleClient whose SDK call raises / answers from `script`; sleeps are recorded, not slept."""
    slept, sent = [], []

    class Completions:
        def create(self, **k):
            sent.append(k)
            item = script.pop(0)
            if isinstance(item, Exception):
                raise item
            msg = type("M", (), {"content": item})
            return type("R", (), {"choices": [type("C", (), {"message": msg, "finish_reason": "stop"})], "model": "m",
                                  "usage": type("U", (), {"prompt_tokens": 3, "completion_tokens": 1})})

    c = OpenAICompatibleClient(base_url="http://x", api_key="k", model="m", sleep=slept.append, **kw)
    c._client = type("O", (), {"chat": type("Ch", (), {"completions": Completions()})})
    c.sends_seed = False
    return c, slept, sent


def test_429_and_503_are_retried_with_backoff_or_retry_after_and_traced():
    c, slept, sent = client([ApiError(429, retry_after="7"), ApiError(503), ApiError(429), "ok"])
    trace = TraceWriter(None)
    r = TracedLLM(c, trace).chat("s", "u")
    assert r.content == "ok" and slept == [7.0, 4.0, 8.0] and len(sent) == 4       # Retry-After, then 2·2^n
    assert [x["status"] for x in r.retries] == [429, 503, 429]
    evs = trace.events("rate_limited")
    assert [(e["http.status_code"], e["amoeba.wait_s"], e["amoeba.gave_up"]) for e in evs] == [
        (429, 7.0, False), (503, 4.0, False), (429, 8.0, False)]
    assert trace.spans("chat")[0]["amoeba.rate_limit_retries"] == 3


def test_it_gives_up_after_five_retries_and_the_waits_are_still_traced():
    c, slept, _ = client([ApiError(503)] * 6)
    trace = TraceWriter(None)
    with pytest.raises(ApiError):
        TracedLLM(c, trace).chat("s", "u")
    assert slept == [2.0, 4.0, 8.0, 16.0, 32.0]
    assert [e["amoeba.gave_up"] for e in trace.events("rate_limited")] == [True] * 5


def test_a_spending_cap_and_other_errors_are_not_retried():
    cap = ApiError(429, "Your project has exceeded its monthly spending cap. RESOURCE_EXHAUSTED")
    c, slept, _ = client([cap])
    with pytest.raises(ApiError):
        c.chat("s", "u")
    c2, slept2, _ = client([ApiError(500)])
    with pytest.raises(ApiError):
        c2.chat("s", "u")
    assert slept == [] and slept2 == []


def test_min_seconds_between_calls_spaces_calls_out():
    c, slept, _ = client(["a", "b"], min_seconds_between_calls=5.0)
    first, second = c.chat("s", "u"), c.chat("s", "u")
    assert first.throttle_wait_s == 0 and len(slept) == 1 and 4.5 < slept[0] <= 5.0 and second.throttle_wait_s > 4.5
