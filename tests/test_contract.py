"""D61 — the step contract: plain code lists what each helper must account for before a step, checks the evidence
after it and sets the outcome (gaps G1–G6 of the as-built page). Offline, with the mock LLM."""
import re

from amoeba.interp.plan_runner import (PlanOptions, PlanRunner, names_match, not_needed_marks, strip_not_needed,
                                       tool_ok)
from amoeba.interp.runtime import Interpreter
from scripts.run_task import cli_plan_options, parse_args
from tests.test_plan_runner import BODY, DIAMOND, plan_team, step_no

ON = PlanOptions(contract="on")
NOT_NEEDED = "\nNOT NEEDED: web_search — the prices are in the task\nNOT NEEDED: database_sandbox — no run needed\n"


def reply(action: str, text: str) -> str:
    return f"## Thought\nok\n\n## CurrentStep\nnow\n\n## Action\n{action}\n\n## ActionInput\n{text}"


def worker(extra: str = "", on_refine: str = ""):
    """Every step answers with a passing body; `extra` is added to it, `on_refine` too after a refine note."""
    def run(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        more = on_refine if "Plain code checked this step's output and found" in user else ""
        return reply("Final Output", f"OUT-{n}\n{BODY}{extra}{more}")
    return run


def run(task, envelope, trace, tools, script, text=DIAMOND, tmp_path=None, setup=None, options=ON):
    llm, cfg = plan_team(task, envelope, trace, text=text, plan_worker=script)
    if setup:
        setup(cfg)
    ep = Interpreter(llm, tools, trace, run_dir=tmp_path, plan_options=options).run(cfg, task, seed=0)
    return llm, cfg, {s["step"]: s for s in ep.steps}, ep


# ---- the small parts ----------------------------------------------------------------------------------------------
def test_tool_results_that_count_as_used():
    assert tool_ok("[S1] pool:fx · rate (cite a fact by its [S1]):\n95.82")
    assert tool_ok("[local:Bash] [S2] (cite …)\n12586269025")
    for bad in ("error: pool:fx failed: timeout", "refused: local:Bash — network_command", "[local:Bash error]\nboom",
                "[S3] pool:fx · rate returned an error (cite a fact by its [S3]):"):
        assert not tool_ok(bad)


def test_not_needed_lines_are_read_and_removed():
    text = "Result 1\nNOT NEEDED: route_engine — distances are in the task\n- NOT NEEDED: `pool:fx` (no rates)\nEnd"
    assert not_needed_marks(text) == ["route_engine", "pool:fx"]
    assert strip_not_needed(text) == "Result 1\nEnd"
    assert names_match("pool:weather-mcp", "weather mcp") and names_match("Python Interpreter", "python_interpreter")
    assert not names_match("fx", "pdf_reader")


def test_the_cli_turns_the_contract_on():
    args = parse_args(["--toy"])
    assert args.step_contract == "on" and cli_plan_options(args).contract == "on"
    assert PlanOptions().contract == "off"                         # the library default keeps the earlier behaviour


# ---- G1: a capability the helper lacked ---------------------------------------------------------------------------
def test_an_undeclared_missing_capability_gets_one_refine_turn_then_marks_the_step_partial(task, envelope, trace, tools):
    llm, cfg, by, ep = run(task, envelope, trace, tools, worker())
    first = [c["messages"][-1]["content"] for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "1"]
    assert "Plain code checks this step's contract: web_search (asked for, not available)" in first[0]
    assert len(first) == 2 and "Cost Analyst asked for web_search" in first[1]    # one refine turn, the finding named
    one = by[1]
    assert one["refine_reason"] == "contract" and one["contract_missing"] == ["web_search"]
    assert (one["status"], one["status_reason"]) == ("partial", "lacked: web_search; not declared by the helper: "
                                                                "web_search")
    assert one["causes"] == ["capability"] and by[2]["contract_missing"] == ["database_sandbox"]
    assert "- BLOCKED: database_sandbox (the team had no such capability; added by plain code)" in ep.answer
    assert "- BLOCKED: web_search" in ep.answer
    [ev] = [e for e in trace.events("contract_check") if e["amoeba.step"] == 1]
    assert ev["amoeba.missing"] == ["web_search"] and ev["amoeba.tool_calls"] == 0
    assert trace.events("step_contract")[0]["amoeba.contract"]["Cost Analyst"]["needs"] == ["web_search"]


def test_not_needed_accounts_for_it_and_leaves_the_step_done(task, envelope, trace, tools):
    llm, cfg, by, ep = run(task, envelope, trace, tools, worker(NOT_NEEDED))
    assert [by[n]["status"] for n in (1, 2, 3, 4)] == ["done"] * 4
    assert by[1]["not_needed"] == ["web_search", "database_sandbox"] and not by[1]["refine"]
    assert "NOT NEEDED" in by[1]["contributions"][0]["input"]                   # the helper wrote it ...
    assert "NOT NEEDED" not in ep.answer                                         # ... plain code took it out
    assert "BLOCKED" not in ep.answer


def test_a_blocked_line_after_the_refine_turn_is_a_declared_gap(task, envelope, trace, tools):
    llm, cfg, by, ep = run(task, envelope, trace, tools, worker(
        on_refine="\nBLOCKED: web_search — no live prices\nBLOCKED: database_sandbox — nothing was run\n"))
    assert (by[1]["status"], by[1]["status_reason"]) == ("partial", "lacked: database_sandbox, web_search")
    assert by[1]["contract_missing"] == [] and by[1]["refine_reason"] == "contract"


def test_with_the_contract_off_nothing_changes(task, envelope, trace, tools):
    llm, cfg, by, ep = run(task, envelope, trace, tools, worker(), options=PlanOptions())
    assert [by[n]["status"] for n in (1, 2, 3, 4)] == ["done"] * 4 and "contract" not in by[1]
    assert trace.events("step_contract") == [] and "Plain code checks this step's contract" not in \
        llm.calls_of("plan_worker")[0]["messages"][-1]["content"]


# ---- G2: an attached tool that was never used ---------------------------------------------------------------------
def give_fx(tools, result="[S1] pool:fx · rate (cite a fact by its [S1]):\nrate 95.82"):
    tools.register("pool:fx", "pool tool fx", lambda text: result)

    def setup(cfg):
        cfg.meta["capability_requests"] = []                          # only the attached tool is in the contract
        for a in cfg.agents.values():
            a.missing_tools = []
            if a.name == "Cost Analyst":
                a.tools.append("pool:fx")
                a.pool.append({"kind": "tool", "id": "io.example/fx", "name": "pool:fx", "request": "currency_api",
                               "text": "fx rates"})
    return setup


def test_an_attached_tool_never_called_makes_the_step_partial_and_the_answer_says_so(task, envelope, trace, tools):
    llm, cfg, by, ep = run(task, envelope, trace, tools, worker(), setup=give_fx(tools))
    first = [c["messages"][-1]["content"] for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "1"]
    assert "pool:fx (given to you)" in first[0] and "Cost Analyst was given pool:fx for this step but never called it" \
        in first[1]
    assert (by[1]["status"], by[1]["status_reason"]) == ("partial", "attached unused: pool:fx")
    assert by[1]["causes"] == ["unused_tool"] and by[2]["status"] == "done"      # step 2's helper has no contract
    assert "- NOT USED: pool:fx (given to the team for step 1, 3 but never used; added by plain code)" in ep.answer


def test_a_successful_call_fulfils_the_contract(task, envelope, trace, tools):
    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if "'pool:fx'" in user and "pool:fx):" not in user:
            return reply("pool:fx", "USD to INR")
        return reply("Final Output", f"OUT-{n}\n{BODY}")
    llm, cfg, by, ep = run(task, envelope, trace, tools, script, setup=give_fx(tools))
    assert by[1]["status"] == "done" and by[1]["unused"] == []
    [call] = by[1]["tool_calls"]
    assert (call["agent"], call["tool"], call["ok"]) == ("Cost Analyst", "pool:fx", True)


def test_a_tool_whose_every_call_failed_is_named_as_such(task, envelope, trace, tools):
    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if "'pool:fx'" in user and "(pool:fx):" not in user:
            return reply("pool:fx", "USD to INR")
        return reply("Final Output", f"OUT-{n}\n{BODY}")
    llm, cfg, by, ep = run(task, envelope, trace, tools, script, setup=give_fx(tools, "error: pool:fx failed: timeout"))
    assert "every call to it failed" in by[1]["refine"]["findings"][0]
    assert by[1]["unused"] == ["pool:fx"] and by[1]["tool_calls"][0]["ok"] is False


# ---- G4: the verifier sees the evidence -----------------------------------------------------------------------------
def test_the_verifier_is_shown_what_each_checked_step_used(task, envelope, trace, tools):
    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "1" and "(pool:fx):" not in user:
            return reply("pool:fx", "USD to INR")
        return reply("Final Output", f"OUT-{n}\n{BODY}")
    llm, cfg, by, ep = run(task, envelope, trace, tools, script, setup=give_fx(tools))
    three = [c["messages"][-1]["content"] for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "3"][0]
    assert "You are VERIFYING" in three and "Evidence plain code recorded for step 1:" in three
    assert "- tool calls: 1" in three and "Cost Analyst → pool:fx (ok): 'USD to INR' → [S1] pool:fx" in three
    two = [c["messages"][-1]["content"] for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == "2"][0]
    assert "Evidence plain code recorded" not in two                   # a work step is not shown it


# ---- G5: work produced but left out of the answer ----------------------------------------------------------------
class FakeLocal:
    """What the runner reads of a LocalToolbox: files made per step, has_file, begin_step, the source book."""

    def __init__(self, files):
        self.files, self.book = files, None

    def begin_step(self, step, trace=None):
        pass

    def has_file(self, name):
        return any(p.endswith(name.split("/")[-1]) for p in self.files)


def test_a_file_the_answer_leaves_out_is_asked_for_then_listed_by_plain_code(task, envelope, trace, tools):
    tools.local = FakeLocal({"chart.png": {"path": "chart.png", "size": 22026, "step": 2}})
    llm, cfg, by, ep = run(task, envelope, trace, tools, worker(NOT_NEEDED))
    [first, again] = [c["messages"][-1]["content"] for c in llm.calls_of("plan_summariser")]
    assert "status: done; files made: chart.png" in first                   # the summariser is told
    assert "the team made these files but the answer does not name them: chart.png (step 2)" in again
    assert "## Files made\n- chart.png (22,026 bytes, made in step 2; listed by plain code)" in ep.answer
    check = by[4]["summary_check"]
    assert check["files_listed_by_code"] == ["chart.png"] and by[2]["files_made"][0]["path"] == "chart.png"


def test_a_file_the_answer_names_needs_nothing(task, envelope, trace, tools):
    tools.local = FakeLocal({"chart.png": {"path": "chart.png", "size": 10, "step": 2}})
    llm, cfg, by, ep = run(task, envelope, trace, tools, worker(NOT_NEEDED + "\nSee chart.png.\n"))
    assert len(llm.calls_of("plan_summariser")) == 1 and "## Files made" not in ep.answer


def test_cited_figures_missing_from_the_answer_are_found(task, envelope, trace, tools):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=worker())
    r = PlanRunner(Interpreter(llm, tools, trace), cfg, task, ep=None, options=ON)
    r.ledger = {"95.82": {"status": "cited", "step": 1, "as": "95.82", "sources": ["S1"]},
                "12": {"status": "untagged", "step": 1, "as": "12", "sources": []},
                "7": {"status": "cited", "step": 1, "as": "7", "sources": ["S1"]}}
    gaps = r.answer_gaps(4, "The rate is unknown.")
    assert gaps == {"files": [], "figures": [{"figure": "95.82", "step": 1, "sources": ["S1"]}]}
    assert r.answer_gaps(4, "The rate is 95.82 [S1].")["figures"] == []


# ---- G6: rework by cause -----------------------------------------------------------------------------------------------
def test_a_producer_that_only_lacked_a_capability_is_not_reworked(task, envelope, trace, tools):
    def script(messages, seed):
        n = step_no(messages)
        if n == "3":
            return reply("Final Output", "Verdict: FAIL\nIssues:\n1. step 1: the prices are not from a source\n\n"
                                         f"OUT-3\n{BODY}{NOT_NEEDED}")
        return reply("Final Output", f"OUT-{n}\n{BODY}" + ("\nBLOCKED: web_search — no live prices\n" if n == "1"
                                                           else NOT_NEEDED))
    llm, cfg, by, ep = run(task, envelope, trace, tools, script)
    assert by[1]["causes"] == ["capability"] and by[3]["verdict"] == "FAIL"
    [skip] = trace.events("rework_skipped")
    assert (skip["amoeba.step"], skip["amoeba.reason"], skip["amoeba.lacked"]) == (1, "capability_missing", ["web_search"])
    assert trace.events("rework") == [] and trace.events("reverify") == []


def test_a_producer_with_failed_checks_is_still_reworked(task, envelope, trace, tools):
    def script(messages, seed):
        n, user = step_no(messages), messages[-1]["content"]
        if n == "3" and "RE-CHECK" not in user:
            return reply("Final Output", f"Verdict: FAIL\nIssues:\n1. step 1: wrong\n\nOUT-3\n{BODY}{NOT_NEEDED}")
        return reply("Final Output", f"OUT-{n}\n{BODY}{NOT_NEEDED}")
    llm, cfg, by, ep = run(task, envelope, trace, tools, script)
    assert [e["amoeba.step"] for e in trace.events("rework")] == [1] and trace.events("rework_skipped") == []


# ---- the run record ---------------------------------------------------------------------------------------------
def test_the_step_record_carries_the_contract_and_its_evidence(task, envelope, trace, tools, tmp_path):
    llm, cfg, by, ep = run(task, envelope, trace, tools, worker(), tmp_path=tmp_path)
    one = by[1]
    assert one["contract"] == {"Cost Analyst": {"needs": ["web_search"], "items": []}}
    assert one["tool_calls"] == [] and one["files_made"] == [] and one["not_needed"] == []
    assert re.search(r'"contract_missing": \[\s*"web_search"', (tmp_path / "artifacts" / "step_1.json").read_text())


# ---- G7: a local result is a source of the step ----------------------------------------------------------------------
def test_a_cited_local_result_counts_as_cited(task, envelope, trace, tools):
    from amoeba.pool.mcp import SourceBook
    local = FakeLocal({})
    local.book = SourceBook()
    local.book.begin_step(1)
    local.book._source("local://Bash/abc", "local:Bash · python3 fib.py", "local", "python3 fib.py")
    tools.local = local
    llm, cfg, by, ep = run(task, envelope, trace, tools, worker(NOT_NEEDED + "\nF50 = 12586269025 [S1]\n"))
    assert by[1]["sources"][0]["kind"] == "local" and "S1" in by[1]["visible_source_ids"]
    assert by[1]["provenance"]["cited"] >= 1 and by[1]["provenance"]["hallucinated_citations"] == []
