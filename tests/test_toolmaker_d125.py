"""D125 — Box 4 makes a missing tool: plain code checks feasibility (an offline library and a code runner), the tool
writer's code (imports, banned calls, required functions) and its self-test in the run's workspace through the local
toolbox; the step gets made:<name>; a tool that worked is saved to the library as unreviewed and offered again only
after the user approves it. Offline: the mock LLM and the fake local-tool server (process isolation, as in
test_localtools)."""
import json

import pytest

import amoeba.adapt.toolmaker as tm
from amoeba.adapt.toolmaker import ToolLibrary, check_code, feasible, file_kind, parse_tool, tool_text, tw_config
from amoeba.interp.plan_runner import PlanOptions
from amoeba.task.models import Task
from amoeba.tools.registry import default_registry
from scripts import tool_library
from scripts.run_task import run_one
from tests.conftest import fx, mock
from tests.test_localtools import CAP, lsetup, skills  # noqa: F401  (the skills fixture)
from tests.test_plan_runner import step_no

CODE = '''from docx import Document


def run(args):
    name = args.get("file_name") or "memo.docx"
    doc = Document()
    doc.add_heading(args.get("title") or "Memo", 1)
    for line in (args.get("body_markdown") or args.get("text") or "").splitlines():
        doc.add_paragraph(line)
    doc.save(name)
    return f"saved {name}"


def self_test():
    run({"title": "T", "body_markdown": "hello", "file_name": "selftest.docx"})
    assert "hello" in [p.text for p in Document("selftest.docx").paragraphs]
'''
REPLY = ('Thought: write it.\n{"name": "docx_memo", "description": "writes a memo as a .docx file", '
         '"input": "{\\"title\\": ..., \\"body_markdown\\": ..., \\"file_name\\": ...}"}\n```python\n' + CODE + "```\n")


class Local:
    """What feasible() reads of a local toolbox."""
    def __init__(self, up=True):
        self.server, self.exposed = (object() if up else None), ["Bash", "Read"]


# ---- the parts ------------------------------------------------------------------------------------------------------
def test_feasibility_needs_an_offline_library_and_a_code_runner():
    cfg = tw_config()
    assert file_kind("docx_generator", cfg) == "docx" and file_kind("excel_writer", cfg) == "xlsx"
    assert file_kind("weather_api", cfg) is None
    f = feasible(["docx_generator"], Local())
    assert f["ok"] and f["kind"] == "docx" and f["libraries"] == ["docx"]
    assert feasible(["docx_generator"], None)["why"] == "tool writer: no code runner (local tools are off)"
    assert feasible(["docx_generator"], Local(up=False))["ok"] is False
    assert "no offline library for weather_api" in feasible(["weather_api"], Local())["why"]


def test_plain_code_checks_the_written_code_before_it_runs():
    tool = parse_tool(REPLY)
    assert tool["name"] == "docx_memo" and "def self_test" in tool["code"] and check_code(tool, ["docx"]) == []
    bad = dict(tool, code="import subprocess, os\nos.system('ls')\neval('1')\ndef run(args):\n    return ''\n")
    problems = check_code(bad, ["docx"])
    assert any("import subprocess" in p for p in problems) and any("import os" in p for p in problems)
    assert ".system is not allowed" in problems and "eval() is not allowed" in problems
    assert "the code must define self_test()" in problems
    assert check_code(dict(tool, name="Bad Name"), ["docx"])[0].startswith("name must be")
    with pytest.raises(ValueError, match="no a ```python block"):
        parse_tool('{"name": "x"}')
    assert tool_text(tool).rstrip().endswith('print(run(_args))')          # plain code's harness, not the model's


def test_the_library_offers_only_approved_unchanged_tools(tmp_path, capsys):
    lib, tool = ToolLibrary(tmp_path), parse_tool(REPLY)
    m = lib.save(tool, tool_text(tool), {"capability": "docx_generator", "kind": "docx", "task_id": "t1"})
    assert m["status"] == "unreviewed" and lib.find("docx_generator", "docx") is None
    assert lib.save(tool, tool_text(tool), {"capability": "x", "kind": "docx"})["name"] == "docx_memo_2"   # no overwrite
    assert tool_library.main(["--root", str(tmp_path), "approve", "docx_memo"]) == 0
    assert lib.find("docx_generator", "docx")["name"] == "docx_memo"
    assert lib.find("word_writer", "docx")["name"] == "docx_memo"                 # by file type
    (tmp_path / "docx_memo" / "tool.py").write_text("print('changed')\n")
    assert lib.find("docx_generator", "docx") is None                           # edited after approval
    tool_library.main(["--root", str(tmp_path), "list"])
    assert "changed since it was saved or approved" in capsys.readouterr().out


# ---- a whole run ----------------------------------------------------------------------------------------------------
def worker(messages, seed):
    """Step 1 owes a .docx: BLOCKED until a made: tool is listed; then it calls it once and finishes."""
    n, user = step_no(messages), messages[-1]["content"]
    if n != "1":
        return "## Thought\nok\n\n## CurrentStep\nanswer\n\n## Action\nFinal Output\n\n## ActionInput\n396\n"
    if "made:docx_memo" in user and "saved memo.docx" not in user:
        args = json.dumps({"title": "TCO memo", "body_markdown": "Keep diesel.", "file_name": "memo.docx"})
        return f"## Thought\nuse it\n\n## CurrentStep\nmemo\n\n## Action\nmade:docx_memo\n\n## ActionInput\n{args}\n"
    if "made:docx_memo" in user:
        return ("## Thought\nok\n\n## CurrentStep\ndone\n\n## Action\nFinal Output\n\n## ActionInput\n"
                "The memo was saved to memo.docx.\n")
    return ("## Thought\nno tool\n\n## CurrentStep\nmemo\n\n## Action\nFinal Output\n\n## ActionInput\n"
            "396\nBLOCKED: docx_generator — no tool makes a .docx file\n")


def run_h3_shape(tmp_path, skills, envelope, writer):
    plan = (fx(CAP).replace("web_search", "docx_generator")
            .replace("1. [Researcher]: Find and compute the value. Output: the number.",
                     "1. [Researcher]: Write the memo. Output: docx: the memo file."))
    llm = mock(planner=[plan], pool_picker=lambda m, s: "NONE", plan_worker=worker, tool_writer=writer,
               fix_proposer=["no edit"] * 4)
    r = run_one(Task(prompt="Write the TCO memo as a Word file."), "plan", llm, envelope, default_registry(),
                tmp_path / "runs", local=lsetup(skills), plan_options=PlanOptions(adapt="on"))
    return r, llm, json.loads((tmp_path / "runs" / r.run_id / "result.json").read_text())


@pytest.fixture
def library(tmp_path, monkeypatch):
    root = tmp_path / "tool_library"
    monkeypatch.setattr(tm, "library_root", lambda cfg=None: root)
    return root


def test_box4_writes_the_missing_tool_and_the_step_uses_it(skills, tmp_path, envelope, library):
    r, llm, res = run_h3_shape(tmp_path, skills, envelope, [REPLY])
    made = res["adaptation"]["tools_made"]
    assert made[0]["tool"] == "made:docx_memo" and made[0]["how"] == "written"
    assert made[0]["library"] == "saved as docx_memo (unreviewed)"
    fix = next(f for f in res["adaptation"]["fixes"] if f["kind"] == "make_tool")
    assert fix["result"] == "recovered" and fix["rung"] == "W"
    assert {"path": "memo.docx", "size": pytest.approx(36000, rel=0.5), "step": 1} in res["files_created"]
    assert not any(f["path"].startswith("made_tools/") or "selftest" in f["path"]      # neither the code nor the
                   for f in res["files_created"])                                       # self-test's example file
    assert json.loads((library / "docx_memo" / "manifest.json").read_text())["status"] == "unreviewed"
    assert len(llm.calls_of("tool_writer")) == 1 and "step 1" not in (r.error or "")   # step 2: the fixture's own skill gap


def test_an_unreviewed_tool_is_never_offered_and_an_approved_one_is_reused(skills, tmp_path, envelope, library):
    run_h3_shape(tmp_path / "a", skills, envelope, [REPLY])                  # saved, unreviewed
    _, llm, _ = run_h3_shape(tmp_path / "b", skills, envelope, [REPLY])
    assert len(llm.calls_of("tool_writer")) == 1                              # not offered: written again
    assert tool_library.main(["--root", str(library), "approve", "docx_memo"]) == 0
    _, llm, res = run_h3_shape(tmp_path / "c", skills, envelope, [])
    assert llm.calls_of("tool_writer") == []                                  # the approved tool, self-tested again
    assert res["adaptation"]["tools_made"][0]["how"] == "library"


def test_a_refused_tool_is_written_once_more_then_the_next_rung_takes_over(skills, tmp_path, envelope, library):
    evil = REPLY.replace("from docx import Document", "import subprocess\nfrom docx import Document")
    r, llm, res = run_h3_shape(tmp_path, skills, envelope, [evil, evil])
    fix = next(f for f in res["adaptation"]["fixes"] if f["kind"] == "make_tool")
    assert fix["result"].startswith("failed: tool writer: no tool passed") and "import subprocess" in fix["result"]
    assert "import subprocess is not allowed" in llm.calls_of("tool_writer")[1]["messages"][-1]["content"]
    assert not library.exists() and res["adaptation"]["tools_made"] == []
