"""D127 — tools reach the helpers that ask for them, and missing data is not taken for a missing tool. Offline: the
fake local-tool server, a pool cache whose servers do not answer, the mock LLM."""
import json

from amoeba.adapt.fixes import candidates
from amoeba.adapt.proposer import fix_problems, parse_fix
from amoeba.adapt.stuck import classify_lacked, diagnose, step_signals
from amoeba.capabilities import normalise
from amoeba.interp.plan_runner import blocked_marks, missing_data_marks, unmark
from amoeba.interp.trace import TraceWriter
from amoeba.localtools.toolbox import LocalToolbox
from amoeba.pool.stock import helpers_for, stock_toolbox
from amoeba.tools.registry import default_registry
from tests.conftest import fx, mock
from tests.test_localtools import CAP, cache, draft_cfg, lsetup, pool_setup, req, skills  # noqa: F401


# ---- Problem 1: a request names the code runner in the words helpers use ----------------------------------------
def test_the_names_helpers_give_a_code_runner_map_to_code_execution():
    for name in ("Bash", "bash", "Shell", "python", "Python3", "command line", "code_interpreter", "Jupyter"):
        assert normalise(name) == ("code_execution", True), name
    assert normalise("python libraries")[1] is False          # only the whole name maps, never a word inside it


def test_a_request_for_bash_reaches_local_bash(skills, tmp_path):
    b = LocalToolbox(lsetup(skills), tmp_path / "run", TraceWriter(None))
    b.start()
    for name in ("Bash", "bash", "shell", "local:Read"):
        q = req(name)
        q.canonical = normalise(name)[0]
        top = b.candidates(q, 5)[0]
        assert top[0] == 100 and top[1]["id"] == ("local:Read" if "Read" in name else "local:Bash"), name
    b.finish()


# ---- Problem 3: one request field naming two roles is for both ------------------------------------------------
def test_a_request_naming_two_roles_is_for_both(task, envelope):
    cfg = draft_cfg(task, envelope, fx(CAP))
    for field in ("Researcher; Writer", "Researcher and Writer", "Researcher, Writer", "[Researcher] / [Writer]"):
        assert sorted(a.name for a in helpers_for(req("x", role=field), cfg)) == ["Researcher", "Writer"], field
    assert [a.name for a in helpers_for(req("x", role="Researcher"), cfg)] == ["Researcher"]
    assert helpers_for(req("x", role="Nobody"), cfg) == []


# ---- Problem 2: a pick whose server does not answer gives way to the next vetted candidate --------------------
def test_a_failed_pick_falls_through_to_the_next_candidate(cache, skills, tmp_path, task, envelope):
    cfg = draft_cfg(task, envelope, fx(CAP).replace("web_search", "remote_sandbox"))
    b = LocalToolbox(lsetup(skills), tmp_path / "run", TraceWriter(None))
    llm = mock(pool_picker=["io.example/py-sandbox"])
    q = req("remote_sandbox", what="runs python code")
    reg, summary = stock_toolbox([q], cfg, default_registry(), llm, b.trace, pool_setup(cache), local=b)
    fell = b.trace.events("pool_fallthrough")
    assert [e["amoeba.pool.id"] for e in fell] == ["io.example/py-sandbox"]
    assert fell[0]["amoeba.reason"] == "connect_failed"
    assert (q.status, q.pool_id) == ("filled", "local:Bash") and "local:Bash" in reg
    b.finish()


def test_a_local_item_comes_first_on_an_equal_score(cache, skills, tmp_path, task, envelope):
    cfg = draft_cfg(task, envelope, fx(CAP))
    b = LocalToolbox(lsetup(skills), tmp_path / "run", TraceWriter(None))
    llm = mock(pool_picker=lambda m, s: "NONE")
    stock_toolbox([req("runner", what="python code")], cfg, default_registry(), llm, b.trace, pool_setup(cache),
                  local=b)
    cands = b.trace.events("pool_match")[0]["amoeba.pool.candidates"]
    for x, y in zip(cands, cands[1:]):                 # by score, and a local item before an internet one on a tie
        assert (-x["score"], x.get("source") != "local") <= (-y["score"], y.get("source") != "local")
    b.finish()


# ---- Problem 4: missing data is research, not a tool ------------------------------------------------------------
def test_lacked_items_that_name_data_are_missing_data():
    kind = lambda x, plan=None, n=1: classify_lacked(x, n, plan or {}, [])["kind"]
    for x in ("US Nominal Income", "Charging Infrastructure", "Maintenance Cost", "email body",
              "Delivery Lead email body", "IN Nominal Income — searched census.gov"):
        assert kind(x) == "missing_data", x
    for x in ("send_email", "Bash", "python_interpreter", "BLS Search", "pricing API", "docx_generator", "fetch_url"):
        assert kind(x) == "capability", x
    plan = {1: {"output": "table of nominal income by year", "roles": ["Researcher"]}, 2: {"roles": ["Analyst"]}}
    assert classify_lacked("nominal income by year", 2, plan, [1])["kind"] == "missing_input"    # an earlier step had it


def test_missing_data_lines_are_read_even_in_bold():
    text = "Result.\n- **MISSING DATA:** 2015 median income for Indiana — census.gov tables\nMISSING DATA: none\n"
    assert missing_data_marks(text) == ["2015 median income for Indiana — census.gov tables"]
    assert unmark("**BLOCKED:** send_email — no tool") == "BLOCKED: send_email — no tool"
    assert blocked_marks(unmark("**BLOCKED:** send_email — no tool")) == ["send_email"]


def test_the_watch_names_missing_data_and_its_fixes():
    meta = {"step": 1, "status": "partial", "roles": ["Researcher"], "blocked": ["US Nominal Income"],
            "missing_data": ["IN Nominal Income — searched bls.gov"], "depends_on": []}
    sig = step_signals(meta, plan={1: {"output": "income table", "roles": ["Researcher"]}})
    assert [s["signal"] for s in sig] == ["missing_data"]
    d = diagnose(sig)
    assert d["cause"] == "missing_data" and d["data"] == ["US Nominal Income", "IN Nominal Income — searched bls.gov"]
    assert "work_around" in d["allowed_edits"] and "grant_tool" in d["allowed_edits"]
    opts = {"max_turns": 5, "check_retry_turns": 1, "max_input_chars": 6000}
    fixes, _ = candidates(d, 1, {"opts": opts, "web_missing": ["fetch_url", "web_search"]})
    assert [f["kind"] for f in fixes] == ["grant_tool", "set_run_option:max_turns"]
    assert fixes[0]["params"]["items"] == ["fetch_url", "web_search"]
    fixes, _ = candidates(d, 1, {"opts": opts})                      # the helpers already hold the web tools
    assert [f["kind"] for f in fixes] == ["set_run_option:max_turns"]


def test_a_work_around_for_missing_data_needs_one_fix_tried_first():
    wa = json.dumps({"edit": {"op": "work_around", "params": {
        "capability": "US Nominal Income", "method": "state the gap and use the national series only",
        "done_when": "", "limitation": "The 2015 Indiana figure was not found."}}, "reason": "the data is not online"})
    p = lambda kinds: fix_problems(parse_fix(wa), "missing_data", ["work_around"], {}, set(), ["Researcher"], kinds)
    assert p(set()) == ["work_around is allowed for missing data only after another fix was tried for this step"]
    assert p({"set_run_option:max_turns"}) == []
