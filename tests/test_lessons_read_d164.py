"""D164 — Box 2 and Box 4 read the library: plain-code retrieval (approved, a lesson, helped > hurt, never hurt in
this run's niche, the cause for Box 4; same-niche first, then most-helped; N entries, M characters), a section in the
proposer prompts, the drafting prompts' {lessons} slot for the Planner and both observers, the --lessons /
--lessons-write flags, the replay set never writing, and result.json naming the lessons shown and used. With reading
off the prompts are byte-identical to today's. Offline."""
import json
from pathlib import Path

from amoeba.adapt.lessons import LessonLibrary, key_of, round_verdicts
from amoeba.adapt.retrieval import box2_section, box4_section, retrieve
from amoeba.config.prompts import PROMPT_DIR
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.trace import TraceWriter
from scripts.run_task import cli_plan_options, parse_args
from tests.test_lessons_d163 import LESSON, fault_run, p, row

LESSON_TEXT = "add_role_rule (inv): tell the looping role to stop and give its final output."


def seed_library(root, niche="general", hurt_in=None, status="approved", helped=3, cause="tool_error",
                 op="add_role_rule", scope="inv"):
    lib = LessonLibrary(root)
    for k in range(helped):
        [v] = round_verdicts(row(dict(p("done"), op=op, scope=scope), cause=cause, task_id=f"t{k}"))
        lib.record(v, niche, f"t{k}", f"r{k}")
    if hurt_in:
        [v] = round_verdicts(row(dict(p(new=["x"]), op=op, scope=scope), cause=cause))
        lib.record(v, hurt_in, "t9", "r9")
    eid = key_of(cause, op, scope)
    lib.add_lesson(eid, "A step keeps calling one tool and never ends.", LESSON_TEXT, "medium", "r0")
    lib.set_status(eid, status)
    return lib, eid


def test_retrieval_is_plain_code(tmp_path):
    lib, eid = seed_library(tmp_path)
    assert [e["id"] for e in retrieve(lib, "general", cause="tool_error")] == [eid]
    assert retrieve(lib, "general", cause="max_turns") == []                      # Box 4: the cause must match
    assert [e["id"] for e in retrieve(lib, "general")] == [eid]                   # Box 2: any cause
    lib.set_status(eid, "unreviewed")
    assert retrieve(lib, "general") == []                                          # only approved
    lib2, eid2 = seed_library(tmp_path / "b", hurt_in="calc")
    assert retrieve(lib2, "calc") == [] and retrieve(lib2, "general")                # hurt in this niche: hidden
    lib3, _ = seed_library(tmp_path / "c", helped=1)
    for _ in range(2):
        [v] = round_verdicts(row(p(new=["x"])))
        lib3.record(v, "other", "t8", "r8")
    assert retrieve(lib3, "general") == []                                          # helped must exceed hurt


def test_same_niche_first_then_most_helped_within_the_caps(tmp_path):
    lib, a = seed_library(tmp_path, niche="calc", helped=1)
    _, b = seed_library(tmp_path, niche="general", helped=4, op="grant_tool")
    assert [e["id"] for e in retrieve(lib, "calc")] == [a, b]
    assert [e["id"] for e in retrieve(lib, "general")] == [b, a]
    assert len(retrieve(lib, "general", max_entries=1)) == 1
    text = box4_section(retrieve(lib, "general", cause="tool_error"))
    assert text.startswith("\n\n# What helped before for this cause") and "helped 4, hurt 0" in text
    assert "must still quote" in text and len(box4_section(retrieve(lib, "general"), max_chars=120)) <= 120 + 200
    assert box4_section([]) == "" and box2_section([]) == ""
    assert box2_section(retrieve(lib, "general")).startswith("\n\n# Lessons from earlier tasks")


def test_with_reading_off_the_proposer_prompts_are_byte_identical_to_before(task, envelope, tools, tmp_path):
    seed_library(tmp_path / "lib")
    llm, ep = fault_run(task, envelope, TraceWriter(None, episode_id="x"), tools, tmp_path / "run", tmp_path / "lib")
    for kind in ("fix_proposer_inv", "fix_proposer_dom"):
        prompt = llm.calls_of(kind)[0]["messages"][-1]["content"]
        assert "What helped before" not in prompt
        old = (PROMPT_DIR / f"{kind}.txt").read_text().split("\n", 1)[1].replace("${tried}${lessons}", "${tried}")
        assert "${lessons}" not in old and old.split("# Rules")[1] in prompt        # the tail is unchanged text


def test_with_reading_on_a_matching_proposer_prompt_shows_the_lesson_and_result_names_it(task, envelope, tools,
                                                                                          tmp_path):
    lib, eid = seed_library(tmp_path / "lib")
    opts = PlanOptions(adapt="on", failed_step="run", proposer="scoped", faults=("tool_error:1:30",), contract="on",
                       lessons="on", lessons_write="off", lessons_dir=str(tmp_path / "lib"))
    llm, ep = fault_run(task, envelope, TraceWriter(None, episode_id="y"), tools, tmp_path / "run", tmp_path / "lib",
                        opts=opts)
    prompt = llm.calls_of("fix_proposer_inv")[0]["messages"][-1]["content"]
    assert "# What helped before for this cause" in prompt and LESSON_TEXT in prompt and "helped 3, hurt 0" in prompt
    assert ep.adaptation["lessons"]["shown"] == [eid]
    assert ep.adaptation["lessons"]["used"] == [{"id": eid, "step": 1}]     # the matching fix ended done
    assert not llm.calls_of("reflector") and lib.get(eid)["counts"]["helped"] == 3   # writing off: no change


def test_the_flags_and_their_defaults():
    a = parse_args(["x", "--topology", "plan"])
    assert (a.lessons, a.lessons_write) == ("off", None)
    o = cli_plan_options(a)
    assert (o.lessons, o.lessons_write) == ("off", "on" if o.adapt == "on" else "off")
    o = cli_plan_options(parse_args(["x", "--adapt", "off"]))
    assert o.lessons_write == "off"
    o = cli_plan_options(parse_args(["x", "--lessons", "on", "--lessons-write", "off", "--lessons-dir", "/tmp/l"]))
    assert (o.lessons, o.lessons_write, o.lessons_dir) == ("on", "off", "/tmp/l")


def test_a_replay_task_never_writes_and_box2_sees_the_lessons(tmp_path, envelope, tools):
    from amoeba.task.models import Task
    from scripts.run_task import run_one
    from tests.conftest import fx, mock
    lib, eid = seed_library(tmp_path / "lib")
    llm = mock(planner=[fx("draft_d24_full")], agent_observer=[fx("observer_d24_approve")],
               plan_observer=[fx("observer_d24_approve")], plan_worker=["## Thought\nok\n\n## Final_Output\n1\n"] * 9)
    opts = PlanOptions(adapt="off", lessons="on", lessons_write="on", lessons_dir=str(tmp_path / "lib"))
    r = run_one(Task(prompt="Estimate the monthly cost for 50 tenants at 200 GB each.", set="replay"), "plan", llm,
                envelope, tools, tmp_path / "runs", draft_prompts="d24", plan_options=opts)
    for kind in ("planner", "agent_observer", "plan_observer"):
        assert any("# Lessons from earlier tasks" in json.dumps(c["messages"]) and LESSON_TEXT in json.dumps(
            c["messages"]) for c in llm.calls_of(kind)), kind
    res = json.loads((tmp_path / "runs" / r.run_id / "result.json").read_text())
    assert res["lessons"]["shown"] == [eid] and res["lessons"]["write"] == "off (replay task)"


def test_stage_e_passes_the_flags_to_both_arms(tmp_path):
    from scripts.stage_e import arm_command
    cmd = arm_command("on", Path("t.jsonl"), 0, tmp_path, tmp_path / "p.json", tmp_path, ["--topology", "plan"],
                      lessons="on", lessons_write="off")
    assert cmd[cmd.index("--lessons") + 1] == "on" and cmd[cmd.index("--lessons-write") + 1] == "off"
