"""D124 — an accepted work-around ends the stuck signals it stands in for, and a fix that only repeats an item is the
same fix. H3 run 4 (d9d4ebc3): the fix proposer's work_around for docx_generator was applied, yet the watch still read
the open request and the step's `docx:` output line, so the step stayed stuck and a second identical grant used up the
per-step limit. Offline, with the mock LLM."""
from amoeba.adapt.fixes import fix_key
from amoeba.adapt.stuck import diagnose, step_signals, waived_view
from amoeba.interp.runtime import Interpreter
from tests.test_proposer_d117 import BODY, ON, edit, good, reply
from tests.test_plan_runner import plan_team, step_no

REQ = {"name": "docx_generator", "for_role": "Cost Analyst", "status": "unfilled", "reason": "pick_none", "kind": "tool"}
META = {"step": 4, "status": "partial", "roles": ["Cost Analyst"], "output_spec": "docx: Final Memo File",
        "blocked": ["docx_generator"], "files_made": [], "status_reason": "lacked: docx_generator"}


def test_a_waived_capability_no_longer_fires_its_signals():
    before = step_signals(META, previous=dict(META), unfilled=[REQ])
    assert {s["signal"] for s in before} == {"capability_unfilled", "no_file_change"}
    view, open_ = waived_view(META, [REQ], {"docx_generator"})
    assert step_signals(view, previous=dict(META), unfilled=open_) == [] and open_ == []
    assert view["status"] == "partial" and META["output_spec"] == "docx: Final Memo File"   # nothing else changed
    other, keep = waived_view(META, [REQ], {"currency_api"})                               # another capability
    assert diagnose(step_signals(other, previous=dict(META), unfilled=keep))["cause"] == "capability"


def test_a_list_that_only_repeats_an_item_is_the_same_fix():
    g = lambda items: {"kind": "grant_tool", "rung": 2, "target": 4, "params": {"items": items, "exclude": []}}
    assert fix_key(g(["docx_generator", "docx_generator"])) == fix_key(g(["docx_generator"] * 3))
    assert fix_key(g(["a", "b"])) != fix_key(g(["a"]))


def test_the_work_around_lets_the_run_go_on(task, envelope, trace, tools):
    """The H3 shape: an unfilled docx_generator request and a docx output line on step 1."""
    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and "work-around" not in user:
            return reply("Final Output", f"OUT-1\n{BODY}\nBLOCKED: docx_generator — no tool makes a .docx file")
        if n == "1":                       # as in H3: the step stays partial, the helper still names the gap
            return reply("Final Output", f"OUT-1\n{BODY}\nBLOCKED: docx_generator — the memo is in Markdown instead")
        return good(n)
    wa = edit("work_around", capability="docx_generator", method="write the memo in Markdown", done_when="",
              limitation="The memo is in Markdown, not .docx.")
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script,
                         fix_proposer=[edit("grant_tool", role="Cost Analyst", tool="echo"), wa])
    cfg.meta["capability_requests"] = [dict(REQ)]
    cfg.plan[0].output = "docx: Final Memo File"
    ep = Interpreter(llm, tools, trace, plan_options=ON).run(cfg, task, seed=0)
    kinds = [(f["kind"], f["result"].split(":")[0]) for f in ep.adaptation["fixes"]]
    assert kinds[-1] == ("work_around", "finished with limitation") and not ep.error
    assert ep.adaptation["finished_with_limitation_steps"] == [1] and "The memo is in Markdown" in ep.answer
    assert len(ep.steps) >= 4                                                  # the later steps ran
