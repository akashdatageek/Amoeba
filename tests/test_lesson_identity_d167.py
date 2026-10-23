"""D167 — a lesson's counts are about that lesson. (cause, op, scope) is a family; every lesson the reflector writes is
its own entry in the family (its own id, text, status and counts); a lesson's text never changes. A lesson gains
evidence only when a Box 4 proposer that was shown it names it in `from_lesson` (plain code checks: shown, same op and
scope); the round that wrote it is its first sample. Family counts are every verdict, for reports only. Offline."""
import json

from amoeba.adapt.lessons import LessonLibrary, key_of, round_verdicts
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.trace import TraceWriter
from tests.test_lessons_d163 import fault_run, p, row
from tests.test_scoped_proposers_d154 import QUOTE

FAM = key_of("tool_error", "add_role_rule", "inv")


def lesson_json(text):
    return json.dumps({"cue": "A step keeps calling one tool and never ends with its output.", "lesson": text,
                       "confidence": "medium"})


def cite(lid, op="add_role_rule", **params):
    params = params or {"role": "Cost Analyst", "text": "FINISH NOW with your Final Output."}
    return json.dumps({"edit": {"op": op, "params": params}, "reason": "it lets the step finish", "because": QUOTE,
                       **({"from_lesson": lid} if lid else {})})


def seed(root, op="add_role_rule", scope="inv", text="add_role_rule (inv): tell the looping role to stop.",
         status="approved"):
    lib = LessonLibrary(root)
    [v] = round_verdicts(row(dict(p("done"), op=op, scope=scope)))
    lib.record(v, "general", "t0", "r0")
    les = lib.add_lesson(v["id"], "A step keeps calling one tool and never ends.", text, "medium", "r0",
                         first=v, niche="general", task_id="t0")
    lib.set_status(les["id"], status)
    return lib, les["id"]


def lessons_on(lib_dir):
    return PlanOptions(adapt="on", failed_step="run", proposer="scoped", faults=("tool_error:1:30",), contract="on",
                       lessons="on", lessons_write="on", lessons_dir=str(lib_dir))


def test_three_different_lessons_are_three_entries_with_their_own_counts(task, envelope, tools, tmp_path):
    lib_dir = tmp_path / "lib"
    texts = [f"add_role_rule (inv): rule number {w} for a looping role." for w in ("one", "two", "three")]
    for k, text in enumerate(texts):
        fault_run(task, envelope, TraceWriter(None, episode_id=f"e{k}"), tools, tmp_path / f"run{k}", lib_dir,
                  reflector=(lesson_json(text),))
    lib = LessonLibrary(lib_dir)
    got = lib.lessons(FAM)
    assert sorted(x["lesson"] for x in got) == sorted(texts)                 # three lessons, not one rewritten
    assert all(x["counts"]["helped"] == 1 and x["status"] == "unreviewed" for x in got)
    assert lib.get(FAM)["counts"]["helped"] == 3                               # the family: every verdict (reports)


def test_an_approved_lesson_text_never_changes(tmp_path):
    lib, lid = seed(tmp_path)
    new = lib.add_lesson(FAM, "another cue", "add_role_rule (inv): a different rule.", "low", "r1")
    assert new["id"] != lid and new["status"] == "unreviewed"
    old = lib.lesson(lid)
    assert old["lesson"] == "add_role_rule (inv): tell the looping role to stop." and old["status"] == "approved"
    same = lib.add_lesson(FAM, "a cue", old["lesson"], "low", "r2")             # the same text is the same lesson
    assert same["id"] == lid and len(lib.lessons(FAM)) == 2


def test_a_citation_of_a_lesson_not_shown_or_of_another_op_is_refused(task, envelope, tools, tmp_path):
    lib, lid = seed(tmp_path / "lib", op="grant_tool")                       # shown, but its op is grant_tool
    from amoeba.interp.runtime import Interpreter
    from tests.test_plan_runner import plan_team
    from tests.test_scoped_proposers_d154 import RULE_NO, stall_until
    for bad, why in ((cite("tool_error__add_role_rule__inv__L99"), "was not shown"), (cite(lid), "grant_tool")):
        trace = TraceWriter(None, episode_id="z")
        llm, cfg = plan_team(task, envelope, trace, plan_worker=stall_until("FINISH NOW"),
                             fix_proposer_inv=[bad, cite(None)], fix_proposer_dom=[RULE_NO],
                             reflector=["NO_ENTRY"])
        for a in cfg.agents.values():
            a.missing_tools = []
        cfg.meta["capability_requests"] = []
        ep = Interpreter(llm, tools, trace, run_dir=tmp_path / f"r-{why[:4]}",
                         plan_options=lessons_on(tmp_path / "lib")).run(cfg, task, seed=0)
        [rnd] = [f for f in ep.adaptation["fixes"] if f.get("round")]
        inv = next(c for c in rnd["round"]["candidates"] if c["scope"] == "inv")
        assert any("from_lesson" in x and why in x for x in inv["refusals"]), inv["refusals"]
        assert len(llm.calls_of("fix_proposer_inv")) == 2                     # refused, asked once more


def test_only_a_cited_use_adds_to_a_lesson(task, envelope, tools, tmp_path):
    from amoeba.interp.runtime import Interpreter
    from tests.test_plan_runner import plan_team
    from tests.test_scoped_proposers_d154 import RULE_NO, stall_until
    lib, lid = seed(tmp_path / "lib")

    def go(inv_reply, name):
        trace = TraceWriter(None, episode_id=name)
        llm, cfg = plan_team(task, envelope, trace, plan_worker=stall_until("FINISH NOW"),
                             fix_proposer_inv=[inv_reply], fix_proposer_dom=[RULE_NO], reflector=["NO_ENTRY"])
        for a in cfg.agents.values():
            a.missing_tools = []
        cfg.meta["capability_requests"] = []
        return Interpreter(llm, tools, trace, run_dir=tmp_path / name,
                           plan_options=lessons_on(tmp_path / "lib")).run(cfg, task, seed=0)

    ep = go(cite(None), "plain")                                             # shown, not cited: no evidence
    assert lib.lesson(lid)["counts"]["helped"] == 1 and ep.adaptation["lessons"]["used"] == []
    ep = go(cite(lid), "cited")
    assert lib.lesson(lid)["counts"]["helped"] == 2
    assert [u["id"] for u in ep.adaptation["lessons"]["used"]] == [lid]
    assert lib.get(FAM)["counts"]["helped"] == 3                               # the family counted all three


def test_an_old_library_is_migrated_into_families(tmp_path):
    (tmp_path / "index.jsonl").write_text(json.dumps({
        "id": FAM, "cause": "tool_error", "op": "add_role_rule", "scope": "inv",
        "counts": {"helped": 4, "hurt": 0, "no_effect": 1, "confounded": 0}, "by_niche": {}, "task_ids": ["a", "b"],
        "run_ids": ["r1"], "status": "approved", "cue": "old cue", "lesson": "old lesson text",
        "confidence": "high", "created_at": "2026-10-01T00:00:00+00:00"}) + "\n")
    lib = LessonLibrary(tmp_path)
    [les] = lib.lessons(FAM)
    assert les["lesson"] == "old lesson text" and les["status"] == "unreviewed" and les["family"] == FAM
    fam = lib.get(FAM)
    assert fam["counts"]["helped"] == 4 and "lesson" not in fam and "status" not in fam
