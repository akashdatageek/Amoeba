"""D24/D27 — per-call max_tokens, one retry with double room on finish_reason 'length', reasoning tokens."""
from dataclasses import replace

from amoeba.llm.client import MockLLMClient, OpenAICompatibleClient, _reasoning_tokens
from amoeba.task.draft import OBSERVER_MAX_TOKENS, PLANNER_MAX_TOKENS, draft_team, token_limits
from scripts.eval_draft import attempt
from scripts.run_task import cli_token_limits, parse_args
from tests.conftest import fx, mock

OK = fx("observer_no_suggestions")


def test_every_drafting_role_gets_8192_by_default(task, envelope, trace):
    llm = mock(planner=[fx("draft_round_ok")])
    draft_team(task, llm, envelope, trace)
    assert PLANNER_MAX_TOKENS == OBSERVER_MAX_TOKENS == 8192
    assert [c["max_tokens"] for c in llm.calls] == [8192, 8192, 8192]
    assert [s["gen_ai.request.max_tokens"] for s in trace.spans("chat")] == [8192, 8192, 8192]
    assert all(s["gen_ai.response.finish_reasons"] == ["stop"] for s in trace.spans("chat"))
    assert trace.events("truncated") == []


def test_limits_per_role_from_env_and_cli(monkeypatch, task, envelope, trace):
    monkeypatch.setenv("AMOEBA_MAX_TOKENS_OBSERVER", "3000")
    monkeypatch.setenv("AMOEBA_MAX_TOKENS_PLAN_OBSERVER", "4000")
    assert token_limits() == {"planner": 8192, "agent_observer": 3000, "plan_observer": 4000}
    assert token_limits({"planner": 16000, "plan_observer": None}) == \
        {"planner": 16000, "agent_observer": 3000, "plan_observer": 4000}
    args = parse_args(["--toy", "--planner-max-tokens", "12000", "--observer-max-tokens", "6000"])
    assert cli_token_limits(args) == {"planner": 12000, "agent_observer": 6000, "plan_observer": 6000}
    llm = mock(planner=[fx("draft_round_ok")])
    draft_team(task, llm, envelope, trace, max_tokens=cli_token_limits(args))
    assert [c["max_tokens"] for c in llm.calls] == [12000, 6000, 6000]


class CutOff(MockLLMClient):
    """Reports finish_reason 'length' for the planner (every time), as an API does at max_tokens."""

    def chat_messages(self, messages, seed=0, max_tokens=None):
        resp = super().chat_messages(messages, seed, max_tokens=max_tokens)
        return replace(resp, finish_reason="length", reasoning_tokens=900, reasoning_source="total_minus_visible") \
            if self.calls[-1]["kind"] == "planner" else resp


def cutoff():
    return CutOff(script={"planner": [fx("draft_round_ok")], "agent_observer": [OK], "plan_observer": [OK]})


def test_a_cut_off_reply_is_retried_once_with_double_room_and_both_are_traced(task, envelope, trace, tmp_path):
    llm = cutoff()
    draft_team(task, llm, envelope, trace)
    assert [c["max_tokens"] for c in llm.calls_of("planner")] == [8192, 16384]    # one retry, then accepted
    first, second = trace.events("truncated")
    assert first["amoeba.retry"] is True and second["amoeba.retry"] is False
    chats = trace.spans("chat")
    assert chats[0]["amoeba.truncated"] and chats[1]["amoeba.retry_of_truncated"] is True
    assert chats[0]["amoeba.usage.reasoning_tokens"] == 900 and trace.total_reasoning_tokens == 1800
    row = attempt(task, 0, cutoff(), envelope, tmp_path, 0)
    assert row["truncated"] == 2 and row["truncation_retries"] == 1 and row["reasoning_tokens"] == 1800


def test_reasoning_tokens_reported_or_inferred():
    u = lambda **k: type("U", (), k)
    details = type("D", (), {"reasoning_tokens": 120})
    assert _reasoning_tokens(u(completion_tokens_details=details, total_tokens=500, prompt_tokens=10,
                               completion_tokens=20)) == (120, "reported")
    # Gemini's OpenAI layer (checked 2026-09-24): details null, total 407 = 11 + 15 visible + 381 hidden
    assert _reasoning_tokens(u(completion_tokens_details=None, total_tokens=407, prompt_tokens=11,
                               completion_tokens=15)) == (381, "total_minus_visible")
    assert _reasoning_tokens(u(completion_tokens_details=None, total_tokens=26, prompt_tokens=11,
                               completion_tokens=15)) == (0, None)
    assert _reasoning_tokens(None) == (0, None)


def test_openai_client_sends_the_per_call_limit_and_reads_finish_reason_and_reasoning():
    sent = []

    class Completions:
        def create(self, **kw):
            sent.append(kw)
            msg = type("M", (), {"content": "ok"})
            choice = type("C", (), {"message": msg, "finish_reason": "length"})
            return type("R", (), {"choices": [choice], "model": "m",
                                  "usage": type("U", (), {"prompt_tokens": 3, "completion_tokens": 1,
                                                          "total_tokens": 54, "completion_tokens_details": None})})

    c = OpenAICompatibleClient(base_url="http://x", api_key="k", model="m")
    c._client = type("O", (), {"chat": type("Ch", (), {"completions": Completions()})})
    r = c.chat("s", "u", max_tokens=8192)
    assert (r.finish_reason, r.reasoning_tokens, r.reasoning_source) == ("length", 50, "total_minus_visible")
    c.chat("s", "u")
    assert [k["max_tokens"] for k in sent] == [8192, 2048]
