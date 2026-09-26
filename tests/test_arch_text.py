"""D55 — the as-built page: `# box:` tags in the code, unassigned code, and the per-box text cache (a cheap model
re-checks a box's words only when that box's facts change; numbers are placeholders filled from the code)."""
import json
import sys
from pathlib import Path

import pytest

from amoeba.llm.client import ChatResponse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import arch_extract as X  # noqa: E402
import arch_text as T  # noqa: E402


class Src(X.Facts):
    """Facts over given source texts instead of the repository."""

    def __init__(self, files: dict[str, str]):
        import ast
        self.trees, self.src, self.defs, self.by_name = {}, {}, {}, {}
        for path, text in files.items():
            self.trees[path] = ast.parse(text)
            self.src[path] = text.split("\n")
            self._collect(path, self.trees[path].body, "", None)


@pytest.fixture
def boxes(monkeypatch):
    monkeypatch.setattr(X, "BOXES", [{"id": "a", "anchors": ["m.py::f"]}, {"id": "b", "anchors": []}])


def test_tags_put_code_in_boxes(boxes):
    F = Src({"m.py": "# box: a, b\n@dec\ndef f():\n    pass\n\n\ndef g():\n    pass\n\n\nclass K:\n    # box: b\n    def m(self):\n        pass\n"})
    tags, errors = X.box_tags(F)
    assert errors == [] and tags == {"m.py::f": ["a", "b"], "m.py::K.m": ["b"]}
    assert X.check_anchors(F, tags) == []
    X.tagged_anchors(tags)
    assert X.BOXES[1]["anchors"] == ["m.py::K.m", "m.py::f"]          # tagged code joins its box by itself
    un = X.unassigned(F, tags, prev_defs={"m.py::f", "m.py::K"})
    assert [(u["key"], u["new"]) for u in un] == [("m.py::g", True)]    # K is covered by its tagged method


def test_bad_tags_and_anchors_fail(boxes):
    F = Src({"m.py": "# box: nosuch\ndef f():\n    pass\n\n# box: a\nx = 1\n"})
    tags, errors = X.box_tags(F)
    assert "m.py:1: '# box: nosuch' names no box" in errors[0] and "not directly above a def" in errors[1]
    assert X.check_anchors(F, tags) == ["box a: m.py::f has no '# box: a' tag above it"]
    F = Src({"m.py": "def g():\n    pass\n"})
    assert X.check_anchors(F, {}) == ["box a: anchor m.py::f points at code that does not exist"]


def test_every_box_anchor_in_the_repository_is_tagged():
    F = X.Facts()
    tags, errors = X.box_tags(F)
    assert errors == [] and X.check_anchors(F, tags) == []


# ---- numbers ----------------------------------------------------------------------------------------------------
def test_placeholders():
    consts = {"MAX_ROUNDS": 3, "PlanOptions.max_input_chars": 6000, "a.b": 2, "c": 2}
    text, replaced, left = T.templatize("At most 3 rounds, 6,000 characters, 2 retries, 7 days", consts)
    assert text == "At most {MAX_ROUNDS} rounds, {PlanOptions.max_input_chars} characters, 2 retries, 7 days"
    assert left == ["2", "7"]                                   # ambiguous or unknown numbers stay as they are
    assert T.fill(text, {**consts, "MAX_ROUNDS": 4}) == ("At most 4 rounds, 6,000 characters, 2 retries, 7 days", [])
    assert T.fill("{NOPE}", consts) == ("{NOPE}", ["NOPE"])
    assert T.templatize("D53 R1 step_3 v2.1", {"x": 53, "y": 1})[0] == "D53 R1 step_3 v2.1"   # labels are not numbers


# ---- the cache --------------------------------------------------------------------------------------------------
class Stub:
    model = "cheap-model"

    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def chat_messages(self, messages, seed=0, max_tokens=None):
        self.prompts.append(messages[-1]["content"])
        return ChatResponse(content=self.replies.pop(0), input_tokens=300, output_tokens=20, model=self.model)


class NoDefs:
    defs = {}


def box(sig="f(x)", guard="if x > 3"):
    return {"id": "a", "title": "Box A", "kind": "code", "status": "built", "sentence": "", "what": [],
            "anchors": [{"key": "m.py::f", "kind": "function", "signature": sig, "doc": "", "callees": [], "line": 1}],
            "guards": [{"kind": "reject", "code": guard, "effect": "raise ValueError"}], "checks": []}


HAND = {"a": {"sentence": "Rejects big inputs.", "what": ["Stops when x passes the cap."]}}


def build(tmp_path, monkeypatch, b, llm, hand=HAND, consts=None):
    monkeypatch.setattr(T, "CACHE", tmp_path / "box_text.json")
    monkeypatch.setattr(T, "LOG", tmp_path / "text_log.jsonl")
    monkeypatch.setattr(T, "numeric_facts", lambda F, bx, C: consts or {})
    log = T.update_texts([b], NoDefs(), [], {}, hand, llm=llm, commit="abc")
    return log, b


def test_no_change_costs_nothing(tmp_path, monkeypatch):
    log, _ = build(tmp_path, monkeypatch, box(), llm=Stub())
    assert log["hand"] == 1 and log["llm_calls"] == 0
    stub = Stub()
    log, b = build(tmp_path, monkeypatch, box(), llm=stub)
    assert (log["unchanged"], log["llm_calls"], log["input_tokens"], stub.prompts) == (1, 0, 0, [])
    assert b["sentence"] == "Rejects big inputs." and b["text_source"] == "hand"
    lines = (tmp_path / "text_log.jsonl").read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["llm_calls"] == 0          # every rebuild is logged


def test_line_moves_and_new_values_are_not_changes(tmp_path, monkeypatch):
    build(tmp_path, monkeypatch, box(), llm=Stub())
    moved = box()
    moved["anchors"][0]["line"] = 40
    moved["checks"] = []
    log, _ = build(tmp_path, monkeypatch, moved, llm=Stub())
    assert log["unchanged"] == 1 and log["llm_calls"] == 0


def test_changed_facts_ask_the_model_once_keep(tmp_path, monkeypatch):
    build(tmp_path, monkeypatch, box(), llm=Stub())
    stub = Stub('{"verdict": "keep"}')
    log, b = build(tmp_path, monkeypatch, box(guard="if x > 3 and y"), llm=stub)
    assert (log["checked"], log["kept"], log["llm_calls"], log["input_tokens"], log["model"]) == (1, 1, 1, 300, "cheap-model")
    p = stub.prompts[0]
    assert "0. Rejects big inputs.\n1. Stops when x passes the cap." in p and '+   "if x > 3 and y"' in p and "still true" in p
    assert b["text_source"] == "hand (model: still true)"
    log, _ = build(tmp_path, monkeypatch, box(guard="if x > 3 and y"), llm=Stub())   # checked: no second call
    assert log["llm_calls"] == 0


def test_rewrite_uses_placeholders_and_rejects_invented_numbers(tmp_path, monkeypatch):
    build(tmp_path, monkeypatch, box(), llm=Stub(), consts={"CAP": 5})
    good = '{"verdict": "rewrite", "changes": [{"line": 0, "text": "Rejects inputs over 5."}, {"line": 1, "text": "- Stops at {CAP}."}]}'
    log, b = build(tmp_path, monkeypatch, box(sig="f(x, y)"), llm=Stub(good), consts={"CAP": 5})
    assert log["rewritten"] == 1 and b["sentence"] == "Rejects inputs over 5." and b["sentence_tpl"] == "Rejects inputs over {CAP}."
    log, b = build(tmp_path, monkeypatch, box(sig="f(x, y)"), llm=Stub(), consts={"CAP": 8})    # new value: no call
    assert log["llm_calls"] == 0 and b["what"] == ["Stops at 8."]
    bad = '{"verdict": "rewrite", "changes": [{"line": 0, "text": "Rejects inputs over 12."}]}'
    log, b = build(tmp_path, monkeypatch, box(sig="f(x, y, z)"), llm=Stub(bad), consts={"CAP": 8})
    assert log["rejected"] == 1 and b["sentence"] == "Rejects inputs over 8." and b["text_stale"]
    log, b = build(tmp_path, monkeypatch, box(sig="f(x, y, z)"), llm=Stub(bad), consts={"CAP": 8})
    assert log["llm_calls"] == 0 and log["stale"] == 1 and b["text_stale"]   # same facts: not asked again


def test_without_a_model_the_box_is_marked_stale(tmp_path, monkeypatch):
    build(tmp_path, monkeypatch, box(), llm=Stub())
    log, b = build(tmp_path, monkeypatch, box(sig="g()"), llm=None)
    assert log["stale"] == 1 and "no model" in b["text_stale"] and b["sentence"] == "Rejects big inputs."
    stub = Stub('{"verdict": "keep"}')
    log, b = build(tmp_path, monkeypatch, box(sig="g()"), llm=stub)             # re-checked once a model is there
    assert log["llm_calls"] == 1 and b["text_stale"] is None


def test_a_hand_edit_wins_without_a_call(tmp_path, monkeypatch):
    build(tmp_path, monkeypatch, box(), llm=Stub())
    log, b = build(tmp_path, monkeypatch, box(sig="h()"), llm=Stub(),
                   hand={"a": {"sentence": "New words.", "what": []}})
    assert log["hand"] == 1 and log["llm_calls"] == 0 and b["sentence"] == "New words."


def test_line_edits_keep_every_other_line():
    assert T.apply_changes("S", ["a", "b", "c"], [{"line": 2, "text": "- B"}, {"line": 3, "text": None},
                                                   {"line": "new", "text": "d"}]) == ("S", ["a", "B", "d"])
    assert T.apply_changes("S", ["a"], [{"line": 5, "text": "x"}]) is None          # no such line
    assert T.apply_changes("S", ["a"], [{"line": 0, "text": None}]) is None         # the summary cannot go
    assert T.parse_reply('{"verdict": "rewrite", "sentence": "x"}') is None         # the old whole-text form


def test_an_api_error_marks_the_box_stale_and_the_build_goes_on(tmp_path, monkeypatch):
    class Down(Stub):
        def chat_messages(self, messages, seed=0, max_tokens=None):
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
    build(tmp_path, monkeypatch, box(), llm=Stub())
    log, b = build(tmp_path, monkeypatch, box(sig="q()"), llm=Down())
    assert log["stale"] == 1 and "429" in b["text_stale"] and b["sentence"] == "Rejects big inputs."
