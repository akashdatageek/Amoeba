"""D87 — Box 6, the Architect: invalid JSON is retried once; a disallowed edit, a repeat of a failed edit and a leaked
held-out phrase are all refused; the prompt carries the diagnosis, recipe, allowed edits with their shapes, the failed
list and practice examples — never held-out text. Offline (mock LLM)."""
import json

from amoeba.adapt.architect import build_prompt, log_unresolved, propose
from amoeba.adapt.diagnoser import Diagnosis
from amoeba.adapt.recipe import seed_recipe
from amoeba.adapt.stream import StreamTask
from amoeba.interp.trace import TraceWriter
from amoeba.llm.client import MockLLMClient

D = Diagnosis(family="calc", symptom="feedback: assumptions section missing in 3/3 runs", cause="feedback",
              where={"last_work_step": True}, evidence=["run9/result.json rubric failed item 'assumptions section'"],
              allowed_edits=["add_planner_rule", "tighten_done_when", "add_role_rule"],
              examples=[{"task": "A practice task about paint.", "step": 3, "do": "write the answer", "output": "memo",
                         "done_when": "answer written", "evidence": ["x"], "score": 0.75}])
HELD = [StreamTask(id="m1-calc-hpost-6", prompt="A car is rented for 9 days at $47 a day, with insurance at $12 a day.",
                   family="calc", split="heldout", phase="post",
                   rubric={"expected_numbers": [{"name": "total", "value": 657, "unit": "USD"}]})]
GOOD = json.dumps({"edit": {"op": "add_planner_rule", "params": {"text": "End every answer with a short section "
                                                                          "headed Assumptions."}},
                   "rationale": "The feedback names a missing assumptions section.", "predicted_delta": 0.2})


def go(*replies, failed=()):
    llm = MockLLMClient(script={"architect": list(replies)})
    h, rec = propose(D, seed_recipe("calc"), list(failed), HELD, llm, TraceWriter(None, episode_id="t"), "h-a10-1")
    return llm, h, rec


def test_a_valid_reply_becomes_a_hypothesis():
    llm, h, rec = go(GOOD)
    assert h.hypothesis_id == "h-a10-1" and h.edit.op == "add_planner_rule" and h.predicted_delta == 0.2
    assert len(rec["attempts"]) == 1 and llm.calls[0]["kind"] == "architect"


def test_invalid_json_is_retried_once_with_the_error_shown():
    llm, h, rec = go("Here is my idea: add a rule.", GOOD)
    assert h is not None and len(rec["attempts"]) == 2
    assert "refused by the checks" in llm.calls[1]["messages"][-1]["content"]
    llm, h, rec = go("no json", "still none")
    assert h is None and rec["no_hypothesis"] and len(llm.calls) == 2           # one retry, then it gives up


def test_a_disallowed_edit_is_refused():
    bad = json.dumps({"edit": {"op": "grant_tool", "params": {"select": {"all_roles": True}, "tool": "calc"}},
                      "rationale": "x", "predicted_delta": 0.1})
    _, h, rec = go(bad, bad)
    assert h is None and "not allowed for cause 'feedback'" in rec["attempts"][0]["problems"][0]


def test_a_repeat_of_a_failed_edit_is_refused():
    failed = [{"edit": {"op": "add_planner_rule", "params": {"text": "end every answer with a short section headed "
                                                                     "assumptions."}},
               "observed_delta": 0.0, "reasons": ["2 no real gain"]}]
    _, h, rec = go(GOOD, GOOD, failed=failed)
    assert h is None and "already tried" in rec["attempts"][0]["problems"][0]


def test_a_leaked_held_out_phrase_is_refused():
    leak = json.dumps({"edit": {"op": "add_planner_rule", "params": {"text": "When a car is rented for 9 days at $47 "
                                                                              "a day, add the insurance."}},
                       "rationale": "x", "predicted_delta": 0.1})
    _, h, rec = go(leak, leak)
    assert h is None and any(p.startswith("leakage") for p in rec["attempts"][0]["problems"])


def test_out_of_range_prediction_and_extra_keys_are_refused():
    _, h, _ = go(json.dumps({"edit": {"op": "add_planner_rule", "params": {"text": "x"}}, "rationale": "x",
                             "predicted_delta": 3}), GOOD)
    assert h is not None                                                         # refused once, then the retry passes
    _, h, rec = go(json.dumps({"edit": {"op": "add_planner_rule", "params": {"text": "x"}}, "rationale": "x",
                               "predicted_delta": 0.1, "why": "x"}), "{}")
    assert h is None


def test_the_prompt_has_what_the_spec_lists_and_no_held_out_text(tmp_path):
    p = build_prompt(D, seed_recipe("calc"), [{"edit": {"op": "add_role_rule", "params": {}}, "observed_delta": 0.0,
                                                "reasons": ["2 no real gain"]}])
    for part in ("feedback: assumptions section missing", "family: calc", "add_planner_rule: params {\"text\"",
                 "tighten_done_when: params {\"select\": SELECTOR", "SELECTOR = ", "add_role_rule", "2 no real gain",
                 "A practice task about paint.", "write the answer"):
        assert part in p, part
    assert "car is rented" not in p and "hpost" not in p
    row = log_unresolved(tmp_path, {"at_order": 10}, D, ["h-a10-1", "h-a10-2", "h-a10-3"])
    assert json.loads((tmp_path / "human_queue.jsonl").read_text())["hypotheses_tried"] == row["hypotheses_tried"]
