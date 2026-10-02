"""D80 — Box 0, the task stream: shifts apply at the right order; held-out tasks never enter the practice loop; the
feedback channel exposes item names only; --disable-tools takes a tool out of one run. Offline."""
import json

import pytest

from amoeba.adapt.stream import HeldOutLeak, Stream, StreamTask, feedback, feedback_record, leaks, load_stream
from amoeba.safety.envelope import Envelope
from amoeba.task.draft import toolbox_text
from amoeba.task.evaluate import rubric_score
from amoeba.task.models import Task
from amoeba.tools.registry import default_registry
from scripts.run_task import disable_tools, run_one
from tests.conftest import fx, mock

NUM = {"expected_numbers": [{"name": "total", "value": 42, "unit": "", "tolerance": 0}]}
WITH_ITEM = {**NUM, "required_deliverables": [{"name": "assumptions section", "any_of": ["(?im)^#+ assumptions"]}]}


def t(id_, split, phase, order=None, family="calc", rubric=None, prompt="Add 40 and 2."):
    return StreamTask(id=id_, prompt=prompt, family=family, split=split, phase=phase, order=order,
                      rubric=rubric or (WITH_ITEM if phase == "post" and family == "calc" else NUM))


def stream():
    tasks = [t("p1", "practice", "pre", 1), t("p2", "practice", "pre", 2), t("p3", "practice", "post", 3),
             t("p4", "practice", "post", 4), t("c5", "practice", "pre", 5, family="code"),
             t("c6", "practice", "post", 6, family="code"),
             t("h1", "heldout", "post", prompt="Seven bakers each bake six loaves; how many loaves are baked today?"),
             t("h2", "heldout", "pre")]
    return Stream(name="fx", tasks=tasks, shifts=[
        {"after": 2, "family": "calc", "kind": "feedback", "items": ["assumptions section"]},
        {"after": 5, "family": "code", "kind": "remove_tool", "tool": "local:Bash"}])


def test_shifts_apply_from_the_order_after_them():
    s = stream()
    by = {x.id: x for x in s.practice()}
    assert [x.id for x in s.practice()] == ["p1", "p2", "p3", "p4", "c5", "c6"]
    assert s.shifts_due(by["p2"]) == [] and [x.kind for x in s.shifts_due(by["p3"])] == ["feedback"]
    assert s.disabled_tools(by["c5"]) == [] and s.disabled_tools(by["c6"]) == ["local:Bash"]
    assert s.disabled_tools(by["p4"]) == []                       # another family's shift does not apply


def test_heldout_tasks_never_enter_the_practice_loop():
    s = stream()
    assert all(x.split == "practice" for x in s.practice()) and "h1" not in [x.id for x in s.practice("calc")]
    assert [x.id for x in s.heldout("calc")] == ["h1", "h2"]       # post first: for Box 7 only
    with pytest.raises(HeldOutLeak):
        s.shifts_due(s.heldout("calc")[0])
    with pytest.raises(HeldOutLeak):
        feedback_record(s.heldout("calc")[0], {"rubric": None})


def test_the_stream_file_is_checked_when_loaded():
    with pytest.raises(ValueError, match="post-phase"):            # a pre task carrying the new item
        Stream(name="x", tasks=[t("a", "practice", "pre", 1, rubric=WITH_ITEM)],
               shifts=[{"after": 1, "family": "calc", "kind": "feedback", "items": ["assumptions section"]}])
    with pytest.raises(ValueError, match="mentions"):              # a prompt that gives the item away
        Stream(name="x", tasks=[t("a", "practice", "post", 2, prompt="Add 40 and 2 with an assumptions section.")],
               shifts=[{"after": 1, "family": "calc", "kind": "feedback", "items": ["assumptions section"]}])
    with pytest.raises(ValueError, match="post"):                  # order and phase disagree
        Stream(name="x", tasks=[t("a", "practice", "pre", 3)],
               shifts=[{"after": 1, "family": "calc", "kind": "remove_tool", "tool": "calc"}])
    with pytest.raises(ValueError):                                 # held-out tasks carry no order
        t("h", "heldout", "post", order=4)


def test_the_feedback_channel_gives_item_names_only():
    s = stream()
    graded = rubric_score("The total is 42.", s.practice()[2].rubric)
    rec = feedback_record(s.practice()[2], {"rubric": graded})
    assert rec == {"task_id": "p3", "order": 3, "family": "calc", "failed_items": ["assumptions section"]}
    assert feedback(graded) == ["assumptions section"] and "#+" not in json.dumps(rec)
    assert feedback(rubric_score("## Assumptions\nnone\nThe total is 42.", s.practice()[2].rubric)) == []


M1 = pytest.mark.skipif(not __import__("pathlib").Path("tasks/stream_m1.jsonl").exists(),
                        reason="stream_m1 is committed after it is approved")


def test_leakage_screen():
    s = stream()
    held = s.heldout("calc")
    assert leaks("Always state assumptions in a short section.", held) == []
    assert leaks("seven bakers each bake six loaves; how many loaves are", held)       # an 8-word sequence
    assert any("id" in x for x in leaks("like the task fx-h-9", [t("fx-h-9", "heldout", "post")]))
    assert any("number" in x for x in leaks("check that 17,589.18 appears", [t("h", "heldout", "pre", rubric={
        "expected_numbers": [{"name": "v", "value": 17589.18, "unit": "USD"}]})]))


@M1
def test_the_m1_stream_file_is_well_formed():
    s = load_stream("m1")
    assert [x.order for x in s.practice()] == list(range(1, 17))
    assert [x.phase for x in s.practice()] == ["pre"] * 8 + ["post"] * 8
    assert len(s.heldout("calc", "post")) == 5 and len(s.heldout("calc", "pre")) == 3
    assert all("assum" not in x.prompt.lower() for x in s.tasks)


# ---- --disable-tools -------------------------------------------------------------------------------------------
def test_disable_tools_takes_a_tool_out_of_the_registry_envelope_and_toolbox_text():
    reg, pool, local = disable_tools(["calc"], default_registry())
    assert "calc" not in reg and "echo" in reg and "calc" in default_registry()
    env = Envelope.from_registry(reg)
    assert "calc" not in toolbox_text(env) and "calc" in toolbox_text(Envelope.from_registry(default_registry()))
    from amoeba.localtools.toolbox import LocalSetup
    from amoeba.pool.stock import PoolSetup
    _, pool, local = disable_tools(["local:Bash", "pool-x"], default_registry(), PoolSetup(), LocalSetup())
    assert "Bash" not in local.config["allowed_tools"] and "Read" in local.config["allowed_tools"]
    assert pool.disabled == {"local:Bash", "pool-x"}
    text = toolbox_text(Envelope.from_registry(default_registry()), local=True, disabled=["local:Bash"])
    assert "Bash" not in text and "Read" in text


def test_a_run_with_a_disabled_tool_records_it_and_a_normal_run_is_unchanged(tmp_path):
    from tests.test_rubric import SCRIPTS
    task = Task(prompt="Compute 17 * 23 + 5.")
    reg, _, _ = disable_tools(["calc"], default_registry())
    env = Envelope.from_registry(reg)
    llm = mock(worker=[fx("worker_final_output")], **SCRIPTS["d19"])
    r = run_one(task, "flat", llm, env, reg, tmp_path / "a", disabled_tools=["calc"])
    out = json.loads((tmp_path / "a" / r.run_id / "result.json").read_text())
    assert out["disabled_tools"] == ["calc"]
    assert "calc" not in json.dumps([c["messages"] for c in llm.calls if c["kind"] == "planner"])
    llm2 = mock(worker=[fx("worker_final_output")], **SCRIPTS["d19"])
    r2 = run_one(task, "flat", llm2, Envelope.from_registry(default_registry()), default_registry(), tmp_path / "b")
    assert "disabled_tools" not in json.loads((tmp_path / "b" / r2.run_id / "result.json").read_text())
