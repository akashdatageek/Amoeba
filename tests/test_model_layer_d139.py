"""D139 — the model layer's remaining audit items on top of D134: every structured field required (optional ones
nullable), replies validated in code with enum case ignored and provider nulls falling back to defaults, the step
prompt's stable head cached, and one compact retry for a non-reasoning block. Offline."""
from typing import Literal

from pydantic import BaseModel, Field

from amoeba.interp.step_protocol import FINAL, check_args, final_text
from amoeba.interp.trace import TracedLLM, TraceWriter
from amoeba.llm.anthropic_client import to_claude_schema
from amoeba.llm.client import ChatResponse, LLMClient, validate_reply
from tests.test_anthropic_d134 import SPEC, fake, reply, text


class Pick(BaseModel):
    choice: Literal["KEEP", "DROP"]
    reason: str = ""
    score: int | None = None
    tags: list[str] = Field(default_factory=list, min_length=0)


def test_every_field_is_required_and_optional_ones_are_nullable():
    s = to_claude_schema(Pick)
    assert s["required"] == ["choice", "reason", "score", "tags"]
    assert {"type": "null"} in s["properties"]["reason"]["anyOf"]
    assert s["properties"]["score"]["anyOf"].count({"type": "null"}) == 1        # already nullable: not doubled
    assert s["properties"]["choice"] == {"enum": ["KEEP", "DROP"], "type": "string"}


def test_replies_are_validated_in_code_enum_case_and_nulls():
    assert validate_reply(Pick, {"choice": "keep", "reason": None, "score": None, "tags": None}) == \
        {"choice": "KEEP", "reason": "", "score": None, "tags": []}
    assert validate_reply(Pick, {"choice": "maybe"}) is None
    final = {"status": "Done", "output": "x", "blocked": None, "missing_data": None, "missing_input": None,
             "not_needed": None, "verdict": "pass", "issues": None}
    assert check_args(FINAL, final, {}) is None and final_text(final).startswith("Verdict: PASS")


def test_the_stable_head_of_a_step_prompt_is_cached():
    c, sent = fake(reply(text("ok")))
    user = "You are carrying out one step.\n# Task\nT\n# Your role card\nCard\n# Work done so far in this step\nturn 3"
    c.chat_messages([{"role": "system", "content": "S"}, {"role": "user", "content": user}], tools=[SPEC],
                    cache_prefix=True)
    blocks = sent.sent[0]["messages"][-1]["content"]
    assert blocks[0]["cache_control"] == {"type": "ephemeral"} and blocks[0]["text"].endswith("Card")
    assert blocks[1]["text"].startswith("\n# Work done so far") and "cache_control" not in blocks[1]
    assert sum("cache_control" in str(x) for x in (sent.sent[0]["system"], sent.sent[0]["tools"][-1])) == 2
    c2, sent2 = fake(reply(text("ok")))
    c2.chat_messages([{"role": "user", "content": user}])                       # no cache_prefix: one block
    assert len(sent2.sent[0]["messages"][-1]["content"]) == 1


class BlockOnce(LLMClient):
    model = "stub"

    def __init__(self, category):
        self.category, self.seen = category, []

    def chat_messages(self, messages, seed=0, max_tokens=None, **kw):
        self.seen.append(messages[-1]["content"])
        if len(self.seen) == 1:
            return ChatResponse("", finish_reason="refusal", refusal_category=self.category)
        return ChatResponse("fine", 10, 2, finish_reason="stop")


def test_a_non_reasoning_block_gets_one_compact_retry():
    tr, stub = TraceWriter(None), BlockOnce("general_harms")
    r = TracedLLM(stub, tr).chat_messages([{"role": "user", "content": "full"}],
                                          compact=[{"role": "user", "content": "compact"}])
    assert r.content == "fine" and stub.seen == ["full", "compact"] and tr.events("compact_retry")
    tr2, stub2 = TraceWriter(None), BlockOnce("reasoning_extraction")
    TracedLLM(stub2, tr2).chat_messages([{"role": "user", "content": "full"}],
                                        compact=[{"role": "user", "content": "compact"}])
    assert stub2.seen == ["full"] and not tr2.events("compact_retry")             # the prompt's fault: no retry
    tr3, stub3 = TraceWriter(None), BlockOnce("cyber")
    TracedLLM(stub3, tr3).chat_messages([{"role": "user", "content": "full"}])
    assert stub3.seen == ["full"]                                                 # no compact variant: no retry
