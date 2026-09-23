"""D24 step 6 — per-call max_tokens (Planner 8192) and a trace flag when a reply stops at the limit."""
from dataclasses import replace

from amoeba.llm.client import MockLLMClient, OpenAICompatibleClient
from amoeba.task.draft import OBSERVER_MAX_TOKENS, PLANNER_MAX_TOKENS, draft_team
from scripts.eval_draft import attempt
from tests.conftest import fx, mock


def test_planner_asks_for_more_tokens_than_the_observers(task, envelope, trace):
    llm = mock(planner=[fx("draft_round_ok")])
    draft_team(task, llm, envelope, trace)
    assert PLANNER_MAX_TOKENS == 8192 and OBSERVER_MAX_TOKENS == 2048
    assert [c["max_tokens"] for c in llm.calls] == [8192, 2048, 2048]
    assert [s["gen_ai.request.max_tokens"] for s in trace.spans("chat")] == [8192, 2048, 2048]
    assert all(s["gen_ai.response.finish_reasons"] == ["stop"] for s in trace.spans("chat"))
    assert trace.events("truncated") == []


class CutOff(MockLLMClient):
    """Reports finish_reason 'length' for the planner, as an API does when max_tokens is reached."""

    def chat_messages(self, messages, seed=0, max_tokens=None):
        resp = super().chat_messages(messages, seed, max_tokens=max_tokens)
        return replace(resp, finish_reason="length") if self.calls[-1]["kind"] == "planner" else resp


def test_a_cut_off_reply_is_flagged(task, envelope, trace, tmp_path):
    llm = CutOff(script={"planner": [fx("draft_round_ok")], "agent_observer": [fx("observer_no_suggestions")],
                         "plan_observer": [fx("observer_no_suggestions")]})
    draft_team(task, llm, envelope, trace)
    [ev] = trace.events("truncated")
    assert ev["gen_ai.agent.name"] == "planner" and ev["gen_ai.request.max_tokens"] == 8192
    assert trace.spans("chat")[0]["amoeba.truncated"] is True and "amoeba.truncated" not in trace.spans("chat")[1]
    row = attempt(task, 0, CutOff(script={"planner": [fx("draft_round_ok")],
                                          "agent_observer": [fx("observer_no_suggestions")],
                                          "plan_observer": [fx("observer_no_suggestions")]}), envelope, tmp_path, 0)
    assert row["truncated"] == 1


def test_openai_client_sends_the_per_call_limit_and_reads_finish_reason():
    sent = []

    class Completions:
        def create(self, **kw):
            sent.append(kw)
            msg = type("M", (), {"content": "ok"})
            choice = type("C", (), {"message": msg, "finish_reason": "length"})
            return type("R", (), {"choices": [choice], "model": "m",
                                  "usage": type("U", (), {"prompt_tokens": 3, "completion_tokens": 1})})

    c = OpenAICompatibleClient(base_url="http://x", api_key="k", model="m")
    c._client = type("O", (), {"chat": type("Ch", (), {"completions": Completions()})})
    assert c.chat("s", "u", max_tokens=8192).finish_reason == "length"
    c.chat("s", "u")
    assert [k["max_tokens"] for k in sent] == [8192, 2048]
